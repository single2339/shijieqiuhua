"""Dynamic factor registry (W2.6 — owns the real scoring rules).

Maps a (request, profile, evidence) triple to a list of FactorImpact entries
the prediction layer consumes. v1 ships 6 baseline factors that parse the
dongqiudi analysis excerpt for form/H2H direction signals:

- fixture.existence       — always enabled; the spine of every job
- form.recent_signal      — enabled iff fundamental.* evidence, scored from PPG
- squad.availability      — disabled until the user supplies lineup info
- uncertainty.youth_volatility — penalty applied only on U23/youth profiles
- h2h.relevance           — enabled iff fundamental.* evidence, scored from W-L
- weather.exposure        — enabled iff weather evidence present
"""
from __future__ import annotations

import re

from .models import FactorImpact, FootballOsintJobRequest, MatchProfile, OsintEvidence


def build_factors(
    request: FootballOsintJobRequest,
    profile: MatchProfile,
    evidence: list[OsintEvidence],
) -> list[FactorImpact]:
    fixture_evidence = [ev.id for ev in evidence if ev.topic.startswith("fixture.")]
    fundamental_evidence = [ev.id for ev in evidence if ev.topic.startswith("fundamental.")]
    weather_evidence = [ev.id for ev in evidence if ev.topic.startswith("weather.")]
    has_fundamental = bool(fundamental_evidence)
    has_weather = bool(weather_evidence)
    youth = "u23" in profile.competition_type

    # Parse the fundamental evidence text for form/H2H/squad/standings signals
    fundamental_text = "\n".join(ev.raw_excerpt for ev in evidence if ev.topic.startswith("fundamental."))
    form_score = _score_recent_form(fundamental_text, request)
    h2h_score = _score_h2h(fundamental_text, request)
    squad_score, has_sideline = _score_squad(fundamental_text, request)
    standings_score = _score_standings(fundamental_text, request)

    # Combine form + standings into a single form signal
    combined_form = form_score + standings_score
    combined_form = max(-0.18, min(0.18, combined_form))

    return [
        FactorImpact(
            factor_id="fixture.existence",
            label="比赛验证",
            group="fixture",
            enabled=True,
            weight=0.14,
            impact=0.0,
            direction="neutral",
            confidence=0.58,
            evidence_ids=fixture_evidence,
        ),
        FactorImpact(
            factor_id="form.recent_signal",
            label="近期状态信号",
            group="form",
            enabled=has_fundamental,
            weight=0.16 if (has_fundamental and not youth) else (0.12 if has_fundamental else 0.0),
            impact=combined_form,
            direction=_direction(combined_form),
            confidence=0.42 if has_fundamental else 0.0,
            evidence_ids=fundamental_evidence,
            missing_reason="" if has_fundamental else "未抓取到懂球帝赛前分析，无法形成近期状态信号",
        ),
        FactorImpact(
            factor_id="squad.availability",
            label="阵容可用性",
            group="squad",
            enabled=has_fundamental and has_sideline,
            weight=0.10 if (has_fundamental and has_sideline) else 0.0,
            impact=squad_score,
            direction=_direction(squad_score),
            confidence=0.35 if has_sideline else 0.0,
            evidence_ids=fundamental_evidence,
            missing_reason="" if has_sideline else "暂无伤病/缺席数据，阵容因子不启用",
        ),
        FactorImpact(
            factor_id="uncertainty.youth_volatility",
            label="青年赛事波动",
            group="uncertainty",
            enabled=youth,
            weight=0.20 if youth else 0.04,
            impact=-0.10 if youth else 0.0,
            direction="neutral",
            confidence=0.82 if youth else 0.0,
            evidence_ids=fixture_evidence,
            missing_reason="" if youth else "非青年赛事，青年波动因子不启用",
        ),
        FactorImpact(
            factor_id="h2h.relevance",
            label="历史交锋参考性",
            group="h2h",
            enabled=has_fundamental,
            weight=(0.05 if youth else 0.10) if has_fundamental else 0.0,
            impact=h2h_score,
            direction=_direction(h2h_score),
            confidence=0.25 if has_fundamental else 0.0,
            evidence_ids=fundamental_evidence,
            missing_reason="" if has_fundamental else "缺历史交锋证据，h2h 因子不启用",
        ),
        FactorImpact(
            factor_id="weather.exposure",
            label="天气影响",
            group="weather",
            enabled=has_weather,
            weight=0.08 if has_weather else 0.0,
            impact=0.03 if has_weather else 0.0,
            direction="neutral",
            confidence=0.45 if has_weather else 0.0,
            evidence_ids=weather_evidence,
            missing_reason="" if has_weather else "未获取比赛日天气数据，可从 Open-Meteo 自动补采",
        ),
    ]


# ── content scoring helpers ──

_FORM_RE = re.compile(r"([^\s]+)近期战绩[：:]\s*(\d+)胜(\d+)平(\d+)负")
_H2H_RE = re.compile(
    r"历史交锋[：:]\s*([^\s]+)\s*(\d+)胜(\d+)平(\d+)负[，,\s]*([^\s]+)\s*(\d+)胜(\d+)平(\d+)负"
)
_SIDELINE_RE = re.compile(r"伤停信息[：:]\s*([^\s]+)\s*(\d+)\s*人缺席[，,]\s*([^\s]+)\s*(\d+)\s*人缺席")
_STANDINGS_RE = re.compile(r"积分榜[：:]\s*(.+?)(?:，|；|$)")


def _score_recent_form(text: str, request: FootballOsintJobRequest) -> float:
    """Compare home vs away recent form PPG from the analysis excerpt.

    Returns a score in [-0.15, 0.15]: positive favours home.
    """
    home_name = request.home_team
    away_name = request.away_team
    records: dict[str, tuple[int, int, int]] = {}
    for m in _FORM_RE.finditer(text):
        name = m.group(1)
        w, d, l = int(m.group(2)), int(m.group(3)), int(m.group(4))
        records[name] = (w, d, l)

    home_rec = records.get(home_name)
    away_rec = records.get(away_name)
    if not home_rec or not away_rec:
        return 0.0

    games = sum(home_rec)
    if games == 0:
        return 0.0
    home_ppg = (home_rec[0] * 3 + home_rec[1]) / games
    away_games = sum(away_rec)
    away_ppg = (away_rec[0] * 3 + away_rec[1]) / away_games if away_games else 0.0

    # 1.0 PPG diff ≈ 0.10 impact, capped at ±0.15
    raw = (home_ppg - away_ppg) * 0.10
    return max(-0.15, min(0.15, round(raw, 3)))


def _score_h2h(text: str, request: FootballOsintJobRequest) -> float:
    """Extract H2H advantage from the analysis excerpt.

    Returns a score in [-0.12, 0.12]: positive favours home.
    """
    home_name = request.home_team
    away_name = request.away_team
    m = _H2H_RE.search(text)
    if not m:
        return 0.0

    name_a, wa, da, la = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    name_b, wb, db, lb = m.group(5), int(m.group(6)), int(m.group(7)), int(m.group(8))

    if home_name not in (name_a, name_b) or away_name not in (name_a, name_b):
        return 0.0

    if name_a == home_name:
        home_w, home_l = wa, la
    else:
        home_w, home_l = wb, lb

    total = home_w + home_l
    if total == 0:
        return 0.0
    advantage = (home_w - home_l) / total
    return max(-0.12, min(0.12, round(advantage * 0.12, 3)))


def _score_squad(text: str, request: FootballOsintJobRequest) -> tuple[float, bool]:
    """Compare absence counts: fewer absences = advantage.

    Returns (score, has_data). Score in [-0.10, 0.10].
    """
    m = _SIDELINE_RE.search(text)
    if not m:
        return 0.0, False

    name_a, abs_a = m.group(1), int(m.group(2))
    name_b, abs_b = m.group(3), int(m.group(4))
    home_name = request.home_team
    away_name = request.away_team

    if home_name not in (name_a, name_b) or away_name not in (name_a, name_b):
        return 0.0, True

    home_abs = abs_a if name_a == home_name else abs_b
    away_abs = abs_b if name_a == home_name else abs_a

    # Each extra absence → 0.03 impact, capped at ±0.10
    raw = (away_abs - home_abs) * 0.03
    return max(-0.10, min(0.10, round(raw, 3))), True


def _score_standings(text: str, request: FootballOsintJobRequest) -> float:
    """Compare standings rank: better rank → small advantage.

    Returns a score in [-0.06, 0.06].
    """
    home_name = request.home_team
    away_name = request.away_team

    def _find_rank(name: str) -> int | None:
        # Look for "{name} 第N名" in the text
        m = re.search(re.escape(name) + r"\s*第(\d+)名", text)
        return int(m.group(1)) if m else None

    home_rank = _find_rank(home_name)
    away_rank = _find_rank(away_name)
    if not home_rank or not away_rank:
        return 0.0

    # Lower rank number = better. Each rank diff → 0.015 impact, capped at ±0.06
    raw = (away_rank - home_rank) * 0.015
    return max(-0.06, min(0.06, round(raw, 3)))


def _direction(score: float) -> str:
    if score > 0.01:
        return "home"
    if score < -0.01:
        return "away"
    return "neutral"
