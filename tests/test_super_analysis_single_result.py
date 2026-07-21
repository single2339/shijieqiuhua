import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend import main
from backend.agents.intelligence.review_store import InvestigationReviewStore
from backend.models import InvestigationReviewRequest, SuperAnalysisRequest
from backend.processors import progress


class _FakeSuperAgent:
    async def run(self, _task):
        return SimpleNamespace(
            data={
                "question": "测试问题",
                "analysis": "超级分析结果。",
                "relevant_items": [],
                "web_results": [],
                "hypothesis_assessment": None,
                "collection_status": "complete",
                "provider_statuses": {"internal": "success"},
                "degraded": False,
                "analysis_status": "complete",
                "errors": [],
                "model": "configured-model",
            }
        )


@pytest.mark.asyncio
async def test_super_analysis_returns_single_result_without_review(monkeypatch):
    """The endpoint returns ONE analysis — no appended 'osint-core 复核' round."""
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_a, **_k: _FakeSuperAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_a, **_k: None)

    response = await main.intel_super_analysis(
        SuperAnalysisRequest(question="测试问题"),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 1},
    )

    assert response.analysis == "超级分析结果。"
    assert "osint-core 复核" not in response.analysis
    assert response.model == "configured-model"


def test_second_pass_reviewer_is_removed():
    """The osint-core second-pass reviewer is gone — single-result contract."""
    assert not hasattr(main, "_run_local_super_analysis_enhancement")


@pytest.mark.asyncio
async def test_super_analysis_preserves_client_request_id_and_owner(monkeypatch):
    captured_task = None

    class _CapturingAgent(_FakeSuperAgent):
        async def run(self, task):
            nonlocal captured_task
            captured_task = task
            return await super().run(task)

    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_a, **_k: _CapturingAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_a, **_k: None)

    response = await main.intel_super_analysis(
        SuperAnalysisRequest(question="测试问题", request_id="client-safe-id"),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 7},
    )

    assert response.request_id == "client-safe-id"
    assert captured_task.params["request_id"] == "client-safe-id"
    assert captured_task.params["owner_id"] == 7


@pytest.mark.asyncio
async def test_super_analysis_forwards_targeted_investigation_scope(monkeypatch):
    captured_task = None

    class _CapturingAgent(_FakeSuperAgent):
        async def run(self, task):
            nonlocal captured_task
            captured_task = task
            return await super().run(task)

    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_a, **_k: _CapturingAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_a, **_k: None)

    await main.intel_super_analysis(
        SuperAnalysisRequest(
            question="该网站与哪些实体有关？",
            investigation_type="website",
            target="example.com",
            verification_depth="deep",
        ),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 9},
    )

    assert captured_task.params["investigation_type"] == "website"
    assert captured_task.params["target"] == "example.com"
    assert captured_task.params["verification_depth"] == "deep"


@pytest.mark.asyncio
async def test_super_analysis_creates_owner_scoped_pending_review_case(monkeypatch, tmp_path):
    class _InvestigationAgent(_FakeSuperAgent):
        async def run(self, _task):
            result = await super().run(_task)
            result.data["investigation"] = {
                "playbook": "event",
                "scope": {"target": "示例事件"},
                "plan": {"playbook": "event", "target": "示例事件"},
            }
            return result

    store = InvestigationReviewStore(tmp_path / "reviews.db")
    monkeypatch.setattr(main, "_super_analysis_review_store", store, raising=False)
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_a, **_k: _InvestigationAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_a, **_k: None)

    response = await main.intel_super_analysis(
        SuperAnalysisRequest(question="示例事件是否影响运输？", request_id="review-case-001"),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 11},
    )

    assert response.investigation.analyst_review.status == "pending"
    assert store.get_review("review-case-001", owner_id=11).status == "pending"


@pytest.mark.asyncio
async def test_super_analysis_review_submission_is_owner_scoped(monkeypatch, tmp_path):
    store = InvestigationReviewStore(tmp_path / "reviews.db")
    store.create_case("review-case-002", owner_id=11, playbook="event")
    monkeypatch.setattr(main, "_super_analysis_review_store", store, raising=False)
    monkeypatch.setattr(main, "record_activity", lambda *_a, **_k: None)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))

    review = await main.submit_super_analysis_review(
        "review-case-002",
        InvestigationReviewRequest(status="needs_follow_up", notes="需补充原始来源"),
        request,
        {"id": 11},
    )

    assert review.status == "needs_follow_up"
    assert review.reviewer_id == 11
    assert review.notes == "需补充原始来源"

    with pytest.raises(HTTPException) as exc_info:
        await main.submit_super_analysis_review(
            "review-case-002",
            InvestigationReviewRequest(status="approved", notes="越权复核"),
            request,
            {"id": 12},
        )
    assert exc_info.value.status_code == 403


def test_progress_is_namespaced_by_owner():
    progress.init_progress("shared-public-id", owner_id=1)
    progress.init_progress("shared-public-id", owner_id=2)
    progress.set_progress("shared-public-id", "collecting", "owner one", 10, owner_id=1)
    progress.set_progress("shared-public-id", "analyzing", "owner two", 40, owner_id=2)

    assert progress.get_progress("shared-public-id", owner_id=1)["message"] == "owner one"
    assert progress.get_progress("shared-public-id", owner_id=2)["message"] == "owner two"
    assert progress.get_progress("missing-id", owner_id=1) is None


def test_progress_eviction_does_not_cross_owner_boundaries():
    progress._states.clear()
    progress.init_progress("victim-state", owner_id=1)
    for index in range(65):
        progress.init_progress(f"attacker-{index}", owner_id=2)

    assert progress.get_progress("victim-state", owner_id=1) is not None



def test_super_analysis_request_id_rejects_unsafe_values():
    with pytest.raises(ValidationError):
        SuperAnalysisRequest(question="测试", request_id="../shared")


def test_super_analysis_skills_reject_unapproved_names():
    with pytest.raises(ValidationError):
        SuperAnalysisRequest(
            question="测试",
            skills=["../../../.opencode/config"],
        )


def test_sensitive_investigation_requires_authorization_and_purpose():
    with pytest.raises(ValidationError):
        SuperAnalysisRequest(
            question="调查目标公开活动",
            investigation_type="person",
            target="示例目标",
            purpose="",
            authorized=False,
        )


def test_super_analysis_quota_is_per_user_and_windowed():
    main._super_analysis_rate_store.clear()

    assert all(main._consume_super_analysis_quota(7, now=100.0) for _ in range(5))
    assert main._consume_super_analysis_quota(7, now=100.0) is False
    assert main._consume_super_analysis_quota(8, now=100.0) is True
    assert main._consume_super_analysis_quota(7, now=161.0) is True



@pytest.mark.asyncio
async def test_super_analysis_rejects_second_inflight_request():
    main._super_analysis_rate_store.clear()
    main._super_analysis_inflight.add(77)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await main.intel_super_analysis(
                SuperAnalysisRequest(question="测试"),
                SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
                {"id": 77},
            )
    finally:
        main._super_analysis_inflight.discard(77)

    assert exc_info.value.status_code == 429

@pytest.mark.asyncio
async def test_cancelled_super_analysis_marks_progress_terminal(monkeypatch):
    class _BlockingAgent:
        async def run(self, _task):
            await asyncio.Event().wait()

    owner_id = 78
    request_id = "cancelled-request"
    main._super_analysis_rate_store.clear()
    main._super_analysis_inflight.discard(owner_id)
    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_a, **_k: _BlockingAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_a, **_k: None)

    task = asyncio.create_task(main.intel_super_analysis(
        SuperAnalysisRequest(question="测试", request_id=request_id),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": owner_id},
    ))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    state = progress.get_progress(request_id, owner_id)
    assert state is not None
    assert state["phase"] == "error"
    assert state["message"] == "分析已取消"
    assert owner_id not in main._super_analysis_inflight


def test_legacy_super_analysis_route_is_removed():
    paths = {route.path for route in main.app.routes}
    assert "/api/intel/super-analysis" in paths
    assert "/api/super-analysis" not in paths


@pytest.mark.asyncio
async def test_super_analysis_preserves_confidence_level_and_hypothesis_trace(monkeypatch):
    class _RichFakeAgent:
        model = "runtime-model"

        async def run(self, _task):
            return SimpleNamespace(data={
                "question": "测试问题",
                "analysis": "结构化分析",
                "relevant_items": [{
                    "title": "证据一",
                    "source": "reuters",
                    "date": "2026-07-16",
                    "layer": "trade",
                    "quality_score": 0.8,
                    "independent_source_count": 1,
                    "source_class": "high-credibility",
                    "content_snippet": "证据摘要",
                }],
                "web_results": [],
                "hypothesis_assessment": {
                    "hypothesis": "测试假设",
                    "prior_probability": 0.5,
                    "posterior_probability": 0.6,
                    "verdict": "uncertain",
                    "confidence_level": "L3",
                    "independent_source_count": 1,
                    "evidence": [{
                        "evidence_id": "I1",
                        "source": "reuters",
                        "relation": "support",
                        "strength": "weak",
                        "likelihood_ratio": 1.5,
                        "posterior_probability": 0.6,
                        "rationale": "有限支持",
                    }],
                },
                "collection_status": "complete",
                "provider_statuses": {"internal": "success"},
                "degraded": False,
                "analysis_status": "complete",
                "errors": [],
                "model": "runtime-model",
            })

    monkeypatch.setattr(main.AgentRegistry, "create", lambda *_a, **_k: _RichFakeAgent())
    monkeypatch.setattr(main, "record_activity", lambda *_a, **_k: None)

    response = await main.intel_super_analysis(
        SuperAnalysisRequest(question="测试问题"),
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
        {"id": 3},
    )

    assert response.hypothesis_assessment.confidence_level == "L3"
    assert response.relevant_items[0].independent_source_count == 1
    assert response.hypothesis_assessment.posterior_probability == 0.6
    assert response.model == "runtime-model"
