"""Persistent English→Chinese cache for football team / competition names.

football-data.org only returns English names, but the UI is Chinese. Each
unique name is translated once via the DeepSeek API and cached to disk, so the
frontend's repeated /fixtures polls cost nothing after the first lookup.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

_CACHE_PATH = Path("bronze_storage") / "football_osint" / "_name_translations.json"
_LOCK = threading.Lock()
_TIMEOUT = 30.0


def translate(names: list[str]) -> dict[str, str]:
    """Return ``{english: chinese}`` for every name, translating misses once.

    On LLM failure (or no API key) a missing name maps to itself so the UI
    still renders something rather than an empty label.
    """
    unique = sorted({n.strip() for n in names if n and n.strip()})
    if not unique:
        return {}
    with _LOCK:
        cache = _load()
        missing = [n for n in unique if n not in cache]
        if missing:
            fresh = _translate_via_llm(missing)
            for name in missing:
                cache[name] = fresh.get(name, name)  # fall back to English
            _save(cache)
        return {name: cache.get(name, name) for name in unique}


def to_english(name: str) -> str:
    """Reverse-lookup the English original for a Chinese name via the cache.

    Fixtures are shown with translated Chinese names, but quality preview/stats
    sites are English — search queries need the English original. Names selected
    from the sidebar were translated earlier, so they're in the cache. Falls
    back to the input when there's no mapping (already English, or uncached).
    """
    name = (name or "").strip()
    if not name:
        return name
    with _LOCK:
        cache = _load()
    for english, chinese in cache.items():
        if chinese == name:
            return english
    return name


def _load() -> dict[str, str]:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save(mapping: dict[str, str]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _translate_via_llm(names: list[str]) -> dict[str, str]:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    if not api_key:
        return {}

    system = (
        "你是足球术语翻译专家。把给定的英文足球球队名/赛事名翻译成中文官方或通用译名"
        "（例如 Real Madrid→皇家马德里，FIFA World Cup→世界杯）。"
        "只返回一个 JSON 对象：键是原始英文名，值是中文译名，不要任何额外文字。"
    )
    user = "请翻译以下名称：\n" + json.dumps(names, ensure_ascii=False)

    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        result = json.loads(content)
        return {str(k): str(v) for k, v in result.items() if v}
    except Exception as e:
        log.warning("name translation failed: %s", e)
        return {}
