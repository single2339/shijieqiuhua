"""OSINT-core compliant Q&A pipeline.

For each question dimension, this module:
1. Extracts dimension-specific evidence from collected data
2. Rates confidence based on evidence quality for THIS question
3. Separates confirmed facts from assessments
4. Provides alternative explanations
5. Outputs osint-core format: 摘要→确认事实→推测→替代→缺口
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..models import FootballOsintJob

_DIMENSION_SPECS: dict[str, dict] = {
    "half": {
        "keywords": ["半场","上半","下半","上半场","下半场"],
        "needs": ["form_data", "h2h_data"],
        "nice_to_have": ["first_half_stats", "tactical_analysis"],
        "search_hints": ["半场表现","上半场进球","开局战术"],
    },
    "cards": {
        "keywords": ["红黄牌","黄牌","红牌","牌","犯规","裁判"],
        "needs": ["referee_data", "discipline_stats"],
        "nice_to_have": ["card_history", "match_importance"],
        "search_hints": ["场均犯规","黄牌统计","裁判执法风格"],
    },
    "corners": {
        "keywords": ["角球","角"],
        "needs": ["corner_stats", "possession_data", "cross_data"],
        "nice_to_have": ["tactical_analysis", "attack_style"],
        "search_hints": ["场均角球","角球数据","边路进攻","传中次数"],
    },
    "goals": {
        "keywords": ["进球","总进球","进球数","大球","小球","比分"],
        "needs": ["form_data", "goal_stats"],
        "nice_to_have": ["xG_data", "defense_record"],
        "search_hints": ["场均进球","进球数据","攻防统计"],
    },
    "player": {
        "keywords": ["球员","核心","主力","首发","状态","伤病","缺席","阵容"],
        "needs": ["squad_data", "injury_data"],
        "nice_to_have": ["lineup_prediction", "player_form"],
        "search_hints": ["伤病报告","首发预测","阵容新闻"],
    },
    "risk": {
        "keywords": ["风险","临场","变数","不确定","意外"],
        "needs": ["form_data", "squad_data", "weather_data"],
        "nice_to_have": ["latest_news", "pre_match_analysis"],
        "search_hints": ["赛前新闻","最新动态","临场变数"],
    },
}


@dataclass
class OsintAnalysis:
    dimension: str = ""
    confirmed_facts: list[str] = field(default_factory=list)
    assessments: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    confidence_level: str = "L4"
    confidence_reason: str = ""
    answer: str = ""


def analyze(job: FootballOsintJob, question: str, lean: str = "") -> OsintAnalysis:
    """Main entry point: osint-core analysis for a specific question."""
    dim = _match_dimension(question)
    spec = _DIMENSION_SPECS.get(dim, {})

    _LEAN_CN: dict[str, str] = {
        "home": "主队占优", "away": "客队占优", "draw": "平局倾向",
        "home_or_draw": "主队不败", "away_or_draw": "客队不败",
        "info_insufficient": "信息不足",
    }
    lean_cn = _LEAN_CN.get(lean, "")

    confirmed = _extract_confirmed_facts(job, dim, spec)
    assessments = _make_assessments(job, dim, confirmed, lean, lean_cn)
    alternatives = _find_alternatives(job, dim)
    gaps = _find_data_gaps(job, dim, spec)
    level, reason = _grade_dimension(job, dim, confirmed, gaps, spec)
    answer_text = _format_report(job, dim, confirmed, assessments, alternatives, gaps, level, reason, lean_cn)

    return OsintAnalysis(
        dimension=dim,
        confirmed_facts=confirmed,
        assessments=assessments,
        alternatives=alternatives,
        data_gaps=gaps,
        confidence_level=level,
        confidence_reason=reason,
        answer=answer_text,
    )


def _match_dimension(question: str) -> str:
    q = question.lower()
    # Check specific dimensions first (corners/cards/goals beat generic half/risk)
    priority = ["cards", "corners", "goals", "player", "risk", "half"]
    for dim_id in priority:
        spec = _DIMENSION_SPECS[dim_id]
        if any(kw in q for kw in spec["keywords"]):
            return dim_id
    return ""


def _extract_confirmed_facts(job: FootballOsintJob, dim: str, spec: dict) -> list[str]:
    """Pull confirmed facts from evidence relevant to this dimension."""
    facts: list[str] = []
    home_name = job.match.home_team
    away_name = job.match.away_team

    facts.append(f"比赛目标已确认：{home_name} vs {away_name}，{job.match.competition or '赛事未指定'}")

    for ev in job.evidence:
        if not ev.topic.startswith("fundamental."):
            continue
        text = ev.raw_excerpt

        for m in re.finditer(r"([^\s]+)近期战绩[：:]\s*(\d+)胜(\d+)平(\d+)负", text):
            name = m.group(1)
            w, d, l = int(m.group(2)), int(m.group(3)), int(m.group(4))
            games = w + d + l
            if name in (home_name, away_name) and games > 0:
                ppg = (w * 3 + d) / games
                facts.append(
                    f"确认事实：{name} 近{games}场 {w}W{d}D{l}L（PPG={ppg:.2f}）— 来源: 懂球帝 — L3"
                )

        h2h_m = re.search(
            r"历史交锋[：:]\s*([^\s]+)\s*(\d+)胜(\d+)平(\d+)负[，,\s]*([^\s]+)\s*(\d+)胜(\d+)平(\d+)负", text
        )
        if h2h_m:
            facts.append(
                f"确认事实：历史交锋 {h2h_m.group(1)}{h2h_m.group(2)}W{h2h_m.group(3)}D{h2h_m.group(4)}L "
                f"vs {h2h_m.group(5)}{h2h_m.group(6)}W{h2h_m.group(7)}D{h2h_m.group(8)}L — 来源: 懂球帝 — L3"
            )

        sideline_m = re.search(r"伤停信息[：:]\s*([^\s]+)\s*(\d+)\s*人缺席[，,]\s*([^\s]+)\s*(\d+)\s*人缺席", text)
        if sideline_m:
            facts.append(
                f"确认事实：{sideline_m.group(1)} {sideline_m.group(2)}人缺席，"
                f"{sideline_m.group(3)} {sideline_m.group(4)}人缺席 — 来源: 懂球帝 — L3"
            )

    # Extract dimension-specific data from search results
    hints = spec.get("search_hints", [])
    for ev in job.evidence:
        if not ev.topic.startswith("search."):
            continue
        snippet = (ev.raw_excerpt or ev.claim or "").lower()
        if not any(hint in snippet for hint in hints):
            continue
        nums = re.findall(r"(\d+\.?\d*)\s*(?:个|次|场|球|张|％|%)", snippet)
        if nums and ev.claim:
            facts.append(
                f"搜索发现：{ev.claim[:120]}（含数据: {', '.join(nums[:3])}）— 来源: DDG搜索 — L4（未交叉验证）"
            )
        elif ev.claim:
            facts.append(f"搜索发现：{ev.claim[:150]} — 来源: DDG搜索 — L4（未交叉验证）")
        if len([f for f in facts if "搜索发现" in f]) >= 3:
            break

    # Weather
    if dim == "risk" or "weather_data" in spec.get("needs", []):
        for ev in job.evidence:
            if ev.topic.startswith("weather."):
                facts.append(f"确认事实：{ev.claim} — 来源: Open-Meteo — L3")
                break

    return facts


def _make_assessments(job: FootballOsintJob, dim: str, confirmed: list[str], lean: str = "", lean_cn: str = "") -> list[str]:
    """Make assessments based on confirmed facts."""
    assessments: list[str] = []
    home_name = job.match.home_team
    away_name = job.match.away_team
    home_ppg = 0.0
    away_ppg = 0.0

    for fact in confirmed:
        m = re.search(rf"{re.escape(home_name)}.+?PPG=([\d.]+)", fact)
        if m:
            home_ppg = float(m.group(1))
        m = re.search(rf"{re.escape(away_name)}.+?PPG=([\d.]+)", fact)
        if m:
            away_ppg = float(m.group(1))

    # ── lean-aware "better" determination ──
    # Pipeline direction overrides raw PPG when the two disagree, so all
    # dimension predictions (goals, corners, cards, half) stay consistent.
    if lean in ("home", "home_or_draw"):
        better = home_name
    elif lean in ("away", "away_or_draw"):
        better = away_name
    elif lean == "draw":
        better = ""  # balanced — neither side favored
    else:
        better = home_name if home_ppg > away_ppg else away_name
    ppg_diff = abs(home_ppg - away_ppg)

    if dim == "half":
        if ppg_diff > 0.3:
            assessments.append(f"推测：{better}近期状态更优（PPG差={ppg_diff:.2f}），上半场可能占据主动。")
        else:
            assessments.append("推测：两队近期状态接近，上半场可能呈均势开局。")
        assessments.append("推测：开场前15分钟是判断上半场走势的关键窗口。")

    elif dim == "cards":
        if ppg_diff > 0.3:
            assessments.append(f"推测：{better}占优可能导致另一方防守压力增大，犯规和黄牌风险随之上升。")
        else:
            assessments.append("推测：均势比赛通常对抗更为激烈，红黄牌风险中性偏高。")
        assessments.append("推测：缺少当值裁判数据，裁判执法风格是最大未知变量。")

    elif dim == "corners":
        if home_ppg > 0 and away_ppg > 0:
            home_g = round((home_ppg / 3.0) * 2.5, 1)
            away_g = round((away_ppg / 3.0) * 2.5, 1)
            t_lo = max(1, int(home_g + away_g - 0.5))
            t_hi = min(6, int(home_g + away_g + 0.5))
            # lean-aware corner split (better is already lean-adjusted above)
            if better == home_name:
                hc, ac = ("5-7", "3-4")
            elif better == away_name:
                hc, ac = ("3-4", "5-7")
            else:
                hc, ac = ("4-5", "4-5")
            total_c = f"{int(hc.split('-')[0]) + int(ac.split('-')[0])}-{int(hc.split('-')[1]) + int(ac.split('-')[1])}"
            assessments.append(
                f"推测：基于近期状态，总进球预估 {t_lo}-{t_hi} 球（{home_name}约{home_g}球, {away_name}约{away_g}球），"
                f"总角球预估 {total_c} 个（{home_name} {hc}个, {away_name} {ac}个）。"
            )
        else:
            assessments.append("推测：数据不足，按一般规律给出基线判断——双方角球大致均势，总角球落在中性区间（约 8-10 个），本结论可靠性较低，仅供参考。")
        assessments.append("推测：缺少控球率和传中数据，角球估计偏差可能很大（±3个）。")

    elif dim == "goals":
        if home_ppg > 0 and away_ppg > 0:
            home_g = round((home_ppg / 3.0) * 2.5, 1)
            away_g = round((away_ppg / 3.0) * 2.5, 1)
            t_lo = max(1, int(home_g + away_g - 0.5))
            t_hi = min(6, int(home_g + away_g + 0.5))
            assessments.append(
                f"推测：基于双方近期PPG（{home_name}={home_ppg:.2f}, {away_name}={away_ppg:.2f}），"
                f"总进球预估 {t_lo}-{t_hi} 球。"
            )
        else:
            assessments.append("推测：数据不足，按一般规律给出基线判断——总进球大致落在 2-3 球的中性区间，本结论可靠性较低，仅供参考。")

    elif dim == "player":
        for fact in confirmed:
            if "人缺席" in fact:
                assessments.append(f"推测：根据伤停数据，{fact.split('—')[0].replace('确认事实：', '')}")
                break
        if not any("人缺席" in a for a in assessments):
            assessments.append("推测：目前两队均无显著伤停，阵容完整度接近。")

    elif dim == "risk":
        assessments.append("推测：最大不确定性来自赛前首发名单和现场天气。")
        if ppg_diff > 0.3:
            assessments.append(f"推测：若{better}首发完整，预期走势将符合PPG差距。")

    return assessments


def _find_alternatives(job: FootballOsintJob, dim: str) -> list[str]:
    """Alternative explanations that could overturn the assessment."""
    alternatives = ["若赛程或对阵信息有误，对战双方信息可能存在误差。"]

    if dim in ("half", "corners", "goals"):
        alternatives.append("临场首发大幅变动或主力缺阵可能彻底改变比赛节奏和进攻倾向。")
    if dim in ("cards",):
        alternatives.append("若当值裁判执法风格偏宽松，红黄牌数量可能远低于预估。")
    if dim in ("player",):
        alternatives.append("赛前伤病传闻可能不准确，球员可能带伤出战。")

    return alternatives[:3]


def _find_data_gaps(job: FootballOsintJob, dim: str, spec: dict) -> list[str]:
    """Identify data we're missing for this dimension — only unmet needs."""
    gap_desc = {
        "corner_stats": "缺少两队场均角球数据（需进阶统计源）",
        "possession_data": "缺少控球率和传球数据",
        "cross_data": "缺少传中次数和边路进攻比例",
        "referee_data": "缺少当值裁判历史执法数据",
        "discipline_stats": "缺少两队近期场均犯规和得牌统计",
        "goal_stats": "缺少两队场均进球/失球精确数据",
        "xG_data": "缺少预期进球（xG）等进阶数据",
        "injury_data": "缺少官方伤病详细报告",
        "lineup_prediction": "缺少可靠赛前首发预测",
        "first_half_stats": "缺少上半场 vs 下半场分时段数据",
        "tactical_analysis": "缺少详细战术分析报告",
        "attack_style": "缺少进攻方式分布（边路 vs 中路）",
    }

    # Check which needs are already covered by evidence
    satisfied = set()
    all_text = " ".join(ev.raw_excerpt.lower() for ev in job.evidence)

    form_covered = any("近期战绩" in ev.raw_excerpt for ev in job.evidence if ev.topic.startswith("fundamental."))
    if form_covered:
        satisfied.add("form_data")
    h2h_covered = any("历史交锋" in ev.raw_excerpt for ev in job.evidence if ev.topic.startswith("fundamental."))
    if h2h_covered:
        satisfied.add("h2h_data")
    if any("缺席" in ev.raw_excerpt for ev in job.evidence if ev.topic.startswith("fundamental.")):
        satisfied.add("squad_data")
        satisfied.add("injury_data")
    if any(ev.topic.startswith("weather.") for ev in job.evidence):
        satisfied.add("weather_data")

    gaps = []
    for need in spec.get("needs", []):
        if need not in satisfied:
            desc = gap_desc.get(need, f"缺少 {need}")
            gaps.append(desc)

    return gaps[:3]


def _grade_dimension(job: FootballOsintJob, dim: str, confirmed: list[str], gaps: list[str], spec: dict) -> tuple[str, str]:
    """Grade confidence for THIS dimension, not the whole job."""
    needs = spec.get("needs", [])
    n_needs = len(needs)
    covered = n_needs - len(gaps)
    coverage = covered / n_needs if n_needs > 0 else 0

    sources = set()
    for fact in confirmed:
        m = re.search(r"来源[：:]\s*([^—\s]+)", fact)
        if m:
            sources.add(m.group(1))
    n_sources = len(sources)

    if n_sources >= 3 and coverage >= 0.66:
        return "L1", f"≥3个独立来源，{covered}/{n_needs}类关键数据覆盖"
    elif n_sources >= 2 and coverage >= 0.33:
        return "L2", f"2个独立来源，{covered}/{n_needs}类关键数据可用"
    elif n_sources >= 1:
        return "L3", f"仅{covered}/{n_needs}类数据可用，{n_sources}个来源"
    else:
        return "L4", "仅有间接证据"


_DIM_NAMES = {
    "half": "半场主动权", "cards": "红黄牌风险", "corners": "角球趋势",
    "goals": "进球数", "player": "球员/阵容", "risk": "临场风险",
}


def _format_report(
    job: FootballOsintJob, dim: str,
    confirmed: list[str], assessments: list[str],
    alternatives: list[str], gaps: list[str],
    level: str, reason: str,
    lean_cn: str = "",
) -> str:
    """Format as osint-core report."""
    direction_line = f"方向研判: {lean_cn}" if lean_cn else ""
    lines = [
        f"情报摘要 — {_DIM_NAMES.get(dim, '综合')}",
        "━" * 32,
        f"目标: {job.match.home_team} vs {job.match.away_team}",
        f"赛事: {job.match.competition or '未指定'}",
        f"情报等级: {level} — {reason}",
    ]
    if direction_line:
        lines.append(direction_line)
    lines.extend([
        "",
        "确认事实:",
    ])
    for fact in confirmed[-6:]:
        lines.append(f"  • {fact}")
    lines.append("")
    lines.append("推测判断:")
    for a in assessments:
        lines.append(f"  • {a}")
    if alternatives:
        lines.append("")
        lines.append("替代解释（可能推翻结论）:")
        for a in alternatives:
            lines.append(f"  • {a}")
    if gaps:
        lines.append("")
        lines.append("数据缺口:")
        for g in gaps:
            lines.append(f"  • {g}")
    return "\n".join(lines)
