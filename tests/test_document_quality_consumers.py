import pytest

from backend import main, mcp_server
from backend.agents.models import AgentTask
from backend.agents.processors.document_quality import DocumentQualityAgent
from backend.agents.processors.pipeline import CollectionPipelineAgent


@pytest.mark.asyncio
async def test_document_quality_agent_reports_quality_not_truth_probability():
    result = await DocumentQualityAgent().run(AgentTask(
        task_type="document_quality",
        params={"text": "Reuters reported a dated, specific event.", "source_system": "reuters"},
    ))

    assert 0 <= result.data["quality_score"] <= 1
    assert "confidence_level" not in result.data
    assert result.data["source_class"] == "high-credibility"
    assert "posterior" not in result.data
    assert "verdict" not in result.data


@pytest.mark.asyncio
async def test_collection_pipeline_uses_document_quality_contract():
    result = await CollectionPipelineAgent().run(AgentTask(
        task_type="pipeline",
        params={
            "text": "A specific report with a date: 2026-07-16.",
            "source_system": "reuters",
            "translate": False,
            "summarize": False,
            "classify": False,
            "locate": False,
            "document_quality": True,
        },
    ))

    assert "document_quality" in result.data
    assert "bayesian" not in result.data
    assert "posterior" not in result.data["document_quality"]


@pytest.mark.asyncio
async def test_mcp_exposes_document_quality_instead_of_fake_bayesian_probability():
    assert hasattr(mcp_server, "assess_document_quality_tool")
    assert not hasattr(mcp_server, "compute_bayesian_tool")

    result = await mcp_server.assess_document_quality_tool(
        "A source document with concrete details.",
        "reuters",
    )

    assert 0 <= result["quality_score"] <= 1
    assert "confidence_level" not in result
    assert "posterior" not in result
    assert "verdict" not in result


def test_public_processing_contract_uses_document_quality_name():
    paths = {route.path for route in main.app.routes}
    assert "/api/process/document-quality" in paths
    assert "/api/process/bayesian-score" not in paths
    assert "document_quality" in main.PipelineRequest.model_fields
    assert "bayesian" not in main.PipelineRequest.model_fields
