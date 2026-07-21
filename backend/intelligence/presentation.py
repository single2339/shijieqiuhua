"""将持久化的情报产品层数据适配到现有分析接口契约。"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.intelligence.store import IntelligenceStore


_CONFIDENCE_LABELS = {
    "L1": "已确认",
    "L2": "很可能",
    "L3": "可能",
    "L4": "推测",
}
_VERIFICATION_LABELS = {
    "L1": "多源确认",
    "L2": "交叉支持",
    "L3": "单一可靠来源",
    "L4": "待核查",
}
_EVENT_TYPE_LABELS = {
    "military_exercise": "军事演习",
    "export_control": "出口管制",
    "cyber_incident": "网络安全事件",
    "energy_disruption": "能源供应中断",
    "natural_hazard": "自然灾害",
    "financial_action": "金融政策行动",
    "trade_disruption": "贸易中断",
    "aviation_disruption": "航空运行中断",
    "health_emergency": "公共卫生紧急事件",
    "political_change": "政局变化",
    "civil_unrest": "社会动荡",
    "logistics_disruption": "物流中断",
    "agricultural_shock": "农业与粮食冲击",
    "technology_restriction": "技术限制",
}
_INDICATOR_LABELS = {
    "I&W-MILITARY-EXERCISE": "军事演习",
    "I&W-EXPORT-CONTROL": "出口管制",
    "I&W-CYBER-DISRUPTION": "网络安全中断",
    "I&W-ENERGY-DISRUPTION": "能源供应中断",
    "I&W-HAZARD-IMPACT": "自然灾害影响",
    "I&W-FINANCIAL-ACTION": "金融政策行动",
    "I&W-TRADE-DISRUPTION": "贸易中断",
    "I&W-AIRSPACE-CLOSURE": "空域关闭",
    "I&W-HEALTH-EMERGENCY": "公共卫生紧急事件",
    "I&W-POLITICAL-CHANGE": "政局变化",
    "I&W-CIVIL-UNREST": "社会动荡",
    "I&W-LOGISTICS-DISRUPTION": "物流中断",
    "I&W-AGRICULTURAL-SHOCK": "农业与粮食冲击",
    "I&W-TECHNOLOGY-RESTRICTION": "技术限制",
}
_CLAIM_STATUS_LABELS = {
    "unverified": "待核查",
    "supported": "已获支持",
    "disputed": "存在争议",
    "refuted": "已被反驳",
}


def _in_scope(event: dict, scope: dict) -> bool:
    day = str(event.get("event_time") or "")[:10]
    date = str(scope.get("date") or "")
    start_date = date or str(scope.get("start_date") or "")
    end_date = date or str(scope.get("end_date") or "")
    layers = {str(layer) for layer in scope.get("layers", []) if layer}
    if start_date and day < start_date:
        return False
    if end_date and day > end_date:
        return False
    if layers and event.get("layer") not in layers:
        return False
    return True


def _confidence(event: dict, evidence_ids: list[str]) -> dict:
    level = str(event["confidence_level"])
    independent = int(event["independent_source_count"])
    evidence_count = int(event["evidence_count"])
    return {
        "level": level,
        "label": _CONFIDENCE_LABELS.get(level, "待核查"),
        "rationale": f"{independent} 个独立信源、{evidence_count} 条证据；转载源已按独立性分组去重。",
        "independent_source_count": independent,
        "evidence_count": evidence_count,
        "evidence_ids": evidence_ids,
    }


def build_event_cluster_result(
    store: IntelligenceStore,
    *,
    scope: dict | None = None,
    limit: int = 50,
) -> dict:
    """Build the event-first view consumed by the analysis dashboard."""
    scope = scope or {}
    events = [event for event in store.list_events(limit=max(limit * 4, limit)) if _in_scope(event, scope)]
    clusters: list[dict] = []
    for event in events[:limit]:
        points = store.list_points(event_id=event["event_id"], limit=100)
        claims = store.list_claims(event["event_id"])
        evidence_ids = [point["point_id"] for point in points]
        confidence = _confidence(event, evidence_ids)
        verification = _VERIFICATION_LABELS.get(event["confidence_level"], "待核查")
        evidence = [
            {
                "id": point["point_id"],
                "item_id": point["silver_document_id"],
                "title": point["title"],
                "summary": point["statement"],
                "source": point["source_key"],
                "sources": [point["source_key"]],
                "date": str(point["published_at"])[:10],
                "layer": point["layer"],
                "country": "",
                "confidence": point["relevance_score"],
                "confidence_level": event["confidence_level"],
                "confidence_label": confidence["label"],
                "url": point["url"],
                "verification": verification,
                "independent_source_count": event["independent_source_count"],
            }
            for point in points
        ]
        claim_rows = [
            {
                "id": claim["claim_id"],
                "claim": claim["statement"],
                "confidence": confidence,
                "support_count": event["evidence_count"],
                "source_count": event["independent_source_count"],
                "evidence_ids": [claim["point_id"]],
                "verification_status": _CLAIM_STATUS_LABELS.get(
                    claim["verification_status"], claim["verification_status"]
                ),
            }
            for claim in claims
        ]
        key_terms = sorted({
            _INDICATOR_LABELS.get(indicator, indicator)
            for point in points
            for indicator in point.get("indicator_ids", [])
        })
        event_day = str(event["event_time"])[:10]
        clusters.append({
            "id": event["event_id"],
            "title": event["title"],
            "summary": (
                f"{_EVENT_TYPE_LABELS.get(event['event_type'], event['event_type'])} · "
                f"{event['evidence_count']} 条证据 · "
                f"{event['independent_source_count']} 个独立信源 · {verification}"
            ),
            "start_date": event_day,
            "end_date": event_day,
            "countries": [],
            "layers": [event["layer"]],
            "item_count": event["evidence_count"],
            "source_count": event["independent_source_count"],
            "confidence": confidence,
            "verification_status": verification,
            "key_terms": key_terms,
            "claims": claim_rows,
            "evidence": evidence,
        })

    return {
        "scope": scope,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_items": sum(int(event["evidence_count"]) for event in events),
        "total_clusters": len(events),
        "unclustered_count": sum(1 for event in events if int(event["evidence_count"]) == 1),
        "clusters": clusters,
    }


def build_warning_indicator_result(events_result: dict) -> dict:
    """从已持久化、独立评级的情报事件生成可审计的指标与预警结果。"""
    indicators: list[dict] = []
    high_impact_layers = {
        "military", "cyber", "politics", "finance", "energy", "health", "aviation", "economy",
    }
    for event in events_result.get("clusters", []):
        confidence = event["confidence"]
        level = confidence["level"]
        layers = set(event.get("layers", []))
        if level not in {"L1", "L2"} or not layers & high_impact_layers:
            continue
        if level == "L1" and layers & {"military", "cyber"}:
            severity = "critical"
        else:
            severity = "high"
        evidence_ids = [evidence["id"] for evidence in event.get("evidence", [])]
        indicators.append({
            "id": f"IW-{len(indicators) + 1:03d}",
            "title": event["title"],
            "severity": severity,
            "status": "triggered",
            "confidence": confidence,
            "trigger": (
                f"{event['verification_status']} · {event['item_count']} 条证据 · "
                f"{event['source_count']} 个独立信源"
            ),
            "rationale": "事件命中受控预警指标，并达到独立信源交叉验证门槛。",
            "countries": event.get("countries", []),
            "layers": event.get("layers", []),
            "related_event_ids": [event["id"]],
            "evidence_ids": evidence_ids,
            "next_steps": [
                "核对一手来源原文、发布时间和适用范围。",
                "检索反证、否认和后续升级信号。",
                "按事件时效持续更新独立信源计数。",
            ],
            "review_window": "6h" if severity == "critical" else "12h",
        })

    if any(indicator["severity"] == "critical" for indicator in indicators):
        overall_level = "critical"
    elif indicators:
        overall_level = "high"
    else:
        overall_level = "normal"
    weak_events = [
        event for event in events_result.get("clusters", [])
        if event["confidence"]["level"] in {"L3", "L4"}
    ]
    collection_requirements = []
    if weak_events:
        collection_requirements.append({
            "priority": "高",
            "task": "为单源事件补充独立验证",
            "rationale": f"{len(weak_events)} 个事件尚未达到 L2 交叉验证门槛。",
            "query": "",
        })
    return {
        "scope": events_result.get("scope", {}),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_items": events_result.get("total_items", 0),
        "overall_level": overall_level,
        "active_indicator_count": len(indicators),
        "methodology": "指标与预警：仅使用通过准入、完成事件归并并按独立信源评级的情报产品层证据。",
        "indicators": indicators,
        "collection_requirements": collection_requirements,
    }
