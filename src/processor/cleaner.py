from __future__ import annotations

import html as html_lib
import html
import re
import unicodedata
from typing import Optional

from bs4 import BeautifulSoup, NavigableString

# ── Character-level cleaners ──────────────────────────────────────────────

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MULTI_SPACE_RE = re.compile(r" {2,}")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
TRAILING_SPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)
LEADING_SPACE_RE = re.compile(r"^[ \t]+", re.MULTILINE)

# Common boilerplate patterns in web content
BOILERPLATE_PATTERNS: list[re.Pattern] = [
    re.compile(r"cookie[_\s]?policy", re.IGNORECASE),
    re.compile(r"privacy[_\s]?policy", re.IGNORECASE),
    re.compile(r"terms?\s+of\s+service", re.IGNORECASE),
    re.compile(r"all\s+rights?\s+reserved", re.IGNORECASE),
    re.compile(r"click\s+(here|to|for)", re.IGNORECASE),
    re.compile(r"subscribe", re.IGNORECASE),
    re.compile(r"newsletter", re.IGNORECASE),
    re.compile(r"advertisement", re.IGNORECASE),
    re.compile(r"share\s+(on|this|article)", re.IGNORECASE),
    re.compile(r"follow\s+us", re.IGNORECASE),
    re.compile(r"read\s+more", re.IGNORECASE),
    re.compile(r"related\s+(articles?|stories?|posts?)", re.IGNORECASE),
    re.compile(r"comments?\s+are?\s+closed", re.IGNORECASE),
    re.compile(r"loading\.\.\.", re.IGNORECASE),
    re.compile(r"javascript", re.IGNORECASE),
    re.compile(r"function\s*\(.*\)", re.IGNORECASE),
]


def strip_control_chars(text: str) -> str:
    """Remove non-printable control characters except tab/newline."""
    return CONTROL_CHARS_RE.sub("", text)


def normalize_unicode(text: str) -> str:
    """NFKC normalization to collapse compatible codepoints."""
    return unicodedata.normalize("NFKC", text)


def normalize_whitespace(text: str) -> str:
    """Collapse excessive whitespace: trim lines, limit consecutive newlines."""
    text = TRAILING_SPACE_RE.sub("", text)
    text = LEADING_SPACE_RE.sub("", text)
    text = MULTI_SPACE_RE.sub(" ", text)
    text = MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


# ── HTML cleaners ─────────────────────────────────────────────────────────

TAG_BLACKLIST = {"script", "style", "nav", "footer", "header", "noscript",
                 "iframe", "form", "button", "select", "input", "textarea",
                 "svg", "canvas", "aside", "menu", "menuitem"}
BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
              "li", "blockquote", "section", "article", "figure",
              "figcaption", "details", "summary", "pre", "hr",
              "table", "tr", "td", "th", "tbody", "thead", "tfoot",
              "ol", "ul", "dl", "dt", "dd", "br", "tr", "td"}


def strip_html(html: str) -> str:
    """Remove HTML tags, strip scripts/styles, extract readable text.

    Handles both full HTML documents and fragments.
    """
    if not html or "<" not in html:
        return html

    soup = BeautifulSoup(html, "lxml")

    # Remove blacklisted tags and their content entirely
    for tag in TAG_BLACKLIST:
        for el in soup.find_all(tag):
            el.decompose()

    # Replace block tags with newlines for readability
    for tag in BLOCK_TAGS:
        for el in soup.find_all(tag):
            el.append("\n")

    # Extract text, preserving paragraph breaks
    parts: list[str] = []
    for el in soup.children:
        if isinstance(el, NavigableString):
            text = str(el)
            if text.strip():
                parts.append(text)
        else:
            text = el.get_text(separator=" ")
            if text.strip():
                parts.append(text)

    raw = "".join(parts)
    return raw


# ── Line-length normalization ─────────────────────────────────────────────

# Lines longer than this are split at sentence boundaries
MAX_LINE_LENGTH = 2000
SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？.!?])\s+")


def normalize_lines(text: str, max_length: int = MAX_LINE_LENGTH) -> str:
    """Break overly long lines at sentence boundaries."""
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if len(line) <= max_length:
            out.append(line)
        else:
            out.extend(SENTENCE_BOUNDARY.split(line))
    return "\n".join(out)


# ── Common URL/page content normalization ─────────────────────────────────

URL_CLEAN_RE = re.compile(r"utm_[a-z]+=[^&\s]+|fbclid=[^&\s]+|gclid=[^&\s]+")
TRACKING_PREFIXES = ("#", "//")


def clean_url(url: str) -> str:
    """Remove tracking parameters from URLs."""
    if not url:
        return url
    cleaned = URL_CLEAN_RE.sub("", url)
    cleaned = cleaned.rstrip("?&")
    for prefix in TRACKING_PREFIXES:
        if cleaned.startswith(prefix):
            return url  # can't safely strip, return original
    return cleaned


# ── Boilerplate detection ─────────────────────────────────────────────────

# Boilerplate-only line: short line that matches a boilerplate pattern.
# We only remove a line if it's short AND the match is a significant
# portion of the line (to avoid false positives like "Read more" at the
# end of a sentence).
BOILERPLATE_MAX_LENGTH = 60


def _is_boilerplate_line(line: str) -> bool:
    """Check if a line is predominantly boilerplate (short + pattern match)."""
    stripped = line.strip()
    if not stripped or len(stripped) > BOILERPLATE_MAX_LENGTH:
        return False
    for pattern in BOILERPLATE_PATTERNS:
        m = pattern.search(stripped)
        if m and len(m.group()) >= len(stripped) * 0.5:
            return True
    return False


def strip_boilerplate(text: str) -> str:
    """Remove short boilerplate-only lines (e.g. cookie notices, nav links)."""
    lines = text.split("\n")
    out = [line for line in lines if not _is_boilerplate_line(line)]
    return "\n".join(out)


# ── Main cleaning pipeline ────────────────────────────────────────────────

def clean_text(text: str, mime_hint: Optional[str] = None) -> str:
    """Full cleaning pipeline: HTML → readable, normalized, deduped text.

    Args:
        text: Raw input text (may contain HTML tags).
        mime_hint: MIME type hint for additional processing decisions.

    Returns:
        Cleaned and normalized text.
    """
    if not text:
        return ""

    # Step 1: Strip HTML if content looks like HTML
    if mime_hint and ("html" in mime_hint or "xml" in mime_hint):
        text = strip_html(text)
    elif "<" in text and ">" in text:
        text = strip_html(text)

    # Step 2: Decode HTML entities (e.g. &amp; → &, &mdash; → —)
    text = html.unescape(text)

    # Step 3: Unicode normalization
    text = normalize_unicode(text)

    # Step 4: Remove control characters
    text = strip_control_chars(text)

    # Step 5: Normalize whitespace
    text = normalize_whitespace(text)

    # Step 6: Remove boilerplate lines
    text = strip_boilerplate(text)

    # Step 7: Normalize line lengths
    text = normalize_lines(text)

    return text
