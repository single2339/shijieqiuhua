"""Deterministic admission policy for professional intelligence products."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from backend.collectors.horizon.models import ContentItem
from backend.intelligence.source_policy import SourceProfile, SourceTier
from backend.models import IntelLayer


class AdmissionStatus(str, Enum):
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


@dataclass(frozen=True)
class AdmissionDecision:
    status: AdmissionStatus
    score: float
    reasons: tuple[str, ...]
    pir_ids: tuple[str, ...]
    indicator_ids: tuple[str, ...]
    event_type: str
    layer: IntelLayer
    impact: str
    urgency: str

    @property
    def accepted(self) -> bool:
        return self.status is AdmissionStatus.ACCEPTED


@dataclass(frozen=True)
class _IndicatorRule:
    event_type: str
    layer: IntelLayer
    pir_id: str
    indicator_id: str
    terms: tuple[str, ...]
    impact: str = "medium"


# Ordered from the most specific warning indicators to broader developments.
_RULES = (
    _IndicatorRule(
        "military_exercise", IntelLayer.MILITARY, "PIR-MILITARY-POSTURE",
        "I&W-MILITARY-EXERCISE",
        ("military exercise", "live-fire exercise", "combat aircraft", "naval exercise", "军事演习", "实弹演习", "作战飞机", "海上演习"),
        "high",
    ),
    _IndicatorRule(
        "export_control", IntelLayer.ECONOMY, "PIR-STRATEGIC-TRADE",
        "I&W-EXPORT-CONTROL",
        ("export ban", "export control", "export restriction", "critical minerals", "rare earth", "出口禁令", "出口管制", "出口限制", "关键矿产", "稀土"),
        "high",
    ),
    _IndicatorRule(
        "cyber_incident", IntelLayer.CYBER, "PIR-CYBER-THREAT",
        "I&W-CYBER-DISRUPTION",
        ("ransomware", "data breach", "cyberattack", "critical infrastructure attack", "勒索软件", "数据泄露", "网络攻击", "关键基础设施攻击"),
        "high",
    ),
    _IndicatorRule(
        "energy_disruption", IntelLayer.ENERGY, "PIR-ENERGY-SECURITY",
        "I&W-ENERGY-DISRUPTION",
        ("pipeline outage", "power outage", "oil embargo", "gas supply cut", "refinery shutdown", "管道中断", "大范围停电", "石油禁运", "天然气断供", "炼油厂停产"),
        "high",
    ),
    _IndicatorRule(
        "natural_hazard", IntelLayer.NATURE, "PIR-NATURAL-HAZARDS",
        "I&W-HAZARD-IMPACT",
        ("earthquake", "tsunami warning", "volcanic eruption", "major flood", "wildfire evacuation", "地震", "海啸预警", "火山喷发", "严重洪水", "山火疏散"),
        "high",
    ),
    _IndicatorRule(
        "financial_action", IntelLayer.FINANCE, "PIR-FINANCIAL-STABILITY",
        "I&W-FINANCIAL-ACTION",
        ("emergency rate", "capital controls", "bank run", "debt default", "currency intervention", "紧急降息", "紧急加息", "资本管制", "银行挤兑", "债务违约", "汇率干预"),
        "high",
    ),
    _IndicatorRule(
        "trade_disruption", IntelLayer.ECONOMY, "PIR-STRATEGIC-TRADE",
        "I&W-TRADE-DISRUPTION",
        ("trade embargo", "new tariff", "customs suspension", "import ban", "贸易禁运", "加征关税", "海关暂停", "进口禁令"),
        "medium",
    ),
    _IndicatorRule(
        "aviation_disruption", IntelLayer.AVIATION, "PIR-AVIATION-SECURITY",
        "I&W-AIRSPACE-CLOSURE",
        ("airspace closure", "closes airspace", "closed the airspace", "notam", "flight suspension", "空域关闭", "关闭空域", "航班停飞"),
        "high",
    ),
    _IndicatorRule(
        "health_emergency", IntelLayer.HEALTH, "PIR-PUBLIC-HEALTH",
        "I&W-HEALTH-EMERGENCY",
        ("public health emergency", "disease outbreak", "quarantine order", "pandemic alert", "公共卫生紧急状态", "疫情暴发", "隔离令", "大流行预警"),
        "high",
    ),
    _IndicatorRule(
        "political_change", IntelLayer.POLITICS, "PIR-POLITICAL-STABILITY",
        "I&W-POLITICAL-CHANGE",
        ("state of emergency", "government collapse", "military coup", "resigned as president", "进入紧急状态", "政府垮台", "军事政变", "总统辞职"),
        "high",
    ),
    _IndicatorRule(
        "civil_unrest", IntelLayer.SOCIETY, "PIR-SOCIAL-STABILITY",
        "I&W-CIVIL-UNREST",
        ("mass protest", "general strike", "riot police", "nationwide unrest", "大规模抗议", "全国罢工", "防暴警察", "全国骚乱"),
        "medium",
    ),
    _IndicatorRule(
        "logistics_disruption", IntelLayer.ECONOMY, "PIR-SUPPLY-CHAIN",
        "I&W-LOGISTICS-DISRUPTION",
        ("port closure", "shipping disruption", "canal blocked", "rail freight suspension", "港口关闭", "航运中断", "运河堵塞", "铁路货运暂停"),
        "high",
    ),
    _IndicatorRule(
        "agricultural_shock", IntelLayer.AGRICULTURE, "PIR-FOOD-SECURITY",
        "I&W-AGRICULTURAL-SHOCK",
        ("crop failure", "grain export ban", "livestock disease", "food emergency", "作物歉收", "粮食出口禁令", "牲畜疫情", "粮食紧急状态"),
        "high",
    ),
    _IndicatorRule(
        "technology_restriction", IntelLayer.TECHNOLOGY, "PIR-TECHNOLOGY-CONTROLS",
        "I&W-TECHNOLOGY-RESTRICTION",
        ("chip export restriction", "semiconductor ban", "technology sanctions", "芯片出口限制", "半导体禁运", "科技制裁"),
        "medium",
    ),
)

_SOURCE_SCORES = {
    SourceTier.PRIMARY: 0.28,
    SourceTier.PROFESSIONAL: 0.24,
    SourceTier.LOCAL: 0.18,
    SourceTier.UNKNOWN: 0.08,
    SourceTier.SOCIAL: 0.04,
    SourceTier.KNOWLEDGE: 0.0,
}
_URGENT_TERMS = (
    "effective immediately", "emergency", "evacuation", "closed", "closure",
    "suspension", "outage", "warning", "notam", "立即生效", "紧急", "疏散", "关闭", "停飞", "中断", "预警",
)


class AdmissionEngine:
    """Score a collected item before translation, summarization, and alerting."""

    def __init__(self, *, acceptance_threshold: float = 0.75) -> None:
        self.acceptance_threshold = acceptance_threshold

    def evaluate(self, item: ContentItem, profile: SourceProfile) -> AdmissionDecision:
        title = (item.title or "").strip()
        content = (item.content or "").strip()
        text = f"{title}\n{content}".lower()
        reasons: list[str] = []

        if not title and not content:
            return AdmissionDecision(
                status=AdmissionStatus.REJECTED,
                score=0.0,
                reasons=("empty_document",),
                pir_ids=(),
                indicator_ids=(),
                event_type="",
                layer=IntelLayer.UNCLASSIFIED,
                impact="low",
                urgency="low",
            )

        rule = next((candidate for candidate in _RULES if any(term in text for term in candidate.terms)), None)
        score = _SOURCE_SCORES[profile.tier]
        if rule:
            score += 0.25 + 0.18
            reasons.append("warning_indicator_match")
        else:
            reasons.append("no_warning_indicator")

        if len(content) >= 80:
            score += 0.10
        else:
            reasons.append("insufficient_content")

        urgency = "high" if any(term in text for term in _URGENT_TERMS) else "medium"
        if urgency == "high":
            score += 0.08
        if rule and rule.impact == "high":
            score += 0.10
        if re.search(r"\b(?:\d{1,2}:\d{2}|\d{4}|government|authority|regulation)\b|政府|监管|当局|海关", text):
            score += 0.06

        if profile.tier is SourceTier.KNOWLEDGE:
            reasons.append("knowledge_source")
            score = min(score, 0.49)
        if profile.tier is SourceTier.SOCIAL:
            reasons.append("social_unverified")
            score = min(score, 0.54)
        if profile.tier is SourceTier.UNKNOWN:
            reasons.append("unknown_source")
            score = min(score, 0.69)
        if len(content) < 40:
            score = min(score, 0.34)

        score = round(min(score, 1.0), 3)
        status = (
            AdmissionStatus.ACCEPTED
            if rule is not None and score >= self.acceptance_threshold
            else AdmissionStatus.QUARANTINED
        )
        if status is AdmissionStatus.ACCEPTED:
            reasons.append("meets_intelligence_threshold")
        else:
            reasons.append("below_intelligence_threshold")

        return AdmissionDecision(
            status=status,
            score=score,
            reasons=tuple(reasons),
            pir_ids=(rule.pir_id,) if rule else (),
            indicator_ids=(rule.indicator_id,) if rule else (),
            event_type=rule.event_type if rule else "",
            layer=rule.layer if rule else IntelLayer.UNCLASSIFIED,
            impact=rule.impact if rule else "low",
            urgency=urgency if rule else "low",
        )
