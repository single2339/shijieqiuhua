from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models import IntelItem

# ── Entity extraction constants ──

STOP_WORDS = {
    "The", "This", "That", "These", "Those", "Report", "New", "News",
    "More", "After", "Over", "Into", "From", "With", "Will", "Says",
    "First", "Last", "Next", "Can", "May", "Has", "Had", "Its",
}

ORG_KEYWORDS = {
    "Inc", "Corp", "Corporation", "Ministry", "Agency", "Department",
    "Committee", "Commission", "Council", "Authority", "Bureau",
    "Institute", "University", "Bank", "Group", "Holdings",
    "Ltd", "LLC", "PLC", "Foundation", "Union", "Alliance",
    "Coalition", "Party", "Congress", "Parliament", "Senate",
    "Forces", "Navy", "Army", "Air", "Force", "Guard",
}

KNOWN_LOCATIONS: set[str] = set()


def _init_locations() -> None:
    if KNOWN_LOCATIONS:
        return
    for loc in [
        "China", "Beijing", "Shanghai", "Guangdong", "Shenzhen", "Hong Kong",
        "United States", "Washington", "New York", "California", "Texas",
        "Russia", "Moscow", "Ukraine", "Kyiv", "Crimea",
        "France", "Paris", "Germany", "Berlin", "UK", "London",
        "Japan", "Tokyo", "South Korea", "Seoul", "North Korea",
        "India", "New Delhi", "Mumbai", "Pakistan", "Islamabad",
        "Iran", "Tehran", "Iraq", "Baghdad", "Syria", "Damascus",
        "Israel", "Jerusalem", "Gaza", "Lebanon", "Beirut",
        "Turkey", "Ankara", "Istanbul", "Greece", "Athens",
        "Italy", "Rome", "Spain", "Madrid", "Portugal", "Lisbon",
        "Brazil", "Sao Paulo", "Argentina", "Buenos Aires",
        "Australia", "Sydney", "Canada", "Ottawa", "Mexico",
        "Egypt", "Cairo", "South Africa", "Nigeria", "Kenya",
        "Taiwan", "Taipei", "Vietnam", "Hanoi", "Thailand", "Bangkok",
        "Singapore", "Malaysia", "Kuala Lumpur", "Indonesia", "Jakarta",
        "Philippines", "Manila", "Myanmar", "Bangladesh", "Dhaka",
        "Saudi Arabia", "Riyadh", "UAE", "Dubai", "Qatar", "Doha",
        "Poland", "Warsaw", "Sweden", "Stockholm", "Norway", "Oslo",
        "Finland", "Helsinki", "Denmark", "Copenhagen",
        "Netherlands", "Amsterdam", "Belgium", "Brussels", "Switzerland",
    ]:
        KNOWN_LOCATIONS.add(loc.lower())


_ENTITY_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b")

LAYER_RISK_WEIGHTS = {
    "military": 1.0,
    "cyber": 0.9,
    "finance": 0.8,
    "politics": 0.8,
    "energy": 0.75,
    "health": 0.7,
    "aviation": 0.6,
    "agriculture": 0.6,
    "economy": 0.5,
    "technology": 0.5,
    "society": 0.4,
    "nature": 0.3,
}

LAYER_LABELS = {
    "nature": "自然生态",
    "economy": "经济产业",
    "finance": "金融",
    "politics": "政治外交",
    "military": "军事",
    "aviation": "民航交通",
    "technology": "科技",
    "society": "社会民生",
    "energy": "能源资源",
    "agriculture": "农业食品",
    "health": "公共卫生",
    "cyber": "网络空间",
}

HIGH_IMPACT_LAYERS = {"military", "cyber", "politics", "finance", "energy", "health"}


def _is_person(text: str) -> bool:
    parts = text.strip().split()
    if len(parts) < 2 or len(parts) > 4:
        return False
    return not any(kw.lower() in text.lower() for kw in ORG_KEYWORDS)


def _is_org(text: str) -> bool:
    if any(kw.lower() in text.lower() for kw in ORG_KEYWORDS):
        return True
    return len(text.strip().split()) >= 4


def _is_location(text: str) -> bool:
    return text.lower().strip() in KNOWN_LOCATIONS


# ═══════════════════════════════════════════════════════════════
# 1 — Timeline
# ═══════════════════════════════════════════════════════════════


def compute_timeline(items: list) -> dict:
    _init_locations()
    date_groups: dict[str, list] = defaultdict(list)

    for item in items:
        d = item.captured_at[:10] if item.captured_at else ""
        if d:
            date_groups[d].append(item)

    points: list[dict] = []
    for date in sorted(date_groups.keys()):
        group = date_groups[date]
        layer_counts: dict[str, int] = defaultdict(int)
        for it in group:
            layer_counts[it.layer.value] += 1

        points.append({
            "date": date,
            "count": len(group),
            "items": [
                {
                    "id": it.id,
                    "title": it.title[:60],
                    "layer": it.layer.value,
                    "country": it.country,
                    "confidence": it.confidence,
                    "source_system": it.source_system,
                }
                for it in group[:10]
            ],
            "layer_counts": dict(layer_counts),
        })

    date_range = {}
    if points:
        date_range["start"] = points[0]["date"]
        date_range["end"] = points[-1]["date"]
        date_range["days"] = len(points)

    return {"points": points, "date_range": date_range}


# ═══════════════════════════════════════════════════════════════
# 2 — Entity Graph
# ═══════════════════════════════════════════════════════════════


def extract_entity_graph(items: list) -> dict:
    _init_locations()
    entity_counts: dict[str, int] = defaultdict(int)
    entity_types: dict[str, str] = {}
    entity_label: dict[str, str] = {}
    co_occurrence: dict[tuple[str, str], int] = defaultdict(int)

    for item in items:
        text = f"{item.title} {item.summary[:200]}"
        candidates = _ENTITY_RE.findall(text)
        entities_in_item: set[str] = set()

        for candidate in candidates:
            c = candidate.strip()
            if not c or len(c) < 3 or c in STOP_WORDS:
                continue
            key = c.lower()
            entity_counts[key] += 1
            if key not in entity_label:
                entity_label[key] = c

            if key not in entity_types:
                if _is_org(c):
                    entity_types[key] = "org"
                elif _is_location(c):
                    entity_types[key] = "location"
                elif _is_person(c):
                    entity_types[key] = "person"
                else:
                    entity_types[key] = "org"
            entities_in_item.add(key)

        # Match known locations in text
        for loc in KNOWN_LOCATIONS:
            if loc in text.lower():
                entities_in_item.add(loc)
                if loc not in entity_types:
                    entity_types[loc] = "location"
                    entity_label[loc] = loc.title()

        # Co-occurrence edges
        ent_list = sorted(entities_in_item)
        for i in range(len(ent_list)):
            for j in range(i + 1, len(ent_list)):
                pair = (ent_list[i], ent_list[j])
                co_occurrence[pair] += 1

    # Top 50 entities
    top_entities = sorted(entity_counts.items(), key=lambda x: -x[1])[:50]
    top_keys = {k for k, _ in top_entities}

    nodes: list[dict] = [
        {
            "id": key,
            "label": entity_label.get(key, key.title()),
            "type": entity_types.get(key, "org"),
            "count": entity_counts[key],
        }
        for key in sorted(top_keys)
    ]

    edges: list[dict] = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in co_occurrence.items()
        if a in top_keys and b in top_keys and w > 0
    ]

    return {"nodes": nodes, "edges": edges}


# ═══════════════════════════════════════════════════════════════
# 3 — Cross-Source Corroboration
# ═══════════════════════════════════════════════════════════════


def compute_corroboration(items: list) -> dict:
    clusters_result = generate_event_clusters(items, limit=100)
    clusters = clusters_result["clusters"]
    source_items: dict[str, set[str]] = defaultdict(set)
    source_events: dict[str, set[str]] = defaultdict(set)
    event_lookup: dict[str, dict] = {}

    for item in items:
        for src in _source_names(item):
            source_items[src].add(item.id)

    for cluster in clusters:
        event_lookup[cluster["id"]] = cluster
        event_sources: set[str] = set()
        for evidence in cluster["evidence"]:
            event_sources.update(src for src in evidence.get("sources", []) if src)
            if evidence.get("source"):
                event_sources.add(evidence["source"])
        for src in event_sources:
            source_events[src].add(cluster["id"])

    top_sources = sorted(source_items.items(), key=lambda x: (-len(source_events.get(x[0], set())), -len(x[1])))[:20]
    sources = [s for s, _ in top_sources]
    n = len(sources)

    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]
    pairs: list[dict] = []

    for i in range(n):
        for j in range(i + 1, n):
            sa, sb = sources[i], sources[j]
            events_a = source_events.get(sa, set())
            events_b = source_events.get(sb, set())
            shared_event_ids = sorted(events_a & events_b)
            shared = len(shared_event_ids)
            total = len(events_a) + len(events_b) - shared
            score = shared / max(total, 1)
            shared_events = [event_lookup[event_id] for event_id in shared_event_ids if event_id in event_lookup]
            confirmed_events = sum(1 for event in shared_events if event["confidence"]["level"] == "L1")
            high_confidence_events = sum(1 for event in shared_events if event["confidence"]["level"] in {"L1", "L2"})
            titles = [event["title"] for event in shared_events[:5]]
            matrix[i][j] = round(score, 3)
            matrix[j][i] = round(score, 3)
            pairs.append({
                "source_a": sa,
                "source_b": sb,
                "shared_topics": shared,
                "total_a": len(events_a),
                "total_b": len(events_b),
                "agreement_score": round(score, 3),
                "shared_events": shared,
                "confirmed_events": confirmed_events,
                "high_confidence_events": high_confidence_events,
                "shared_event_ids": shared_event_ids[:10],
                "shared_event_titles": titles,
                "verification_summary": (
                    f"共同支撑 {shared} 个事件簇，其中 {confirmed_events} 个达到 L1，"
                    f"{high_confidence_events} 个达到 L1/L2。"
                ),
            })

    for i in range(n):
        matrix[i][i] = 1.0

    pairs.sort(key=lambda x: (-x["high_confidence_events"], -x["shared_events"], -x["agreement_score"]))
    return {
        "sources": sources,
        "matrix": matrix,
        "top_pairs": pairs[:30],
        "event_count": clusters_result["total_clusters"],
        "claim_count": sum(len(cluster["claims"]) for cluster in clusters),
    }


# ═══════════════════════════════════════════════════════════════
# 4 — Anomaly Detection (Z-Score)
# ═══════════════════════════════════════════════════════════════


def detect_anomalies(items: list) -> dict:
    layer_date_counts: dict[tuple[str, str], int] = defaultdict(int)
    layer_date_countries: dict[tuple[str, str], set[str]] = defaultdict(set)

    for item in items:
        d = item.captured_at[:10] if item.captured_at else ""
        if d:
            key = (item.layer.value, d)
            layer_date_counts[key] += 1
            if item.country:
                layer_date_countries[key].add(item.country)

    layer_counts: dict[str, list[int]] = defaultdict(list)
    for (layer, date), count in layer_date_counts.items():
        layer_counts[layer].append(count)

    baseline: dict[str, dict] = {}
    for layer, counts in layer_counts.items():
        n = len(counts)
        mean = sum(counts) / n if n > 0 else 0
        variance = sum((c - mean) ** 2 for c in counts) / n if n > 0 else 0
        std = math.sqrt(variance)
        baseline[layer] = {"mean": round(mean, 2), "std": round(std, 2), "days": n}

    anomalies: list[dict] = []
    for (layer, date), count in layer_date_counts.items():
        bl = baseline.get(layer, {})
        std = max(bl.get("std", 1.0), 1.0)
        mean = bl.get("mean", 0.0)
        z = (count - mean) / std

        if abs(z) > 1.5:
            az = abs(z)
            if az >= 3.0:
                severity = "critical"
            elif az >= 2.5:
                severity = "high"
            elif az >= 2.0:
                severity = "medium"
            else:
                severity = "low"

            countries = layer_date_countries.get((layer, date), set())
            anomalies.append({
                "date": date,
                "layer": layer,
                "country": ", ".join(sorted(countries)[:3]),
                "actual_count": count,
                "expected_count": round(mean, 1),
                "z_score": round(z, 2),
                "severity": severity,
            })

    anomalies.sort(key=lambda x: -abs(x["z_score"]))
    return {"anomalies": anomalies, "baseline": baseline}


# ═══════════════════════════════════════════════════════════════
# 5 — Risk Heatmap
# ═══════════════════════════════════════════════════════════════


def compute_risk_heatmap(items: list) -> dict:
    country_items: dict[str, list] = defaultdict(list)

    for item in items:
        if item.country:
            country_items[item.country].append(item)

    if not country_items:
        return {"regions": []}

    max_density = max(len(v) for v in country_items.values())

    regions: list[dict] = []
    for country, citems in country_items.items():
        density_norm = min(len(citems) / max(max_density, 1), 1.0)
        avg_conf = sum(it.confidence for it in citems) / len(citems) if citems else 0.0

        layer_counts: dict[str, int] = defaultdict(int)
        for it in citems:
            layer_counts[it.layer.value] += 1
        total = len(citems) or 1
        layer_breakdown = {k: round(v / total, 3) for k, v in layer_counts.items()}

        layer_risk = sum(
            LAYER_RISK_WEIGHTS.get(layer, 0.3) * count / total
            for layer, count in layer_counts.items()
        )

        risk_score = density_norm * 0.3 + avg_conf * 0.3 + layer_risk * 0.4
        regions.append({
            "country": country,
            "risk_score": round(risk_score, 3),
            "intel_density": len(citems),
            "avg_confidence": round(avg_conf, 3),
            "layer_breakdown": layer_breakdown,
        })

    regions.sort(key=lambda x: -x["risk_score"])
    return {"regions": regions}


# ═══════════════════════════════════════════════════════════════
# 6 — Gap Analysis
# ═══════════════════════════════════════════════════════════════


def analyze_gaps(items: list) -> dict:
    gaps: list[dict] = []
    coverage_stats: dict = {}

    if not items:
        return {"gaps": [], "coverage_stats": {"total_items": 0}}

    # Topic gaps
    layer_counts: dict[str, int] = defaultdict(int)
    for it in items:
        layer_counts[it.layer.value] += 1
    total = len(items)

    for layer, count in layer_counts.items():
        pct = count / total
        if pct < 0.05:
            gaps.append({
                "gap_type": "topic",
                "description": f"'{layer}' 图层情报仅占 {pct:.1%}，可能存在监测盲区",
                "severity": "high" if pct < 0.02 else "medium",
                "affected_region": "",
                "affected_layer": layer,
                "recommendation": f"建议增加 {layer} 相关数据源或扩大采集范围",
            })

    # Region gaps
    country_counts: dict[str, int] = defaultdict(int)
    for it in items:
        if it.country:
            country_counts[it.country] += 1

    sparse_countries = sorted(
        [(c, n) for c, n in country_counts.items() if n < 2],
        key=lambda x: x[1],
    )[:10]
    if sparse_countries:
        names = ", ".join(c for c, _ in sparse_countries[:5])
        gaps.append({
            "gap_type": "region",
            "description": f"以下地区情报稀少（<2条）: {names}",
            "severity": "high" if len(sparse_countries) > 5 else "medium",
            "affected_region": names,
            "affected_layer": "",
            "recommendation": "建议针对这些地区配置定向采集源",
        })

    # Time gaps
    date_set: set[str] = set()
    for it in items:
        d = it.captured_at[:10] if it.captured_at else ""
        if d:
            date_set.add(d)
    dates_sorted = sorted(date_set)

    if len(dates_sorted) >= 2:
        try:
            start = datetime.strptime(dates_sorted[0], "%Y-%m-%d")
            end = datetime.strptime(dates_sorted[-1], "%Y-%m-%d")
            total_days = (end - start).days + 1
            coverage_pct = len(dates_sorted) / max(total_days, 1)

            max_gap = 0
            current_gap = 0
            d = start
            while d <= end:
                ds = d.strftime("%Y-%m-%d")
                if ds not in date_set:
                    current_gap += 1
                else:
                    max_gap = max(max_gap, current_gap)
                    current_gap = 0
                d += timedelta(days=1)
            max_gap = max(max_gap, current_gap)

            if max_gap > 3:
                gaps.append({
                    "gap_type": "time",
                    "description": f"存在连续 {max_gap} 天的时间窗口无情报数据",
                    "severity": "critical" if max_gap > 7 else "high" if max_gap > 5 else "medium",
                    "affected_region": "",
                    "affected_layer": "",
                    "recommendation": "建议检查采集器运行状态，增加采集频率或来源",
                })

            coverage_stats["time_coverage"] = round(coverage_pct, 3)
            coverage_stats["date_range_days"] = total_days
            coverage_stats["active_days"] = len(dates_sorted)
        except (ValueError, IndexError):
            pass

    # Cross-source gaps
    single_source_count = sum(1 for it in items if len(it.sources) <= 1)
    single_source_pct = single_source_count / max(total, 1)
    if single_source_pct > 0.3:
        gaps.append({
            "gap_type": "cross_source",
            "description": f"{single_source_pct:.1%} 的情报仅来自单一来源，缺乏交叉验证",
            "severity": "critical" if single_source_pct > 0.5 else "high" if single_source_pct > 0.4 else "medium",
            "affected_region": "",
            "affected_layer": "",
            "recommendation": "增加信息来源多样性，优先对高置信度单源情报进行手动验证",
        })

    coverage_stats["total_items"] = total
    coverage_stats["countries_covered"] = len(country_counts)
    coverage_stats["single_source_pct"] = round(single_source_pct, 3)
    coverage_stats["layers_covered"] = sum(1 for c in layer_counts.values() if c > 0)

    gaps.sort(
        key=lambda g: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(g["severity"], 0),
        reverse=True,
    )
    return {"gaps": gaps, "coverage_stats": coverage_stats}


# ═══════════════════════════════════════════════════════════════
# 7 — Situation Brief
# ═══════════════════════════════════════════════════════════════


CONFIDENCE_LABELS = {
    "L1": "确认",
    "L2": "高可信",
    "L3": "中可信",
    "L4": "推测",
}


CONFIDENCE_WEIGHTS = {"L1": 4, "L2": 3, "L3": 2, "L4": 1}

CLAIM_STOP_WORDS = {
    "about", "after", "again", "against", "also", "amid", "before", "being",
    "could", "first", "from", "have", "into", "more", "near", "over",
    "report", "reported", "reports", "said", "says", "their", "there",
    "this", "that", "these", "those", "under", "with", "would",
    "最新", "报道", "消息", "表示", "相关", "发生",
}


def _source_names(item) -> set[str]:
    sources = {src.strip() for src in (getattr(item, "sources", []) or []) if src and src.strip()}
    source_system = (getattr(item, "source_system", "") or "").strip()
    if source_system:
        sources.add(source_system)
    return sources


def _confidence_assessment(items: list, evidence_ids: list[str] | None = None) -> dict:
    support = [item for item in items if item is not None]
    source_names: set[str] = set()
    for item in support:
        source_names.update(_source_names(item))

    independent_count = len(source_names)
    evidence_count = len(support)
    avg_confidence = sum(getattr(item, "confidence", 0.0) for item in support) / max(evidence_count, 1)
    reliable_single_source = evidence_count > 0 and avg_confidence >= 0.6

    if independent_count >= 3:
        level = "L1"
        rationale = f"{independent_count} 个独立来源交叉支撑，符合三方验证标准。"
    elif independent_count == 2:
        level = "L2"
        rationale = "2 个独立来源支撑，可信度较高但尚未达到三方验证。"
    elif independent_count == 1 and reliable_single_source:
        level = "L3"
        rationale = "1 个可靠来源支撑，可作为中可信线索。"
    else:
        level = "L4"
        rationale = "证据不足或主要依赖间接证据，只能作为推测。"

    return {
        "level": level,
        "label": CONFIDENCE_LABELS[level],
        "rationale": rationale,
        "independent_source_count": independent_count,
        "evidence_count": evidence_count,
        "evidence_ids": evidence_ids or [],
    }


def _confidence_score_from_level(level: str, avg_confidence: float) -> float:
    base = {"L1": 0.9, "L2": 0.76, "L3": 0.6, "L4": 0.38}.get(level, 0.38)
    return round(min(0.98, max(0.05, base * 0.75 + avg_confidence * 0.25)), 3)


def _verification_status(level: str) -> str:
    if level == "L1":
        return "三方确认"
    if level == "L2":
        return "双源支撑"
    if level == "L3":
        return "单源线索"
    return "待核查"


def _overall_confidence(assessments: list[dict]) -> dict:
    if not assessments:
        return {
            "level": "L4",
            "label": CONFIDENCE_LABELS["L4"],
            "rationale": "当前范围内没有足够证据形成整体评级。",
            "independent_source_count": 0,
            "evidence_count": 0,
            "evidence_ids": [],
        }

    weighted = sum(CONFIDENCE_WEIGHTS.get(a["level"], 1) for a in assessments) / len(assessments)
    if weighted >= 3.5:
        level = "L1"
    elif weighted >= 2.5:
        level = "L2"
    elif weighted >= 1.75:
        level = "L3"
    else:
        level = "L4"

    source_count = max(a.get("independent_source_count", 0) for a in assessments)
    evidence_count = sum(a.get("evidence_count", 0) for a in assessments)
    return {
        "level": level,
        "label": CONFIDENCE_LABELS[level],
        "rationale": f"综合 {len(assessments)} 项判断，最高覆盖 {source_count} 个独立来源。",
        "independent_source_count": source_count,
        "evidence_count": evidence_count,
        "evidence_ids": sorted({eid for a in assessments for eid in a.get("evidence_ids", [])}),
    }


def _verification_label(item) -> str:
    source_count = len(_source_names(item))
    if source_count >= 2:
        return "多源印证"
    if getattr(item, "verdict", "") == "verified":
        return "单源高置信"
    if getattr(item, "confidence", 0.0) < 0.45:
        return "低置信待核查"
    return "单源待核查"


def _evidence_id(idx: int) -> str:
    return f"E{idx + 1:02d}"


def _item_score(item) -> float:
    layer = item.layer.value
    source_bonus = min(len(_source_names(item)), 3) * 0.08
    evidence_bonus = min(max(item.evidence_count, 0), 4) * 0.04
    layer_bonus = LAYER_RISK_WEIGHTS.get(layer, 0.3) * 0.2
    return item.confidence * 0.55 + source_bonus + evidence_bonus + layer_bonus


def _make_evidence(items: list, limit: int = 12) -> list[dict]:
    ranked = sorted(items, key=_item_score, reverse=True)[:limit]
    evidence: list[dict] = []
    for idx, item in enumerate(ranked):
        rating = _confidence_assessment([item], [_evidence_id(idx)])
        evidence.append({
            "id": _evidence_id(idx),
            "item_id": item.id,
            "title": item.title,
            "summary": item.summary[:260],
            "source": item.source_system or (item.sources[0] if item.sources else ""),
            "sources": item.sources,
            "date": item.captured_at[:10] if item.captured_at else "",
            "layer": item.layer.value,
            "country": item.country,
            "confidence": round(item.confidence, 3),
            "confidence_level": rating["level"],
            "confidence_label": rating["label"],
            "url": item.url,
            "verification": _verification_label(item),
            "independent_source_count": rating["independent_source_count"],
        })
    return evidence


def _item_day(item) -> datetime | None:
    captured_at = getattr(item, "captured_at", "") or ""
    if not captured_at:
        return None
    try:
        return datetime.strptime(captured_at[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _claim_tokens(item) -> set[str]:
    text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')[:220]}".lower()
    tokens = re.findall(r"[a-z][a-z0-9-]{2,}|[\u4e00-\u9fff]{2,}", text)
    return {token for token in tokens if token not in CLAIM_STOP_WORDS and len(token) >= 3}


def _token_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _date_distance_days(item, cluster: dict) -> int:
    day = _item_day(item)
    if day is None or not cluster["dates"]:
        return 0
    return min(abs((day - cluster_day).days) for cluster_day in cluster["dates"])


def _cluster_match_score(item, cluster: dict, item_tokens: set[str]) -> float:
    similarity = _token_similarity(item_tokens, cluster["tokens"])
    same_country = not item.country or item.country in cluster["countries"]
    same_layer = item.layer.value in cluster["layers"]
    date_distance = _date_distance_days(item, cluster)

    if date_distance > 3:
        return 0.0
    if not same_country and similarity < 0.35:
        return 0.0

    score = similarity
    if same_country:
        score += 0.12
    if same_layer:
        score += 0.08
    if date_distance <= 1:
        score += 0.08
    return score


def _cluster_key_terms(cluster: dict, limit: int = 6) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for item in cluster["items"]:
        for token in _claim_tokens(item):
            counts[token] += 1
    return [token for token, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def _make_claims_for_cluster(group: list, evidence: list[dict]) -> list[dict]:
    top_item = sorted(group, key=_item_score, reverse=True)[0]
    evidence_ids = [e["id"] for e in evidence]
    confidence = _confidence_assessment(group, evidence_ids)
    return [{
        "id": "C1",
        "claim": top_item.title,
        "confidence": confidence,
        "support_count": len(group),
        "source_count": confidence["independent_source_count"],
        "evidence_ids": evidence_ids,
        "verification_status": _verification_status(confidence["level"]),
    }]


def generate_event_clusters(
    items: list,
    scope: dict | None = None,
    limit: int = 20,
) -> dict:
    """Group related items into event/claim clusters for source verification."""
    scope = scope or {}
    if not items:
        return {
            "scope": scope,
            "total_items": 0,
            "total_clusters": 0,
            "unclustered_count": 0,
            "clusters": [],
        }

    clusters: list[dict] = []
    clusters_by_country: dict[str, set[int]] = defaultdict(set)
    clusters_by_token: dict[str, set[int]] = defaultdict(set)
    for item in sorted(items, key=_item_score, reverse=True):
        item_tokens = _claim_tokens(item)
        best_cluster: dict | None = None
        best_cluster_index: int | None = None
        best_score = 0.0
        if item.country:
            candidate_indices = set(clusters_by_country.get(item.country, set()))
            for token in item_tokens:
                candidate_indices.update(clusters_by_token.get(token, set()))
        else:
            # An item without a country is considered a country match by the
            # scoring contract, so every existing cluster remains a candidate.
            candidate_indices = set(range(len(clusters)))

        for cluster_index in sorted(candidate_indices):
            cluster = clusters[cluster_index]
            score = _cluster_match_score(item, cluster, item_tokens)
            if score > best_score:
                best_score = score
                best_cluster = cluster
                best_cluster_index = cluster_index

        if best_cluster and best_score >= 0.24:
            new_tokens = item_tokens - best_cluster["tokens"]
            best_cluster["items"].append(item)
            best_cluster["tokens"].update(item_tokens)
            if item.country:
                best_cluster["countries"].add(item.country)
                clusters_by_country[item.country].add(best_cluster_index)
            best_cluster["layers"].add(item.layer.value)
            day = _item_day(item)
            if day is not None:
                best_cluster["dates"].add(day)
            for token in new_tokens:
                clusters_by_token[token].add(best_cluster_index)
        else:
            day = _item_day(item)
            clusters.append({
                "items": [item],
                "tokens": set(item_tokens),
                "countries": {item.country} if item.country else set(),
                "layers": {item.layer.value},
                "dates": {day} if day is not None else set(),
            })
            cluster_index = len(clusters) - 1
            if item.country:
                clusters_by_country[item.country].add(cluster_index)
            for token in item_tokens:
                clusters_by_token[token].add(cluster_index)

    ranked_clusters = sorted(
        clusters,
        key=lambda cluster: (
            -len(cluster["items"]),
            -len({src for item in cluster["items"] for src in _source_names(item)}),
            -sum(_item_score(item) for item in cluster["items"]),
        ),
    )

    event_clusters: list[dict] = []
    unclustered_count = sum(1 for cluster in ranked_clusters if len(cluster["items"]) == 1)
    for idx, cluster in enumerate(ranked_clusters[:limit], start=1):
        group = sorted(cluster["items"], key=_item_score, reverse=True)
        evidence = _make_evidence(group, limit=8)
        evidence_ids = [e["id"] for e in evidence]
        confidence = _confidence_assessment(group, evidence_ids)
        dates = sorted(day.strftime("%Y-%m-%d") for day in cluster["dates"] if day is not None)
        sources = sorted({src for item in group for src in _source_names(item)})
        title_item = group[0]
        key_terms = _cluster_key_terms(cluster)

        event_clusters.append({
            "id": f"EV{idx:02d}",
            "title": title_item.title,
            "summary": (
                f"聚合 {len(group)} 条相关情报，覆盖 {len(sources)} 个独立来源；"
                f"验证状态：{_verification_status(confidence['level'])}。"
            ),
            "start_date": dates[0] if dates else "",
            "end_date": dates[-1] if dates else "",
            "countries": sorted(cluster["countries"]),
            "layers": sorted(cluster["layers"]),
            "item_count": len(group),
            "source_count": len(sources),
            "confidence": confidence,
            "verification_status": _verification_status(confidence["level"]),
            "key_terms": key_terms,
            "claims": _make_claims_for_cluster(group, evidence),
            "evidence": evidence,
        })

    return {
        "scope": scope,
        "total_items": len(items),
        "total_clusters": len(ranked_clusters),
        "unclustered_count": unclustered_count,
        "clusters": event_clusters,
    }


def _warning_severity(event: dict) -> str:
    layers = set(event.get("layers", []))
    level = event["confidence"]["level"]
    if layers & {"military", "cyber"} and level == "L1":
        return "critical"
    if layers & HIGH_IMPACT_LAYERS and level in {"L1", "L2"}:
        return "high"
    if level in {"L1", "L2"}:
        return "medium"
    return "low"


def _overall_warning_level(indicators: list[dict]) -> str:
    if any(indicator["severity"] == "critical" for indicator in indicators):
        return "critical"
    if any(indicator["severity"] == "high" for indicator in indicators):
        return "high"
    if any(indicator["severity"] == "medium" for indicator in indicators):
        return "watch"
    return "normal"


def generate_warning_indicators(
    items: list,
    scope: dict | None = None,
    requested_layers: list[str] | None = None,
    clusters_result: dict | None = None,
) -> dict:
    """Generate indications-and-warning indicators from event-level evidence."""
    scope = scope or {}
    requested_layers = requested_layers or []
    total = len(items)
    if total == 0:
        return {
            "scope": scope,
            "total_items": 0,
            "overall_level": "normal",
            "active_indicator_count": 0,
            "indicators": [],
            "collection_requirements": [{
                "priority": "高",
                "task": "恢复基础情报采集",
                "rationale": "当前范围没有样本，预警系统无法判定是否存在异常。",
                "query": "",
            }],
        }

    clusters_result = clusters_result or generate_event_clusters(items, scope, limit=50)
    indicators: list[dict] = []
    collection_requirements: list[dict] = []

    for event in clusters_result["clusters"]:
        layers = set(event["layers"])
        level = event["confidence"]["level"]
        if not layers & HIGH_IMPACT_LAYERS:
            continue
        if level not in {"L1", "L2"} and event["source_count"] < 2:
            continue

        severity = _warning_severity(event)
        evidence_ids = []
        for claim in event["claims"]:
            evidence_ids.extend(claim.get("evidence_ids", []))
        indicators.append({
            "id": f"W{len(indicators) + 1:02d}",
            "title": event["title"],
            "severity": severity,
            "status": "triggered" if severity in {"critical", "high"} else "watch",
            "confidence": event["confidence"],
            "trigger": f"{event['verification_status']} · {event['item_count']} 条样本 · {event['source_count']} 个来源",
            "rationale": "高敏感主题出现事件级多源支撑，应进入持续监测队列。",
            "countries": event["countries"],
            "layers": event["layers"],
            "related_event_ids": [event["id"]],
            "evidence_ids": sorted(set(evidence_ids))[:8],
            "next_steps": [
                "补充一手或本地来源确认事件细节。",
                "搜索可能反驳该事件的证据，检查是否存在重复转载。",
                "持续监测 24 小时内是否出现升级、否认或官方确认。",
            ],
            "review_window": "6h" if severity == "critical" else "12h" if severity == "high" else "24h",
        })

    layer_counts: dict[str, int] = defaultdict(int)
    single_source_high_impact: list = []
    for item in items:
        layer_counts[item.layer.value] += 1
        if item.layer.value in HIGH_IMPACT_LAYERS and len(_source_names(item)) <= 1 and item.confidence >= 0.6:
            single_source_high_impact.append(item)

    for layer, count in sorted(layer_counts.items(), key=lambda kv: -kv[1])[:5]:
        pct = count / max(total, 1)
        if layer in HIGH_IMPACT_LAYERS and count >= 3 and pct >= 0.35:
            support = [item for item in items if item.layer.value == layer][:6]
            confidence = _confidence_assessment(support, [])
            indicators.append({
                "id": f"W{len(indicators) + 1:02d}",
                "title": f"{LAYER_LABELS.get(layer, layer)}主题在当前窗口显著集中",
                "severity": "high" if layer in {"military", "cyber"} else "medium",
                "status": "watch",
                "confidence": confidence,
                "trigger": f"{count} 条样本，占当前范围 {pct:.0%}",
                "rationale": "主题集中可能反映态势变化，也可能来自采集源偏向，需要用事件核查和反证搜索确认。",
                "countries": sorted({item.country for item in support if item.country}),
                "layers": [layer],
                "related_event_ids": [],
                "evidence_ids": [],
                "next_steps": [
                    f"围绕{LAYER_LABELS.get(layer, layer)}主题补充不同地域、不同类型来源。",
                    "检查是否由同一来源链路重复扩散造成。",
                ],
                "review_window": "12h",
            })

    if single_source_high_impact:
        support = sorted(single_source_high_impact, key=_item_score, reverse=True)[:6]
        confidence = _confidence_assessment(support, [])
        indicators.append({
            "id": f"W{len(indicators) + 1:02d}",
            "title": "高敏感单源线索需要优先核查",
            "severity": "medium",
            "status": "watch",
            "confidence": confidence,
            "trigger": f"{len(single_source_high_impact)} 条高敏感情报仍为单源支撑",
            "rationale": "单源高置信线索容易被误判为已验证事实，应在纳入判断前完成独立验证。",
            "countries": sorted({item.country for item in support if item.country}),
            "layers": sorted({item.layer.value for item in support}),
            "related_event_ids": [],
            "evidence_ids": [],
            "next_steps": [
                "逐条定位第二独立来源。",
                "优先核查军事、网络、能源、政治相关线索。",
            ],
            "review_window": "24h",
        })

    present_layers = set(layer_counts)
    missing_layers = [layer for layer in requested_layers if layer and layer not in present_layers]
    if missing_layers:
        names = "、".join(LAYER_LABELS.get(layer, layer) for layer in missing_layers[:5])
        collection_requirements.append({
            "priority": "高",
            "task": f"补齐 {names} 图层采集",
            "rationale": "筛选范围内缺少用户关注图层，可能形成预警盲区。",
            "query": names,
        })

    if indicators:
        top_indicator = sorted(
            indicators,
            key=lambda indicator: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(indicator["severity"], 0),
            reverse=True,
        )[0]
        collection_requirements.append({
            "priority": "高" if top_indicator["severity"] in {"critical", "high"} else "中",
            "task": f"围绕预警指标补充证据：{top_indicator['title'][:40]}",
            "rationale": "最高优先级预警需要一手来源、反证和来源独立性复核。",
            "query": " ".join(top_indicator["layers"] + top_indicator["countries"]),
        })

    indicators.sort(
        key=lambda indicator: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(indicator["severity"], 0),
        reverse=True,
    )
    return {
        "scope": scope,
        "total_items": total,
        "overall_level": _overall_warning_level(indicators),
        "active_indicator_count": len(indicators),
        "indicators": indicators[:12],
        "collection_requirements": collection_requirements,
    }


def generate_situation_brief(
    items: list,
    scope: dict | None = None,
    requested_layers: list[str] | None = None,
) -> dict:
    """Generate a deterministic situation brief from current filtered items.

    This is intentionally not a narrative LLM report. It produces auditable
    judgment/evidence/gap/task structures that the UI can inspect.
    """
    scope = scope or {}
    requested_layers = requested_layers or []
    total = len(items)
    if total == 0:
        empty_rating = _overall_confidence([])
        recommended_tasks = [{
            "priority": "高",
            "task": "扩大采集范围并检查采集器状态",
            "rationale": "没有基础证据时，任何态势判断都不可审计。",
            "query": "",
        }]
        return {
            "scope": scope,
            "summary": "当前筛选范围内没有可用于研判的情报。",
            "total_items": 0,
            "intelligence_level": empty_rating,
            "source_count": 0,
            "core_findings": [],
            "confirmed_facts": [],
            "assessments": [],
            "alternative_explanations": [],
            "pending_verification": [{
                "id": "V1",
                "question": "当前筛选条件是否过窄，或采集器是否异常？",
                "priority": "高",
                "rationale": "无数据状态下不能形成任何可审计判断。",
                "related_evidence_ids": [],
            }],
            "key_judgments": [],
            "evidence": [],
            "contradictions": [],
            "collection_gaps": [{
                "description": "当前范围无情报数据，无法形成判断。",
                "severity": "high",
                "related_evidence_ids": [],
            }],
            "recommended_tasks": recommended_tasks,
            "recommended_next_steps": recommended_tasks,
        }

    evidence = _make_evidence(items)
    evidence_by_item = {e["item_id"]: e["id"] for e in evidence}
    layer_items: dict[str, list] = defaultdict(list)
    country_items: dict[str, list] = defaultdict(list)
    source_counts: dict[str, int] = defaultdict(int)
    single_source_items: list = []
    low_conf_items: list = []

    for item in items:
        layer_items[item.layer.value].append(item)
        if item.country:
            country_items[item.country].append(item)
        for src in _source_names(item):
            if src:
                source_counts[src] += 1
        if len(_source_names(item)) <= 1:
            single_source_items.append(item)
        if item.confidence < 0.45:
            low_conf_items.append(item)

    judgments: list[dict] = []
    judgment_assessments: list[dict] = []
    top_layers = sorted(layer_items.items(), key=lambda kv: (-len(kv[1]), -LAYER_RISK_WEIGHTS.get(kv[0], 0.3)))[:3]
    for idx, (layer, group) in enumerate(top_layers):
        support = sorted(group, key=_item_score, reverse=True)[:4]
        avg_conf = sum(i.confidence for i in support) / max(len(support), 1)
        multi_source = sum(1 for i in support if len(_source_names(i)) >= 2)
        layer_label = LAYER_LABELS.get(layer, layer)
        evidence_ids = [evidence_by_item[i.id] for i in support if i.id in evidence_by_item]
        confidence = _confidence_assessment(support, evidence_ids)
        confidence_score = _confidence_score_from_level(confidence["level"], avg_conf)
        judgment_assessments.append(confidence)
        uncertainties: list[str] = []
        if multi_source == 0:
            uncertainties.append("主要证据仍是单源信息，需要独立来源确认。")
        if len(group) / total > 0.45:
            uncertainties.append("该主题占比过高，需排除采集源偏向造成的放大效应。")
        impact = "战略" if layer in {"military", "politics", "cyber", "energy"} else "行业"
        time_sensitivity = "立即" if layer in {"military", "cyber"} else "24h"
        judgments.append({
            "id": f"J{idx + 1}",
            "judgment": f"{layer_label}是当前范围内最突出的情报主题，覆盖 {len(group)} 条，占比 {len(group) / total:.0%}。",
            "confidence_level": confidence["level"],
            "confidence_score": round(confidence_score, 3),
            "impact": impact,
            "time_sensitivity": time_sensitivity,
            "support_count": len(group),
            "evidence_ids": evidence_ids,
            "uncertainties": uncertainties,
            "confidence_assessment": confidence,
        })

    if country_items:
        country, group = max(country_items.items(), key=lambda kv: len(kv[1]))
        support = sorted(group, key=_item_score, reverse=True)[:4]
        evidence_ids = [evidence_by_item[i.id] for i in support if i.id in evidence_by_item]
        high_impact_count = sum(1 for i in group if i.layer.value in HIGH_IMPACT_LAYERS)
        avg_conf = sum(i.confidence for i in support) / max(len(support), 1)
        confidence = _confidence_assessment(support, evidence_ids)
        confidence_score = _confidence_score_from_level(confidence["level"], avg_conf)
        judgment_assessments.append(confidence)
        judgments.append({
            "id": f"J{len(judgments) + 1}",
            "judgment": f"{country} 是当前最集中的地理焦点，关联 {len(group)} 条情报，其中 {high_impact_count} 条属于高敏感主题。",
            "confidence_level": confidence["level"],
            "confidence_score": round(confidence_score, 3),
            "impact": "区域",
            "time_sensitivity": "24h",
            "support_count": len(group),
            "evidence_ids": evidence_ids,
            "uncertainties": ["地理焦点可能反映来源覆盖偏向，不等同于真实风险排序。"],
            "confidence_assessment": confidence,
        })

    multi_source_count = total - len(single_source_items)
    if multi_source_count:
        support = [item for item in items if len(_source_names(item)) >= 2]
        evidence_ids = [e["id"] for e in evidence if e["independent_source_count"] >= 2][:5]
        avg_conf = sum(i.confidence for i in support) / max(len(support), 1)
        confidence = _confidence_assessment(support[:6], evidence_ids)
        confidence_score = _confidence_score_from_level(confidence["level"], avg_conf)
        judgment_assessments.append(confidence)
        judgments.append({
            "id": f"J{len(judgments) + 1}",
            "judgment": f"{multi_source_count} 条情报具备多源或合并来源支撑，可作为优先研判对象。",
            "confidence_level": confidence["level"],
            "confidence_score": round(confidence_score, 3),
            "impact": "战术",
            "time_sensitivity": "24h",
            "support_count": multi_source_count,
            "evidence_ids": evidence_ids,
            "uncertainties": [],
            "confidence_assessment": confidence,
        })

    contradictions: list[dict] = []
    single_source_pct = len(single_source_items) / total
    if single_source_pct > 0.35:
        related = [evidence_by_item[i.id] for i in single_source_items[:6] if i.id in evidence_by_item]
        contradictions.append({
            "description": f"{single_source_pct:.0%} 的情报仍是单源支撑，当前判断存在独立验证不足的问题。",
            "severity": "high" if single_source_pct > 0.6 else "medium",
            "related_evidence_ids": related,
        })
    if low_conf_items:
        related = [evidence_by_item[i.id] for i in low_conf_items[:6] if i.id in evidence_by_item]
        contradictions.append({
            "description": f"{len(low_conf_items)} 条情报置信度低于 45%，应在进入关键判断前复核原始来源。",
            "severity": "medium",
            "related_evidence_ids": related,
        })

    collection_gaps: list[dict] = []
    present_layers = set(layer_items)
    missing_layers = [layer for layer in requested_layers if layer and layer not in present_layers]
    if missing_layers:
        names = "、".join(LAYER_LABELS.get(layer, layer) for layer in missing_layers[:5])
        collection_gaps.append({
            "description": f"当前筛选范围缺少 {names} 图层数据。",
            "severity": "high",
            "related_evidence_ids": [],
        })
    if single_source_pct > 0.35:
        collection_gaps.append({
            "description": "多源验证覆盖不足，难以区分真实态势与单一信源叙事。",
            "severity": "high" if single_source_pct > 0.6 else "medium",
            "related_evidence_ids": [],
        })
    if source_counts:
        top_source, top_count = max(source_counts.items(), key=lambda kv: kv[1])
        if top_count / max(sum(source_counts.values()), 1) > 0.45:
            collection_gaps.append({
                "description": f"来源集中度偏高：{top_source} 贡献了 {top_count} 条来源记录。",
                "severity": "medium",
                "related_evidence_ids": [],
            })

    recommended_tasks: list[dict] = []
    if top_layers:
        layer, _ = top_layers[0]
        recommended_tasks.append({
            "priority": "高",
            "task": f"围绕{LAYER_LABELS.get(layer, layer)}主题补充独立来源",
            "rationale": "当前最突出主题需要通过不同来源类型验证，降低采集偏差。",
            "query": LAYER_LABELS.get(layer, layer),
        })
    if country_items:
        country, _ = max(country_items.items(), key=lambda kv: len(kv[1]))
        recommended_tasks.append({
            "priority": "中",
            "task": f"补充 {country} 本地或一手来源",
            "rationale": "地理焦点需要本地来源、官方来源或现场材料交叉确认。",
            "query": country,
        })
    if single_source_pct > 0.35:
        recommended_tasks.append({
            "priority": "高",
            "task": "优先复核单源高置信情报",
            "rationale": "单源高置信内容最容易被误当成已验证结论。",
            "query": "single-source verification",
        })

    source_count = len(source_counts)
    overall_confidence = _overall_confidence(judgment_assessments)

    confirmed_facts: list[dict] = [{
        "id": "F1",
        "statement": f"当前筛选范围内共收录 {total} 条情报，覆盖 {len(layer_items)} 个主题、{len(country_items)} 个国家/地区。",
        "confidence": _confidence_assessment(items[: min(total, 12)], [e["id"] for e in evidence[:8]]),
        "evidence_ids": [e["id"] for e in evidence[:8]],
        "note": "这是对本系统当前数据集的事实描述，不等同于外部事件已被确认。",
    }]
    if top_layers:
        layer, group = top_layers[0]
        support = sorted(group, key=_item_score, reverse=True)[:4]
        evidence_ids = [evidence_by_item[i.id] for i in support if i.id in evidence_by_item]
        confirmed_facts.append({
            "id": "F2",
            "statement": f"{LAYER_LABELS.get(layer, layer)}是当前样本中数量最高的主题，样本数为 {len(group)} 条。",
            "confidence": _confidence_assessment(support, evidence_ids),
            "evidence_ids": evidence_ids,
            "note": "这是样本分布事实，只说明关注度/采集量，不直接代表真实风险高低。",
        })
    if country_items:
        country, group = max(country_items.items(), key=lambda kv: len(kv[1]))
        support = sorted(group, key=_item_score, reverse=True)[:4]
        evidence_ids = [evidence_by_item[i.id] for i in support if i.id in evidence_by_item]
        confirmed_facts.append({
            "id": "F3",
            "statement": f"{country} 是当前样本中出现最多的地理焦点，关联 {len(group)} 条情报。",
            "confidence": _confidence_assessment(support, evidence_ids),
            "evidence_ids": evidence_ids,
            "note": "地理焦点来自现有样本归类，仍需与本地/一手来源交叉确认。",
        })

    core_findings: list[dict] = []
    assessments: list[dict] = []
    for idx, judgment in enumerate(judgments[:4], start=1):
        confidence = judgment["confidence_assessment"] or _overall_confidence([])
        core_findings.append({
            "id": f"CF{idx}",
            "finding": judgment["judgment"],
            "fact_basis": f"支撑样本 {judgment['support_count']} 条，证据编号：{', '.join(judgment['evidence_ids']) or '无'}。",
            "assessment": "该发现应作为研判入口，后续必须围绕证据链补充反证和独立来源。",
            "confidence": confidence,
            "evidence_ids": judgment["evidence_ids"],
            "implications": [
                f"影响类型：{judgment['impact']}",
                f"处置时效：{judgment['time_sensitivity']}",
            ],
        })
        assessments.append({
            "id": f"A{idx}",
            "statement": judgment["judgment"],
            "confidence": confidence,
            "evidence_ids": judgment["evidence_ids"],
            "note": "分析判断，需与确认事实分开使用。",
        })

    alternative_explanations: list[dict] = []
    if top_layers and len(top_layers[0][1]) / total > 0.45:
        layer, group = top_layers[0]
        support = sorted(group, key=_item_score, reverse=True)[:4]
        alternative_explanations.append({
            "id": "X1",
            "explanation": f"{LAYER_LABELS.get(layer, layer)}占比过高可能来自采集源偏向，而非真实态势单一化。",
            "indicators": ["单一主题样本占比超过 45%", "需检查来源覆盖和关键词规则"],
            "related_evidence_ids": [evidence_by_item[i.id] for i in support if i.id in evidence_by_item],
            "confidence_level": "L4",
        })
    if source_counts:
        top_source, top_count = max(source_counts.items(), key=lambda kv: kv[1])
        if top_count / max(sum(source_counts.values()), 1) > 0.45:
            alternative_explanations.append({
                "id": "X2",
                "explanation": f"当前态势可能被 {top_source} 的报道重点放大，需要引入不同地域和不同类型来源复核。",
                "indicators": [f"{top_source} 贡献 {top_count} 条来源记录", "来源集中度超过 45%"],
                "related_evidence_ids": [],
                "confidence_level": "L4",
            })
    if single_source_pct > 0.35:
        alternative_explanations.append({
            "id": "X3",
            "explanation": "部分判断可能只是单一信源叙事的重复扩散，尚不能视为独立事实。",
            "indicators": [f"单源占比 {single_source_pct:.0%}", "多源验证覆盖不足"],
            "related_evidence_ids": [evidence_by_item[i.id] for i in single_source_items[:6] if i.id in evidence_by_item],
            "confidence_level": "L4",
        })

    pending_verification: list[dict] = []
    for idx, gap in enumerate(collection_gaps[:4], start=1):
        pending_verification.append({
            "id": f"V{idx}",
            "question": gap["description"],
            "priority": "高" if gap["severity"] in {"critical", "high"} else "中",
            "rationale": "该缺口会直接影响判断可信度和可追溯性。",
            "related_evidence_ids": gap.get("related_evidence_ids", []),
        })
    for issue in contradictions[:2]:
        pending_verification.append({
            "id": f"V{len(pending_verification) + 1}",
            "question": issue["description"],
            "priority": "高" if issue["severity"] in {"critical", "high"} else "中",
            "rationale": "需要主动寻找反证，避免确认偏差。",
            "related_evidence_ids": issue.get("related_evidence_ids", []),
        })

    summary = (
        f"当前范围共有 {total} 条情报，覆盖 {len(layer_items)} 个主题、"
        f"{len(country_items)} 个国家/地区；多源支撑 {multi_source_count} 条，"
        f"单源占比 {single_source_pct:.0%}。整体情报等级为 "
        f"{overall_confidence['level']} {overall_confidence['label']}。"
    )

    return {
        "scope": scope,
        "summary": summary,
        "total_items": total,
        "intelligence_level": overall_confidence,
        "source_count": source_count,
        "core_findings": core_findings,
        "confirmed_facts": confirmed_facts,
        "assessments": assessments,
        "alternative_explanations": alternative_explanations,
        "pending_verification": pending_verification,
        "key_judgments": judgments[:6],
        "evidence": evidence,
        "contradictions": contradictions,
        "collection_gaps": collection_gaps,
        "recommended_tasks": recommended_tasks,
        "recommended_next_steps": recommended_tasks,
    }
