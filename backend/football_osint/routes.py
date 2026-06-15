from __future__ import annotations

import asyncio
import os
import threading
import time
from collections import OrderedDict


from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from .adapters import dongqiudi_schedule, football_data_schedule
from .models import FootballOsintAnswer, FootballOsintJob, FootballOsintJobRequest
from .pipeline import run_prediction_sync

router = APIRouter(prefix="/api/football/osint", tags=["football-osint"])

_ANSWER_CONCURRENCY = max(1, int(os.getenv("FOOTBALL_OSINT_ANSWER_CONCURRENCY", "4")))
_ANSWER_SEMAPHORE = asyncio.Semaphore(_ANSWER_CONCURRENCY)

_JOB_CACHE_MAX = max(64, int(os.getenv("FOOTBALL_OSINT_JOB_CACHE_MAX", "512")))
_JOB_CACHE_TTL = max(60, int(os.getenv("FOOTBALL_OSINT_JOB_CACHE_TTL", "3600")))


class _JobCache:
    """Bounded LRU + TTL cache for completed OSINT jobs.

    Keeps the in-memory store from growing unboundedly when the public
    endpoint is hit by many distinct match queries.
    """

    def __init__(self, max_size: int, ttl_seconds: int) -> None:
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, FootballOsintJob]] = OrderedDict()
        self._max = max_size
        self._ttl = ttl_seconds

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        with self._lock:
            self._evict_expired()
            return len(self._store)

    def get(self, key: str) -> FootballOsintJob | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, job = entry
            if time.time() - ts >= self._ttl:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return job

    def set(self, key: str, job: FootballOsintJob) -> None:
        with self._lock:
            self._evict_expired()
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (time.time(), job)
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts >= self._ttl]
        for k in expired:
            del self._store[k]


_JOBS = _JobCache(_JOB_CACHE_MAX, _JOB_CACHE_TTL)


@router.post("/predict-sync", response_model=FootballOsintJob)
async def predict_sync(request: FootballOsintJobRequest):
    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return job


@router.post("/jobs", response_model=FootballOsintJob)
async def create_job(request: FootballOsintJobRequest):
    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return job


@router.post("/answer", response_model=FootballOsintAnswer)
async def answer_question(request: FootballOsintJobRequest):
    if not _is_match_related(request):
        return FootballOsintAnswer(
            related=False,
            analysis_started=False,
            answer="问题与比赛无关",
            reasons=[],
        )

    async with _ANSWER_SEMAPHORE:
        job = await asyncio.to_thread(run_prediction_sync, request)
    _JOBS.set(job.job_id, job)
    return _answer_from_job(job, request.question)


@router.get("/fixtures")
async def list_fixtures(days: int = 3):
    fixtures = await asyncio.to_thread(football_data_schedule.fetch_fixtures, days)

    upcoming = football_data_schedule.upcoming(fixtures)
    return [
        {
            "id": f.match_id,
            "league": f.league,
            "kickoff_at": f.kickoff_at.astimezone(football_data_schedule.CST).strftime("%m-%d %H:%M"),
            "home_team": f.home_team,
            "away_team": f.away_team,
            "status": f.status,
            "home_score": f.home_score,
            "away_score": f.away_score,
        }
        for f in upcoming
    ]


@router.get("/jobs/{job_id}", response_model=FootballOsintJob)
async def get_job(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="football osint job not found")
    return job


@router.get("/jobs/{job_id}/report.md", response_class=PlainTextResponse)
async def get_report(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="football osint job not found")
    return job.report_markdown


def _is_match_related(request: FootballOsintJobRequest) -> bool:
    question = request.question.strip().lower()
    if not question:
        return True
    match_terms = [
        request.home_team,
        request.away_team,
        request.competition,
        "这场",
        "本场",
        "比赛",
        "球队",
        "主队",
        "客队",
        "胜",
        "平",
        "负",
        "进球",
        "角球",
        "红黄牌",
        "半场",
        "阵容",
        "伤停",
        "首发",
        "状态",
        "交锋",
        "赛程",
        
    ]
    return any(term and term.lower() in question for term in match_terms)


_LEAN_JUDGMENT: dict[str, str] = {
    "home": "主队占优",
    "away": "客队占优",
    "draw": "平局倾向",
    "home_or_draw": "主队不败",
    "away_or_draw": "客队不败",
    "info_insufficient": "信息不足",
}

# Question dimension → tailored answer template
# Principle: ALWAYS give a conclusion based on available data, state confidence
# level honestly (even when unreliable), explain what's missing and why.
_QUESTION_ANSWERS: dict[str, dict[str, str]] = {
    "half": {
        "keywords": ["半场", "上半", "下半", "上半场", "下半场"],
        "template": (
            "根据目前掌握的基本面数据，{form_hint}。"
            "综合来看半场主动权可能偏向{lean_dir}。\n\n"
            "⚠️ 本结论信心为 {confidence}，不是可靠判断。半场走势受临场首发、战术部署和开场节奏影响极大。"
            "建议关注开场前 15 分钟的攻守态势。"
        ),
    },
    "cards": {
        "keywords": ["红黄牌", "黄牌", "红牌", "牌", "犯规", "裁判"],
        "template": (
            "红黄牌风险目前缺少直接数据（裁判执法风格、两队纪律统计均未采集）。"
            "仅从比赛基本面推断：{form_hint}，整体对抗强度可能{intensity}。"
            "若比赛走势如预期，红黄牌数量可能{cards_lean}。\n\n"
            "⚠️ 本结论信心为 {confidence}，非常不可靠。红黄牌受临场情绪和裁判尺度影响极大，"
            "实际偏差可能很大。"
        ),
    },
    "corners": {
        "keywords": ["角球", "角"],
        "template": (
            "根据基本面数据估算：{corner_est}。"
            "{form_hint}，{lean_dir}进攻回合可能更多。\n\n"
            "⚠️ 本结论信心为 {confidence}。缺少控球率、传中频率等关键指标，"
            "实际角球数量偏差可能在 ±3 个以上。"
        ),
    },
    "goals": {
        "keywords": ["进球", "总进球", "进球数", "大球", "小球", "比分"],
        "template": (
            "根据近期状态数据估算：{goal_est}。"
            "{form_hint}。\n\n"
            "⚠️ 本结论信心为 {confidence}。进球数受临场阵容、天气、战术等多重因素影响，"
            "实际偏差可能在 ±1 球以上。"
        ),
    },
    "player": {
        "keywords": ["球员", "核心", "主力", "首发", "状态", "伤病", "缺席", "阵容"],
        "template": (
            "根据懂球帝公开伤停数据：{squad_hint}"
            "综合来看，阵容完整度方面{lean_dir}。\n\n"
            "⚠️ 本结论信心为 {confidence}。核心球员的真实状态和首发名单需临场公布后才能确认，"
            "赛前传闻和媒体报道不能作为可靠依据。"
        ),
    },
    "risk": {
        "keywords": ["风险", "临场", "变数", "不确定", "意外"],
        "template": (
            "当前临场风险主要来自以下方面：{uncertainties}。"
            "从基本面来看，{form_hint}，最大变数在于{top_uncertainty}。\n\n"
            "⚠️ 本结论信心为 {confidence}。建议在开赛前 2 小时关注官方首发名单和现场天气更新，"
            "这两个变量可能显著改变赛前判断。"
        ),
    },
}


def _answer_from_job(job: FootballOsintJob, question: str = "") -> FootballOsintAnswer:
    prediction = job.prediction
    confidence = job.confidence

    # ── osint-core analysis pipeline ──
    from .analysis import osint_qa

    analysis = osint_qa.analyze(job, question)

    if analysis.dimension:
        answer = analysis.answer
        judgment = analysis.confidence_level
        reasons = analysis.assessments[:2] + analysis.data_gaps[:1]
        if not reasons:
            reasons = analysis.confirmed_facts[:2]
    elif question:
        # ── no dimension match: try LLM ──
        match_ctx = f"{job.match.home_team} vs {job.match.away_team}，{job.match.competition or '未指定'}"
        ev_lines = []
        for ev in job.evidence[-10:]:
            ev_lines.append(f"[{ev.source}] {(ev.raw_excerpt or ev.claim)[:200]}")
        evidence_text = "\n".join(ev_lines) if ev_lines else "暂无有效证据"

        from .analysis import llm_qa
        llm_answer = llm_qa.answer_question(question, evidence_text, match_ctx)
        if llm_answer:
            answer = llm_answer
        else:
            answer = prediction.summary if prediction else "已完成基本面判断，但暂时没有形成明确倾向。"
        judgment = _LEAN_JUDGMENT.get(prediction.lean, "") if prediction else ""
        reasons = prediction.drivers[:2] if prediction else []
    else:
        answer = prediction.summary if prediction else "已完成基本面判断，但暂时没有形成明确倾向。"
        judgment = _LEAN_JUDGMENT.get(prediction.lean, "") if prediction else ""
        reasons = prediction.drivers[:2] if prediction else []

    return FootballOsintAnswer(
        related=True,
        analysis_started=True,
        answer=answer,
        judgment=judgment,
        reasons=reasons[:3],
        confidence_level=confidence.level if confidence else "L4",
    )


def _template_answer(match_dim: str, job: FootballOsintJob, prediction) -> str:
    """Build a template-based answer for a preset question dimension."""
    cfg = _QUESTION_ANSWERS[match_dim]
    conf = job.confidence
    confidence = f"{conf.level}（{conf.reason}）" if conf else "未知"

    form_factors = [f for f in job.factors if f.enabled and f.factor_id == "form.recent_signal"]
    form_impact = form_factors[0].impact if form_factors else 0.0
    if form_factors and abs(form_impact) > 0.005:
        form_dir = "主队" if form_impact > 0 else "客队"
        form_hint = f"{form_dir}近期状态更优"
    else:
        form_dir = "双方"
        form_hint = "两队近期状态差异不明显"

    squad_factors = [f for f in job.factors if f.enabled and f.factor_id == "squad.availability"]
    squad_impact = squad_factors[0].impact if squad_factors else 0.0
    if squad_factors and abs(squad_impact) > 0.005:
        squad_full = f"根据懂球帝伤停数据，{'主队阵容更完整' if squad_impact > 0 else '客队阵容更完整'}。"
    else:
        squad_full = "目前两队均无显著伤停差异。"

    home_lean = form_impact > 0 or squad_impact > 0
    lean_dir = "主队一方" if home_lean else ("客队一方" if (form_impact < 0 or squad_impact < 0) else "双方均势")

    uncertainties = "、".join(prediction.uncertainties[:2]) if prediction and prediction.uncertainties else "数据覆盖不足"
    top_uncertainty = (prediction.uncertainties[0] if prediction and prediction.uncertainties else "数据覆盖不足")

    intensity = "偏高" if form_impact > 0.02 else ("偏低" if form_impact < -0.02 else "中性")
    cards_lean = f"偏多（预估 4-6 张）" if intensity == "偏高" else (f"偏少（预估 2-4 张）" if intensity == "偏低" else "难以判断")

    # Estimate numbers from PPG data in the evidence
    goal_est, corner_est = _estimate_from_evidence(job, form_impact, home_lean)

    return cfg["template"].format(
        form_hint=form_hint,
        squad_hint=squad_full,
        uncertainties=uncertainties,
        top_uncertainty=top_uncertainty,
        lean_dir=lean_dir,
        confidence=confidence,
        intensity=intensity,
        cards_lean=cards_lean,
        corner_est=corner_est,
        goal_est=goal_est,
    )


def _estimate_from_evidence(job: FootballOsintJob, form_impact: float, home_lean: bool) -> tuple[str, str]:
    """Estimate goal and corner counts from PPG data in the evidence.

    Returns (goal_estimate, corner_estimate) as Chinese strings with numbers.
    """
    import re

    # Defaults when no data
    goal_est = "总进球预估 2-3 球"
    corner_est = "总角球预估 8-10 个"

    # Parse PPG from fundamental evidence
    ppg: dict[str, float] = {}
    _FORM_RE = re.compile(r"([^\s]+)近期战绩[：:]\s*(\d+)胜(\d+)平(\d+)负")
    for ev in job.evidence:
        if not ev.topic.startswith("fundamental."):
            continue
        for m in _FORM_RE.finditer(ev.raw_excerpt):
            name = m.group(1)
            w, d, l = int(m.group(2)), int(m.group(3)), int(m.group(4))
            games = w + d + l
            if games > 0:
                ppg[name] = (w * 3 + d) / games

    home_name = job.match.home_team
    away_name = job.match.away_team
    home_ppg = ppg.get(home_name, 0.0)
    away_ppg = ppg.get(away_name, 0.0)

    if home_ppg > 0 and away_ppg > 0:
        # Goals estimate: (home_ppg + away_ppg) / 2 * 1.2 ≈ expected goals per team
        # Typical range: 0.8–2.5 goals per team
        home_g = round((home_ppg / 3.0) * 2.5, 1)
        away_g = round((away_ppg / 3.0) * 2.5, 1)
        total_lo = max(1, int(home_g + away_g - 0.5))
        total_hi = min(6, int(home_g + away_g + 0.5))
        goal_est = f"总进球预估 {total_lo}-{total_hi} 球（{home_name} 约 {home_g} 球，{away_name} 约 {away_g} 球）"

        # Corners estimate: dominant team gets more
        if home_ppg > away_ppg:
            home_c, away_c = "5-7", "3-4"
        elif away_ppg > home_ppg:
            home_c, away_c = "3-4", "5-7"
        else:
            home_c, away_c = "4-5", "4-5"
        total_c_lo = int(home_c.split("-")[0]) + int(away_c.split("-")[0])
        total_c_hi = int(home_c.split("-")[1]) + int(away_c.split("-")[1])
        corner_est = f"总角球预估 {total_c_lo}-{total_c_hi} 个（{home_name} {home_c} 个，{away_name} {away_c} 个）"

    return goal_est, corner_est
