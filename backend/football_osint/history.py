"""v2 赛后回看 & 多场对比业务逻辑。

端点入口在 routes.py；本模块只做纯数据处理。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.auth.db import get_db
from backend.football_osint.models import FactorImpact, FootballOsintJob
from backend.football_osint.storage import DEFAULT_STORAGE_ROOT

log = logging.getLogger(__name__)

_HISTORY_DEFAULT_DAYS = 30
_HISTORY_MAX_ROWS = 50


# ── history list ──────────────────────────────────────────────────────────────

def get_history_list(*, days: int = _HISTORY_DEFAULT_DAYS) -> list[dict]:
    """已结束比赛列表（摘要字段）。已注册用户可见，访客不可访问。"""
    rows = get_db().execute(
        """
        SELECT job_id, home_team, away_team, kickoff_at, competition,
               predicted_lean, actual_home_score, actual_away_score,
               actual_outcome, lean_correct, scoreline_hit, settled_at
        FROM prediction_record
        WHERE settled_at IS NOT NULL
          AND settled_at >= datetime('now', ?)
        ORDER BY settled_at DESC
        LIMIT ?
        """,
        (f"-{days} days", _HISTORY_MAX_ROWS),
    ).fetchall()

    return [
        {
            "job_id": r["job_id"],
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "kickoff_at": r["kickoff_at"],
            "competition": r["competition"],
            "predicted_lean": r["predicted_lean"],
            "actual_home_score": r["actual_home_score"],
            "actual_away_score": r["actual_away_score"],
            "actual_outcome": r["actual_outcome"],
            "lean_correct": bool(r["lean_correct"]),
            "scoreline_hit": bool(r["scoreline_hit"]),
            "settled_at": r["settled_at"],
            # info_insufficient rows have predicted_lean='info_insufficient' but
            # only definite-lean rows are recorded (record_if_definite gate),
            # so this field is always one of home/away/draw here.
        }
        for r in rows
    ]


# ── history detail ─────────────────────────────────────────────────────────────

def get_history_detail(job_id: str, *, paid: bool) -> dict | None:
    """单场回顾。基础字段对已注册用户开放；factors + retrospective 需付费。

    返回 None 表示该 job_id 没有已结算的 prediction_record。
    """
    row = get_db().execute(
        """
        SELECT job_id, home_team, away_team, kickoff_at, competition,
               predicted_lean, predicted_scoreline_band,
               actual_home_score, actual_away_score, actual_outcome,
               lean_correct, scoreline_hit, settled_at
        FROM prediction_record
        WHERE job_id = ? AND settled_at IS NOT NULL
        """,
        (job_id,),
    ).fetchone()

    if row is None:
        return None

    result: dict[str, Any] = {
        "record": {
            "job_id": row["job_id"],
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "kickoff_at": row["kickoff_at"],
            "competition": row["competition"],
            "predicted_lean": row["predicted_lean"],
            "predicted_scoreline_band": json.loads(row["predicted_scoreline_band"] or "[]"),
            "actual_home_score": row["actual_home_score"],
            "actual_away_score": row["actual_away_score"],
            "actual_outcome": row["actual_outcome"],
            "lean_correct": bool(row["lean_correct"]),
            "scoreline_hit": bool(row["scoreline_hit"]),
            "settled_at": row["settled_at"],
        }
    }

    if not paid:
        return result

    # ── paid-only: factors + retrospective ──
    factors = _load_factors(job_id)
    if factors is None:
        result["factors_expired"] = True
    else:
        result["factors"] = [f.model_dump() for f in factors]
        result["retrospective"] = _build_retrospective(factors, row["actual_outcome"])

    return result


def _load_factors(job_id: str) -> list[FactorImpact] | None:
    """bronze_storage/{job_id}/status.json から因子を読む。失敗時は None（Q-v2-5 降級）。"""
    path = DEFAULT_STORAGE_ROOT / job_id / "status.json"
    if not path.exists():
        return None
    try:
        job = FootballOsintJob.model_validate_json(path.read_text(encoding="utf-8"))
        return job.factors or []
    except Exception:
        log.warning("history: failed to load factors from %s", path)
        return None


def _build_retrospective(factors: list[FactorImpact], actual_outcome: str) -> dict:
    """规则推导因子命中/偏差（Q-v2-3）。

    actual_outcome: 'home' | 'away' | 'draw'（来自 prediction_record）
    命中：enabled 因子的 direction == actual_outcome
    偏差：enabled 因子的 direction != actual_outcome 且 direction != 'neutral'
    neutral / disabled 因子不参与。
    """
    hit, miss = [], []
    for f in factors:
        if not f.enabled or f.direction == "neutral":
            continue
        if f.direction == actual_outcome:
            hit.append(f.label)
        else:
            miss.append(f.label)

    total = len(hit) + len(miss)
    note = (
        f"赛前 {total} 个有效因子中，{len(hit)} 个方向与实际结果吻合，{len(miss)} 个出现偏差。"
        if total
        else "该场比赛缺乏足够因子数据，无法做赛后对照。"
    )
    return {"hit_factors": hit, "miss_factors": miss, "note": note}


# ── compare ───────────────────────────────────────────────────────────────────

def compare_jobs(job_ids: list[str]) -> list[dict]:
    """多场对比摘要（最多 3 场）。从 warm_cache 内存或 bronze_storage 读取。"""
    from backend.football_osint import warm_cache

    results = []
    for jid in job_ids[:3]:
        job = warm_cache.get_cached_by_job_id(jid)
        if job is None:
            # 降级：从 bronze_storage 读
            path = DEFAULT_STORAGE_ROOT / jid / "status.json"
            if not path.exists():
                results.append({"job_id": jid, "error": "数据不可用"})
                continue
            try:
                job = FootballOsintJob.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                results.append({"job_id": jid, "error": "数据解析失败"})
                continue

        pred = job.prediction
        evidence = job.evidence or []
        factors = job.factors or []

        strong = sum(1 for e in evidence if e.confidence >= 0.50)
        weak = sum(1 for e in evidence if 0.25 <= e.confidence < 0.50)
        insufficient = sum(1 for e in evidence if e.confidence < 0.25)
        enabled_count = sum(1 for f in factors if f.enabled)

        results.append({
            "job_id": jid,
            "home_team": job.match.home_team,
            "away_team": job.match.away_team,
            "kickoff_at": job.match.kickoff_at,
            "competition": job.match.competition,
            "predicted_lean": pred.lean if pred else None,
            "confidence_level": job.confidence.level if job.confidence else None,
            "evidence_summary": {
                "strong": strong,
                "weak": weak,
                "insufficient": insufficient,
            },
            "top_uncertainties": (pred.uncertainties[:2] if pred else []),
            "factor_completeness": f"{enabled_count}/{len(factors)}" if factors else "0/0",
        })

    return results
