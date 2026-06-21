"""Dynamic factor registry (W2.6 — owns the real scoring rules).

Maps a (request, profile, evidence) triple to a list of FactorImpact entries
the prediction layer consumes. v1 ships 6 baseline factors that parse the
dongqiudi analysis excerpt for form/H2H direction signals:

- fixture.existence       — always enabled; the spine of every job
- form.recent_signal      — enabled iff LLM extraction or fundamental.* evidence yields form, scored from PPG
- squad.availability      — disabled until the user supplies lineup info
- uncertainty.youth_volatility — penalty applied only on U23/youth profiles
- h2h.relevance           — enabled iff LLM extraction or fundamental.* evidence yields H2H, scored from W-L
- weather.exposure        — enabled iff weather evidence present
"""
from __future__ import annotations

import json
import re

from .analysis import evidence_extraction
from .models import FactorImpact, FootballOsintJobRequest, MatchProfile, OsintEvidence


def build_factors(
    request: FootballOsintJobRequest,
    profile: MatchProfile,
    evidence: list[OsintEvidence],
) -> list[FactorImpact]:
    fixture_evidence = [ev.id for ev in evidence if ev.topic.startswith("fixture.")]
    fundamental_evidence = [ev.id for ev in evidence if ev.topic.startswith("fundamental.")]
    weather_score = 0.0
    for ev in evidence:
        if ev.topic == "weather.open_meteo" and ev.raw_excerpt:
            weather_score = _weather_score_from_raw_excerpt(ev.raw_excerpt)
            break
    weather_evidence = [ev.id for ev in evidence if ev.topic.startswith("weather.")]
    has_fundamental = bool(fundamental_evidence)
    has_weather = bool(weather_evidence)
    youth = "u23" in profile.competition_type

    fundamental_text = "\n".join(ev.raw_excerpt for ev in evidence if ev.topic.startswith("fundamental."))

    # Chinese search + RSS evidence: enriches form scoring when dongqiudi is sparse,
    # and feeds the media.cn_coverage factor below regardless of which path wins.
    cn_evidence = [ev for ev in evidence if (
        ev.topic.startswith("search.cn.")
        or ev.topic.startswith("news.rss.hupu.")
        or ev.topic.startswith("news.rss.dongqiudi.")
        or ev.topic.startswith("news.rss.weibo.")
    )]

    extracted = evidence_extraction.extract(evidence, request)

    if extracted is not None:
        form_score = _form_score_from_records(extracted.home_form, extracted.away_form)
        h2h_score = _h2h_score_from_counts(extracted.h2h_home_wins, extracted.h2h_home_losses)
        has_sideline = extracted.home_absences is not None and extracted.away_absences is not None
        squad_score = _squad_score_from_absences(extracted.home_absences, extracted.away_absences)
        standings_score = _standings_score_from_ranks(extracted.home_rank, extracted.away_rank)
        combined_form = max(-0.18, min(0.18, form_score + standings_score))

        has_form_signal = extracted.home_form is not None and extracted.away_form is not None
        has_h2h = extracted.h2h_home_wins is not None and extracted.h2h_home_losses is not None
        form_evidence_ids = fundamental_evidence + [ev.id for ev in cn_evidence]
        form_weight = (0.12 if youth else 0.16) if has_form_signal else 0.0
        form_confidence = 0.42 if has_form_signal else 0.0
        form_missing_reason = "" if has_form_signal else "LLM 未能从多源证据中抽取近期战绩，无法形成近期状态信号"
        h2h_enabled = has_h2h
        h2h_weight = ((0.05 if youth else 0.10) if has_h2h else 0.0)
        h2h_confidence = 0.25 if has_h2h else 0.0
        h2h_missing_reason = "" if has_h2h else "LLM 未能从多源证据中抽取历史交锋数据，h2h 因子不启用"
        squad_enabled = has_sideline
        squad_weight = 0.10 if has_sideline else 0.0
        squad_confidence = 0.35 if has_sideline else 0.0
        squad_missing_reason = "" if has_sideline else "LLM 未能从多源证据中抽取伤停/缺席数据，阵容因子不启用"
    else:
        cn_text = "\n".join(ev.raw_excerpt for ev in cn_evidence)
        cn_form_score = _score_cn_form(cn_text, request)

        form_score = _score_recent_form(fundamental_text, request)
        h2h_score = _score_h2h(fundamental_text, request)
        squad_score, has_sideline = _score_squad(fundamental_text, request)
        standings_score = _score_standings(fundamental_text, request)
        combined_form = max(-0.18, min(0.18, form_score + standings_score + cn_form_score))

        has_cn_form = cn_form_score != 0.0
        has_form_signal = has_fundamental or has_cn_form
        form_evidence_ids = fundamental_evidence + ([ev.id for ev in cn_evidence] if cn_evidence else [])
        form_weight = (0.12 if youth else 0.16) if has_fundamental else (0.08 if has_cn_form else 0.0)
        form_confidence = 0.42 if has_fundamental else (0.22 if has_cn_form else 0.0)
        form_missing_reason = "" if has_form_signal else "未抓取到懂球帝赛前分析或国内媒体近期战绩，无法形成近期状态信号"
        h2h_enabled = has_fundamental
        h2h_weight = (0.05 if youth else 0.10) if has_fundamental else 0.0
        h2h_confidence = 0.25 if has_fundamental else 0.0
        h2h_missing_reason = "" if has_fundamental else "缺历史交锋证据，h2h 因子不启用"
        squad_enabled = has_fundamental and has_sideline
        squad_weight = 0.10 if squad_enabled else 0.0
        squad_confidence = 0.35 if has_sideline else 0.0
        squad_missing_reason = "" if has_sideline else "暂无伤病/缺席数据，阵容因子不启用"

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
            enabled=has_form_signal,
            weight=form_weight,
            impact=combined_form,
            direction=_direction(combined_form),
            confidence=form_confidence,
            evidence_ids=form_evidence_ids,
            missing_reason=form_missing_reason,
        ),
        FactorImpact(
            factor_id="squad.availability",
            label="阵容可用性",
            group="squad",
            enabled=squad_enabled,
            weight=squad_weight,
            impact=squad_score,
            direction=_direction(squad_score),
            confidence=squad_confidence,
            evidence_ids=fundamental_evidence,
            missing_reason=squad_missing_reason,
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
            enabled=h2h_enabled,
            weight=h2h_weight,
            impact=h2h_score,
            direction=_direction(h2h_score),
            confidence=h2h_confidence,
            evidence_ids=fundamental_evidence,
            missing_reason=h2h_missing_reason,
        ),
        FactorImpact(
            factor_id="weather.exposure",
            label="天气影响",
            group="weather",
            enabled=has_weather,
            weight=0.08 if has_weather else 0.0,
            impact=weather_score,
            direction="neutral",
            confidence=0.45 if has_weather else 0.0,
            evidence_ids=weather_evidence,
            missing_reason="" if has_weather else "未获取比赛日天气数据，可从 Open-Meteo 自动补采",
        ),
        FactorImpact(
            factor_id="media.cn_coverage",
            label="国内媒体报道覆盖",
            group="media",
            enabled=len(cn_evidence) >= 3,
            weight=0.06 if len(cn_evidence) >= 3 else 0.0,
            impact=0.0,
            direction="neutral",
            confidence=0.30 if cn_evidence else 0.0,
            evidence_ids=[ev.id for ev in cn_evidence],
            missing_reason="" if cn_evidence else "未抓取到国内媒体报道，中文覆盖因子不启用",
        ),
    ]


# ── content scoring helpers ──

_FORM_RE = re.compile(r"([^\s]+)近期战绩[：:]\s*(\d+)胜(\d+)平(\d+)负")
_H2H_RE = re.compile(
    r"历史交锋[：:]\s*([^\s]+)\s*(\d+)胜(\d+)平(\d+)负[，,\s]*([^\s]+)\s*(\d+)胜(\d+)平(\d+)负"
)
_SIDELINE_RE = re.compile(r"伤停信息[：:]\s*([^\s]+)\s*(\d+)\s*人缺席[，,]\s*([^\s]+)\s*(\d+)\s*人缺席")
_STANDINGS_RE = re.compile(r"积分榜[：:]\s*(.+?)(?:，|；|$)")

# Chinese media form patterns — matches snippets like "巴西近5场3胜1平1负"
_CN_FORM_RE = re.compile(r"([一-鿿\w]+?)(?:近期|最近|近)\d*场[：:\s]*(\d+)胜(\d+)平(\d+)负")


def _form_score_from_records(
    home_rec: tuple[int, int, int] | None,
    away_rec: tuple[int, int, int] | None,
) -> float:
    """Compare home vs away recent form PPG. Positive favours home.

    Pure arithmetic, no parsing — shared by the regex path (_score_recent_form)
    and the LLM extraction path in build_factors.
    """
    if not home_rec or not away_rec:
        return 0.0
    games = sum(home_rec)
    if games == 0:
        return 0.0
    home_ppg = (home_rec[0] * 3 + home_rec[1]) / games
    away_games = sum(away_rec)
    away_ppg = (away_rec[0] * 3 + away_rec[1]) / away_games if away_games else 0.0
    raw = (home_ppg - away_ppg) * 0.10
    return max(-0.15, min(0.15, round(raw, 3)))


def _score_recent_form(text: str, request: FootballOsintJobRequest) -> float:
    """Parse '{name}近期战绩：W胜D平L负' from dongqiudi text, then score it."""
    home_name = request.home_team
    away_name = request.away_team
    records: dict[str, tuple[int, int, int]] = {}
    for m in _FORM_RE.finditer(text):
        name = m.group(1)
        w, d, l = int(m.group(2)), int(m.group(3)), int(m.group(4))
        records[name] = (w, d, l)
    return _form_score_from_records(records.get(home_name), records.get(away_name))


def _h2h_score_from_counts(home_wins: int | None, home_losses: int | None) -> float:
    """Compare H2H win/loss counts for the home side. Positive favours home."""
    if home_wins is None or home_losses is None:
        return 0.0
    total = home_wins + home_losses
    if total == 0:
        return 0.0
    advantage = (home_wins - home_losses) / total
    return max(-0.12, min(0.12, round(advantage * 0.12, 3)))


def _score_h2h(text: str, request: FootballOsintJobRequest) -> float:
    """Parse '历史交锋：A W胜D平L负，B W胜D平L负' from dongqiudi text, then score it."""
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
    return _h2h_score_from_counts(home_w, home_l)


def _squad_score_from_absences(home_abs: int | None, away_abs: int | None) -> float:
    """Compare absence counts: fewer absences = advantage. Positive favours home."""
    if home_abs is None or away_abs is None:
        return 0.0
    raw = (away_abs - home_abs) * 0.03
    return max(-0.10, min(0.10, round(raw, 3)))


def _score_squad(text: str, request: FootballOsintJobRequest) -> tuple[float, bool]:
    """Parse '伤停信息：A N人缺席，B M人缺席' from dongqiudi text, then score it."""
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
    return _squad_score_from_absences(home_abs, away_abs), True


def _standings_score_from_ranks(home_rank: int | None, away_rank: int | None) -> float:
    """Compare standings rank: lower number (better rank) = advantage. Positive favours home."""
    if not home_rank or not away_rank:
        return 0.0
    raw = (away_rank - home_rank) * 0.015
    return max(-0.06, min(0.06, round(raw, 3)))


def _score_standings(text: str, request: FootballOsintJobRequest) -> float:
    """Parse '{name} 第N名' from dongqiudi text, then score it."""
    home_name = request.home_team
    away_name = request.away_team

    def _find_rank(name: str) -> int | None:
        m = re.search(re.escape(name) + r"\s*第(\d+)名", text)
        return int(m.group(1)) if m else None

    return _standings_score_from_ranks(_find_rank(home_name), _find_rank(away_name))


def _score_cn_form(text: str, request: FootballOsintJobRequest) -> float:
    """Extract form signal from Chinese media search snippets.

    Weaker than dongqiudi structured data (snippets are shorter and less
    reliable), so the impact is capped at ±0.06 — half of _score_recent_form.
    """
    home_name = request.home_team
    away_name = request.away_team
    records: dict[str, tuple[int, int, int]] = {}
    for m in _CN_FORM_RE.finditer(text):
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

    raw = (home_ppg - away_ppg) * 0.06
    return max(-0.06, min(0.06, round(raw, 3)))


def _weather_score_from_raw_excerpt(raw_excerpt: str) -> float:
    """Score weather exposure from Open-Meteo's raw JSON response.

    Heavy rain or high wind makes the match harder to predict and tends to
    suppress scoring/tempo — small negative, neutral direction (it affects
    both sides, not home vs away). Calm weather → 0.0 (no signal either way).
    Capped at [-0.05, 0.0]: this factor nudges confidence, it doesn't pick a
    winner.
    """
    try:
        data = json.loads(raw_excerpt)
        daily = data.get("daily") or {}
        precip = (daily.get("precipitation_probability_max") or [None])[0]
        wind = (daily.get("wind_speed_10m_max") or [None])[0]

        if precip is None and wind is None:
            return 0.0

        penalty = 0.0
        if precip is not None and precip >= 70:
            penalty -= 0.03
        if wind is not None and wind >= 30:
            penalty -= 0.02
        return round(penalty, 3)
    except Exception:
        return 0.0


def _direction(score: float) -> str:
    if score > 0.01:
        return "home"
    if score < -0.01:
        return "away"
    return "neutral"
