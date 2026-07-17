"""Single source of truth for OSINT methodology.

Both the prompt text the LLM follows and the L1-L5 confidence logic the code
computes are defined here, so they can never drift apart. Mirrors the canonical
local skill at ~/.claude/skills/osint-core/SKILL.md (kept in sync by
tests/test_osint_methodology.py).

Consumers:
  - backend/agents/intelligence/super_analyst.py (base prompt + per-item grading)
"""

from __future__ import annotations
import re

from backend.models import Verdict

# Canonical source groups used for both document-quality classification and
# independent-source deduplication.
HIGH_SOURCES = {
    "reuters", "ap", "ap-news", "bbc", "afp", "npr", "nytimes",
    "the-guardian", "guardian", "cnn", "el-pais", "le-monde", "france24", "dw",
}
MEDIUM_SOURCES = {
    "al-jazeera", "al-monitor", "euronews", "ansa", "repubblica",
    "all-africa", "el-universal", "un-news",
}
LOW_SOURCES = {
    "bellingcat", "arstechnica", "bleeping-computer", "medium", "rferl", "fdd",
}
KOL_SOURCES = {
    "oryx", "perun", "ralee85", "geoconfirmed", "osinttechnical", "war-mapper",
    "rybar", "suriyak-maps", "southfront", "redspotted-nro", "covert-cabal",
    "ukikaski", "trent-telenko", "defmon3", "middle-east-monitor",
    "visual-politik", "biggers-geopolitics", "ukraine-frontline", "marksian",
    "casual-scholar", "boston-roundface", "shapan-war", "guancha-kol",
    "intel-crab", "mt-anderson", "eliot-higgins", "christo-grozev", "hi-sutton",
    "simplicius-thinker", "andrew-perpetua", "tatarigami-ua", "jeffrey-lewis",
    "phillips-obrien", "mick-ryan", "franz-gady", "alex-mercouris",
    "brian-berletic", "michael-kofman",
}

# ── Core methodology (RAND 2nd-gen OSINT) ──────────────────────────────

CORE_PRINCIPLES: list[str] = [
    "三方验证 — 任何结论至少 3 个独立来源交叉确认",
    "逆向思维 — 追问“谁会从中受益”、“谁想掩盖什么”",
    "确认偏差警惕 — 主动寻找反驳假设的证据",
    "链上留痕 — 每个结论可回溯至原始来源",
    "技术+人工 — 工具辅助，分析师判断主导",
    "隐私合规 — 遵守所在国/目标国法律法规",
]

INTEL_CYCLE = "收集 → 加工 → 开发 → 生产"

SOURCE_DEDUP_RULE = (
    "独立来源去重：同一通讯社/互相转载/同一原始出处只算 1 个独立来源；"
    "匿名或不可核实来源按保守等级处理。切勿因转载数量多而虚高置信度。"
)

# (code, label, criterion) — drives both the rendered table and classify_confidence.
CONFIDENCE_LEVELS: list[tuple[str, str, str]] = [
    ("L1", "确认", "≥3 个独立来源交叉验证"),
    ("L2", "高可信", "2 个独立来源支持"),
    ("L3", "中可信", "1 个可靠来源"),
    ("L4", "推测", "基于间接证据的合理推断"),
    ("L5", "无效", "多源否定或来源相互矛盾 → 丢弃或重新调查"),
]


def render_methodology() -> str:
    """Render the methodology block injected into LLM system prompts."""
    principles = "\n".join(f"{i}. **{p}**" for i, p in enumerate(CORE_PRINCIPLES, 1))
    levels = "\n".join(
        f"| **{code} {label}** | {crit} |" for code, label, crit in CONFIDENCE_LEVELS
    )
    return (
        "## 核心原则（必须遵守）\n"
        f"{principles}\n\n"
        "## 置信度评级\n"
        "| 等级 | 标准 |\n"
        "|------|------|\n"
        f"{levels}\n\n"
        f"> {SOURCE_DEDUP_RULE}\n\n"
        f"## 情报循环（4步法）\n{INTEL_CYCLE}"
    )


# ── L1-L5 confidence logic ─────────────────────────────────────────────

_SOURCE_CANONICAL_ALIASES = {
    "ap-news": "ap",
    "associated-press": "ap",
    "bbc-news": "bbc",
    "the-guardian": "guardian",
    "theguardian": "guardian",
    "new-york-times": "nytimes",
    "ny-times": "nytimes",
    "deutsche-welle": "dw",
}


def _source_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _contains_token_sequence(tokens: list[str], expected: list[str]) -> bool:
    width = len(expected)
    return any(tokens[index:index + width] == expected for index in range(len(tokens) - width + 1))


_KNOWN_SOURCE_ALIASES = sorted(
    (HIGH_SOURCES | MEDIUM_SOURCES | LOW_SOURCES | KOL_SOURCES)
    | set(_SOURCE_CANONICAL_ALIASES),
    key=lambda name: (len(_source_tokens(name)), len(name)),
    reverse=True,
)


def source_group(src: str) -> str:
    """Normalize a source string to an exact-token dedup group.

    Known wire services / canonical outlets collapse their reposts to one group
    (e.g. multiple feeds carrying a Reuters story → 'reuters'), so syndication
    doesn't inflate the independent-source count. Short identifiers such as
    ``ap`` and ``dw`` only match complete tokens, never substrings of unrelated
    outlet names.
    """

    tokens = _source_tokens(src)
    for alias in _KNOWN_SOURCE_ALIASES:
        if _contains_token_sequence(tokens, _source_tokens(alias)):
            return _SOURCE_CANONICAL_ALIASES.get(alias, alias)
    return "-".join(tokens)


def count_independent_sources(sources: list[str]) -> int:
    """Distinct source groups after dedup; at least 1."""
    groups = {source_group(s) for s in sources if s and s.strip()}
    return len(groups) or 1


def classify_confidence_level(
    independent_sources: int,
    posterior: float,
    verdict,
) -> str:
    """Return the structured L1-L5 code for a hypothesis assessment."""
    verdict_value = getattr(verdict, "value", verdict)
    if verdict_value in {Verdict.FALSE.value, "refuted"} or posterior <= 0.3:
        return "L5"
    if independent_sources >= 3 and posterior >= 0.6:
        return "L1"
    if independent_sources >= 2 and posterior >= 0.5:
        return "L2"
    if independent_sources >= 1 and posterior >= 0.45:
        return "L3"
    return "L4"


def classify_confidence(independent_sources: int, posterior: float, verdict) -> str:
    """Return a human-readable L1-L5 code and Chinese label."""
    level = classify_confidence_level(independent_sources, posterior, verdict)
    labels = {
        "L1": "确认",
        "L2": "高可信",
        "L3": "中可信",
        "L4": "推测",
        "L5": "无效",
    }
    return f"{level}-{labels[level]}"
