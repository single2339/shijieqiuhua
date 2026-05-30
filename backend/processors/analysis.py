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
    source_items: dict[str, set[str]] = defaultdict(set)

    for item in items:
        for src in item.sources:
            if src:
                source_items[src].add(item.id)

    top_sources = sorted(source_items.items(), key=lambda x: -len(x[1]))[:20]
    sources = [s for s, _ in top_sources]
    n = len(sources)

    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]
    pairs: list[dict] = []

    for i in range(n):
        for j in range(i + 1, n):
            sa, sb = sources[i], sources[j]
            set_a = source_items[sa]
            set_b = source_items[sb]
            shared = len(set_a & set_b)
            total = len(set_a) + len(set_b) - shared
            score = shared / max(total, 1)
            matrix[i][j] = round(score, 3)
            matrix[j][i] = round(score, 3)
            pairs.append({
                "source_a": sa,
                "source_b": sb,
                "shared_topics": shared,
                "total_a": len(set_a),
                "total_b": len(set_b),
                "agreement_score": round(score, 3),
            })

    for i in range(n):
        matrix[i][i] = 1.0

    pairs.sort(key=lambda x: -x["agreement_score"])
    return {"sources": sources, "matrix": matrix, "top_pairs": pairs[:30]}


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
