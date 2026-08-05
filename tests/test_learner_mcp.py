import asyncio
from pathlib import Path

from backend.learner_mcp.server import learner_mcp
from backend.learner_mcp.tools import LearnerToolset, learner_tool_definitions


ROOT = Path(__file__).resolve().parents[1]


def test_mcp_exposes_learner_scoped_read_tools() -> None:
    tools = asyncio.run(learner_mcp.list_tools())
    names = {tool.name for tool in tools}

    assert names == {
        "get_my_learning_profile",
        "get_my_test_history",
        "search_my_completed_questions",
        "review_my_completed_question",
        "search_subject_knowledge",
    }
    definitions = learner_tool_definitions()
    assert {item["function"]["name"] for item in definitions} == names
    assert all("student_id" not in item["function"]["parameters"]["properties"] for item in definitions)


def test_subject_knowledge_ranking_prefers_curated_explanation() -> None:
    rows = [
        {
            "resource_id": "criterion:NET_QOS",
            "resource_type": "assessment_criterion",
            "title": "Apply quality of service policy",
            "content": "Apply the criterion.",
        },
        {
            "resource_id": "knowledge:NET_QOS",
            "resource_type": "subject_knowledge",
            "title": "Quality of Service policy",
            "content": "Classify, mark, queue, schedule, police, and shape traffic.",
        },
    ]

    ranked = LearnerToolset._rank(
        rows,
        "What is a quality of service policy?",
        2,
        knowledge=True,
    )

    assert ranked[0]["resource_type"] == "subject_knowledge"


def test_mcp_server_uses_authenticated_claims_not_model_student_ids() -> None:
    source = (ROOT / "backend" / "learner_mcp" / "server.py").read_text()

    assert "get_access_token" in source
    assert 'claims["student_id"]' in source
    assert "ApplicationTokenVerifier" in source
