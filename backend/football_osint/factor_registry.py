"""Dynamic factor registry (W2.6 — owns the real scoring rules).

Maps a (request, profile, evidence) triple to a list of FactorImpact entries
the prediction layer consumes. v1 ships 5 baseline factors:

- fixture.existence       — always enabled; the spine of every job
- form.recent_signal      — enabled iff fundamental.* evidence is present
- squad.availability      — disabled until the user supplies lineup info
- uncertainty.youth_volatility — penalty applied only on U23/youth profiles
- h2h.relevance           — enabled iff fundamental.* evidence is present

PRD §5.2 (profile rules) + §4.5 (factor schema) + decision Q5 (full split).

W2.7 will add per-adapter factors (open_meteo → weather.exposure,
optional_odds → market.liquidity, etc) once the adapter package lands.
"""
from __future__ import annotations

from .models import FactorImpact, FootballOsintJobRequest, MatchProfile, OsintEvidence


def build_factors(
    request: FootballOsintJobRequest,
    profile: MatchProfile,
    evidence: list[OsintEvidence],
) -> list[FactorImpact]:
    fixture_evidence = [ev.id for ev in evidence if ev.topic.startswith("fixture.")]
    fundamental_evidence = [ev.id for ev in evidence if ev.topic.startswith("fundamental.")]
    has_fundamental = bool(fundamental_evidence)
    youth = "u23" in profile.competition_type

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
            impact=0.0,
            direction="neutral",
            confidence=0.42 if has_fundamental else 0.0,
            evidence_ids=fundamental_evidence,
            missing_reason="" if has_fundamental else "未抓取到 Win007/球探基本面，无法形成近期状态信号",
        ),
        FactorImpact(
            factor_id="squad.availability",
            label="阵容可用性",
            group="squad",
            enabled=False,
            weight=0.0,
            impact=0.0,
            direction="neutral",
            confidence=0.0,
            evidence_ids=[],
            missing_reason="未提供伤病或首发证据，阵容可用性因子不启用",
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
            impact=0.0,
            direction="neutral",
            confidence=0.25 if has_fundamental else 0.0,
            evidence_ids=fundamental_evidence,
            missing_reason="" if has_fundamental else "缺历史交锋证据，h2h 因子不启用",
        ),
    ]
