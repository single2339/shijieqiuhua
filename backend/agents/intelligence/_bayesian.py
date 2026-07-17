"""Document-quality and hypothesis-level Bayesian evidence utilities."""

from __future__ import annotations

import re
from backend.config.osint_methodology import classify_confidence_level, source_group
from backend.config.osint_methodology import (
    HIGH_SOURCES,
    KOL_SOURCES,
    LOW_SOURCES,
    MEDIUM_SOURCES,
)


SOURCE_PRIORS: dict[str, dict] = {
    "high": {"probability": 0.70, "quality": "B", "source_class": "high-credibility"},
    "medium": {"probability": 0.55, "quality": "C", "source_class": "medium-credibility"},
    "low": {"probability": 0.40, "quality": "D", "source_class": "low-credibility"},
    "kol": {"probability": 0.30, "quality": "D", "source_class": "kol"},
    "unknown": {"probability": 0.40, "quality": "D", "source_class": "unknown"},
}



def source_prior_class(src: str) -> str:
    group = source_group(src)
    if group in KOL_SOURCES:
        return "kol"
    if group in HIGH_SOURCES:
        return "high"
    if group in MEDIUM_SOURCES:
        return "medium"
    if group in LOW_SOURCES:
        return "low"
    return "unknown"


# ── Document quality assessment ─────────────────────────────────────────────

_NUMBER_PATTERN = re.compile(r"\d[\d,.]*")
_DATE_PATTERN = re.compile(
    r"\d{1,2}月|\d{1,2}日|\d{4}年|January|February|March|April|May|June|"
    r"July|August|September|October|November|December|"
    r"\d{4}-\d{2}-\d{2}|Q[1-4]"
)
_NAMED_ENTITY_PATTERN = re.compile(
    r"[A-Z一-鿿]{2,}(?:市|省|部|局|委员会|公司|集团|组织|基金|银行|大学|学院|医院|中心|署|厅|处|院|会)"
)
_PERCENT_PATTERN = re.compile(r"\d+(?:\.\d+)?%|\d+(?:\.\d+)?个百分点")

_SOURCE_QUALITY = {
    "high": 0.8,
    "medium": 0.65,
    "low": 0.45,
    "kol": 0.4,
    "unknown": 0.5,
}

# Fixed likelihood ratios. Formatting, source reputation, document length and
# numeric-looking text never enter this table: only an explicit relationship
# to a named hypothesis can change its probability.
HYPOTHESIS_LIKELIHOOD_RATIOS: dict[str, dict[str, float]] = {
    "support": {"weak": 1.5, "moderate": 2.5, "strong": 4.0},
    "contradict": {"weak": 2 / 3, "moderate": 0.4, "strong": 0.25},
    "neutral": {"weak": 1.0, "moderate": 1.0, "strong": 1.0},
}


def _analyze_text(text: str) -> dict[str, float]:
    """Measure document presentation quality without judging claim truth."""
    if not text or len(text) < 20:
        return {
            "specificity": 0.2,
            "has_numbers": 0.0,
            "temporal": 0.0,
            "named_entities": 0.0,
        }

    specificity = min(len(text) / 500, 1.0)
    numbers = _NUMBER_PATTERN.findall(text)
    percentages = _PERCENT_PATTERN.findall(text)
    has_numbers = min(len(numbers) / 5, 1.0) * 0.6 + min(len(percentages) / 3, 1.0) * 0.4
    temporal = min(len(_DATE_PATTERN.findall(text)) / 3, 1.0)
    named_entities = min(len(_NAMED_ENTITY_PATTERN.findall(text)) / 3, 1.0)
    return {
        "specificity": round(specificity, 2),
        "has_numbers": round(has_numbers, 2),
        "temporal": round(temporal, 2),
        "named_entities": round(named_entities, 2),
    }


def assess_document_quality(text: str, source_system: str = "") -> dict:
    """Return presentation-quality signals, never evidence confidence or truth."""
    prior_class = source_prior_class(source_system)
    signals = _analyze_text(text)
    source_score = _SOURCE_QUALITY[prior_class]
    quality_score = (
        source_score * 0.45
        + signals["specificity"] * 0.25
        + signals["has_numbers"] * 0.10
        + signals["temporal"] * 0.10
        + signals["named_entities"] * 0.10
    )
    quality_score = round(max(0.0, min(quality_score, 1.0)), 3)
    return {
        "quality_score": quality_score,
        "source_class": SOURCE_PRIORS[prior_class]["source_class"],
        "quality_factors": {
            "source_reputation": source_score,
            **signals,
        },
    }


def _source_dependency_group(source: str) -> str:
    return source_group(source)


def _probability_from_odds(prior: float, likelihood_ratio: float) -> float:
    if prior <= 0:
        return 0.0
    if prior >= 1:
        return 1.0
    odds = prior / (1 - prior)
    updated_odds = odds * likelihood_ratio
    return updated_odds / (1 + updated_odds)


def update_hypothesis(
    hypothesis: str,
    prior_probability: float,
    evidence: list[dict],
) -> dict:
    """Apply explicit support/contradict/neutral evidence to one hypothesis.

    Repeated evidence from the same normalized source uses the square root of
    the fixed LR, preventing syndicated copies from counting as independent
    confirmations. Neutral evidence always has LR=1 and leaves the posterior
    unchanged.
    """
    if not hypothesis.strip():
        raise ValueError("hypothesis is required")
    if not 0 <= prior_probability <= 1:
        raise ValueError("prior_probability must be between 0 and 1")

    current = float(prior_probability)
    seen_sources: set[str] = set()
    assessed_evidence: list[dict] = []
    supporting_sources: set[str] = set()
    contradicting_sources: set[str] = set()
    for item in evidence:
        relation = str(item.get("relation", "")).strip().lower()
        strength = str(item.get("strength", "")).strip().lower()
        if relation not in HYPOTHESIS_LIKELIHOOD_RATIOS:
            raise ValueError("relation must be support, contradict, or neutral")
        if strength not in HYPOTHESIS_LIKELIHOOD_RATIOS[relation]:
            raise ValueError("strength must be weak, moderate, or strong")

        source = str(item.get("source", "")).strip()
        raw_sources = item.get("sources")
        if isinstance(raw_sources, list):
            sources = [str(value).strip() for value in raw_sources if str(value).strip()]
        else:
            sources = [source] if source else []
        groups = list(dict.fromkeys(
            group for group in (_source_dependency_group(value) for value in sources)
            if group
        ))
        base_lr = HYPOTHESIS_LIKELIHOOD_RATIOS[relation][strength]
        effective_lr = 1.0
        for group in groups:
            already_counted = group in seen_sources
            source_lr = base_lr if not already_counted else 1.0
            effective_lr *= source_lr
            if relation != "neutral":
                seen_sources.add(group)
            if relation == "support":
                supporting_sources.add(group)
            elif relation == "contradict":
                contradicting_sources.add(group)
        current = _probability_from_odds(current, effective_lr)
        assessed_evidence.append({
            "evidence_id": str(item.get("evidence_id", "")),
            "source": source,
            "relation": relation,
            "strength": strength,
            "likelihood_ratio": round(effective_lr, 4),
            "posterior_probability": round(current, 4),
            "rationale": str(item.get("rationale", "")),
        })

    posterior = round(current, 4)
    verdict = "verified" if posterior >= 0.7 else "refuted" if posterior <= 0.3 else "uncertain"
    if verdict == "verified":
        independent_source_count = len(supporting_sources)
    elif verdict == "refuted":
        independent_source_count = len(contradicting_sources)
    else:
        independent_source_count = len(supporting_sources | contradicting_sources)
    confidence_level = classify_confidence_level(
        independent_source_count,
        posterior,
        verdict,
    )
    return {
        "hypothesis": hypothesis,
        "prior_probability": float(prior_probability),
        "posterior_probability": posterior,
        "verdict": verdict,
        "confidence_level": confidence_level,
        "independent_source_count": independent_source_count,
        "evidence": assessed_evidence,
    }
