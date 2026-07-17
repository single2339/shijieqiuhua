"""Tests for the single-source-of-truth OSINT methodology module.

Covers the L1-L5 confidence logic (independent-source dedup + L5 on refutation)
and a drift guard that keeps the server methodology aligned with the canonical
local osint-core skill.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.config.osint_methodology import (
    CONFIDENCE_LEVELS,
    CORE_PRINCIPLES,
    classify_confidence,
    count_independent_sources,
    render_methodology,
    source_group,
)
from backend.models import Verdict


# ── source grouping / independent-source dedup ──

def test_reposts_of_same_wire_count_as_one_source():
    # Multiple feeds carrying a Reuters story collapse to one independent source.
    assert count_independent_sources(["Reuters", "rss:reuters-world", "reuters.com"]) == 1


def test_distinct_outlets_count_separately():
    assert count_independent_sources(["Reuters", "BBC News", "新浪财经"]) == 3


def test_empty_sources_floor_at_one():
    assert count_independent_sources([]) == 1
    assert count_independent_sources(["", "  "]) == 1


def test_source_group_normalizes_known_wire():
    assert source_group("Reuters") == source_group("rss:reuters-world")


def test_short_source_ids_never_match_unrelated_substrings():
    assert source_group("Japan Times") == "japan-times"
    assert source_group("DW Akademie") == "dw"
    assert count_independent_sources(["AP", "Japan Times"]) == 2


# ── L1-L5 classification ──

def test_three_independent_sources_high_posterior_is_l1():
    assert classify_confidence(3, 0.8, Verdict.VERIFIED) == "L1-确认"


def test_single_source_caps_at_l3_even_with_high_posterior():
    # The core fix: confidence is driven by independent corroboration, not by a
    # high posterior from a single source.
    assert classify_confidence(1, 0.95, Verdict.VERIFIED) == "L3-中可信"


def test_two_sources_is_l2():
    assert classify_confidence(2, 0.55, Verdict.UNCERTAIN) == "L2-高可信"


def test_refuted_evidence_is_l5():
    assert classify_confidence(3, 0.2, Verdict.FALSE) == "L5-无效"


def test_weak_single_source_is_l4():
    assert classify_confidence(1, 0.40, Verdict.UNCERTAIN) == "L4-推测"


# ── methodology rendering ──

def test_render_methodology_contains_all_five_levels():
    text = render_methodology()
    for code, label, _ in CONFIDENCE_LEVELS:
        assert f"{code} {label}" in text
    assert "L5" in text and "无效" in text
    assert "去重" in text  # source-dedup rule present


# ── drift guard: server methodology must match the local osint-core skill ──

_LOCAL_SKILL = Path.home() / ".claude" / "skills" / "osint-core" / "SKILL.md"


@pytest.mark.skipif(not _LOCAL_SKILL.exists(), reason="local osint-core skill not present")
def test_no_drift_from_local_osint_core_skill():
    local = _LOCAL_SKILL.read_text(encoding="utf-8")
    # Canonical invariants that must exist in both the local skill and the server
    # methodology, so they can't silently diverge.
    for level in ("L1", "L2", "L3", "L4", "L5"):
        assert level in local, f"local skill missing {level}"
    assert "无效" in local, "local skill missing L5-无效 level"
    # Principle keywords (first token of each principle) present locally.
    for principle in CORE_PRINCIPLES:
        keyword = principle.split(" ")[0]
        assert keyword in local, f"local skill missing principle: {keyword}"
