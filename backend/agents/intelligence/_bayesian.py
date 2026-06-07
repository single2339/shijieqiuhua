"""Shared Bayesian evidence framework — mirrors backend/main.py compute_bayesian()."""

from __future__ import annotations

import hashlib
import re
import sys as _sys
from pathlib import Path

# ── import yao-bayesian-skill engine ──
SKILL_DIR = Path.home() / ".cc-switch" / "skills" / "yao-bayesian-skill" / "scripts"
if str(SKILL_DIR) not in _sys.path:
    _sys.path.insert(0, str(SKILL_DIR))

from bayesian_decision_report import apply_odds_update

from backend.models import Verdict

SOURCE_PRIORS: dict[str, dict] = {
    "high": {"probability": 0.70, "quality": "B", "source_class": "high-credibility"},
    "medium": {"probability": 0.55, "quality": "C", "source_class": "medium-credibility"},
    "low": {"probability": 0.40, "quality": "D", "source_class": "low-credibility"},
    "kol": {"probability": 0.30, "quality": "D", "source_class": "kol"},
    "unknown": {"probability": 0.40, "quality": "D", "source_class": "unknown"},
}

HIGH_SOURCES = {"reuters", "ap", "ap-news", "bbc", "afp", "npr", "nytimes",
                "the-guardian", "guardian", "cnn", "el-pais", "le-monde", "france24", "dw"}
MEDIUM_SOURCES = {"al-jazeera", "al-monitor", "euronews", "ansa", "repubblica",
                  "all-africa", "el-universal", "un-news"}
LOW_SOURCES = {"bellingcat", "arstechnica", "bleeping-computer", "medium", "rferl", "fdd"}

KOL_SOURCES = {"oryx", "perun", "ralee85", "geoconfirmed", "osinttechnical", "war-mapper", "rybar",
               "suriyak-maps", "southfront", "redspotted-nro", "covert-cabal", "ukikaski",
               "trent-telenko", "defmon3", "middle-east-monitor", "visual-politik",
               "biggers-geopolitics", "ukraine-frontline", "marksian", "casual-scholar",
               "boston-roundface", "shapan-war", "guancha-kol",
               "intel-crab", "mt-anderson", "eliot-higgins", "christo-grozev",
               "hi-sutton", "simplicius-thinker", "andrew-perpetua", "tatarigami-ua",
               "jeffrey-lewis", "phillips-obrien", "mick-ryan", "franz-gady",
               "alex-mercouris", "brian-berletic", "michael-kofman"}


def source_prior_class(src: str) -> str:
    s = src.lower().strip()
    if s in KOL_SOURCES:
        return "kol"
    for name in HIGH_SOURCES:
        if name in s:
            return "high"
    for name in MEDIUM_SOURCES:
        if name in s:
            return "medium"
    for name in LOW_SOURCES:
        if name in s:
            return "low"
    return "unknown"


# ── Text content analysis for dynamic evidence calibration ──

_NUMBER_PATTERN = re.compile(r'\d[\d,.]*')
_DATE_PATTERN = re.compile(r'\d{1,2}月|\d{1,2}日|\d{4}年|January|February|March|April|May|June|'
                           r'July|August|September|October|November|December|'
                           r'\d{4}-\d{2}-\d{2}|Q[1-4]')
_NAMED_ENTITY_PATTERN = re.compile(
    r'[A-Z一-鿿]{2,}(?:市|省|部|局|委员会|公司|集团|组织|基金|银行|大学|学院|医院|中心|署|厅|处|院|会)'
)
_PERCENT_PATTERN = re.compile(r'\d+(?:\.\d+)?%|\d+(?:\.\d+)?个百分点')


def _analyze_text(text: str) -> dict[str, float]:
    """Extract content quality signals from text for Bayesian evidence calibration.

    Returns scores in [0, 1] for: specificity, has_numbers, temporal, named_entities.
    """
    if not text or len(text) < 20:
        return {"specificity": 0.2, "has_numbers": 0.0, "temporal": 0.0, "named_entities": 0.0}

    length = len(text)
    specificity = min(length / 500, 1.0)

    numbers = _NUMBER_PATTERN.findall(text)
    percentages = _PERCENT_PATTERN.findall(text)
    has_numbers = min(len(numbers) / 5, 1.0) * 0.6 + min(len(percentages) / 3, 1.0) * 0.4

    dates = _DATE_PATTERN.findall(text)
    temporal = min(len(dates) / 3, 1.0)

    entities = _NAMED_ENTITY_PATTERN.findall(text)
    named_entities = min(len(entities) / 3, 1.0)

    return {
        "specificity": round(specificity, 2),
        "has_numbers": round(has_numbers, 2),
        "temporal": round(temporal, 2),
        "named_entities": round(named_entities, 2),
    }


_bayesian_cache: dict[str, tuple] = {}

def compute_bayesian(text: str, source_system: str = "") -> tuple:
    """Use yao-bayesian-skill odds-update with evidence quality tiers (A-E).

    Evidence is calibrated from actual text content (specificity, numbers, temporal refs,
    named entities) combined with source credibility. Different content with the same source
    now produces different posteriors.

    Returns (posterior, trace, verdict, method, prior_quality, prior_class, evidence_items).
    """
    if not text.strip():
        return (0.5, [0.5], Verdict.UNCERTAIN, "", "", "", [])

    cache_key = hashlib.sha256((source_system + text[:500]).encode()).hexdigest()
    if cache_key in _bayesian_cache:
        return _bayesian_cache[cache_key]

    prior_class = source_prior_class(source_system)
    prior_info = SOURCE_PRIORS[prior_class]
    prior = prior_info["probability"]
    signals = _analyze_text(text)

    spec = signals["specificity"]
    num_sig = signals["has_numbers"]
    tmp_sig = signals["temporal"]
    ent_sig = signals["named_entities"]

    evidence_list = []
    ev_items_out = []

    # content-specificity: LR scales with text length and entity density
    spec_lr = round(1.5 + spec * 2.5 + ent_sig * 1.0, 1)
    spec_quality = "A" if spec > 0.7 else "B" if spec > 0.4 else "C" if spec > 0.2 else "D"
    evidence_list.append({
        "name": "content-specificity", "likelihood_ratio": spec_lr,
        "direction": "support", "dependency_discount": 0.7,
    })
    ev_items_out.append(dict(name="content-specificity", quality=spec_quality,
                             lr=spec_lr, dep_discount=0.7, direction="support"))

    # verifiable-numbers: only added when numbers are present
    if num_sig > 0:
        num_lr = round(1.5 + num_sig * 2.0, 1)
        num_quality = "A" if num_sig > 0.7 else "B" if num_sig > 0.4 else "C"
        evidence_list.append({
            "name": "verifiable-numbers", "likelihood_ratio": num_lr,
            "direction": "support", "dependency_discount": 0.8,
        })
        ev_items_out.append(dict(name="verifiable-numbers", quality=num_quality,
                                 lr=num_lr, dep_discount=0.8, direction="support"))

    # temporal: only added when time references are present
    if tmp_sig > 0:
        tmp_lr = round(1.3 + tmp_sig * 0.7, 1)
        tmp_quality = "B" if tmp_sig > 0.5 else "C"
        evidence_list.append({
            "name": "temporal", "likelihood_ratio": tmp_lr,
            "direction": "support", "dependency_discount": 1.0,
        })
        ev_items_out.append(dict(name="temporal", quality=tmp_quality,
                                 lr=tmp_lr, dep_discount=1.0, direction="support"))

    # source-authority: based on source credibility class
    if prior_class in ("high", "medium"):
        evidence_list.append({
            "name": "source-authority", "likelihood_ratio": 1.2,
            "direction": "support", "dependency_discount": 1.0,
        })
        ev_items_out.append(dict(name="source-authority", quality="B",
                                 lr=1.2, dep_discount=1.0, direction="support"))
    elif prior_class != "kol":
        evidence_list.append({
            "name": "source-authority", "likelihood_ratio": 0.8,
            "direction": "support", "dependency_discount": 1.0,
        })
        ev_items_out.append(dict(name="source-authority", quality="D",
                                 lr=0.8, dep_discount=1.0, direction="support"))

    # cross-source: reflects source credibility
    if prior_class in ("high", "medium"):
        evidence_list.append({
            "name": "cross-source", "likelihood_ratio": 1.3,
            "direction": "support", "dependency_discount": 1.0,
        })
        ev_items_out.append(dict(name="cross-source", quality="B",
                                 lr=1.3, dep_discount=1.0, direction="support"))
    else:
        evidence_list.append({
            "name": "cross-source", "likelihood_ratio": 1.1,
            "direction": "support", "dependency_discount": 1.0,
        })
        ev_items_out.append(dict(name="cross-source", quality="D",
                                 lr=1.1, dep_discount=1.0, direction="support"))

    posterior, log, _, _ = apply_odds_update(prior, evidence_list)

    trace = [prior]
    current = prior
    for e in evidence_list:
        p, _, _, _ = apply_odds_update(current, [e])
        current = p
        trace.append(round(p, 4))

    if posterior >= 0.7:
        verdict = Verdict.VERIFIED
    elif posterior <= 0.3:
        verdict = Verdict.FALSE
    else:
        verdict = Verdict.UNCERTAIN

    result = (round(posterior, 3), trace, verdict, "odds-update",
              prior_info["quality"], prior_info["source_class"], ev_items_out)
    _bayesian_cache[cache_key] = result
    return result
