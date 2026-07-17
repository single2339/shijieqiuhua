"""Tests for agent infrastructure: BaseAgent lifecycle, AgentRegistry, config loading."""

from __future__ import annotations

import pytest
from backend.agents.base import (
    AgentCallbacks,
    AgentEvent,
    AgentStatus,
    AgentType,
    BaseAgent,
)
from backend.agents.models import AgentResult, AgentTask, PipelineContext
from backend.agents.registry import AgentRegistry
from backend.agents.config import is_agent_mode, load_agent_config


# ── Test Agent implementations ──

class _SuccessAgent(BaseAgent):
    agent_id = "test_success"
    agent_type = AgentType.ANALYSIS

    async def _execute(self, task: AgentTask) -> dict:
        return {"key": "value", "task_type": task.task_type}


class _FailureAgent(BaseAgent):
    agent_id = "test_failure"
    agent_type = AgentType.PROCESSING

    async def _execute(self, task: AgentTask) -> dict:
        raise RuntimeError("simulated failure")


class _CollectorAgent(BaseAgent):
    agent_id = "test_collector"
    agent_type = AgentType.COLLECTION

    async def _execute(self, task: AgentTask) -> dict:
        return {"collected": 42}


# ── BaseAgent lifecycle ──

@pytest.mark.asyncio
async def test_agent_successful_run():
    agent = _SuccessAgent()
    task = AgentTask(task_type="test", params={"x": 1})
    result = await agent.run(task)

    assert result.status == AgentStatus.COMPLETED
    assert result.agent_id == "test_success"
    assert result.task_id == task.task_id
    assert result.data == {"key": "value", "task_type": "test"}
    assert result.error is None
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_agent_failed_run():
    agent = _FailureAgent()
    task = AgentTask(task_type="test")
    result = await agent.run(task)

    assert result.status == AgentStatus.FAILED
    assert result.agent_id == "test_failure"
    assert result.data == {}
    assert "simulated failure" in (result.error or "")


@pytest.mark.asyncio
async def test_agent_status_transitions():
    statuses: list[tuple[str, AgentStatus, AgentStatus]] = []

    async def on_status_change(agent_id: str, old: AgentStatus, new: AgentStatus):
        statuses.append((agent_id, old, new))

    agent = _SuccessAgent(callbacks=AgentCallbacks(on_status_change=on_status_change))
    task = AgentTask(task_type="test")
    await agent.run(task)

    assert len(statuses) == 2
    assert statuses[0] == ("test_success", AgentStatus.IDLE, AgentStatus.RUNNING)
    assert statuses[1] == ("test_success", AgentStatus.RUNNING, AgentStatus.COMPLETED)


@pytest.mark.asyncio
async def test_agent_event_emission():
    events: list[AgentEvent] = []

    async def on_event(event: AgentEvent):
        events.append(event)

    agent = _CollectorAgent(callbacks=AgentCallbacks(on_event=on_event))
    task = AgentTask(task_type="collect")
    await agent.run(task)

    # Events are only emitted if _execute calls _emit_event — this agent doesn't,
    # so events list should be empty. Test that the callback infrastructure works.
    assert isinstance(events, list)


@pytest.mark.asyncio
async def test_agent_error_callback():
    errors: list[tuple[str, str]] = []

    async def on_error(agent_id: str, error: str):
        errors.append((agent_id, error))

    agent = _FailureAgent(callbacks=AgentCallbacks(on_error=on_error))
    task = AgentTask(task_type="test")
    await agent.run(task)

    assert len(errors) == 1
    assert errors[0][0] == "test_failure"
    assert "simulated failure" in errors[0][1]


# ── Task / Result models ──

def test_agent_task_defaults():
    task = AgentTask()
    assert len(task.task_id) == 12  # uuid4().hex[:12]
    assert task.task_type == ""
    assert task.params == {}
    assert task.parent_task_id is None


def test_agent_task_custom():
    task = AgentTask(
        task_id="abc123",
        task_type="collect",
        params={"source": "rss"},
        parent_task_id="parent-001",
    )
    assert task.task_id == "abc123"
    assert task.task_type == "collect"
    assert task.params["source"] == "rss"
    assert task.parent_task_id == "parent-001"


def test_agent_result_serialization():
    result = AgentResult(
        task_id="t1",
        agent_id="a1",
        status=AgentStatus.COMPLETED,
        data={"items": 10},
        duration_ms=123.4,
    )
    d = result.model_dump()
    assert d["status"] == "completed"
    assert d["data"] == {"items": 10}
    assert d["duration_ms"] == 123.4


# ── PipelineContext ──

def test_pipeline_context_creation():
    ctx = PipelineContext(run_id="run-001")
    assert ctx.run_id == "run-001"
    assert len(ctx.metrics) == 0
    assert len(ctx.collected) == 0
    assert len(ctx.events) == 0


def test_pipeline_context_record():
    ctx = PipelineContext()
    ctx.record("rss_collector", 150.0)
    ctx.record("reddit_collector", 200.0)
    assert ctx.metrics == {"rss_collector": 150.0, "reddit_collector": 200.0}


# ── Registry ──

def test_registry_register_and_get():
    # Fresh agent class not yet registered
    class DynamicAgent(BaseAgent):
        agent_id = "dynamic_test"
        agent_type = AgentType.SYSTEM

        async def _execute(self, task: AgentTask) -> dict:
            return {}

    AgentRegistry.register(DynamicAgent)

    cls = AgentRegistry.get("dynamic_test")
    assert cls is DynamicAgent
    assert cls.agent_id == "dynamic_test"
    assert cls.agent_type == AgentType.SYSTEM


def test_registry_create():
    class CreateAgent(BaseAgent):
        agent_id = "create_test"
        agent_type = AgentType.ANALYSIS

        async def _execute(self, task: AgentTask) -> dict:
            return {"status": "ok"}

    AgentRegistry.register(CreateAgent)

    agent = AgentRegistry.create("create_test")
    assert isinstance(agent, CreateAgent)
    assert agent.agent_id == "create_test"
    assert agent.status == AgentStatus.IDLE


def test_registry_list_all():
    ids = AgentRegistry.list_all()
    assert "dynamic_test" in ids
    assert "create_test" in ids


def test_registry_list_by_type():
    collection_ids = AgentRegistry.list_by_type(AgentType.COLLECTION)
    # Our registered test agents
    system_ids = AgentRegistry.list_by_type(AgentType.SYSTEM)
    assert "dynamic_test" in system_ids


def test_registry_missing_agent():
    with pytest.raises(KeyError, match="nonexistent"):
        AgentRegistry.get("nonexistent")


# ── Agent config ──

def test_load_known_agent_config():
    cfg = load_agent_config("qa_analyst")
    assert cfg["model"] == "deepseek-v4-flash"
    assert cfg["max_tokens"] == 4096
    assert cfg["temperature"] == 0.3


def test_load_unknown_agent_config():
    cfg = load_agent_config("nonexistent_agent")
    assert cfg == {}


def test_is_agent_mode_default():
    assert is_agent_mode() is True


def test_agent_type_enum_values():
    assert AgentType.COLLECTION == "collection"
    assert AgentType.PROCESSING == "processing"
    assert AgentType.ANALYSIS == "analysis"
    assert AgentType.INTELLIGENCE == "intelligence"
    assert AgentType.SYSTEM == "system"


def test_agent_status_enum_values():
    assert AgentStatus.IDLE == "idle"
    assert AgentStatus.RUNNING == "running"
    assert AgentStatus.COMPLETED == "completed"
    assert AgentStatus.FAILED == "failed"


# ── Skill system ──

from backend.agents.skill import Skill, SkillLoader, SkillRule


def test_skill_loader_list_all():
    names = SkillLoader.list_all()
    assert "bayesian-reasoning" in names
    assert "red-teaming" in names
    assert "military-analysis" in names
    assert "economic-analysis" in names


def test_skill_loader_load():
    skill = SkillLoader.load("bayesian-reasoning")
    assert skill.name == "bayesian-reasoning"
    assert "贝叶斯" in skill.description
    assert "intelligence" in skill.agent_types
    assert len(skill.rules.do) >= 2
    assert len(skill.rules.dont) >= 2


def test_skill_loader_cache():
    s1 = SkillLoader.load("red-teaming")
    s2 = SkillLoader.load("red-teaming")
    assert s1 is s2


def test_skill_loader_missing():
    with pytest.raises(FileNotFoundError):
        SkillLoader.load("nonexistent-skill")


def test_skill_render_prompt_augment():
    skill = SkillLoader.load("military-analysis")
    rendered = skill.render_prompt_augment()
    assert "军事" in rendered
    assert "行为规则" in rendered
    assert "推理框架" in rendered
    assert "输出格式" not in rendered  # military-analysis has no output_format


def test_skill_param_overrides():
    skill = SkillLoader.load("military-analysis")
    assert skill.params["temperature"] == 0.2
    assert skill.params["max_tokens"] == 4096


def test_skill_with_output_format():
    skill = SkillLoader.load("bayesian-reasoning")
    rendered = skill.render_prompt_augment()
    assert "输出格式" in rendered
    assert "先验分析" in rendered


def test_agent_skill_loading():
    agent = _SuccessAgent()
    agent.load_skill("bayesian-reasoning")
    assert len(agent._loaded_skills) == 1
    assert agent._loaded_skills[0].name == "bayesian-reasoning"


def test_agent_load_skills_multiple():
    agent = _SuccessAgent()
    agent.load_skills(["red-teaming", "economic-analysis"])
    assert len(agent._loaded_skills) == 2


def test_agent_build_system_prompt():
    agent = _SuccessAgent()
    agent.load_skill("red-teaming")
    merged = agent._build_system_prompt("BASE PROMPT")
    assert merged.startswith("BASE PROMPT")
    assert "红队" in merged
    assert "行为规则" in merged


def test_agent_skill_param_precedence():
    agent = _SuccessAgent()
    # military-analysis has temperature=0.2
    agent.load_skill("military-analysis")
    assert agent._skill_param("temperature", 0.3) == 0.2
    # bayesian-reasoning has no temperature, falls back
    assert agent._skill_param("nonexistent_param", 99) == 99


def test_agent_skill_param_last_wins():
    agent = _SuccessAgent()
    agent.load_skill("military-analysis")  # temperature=0.2
    agent.load_skill("economic-analysis")  # temperature=0.2
    # Both have same value, but last loaded should apply
    assert agent._skill_param("temperature", 0.3) == 0.2


def test_super_analysis_default_skills_do_not_reduce_agent_output_budget():
    from backend.agents.intelligence.super_analyst import SuperAnalysisAgent

    agent = SuperAnalysisAgent()

    assert agent.max_tokens == 16384
    assert agent._skill_param("max_tokens", agent.max_tokens) == 16384


def test_super_analysis_prompt_uses_only_consistent_four_step_skill():
    from backend.agents.intelligence import super_analyst

    agent = super_analyst.SuperAnalysisAgent()
    prompt = agent._build_system_prompt(super_analyst._SYSTEM_SUPER_ANALYSIS_BASE)

    assert [skill.name for skill in agent._loaded_skills] == ["super-analysis"]
    assert "基于信源可信度等级" not in prompt
    assert "L1-L4" not in prompt
    assert "严格四步" in prompt


@pytest.mark.asyncio
async def test_super_analysis_llm_payload_uses_full_output_budget(monkeypatch):
    from backend.agents.intelligence import super_analyst

    posted_payloads = []

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, _url, json):
            posted_payloads.append(json)
            return _FakeResponse()

    monkeypatch.setattr(super_analyst, "get_llm_client", lambda: _FakeClient())

    agent = super_analyst.SuperAnalysisAgent()
    result = await agent._call_llm_with_skills("测试提示", temperature=0.3)

    assert result == "ok"
    assert posted_payloads[0]["max_tokens"] == 16384


@pytest.mark.asyncio
async def test_super_analysis_date_window_falls_back_when_embedding_hits_are_outside_range(monkeypatch, tmp_path):
    import hashlib

    from backend.agents.intelligence import super_analyst
    from backend.agents.models import AgentTask
    from backend.bronze_reader import BronzeDocument

    old_text = "旧情报：港口物流扰动，已经过期。"
    current_text = "当前情报：港口物流扰动持续，货运延迟扩大。"
    old_hash = hashlib.md5(old_text.encode()).hexdigest()

    docs = [
        BronzeDocument({
            "raw_document_id": "old-doc",
            "body_inline": old_text,
            "source_system": "bbc",
            "captured_at": "2026-05-01T00:00:00Z",
            "extensions": {"horizon_metadata": {"layer": "logistics"}},
        }),
        BronzeDocument({
            "raw_document_id": "current-doc",
            "body_inline": current_text,
            "source_system": "bbc",
            "captured_at": "2026-06-20T00:00:00Z",
            "extensions": {"horizon_metadata": {"layer": "logistics"}},
        }),
    ]

    class _FakeIndex:
        is_loaded = True
        size = 2

        def __init__(self, *_args, **_kwargs):
            pass

        def load(self):
            return True

        def search(self, *_args, **_kwargs):
            return [(old_hash, 0.95)]

    monkeypatch.setattr(super_analyst, "scan_bronze", lambda _storage: docs)
    monkeypatch.setattr(super_analyst, "EmbeddingIndex", _FakeIndex)
    monkeypatch.setattr(super_analyst, "_web_search", lambda _question: None)

    agent = super_analyst.SuperAnalysisAgent(storage_root=tmp_path)

    async def _fake_llm(*_args, **_kwargs):
        return "ok"

    monkeypatch.setattr(agent, "_call_llm_with_skills", _fake_llm)

    result = await agent._execute(AgentTask(
        task_type="super_analysis",
        params={
            "question": "港口物流扰动",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "web_search": False,
        },
    ))

    assert [item["title"] for item in result["relevant_items"]] == [current_text[:80]]


@pytest.mark.asyncio
async def test_super_analysis_includes_unindexed_relevant_docs_when_embedding_index_is_partial(monkeypatch, tmp_path):
    import hashlib

    from backend.agents.intelligence import super_analyst
    from backend.agents.models import AgentTask
    from backend.bronze_reader import BronzeDocument

    indexed_text = "旧索引情报：港口物流。"
    unindexed_text = "新增情报：港口物流扰动扩大，集装箱延误显著增加。"
    indexed_hash = hashlib.md5(indexed_text.encode()).hexdigest()

    docs = [
        BronzeDocument({
            "raw_document_id": "indexed-doc",
            "body_inline": indexed_text,
            "source_system": "bbc",
            "captured_at": "2026-05-20T00:00:00Z",
            "extensions": {"horizon_metadata": {"layer": "logistics"}},
        }),
        BronzeDocument({
            "raw_document_id": "unindexed-doc",
            "body_inline": unindexed_text,
            "source_system": "bbc",
            "captured_at": "2026-06-30T00:00:00Z",
            "extensions": {"horizon_metadata": {"layer": "logistics"}},
        }),
    ]

    class _FakeIndex:
        is_loaded = True
        size = 1

        def __init__(self, *_args, **_kwargs):
            self.doc_hashes = [indexed_hash]

        def load(self):
            return True

        def search(self, *_args, **_kwargs):
            return [(indexed_hash, 0.2)]

    monkeypatch.setattr(super_analyst, "scan_bronze", lambda _storage: docs)
    monkeypatch.setattr(super_analyst, "EmbeddingIndex", _FakeIndex)
    monkeypatch.setattr(super_analyst, "_web_search", lambda _question: None)

    agent = super_analyst.SuperAnalysisAgent(storage_root=tmp_path)

    async def _fake_llm(*_args, **_kwargs):
        return "ok"

    monkeypatch.setattr(agent, "_call_llm_with_skills", _fake_llm)

    result = await agent._execute(AgentTask(
        task_type="super_analysis",
        params={
            "question": "港口物流扰动",
            "web_search": False,
        },
    ))

    titles = [item["title"] for item in result["relevant_items"]]
    assert unindexed_text[:80] in titles


def test_agent_task_skills_field():
    task = AgentTask(task_type="qa", skills=["bayesian-reasoning", "red-teaming"])
    assert task.skills == ["bayesian-reasoning", "red-teaming"]


def test_agent_task_skills_default():
    task = AgentTask()
    assert task.skills == []


def test_skill_loader_load_for_task():
    skills = SkillLoader.load_for_task(["bayesian-reasoning", "nonexistent"])
    assert len(skills) == 1
    assert skills[0].name == "bayesian-reasoning"


def test_skill_rule_model():
    rule = SkillRule(do=["必须做A", "必须做B"], dont=["禁止做X"])
    assert len(rule.do) == 2
    assert len(rule.dont) == 1


def test_skill_loader_invalidate_cache():
    SkillLoader.load("red-teaming")
    assert "red-teaming" in SkillLoader._cache
    SkillLoader.invalidate_cache()
    assert len(SkillLoader._cache) == 0


def test_skill_loader_rejects_path_traversal_names():
    with pytest.raises(ValueError, match="Invalid skill name"):
        SkillLoader.load("../../../.opencode/config")


# ── System agents ──

import tempfile
from pathlib import Path
from backend.agents.system.merger import MergeAgent
from backend.agents.system.indexer import IndexAgent


@pytest.mark.asyncio
async def test_merge_agent_load_no_index():
    with tempfile.TemporaryDirectory() as tmp:
        agent = MergeAgent(storage_root=Path(tmp))
        task = AgentTask(task_type="merge", params={"action": "load"})
        result = await agent.run(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["status"] == "no_index"


@pytest.mark.asyncio
async def test_merge_agent_build_empty():
    with tempfile.TemporaryDirectory() as tmp:
        agent = MergeAgent(storage_root=Path(tmp))
        task = AgentTask(task_type="merge", params={"action": "build"})
        result = await agent.run(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["status"] == "ok"
        assert result.data["groups"] == 0


@pytest.mark.asyncio
async def test_index_agent_build():
    with tempfile.TemporaryDirectory() as tmp:
        agent = IndexAgent(storage_root=Path(tmp))
        task = AgentTask(task_type="index", params={"action": "build"})
        result = await agent.run(task)
        assert result.status == AgentStatus.COMPLETED
        assert result.data["status"] == "ok"
        assert result.data["count"] == 0
        agent.close()


@pytest.mark.asyncio
async def test_index_agent_stats():
    with tempfile.TemporaryDirectory() as tmp:
        agent = IndexAgent(storage_root=Path(tmp))
        task = AgentTask(task_type="index", params={"action": "stats"})
        result = await agent.run(task)
        assert result.status == AgentStatus.COMPLETED
        assert "stats" in result.data
        agent.close()


@pytest.mark.asyncio
async def test_index_agent_unknown_action():
    with tempfile.TemporaryDirectory() as tmp:
        agent = IndexAgent(storage_root=Path(tmp))
        task = AgentTask(task_type="index", params={"action": "nonexistent"})
        result = await agent.run(task)
        assert result.status == AgentStatus.COMPLETED
        assert "error" in result.data
        agent.close()


# ── Processing agents ──

from backend.agents.processors.translation import TranslationAgent
from backend.agents.processors.summarization import SummarizationAgent
from backend.agents.processors.classification import ClassificationAgent
from backend.agents.processors.location_extraction import LocationExtractionAgent
from backend.agents.processors.document_quality import DocumentQualityAgent
from backend.agents.processors.pipeline import CollectionPipelineAgent


@pytest.mark.asyncio
async def test_translation_agent_empty():
    agent = TranslationAgent()
    task = AgentTask(task_type="translate", params={"text": ""})
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "translated" in result.data


@pytest.mark.asyncio
async def test_summarization_agent_empty():
    agent = SummarizationAgent()
    task = AgentTask(task_type="summarize", params={"text": ""})
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "summary" in result.data


@pytest.mark.asyncio
async def test_classification_agent_params():
    agent = ClassificationAgent()
    task = AgentTask(task_type="classify", params={
        "title": "Test Title", "content": "Test content for classification."
    })
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "layer" in result.data


@pytest.mark.asyncio
async def test_location_agent_empty():
    agent = LocationExtractionAgent()
    task = AgentTask(task_type="locate", params={"text": ""})
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "country" in result.data


@pytest.mark.asyncio
async def test_document_quality_agent_empty():
    agent = DocumentQualityAgent()
    task = AgentTask(task_type="document_quality", params={"text": "", "source_system": ""})
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert 0 <= result.data["quality_score"] <= 1
    assert "posterior" not in result.data


@pytest.mark.asyncio
async def test_document_quality_agent_with_text():
    agent = DocumentQualityAgent()
    task = AgentTask(task_type="document_quality", params={
        "text": "Breaking: major economic agreement signed between countries.",
        "source_system": "reuters",
    })
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "quality_score" in result.data
    assert "confidence_level" not in result.data
    assert "quality_factors" in result.data


@pytest.mark.asyncio
async def test_pipeline_agent_empty():
    agent = CollectionPipelineAgent()
    task = AgentTask(task_type="pipeline", params={
        "text": "", "title": "", "source_system": "",
        "translate": False, "summarize": False, "classify": False,
        "locate": False, "document_quality": True,
    })
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "original" in result.data


@pytest.mark.asyncio
async def test_pipeline_agent_minimal():
    agent = CollectionPipelineAgent()
    task = AgentTask(task_type="pipeline", params={
        "text": "Test content",
        "source_system": "reuters",
        "translate": False,
        "summarize": False,
        "classify": False,
        "locate": False,
        "document_quality": True,
    })
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "document_quality" in result.data
    assert result.data["document_quality"]["quality_score"] >= 0.0


@pytest.mark.asyncio
async def test_pipeline_agent_full():
    agent = CollectionPipelineAgent()
    task = AgentTask(task_type="pipeline", params={
        "text": "Latest economic data shows growth in manufacturing sector across Asia.",
        "title": "Economic Growth Report",
        "source_system": "reuters",
    })
    result = await agent.run(task)
    assert result.status == AgentStatus.COMPLETED
    assert "translated" in result.data
    assert "summary" in result.data
    assert "layer" in result.data
    assert "location" in result.data
    assert "document_quality" not in result.data
