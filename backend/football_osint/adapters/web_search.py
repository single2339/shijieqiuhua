"""Web search adapter.

Primary backend: Tavily (TAVILY_API_KEY) — an LLM-oriented search API that
returns clean, extracted page content (not just snippets), so the downstream
LLM synthesis gets real preview text (injuries, lineups, predicted XI, odds).

Fallback: DuckDuckGo HTML scraping — used only when no Tavily key is set, so
the pipeline still runs (with weaker results) in zero-config setups.

Both return the same shape: [{title, url, snippet}, ...].
"""
from __future__ import annotations

import logging
import os
import urllib.parse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
MAX_RESULTS = 5

# High-signal football preview/stats domains. Tavily ranks these first when set,
# which is how the manual report reached Opta/Sports Mole/RotoWire-grade sources.
PREVIEW_DOMAINS = [
    "theanalyst.com",
    "sportsmole.co.uk",
    "rotowire.com",
    "si.com",
    "goal.com",
    "espn.com",
]


def search(
    query: str,
    *,
    max_results: int = MAX_RESULTS,
    include_domains: list[str] | None = None,
    use_tavily: bool = True,
) -> list[dict[str, str]]:
    """Return [{title, url, snippet}, ...]. Tavily if keyed, else DDG.

    Set use_tavily=False to skip Tavily and go straight to DDG,
    e.g. for cost-sensitive or lower-signal queries.
    """
    if use_tavily:
        api_key = os.getenv("TAVILY_API_KEY", "")
        if api_key:
            results = _tavily_search(api_key, query, max_results, include_domains)
            if results:
                return results
            # Tavily failed/empty → fall through to DDG so we still return something.
    return _ddg_search(query, max_results)


def _tavily_search(
    api_key: str,
    query: str,
    max_results: int,
    include_domains: list[str] | None,
) -> list[dict[str, str]]:
    payload: dict = {
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }
    if include_domains:
        payload["include_domains"] = include_domains
    try:
        resp = httpx.post(
            TAVILY_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("tavily search %r failed: %s", query, e)
        return []

    results: list[dict[str, str]] = []
    for item in data.get("results", [])[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            # Tavily returns extracted content, far richer than a snippet.
            "snippet": (item.get("content") or "")[:1000],
        })
    return results


def _ddg_search(query: str, max_results: int) -> list[dict[str, str]]:
    try:
        resp = httpx.get(
            DDG_SEARCH_URL,
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        log.warning("ddg search %r failed: %s", query, e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[dict[str, str]] = []
    for result in soup.select(".result")[:max_results]:
        title_el = result.select_one(".result__a")
        snippet_el = result.select_one(".result__snippet")
        if title_el is None:
            continue
        results.append({
            "title": title_el.get_text(strip=True),
            "url": _resolve_url(title_el.get("href") or ""),
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return results


def _resolve_url(href: str) -> str:
    """DDG HTML results link through /l/?uddg=<encoded target>; unwrap it."""
    parsed = urllib.parse.urlparse(href)
    if parsed.path == "/l/":
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        return target or href
    return href
