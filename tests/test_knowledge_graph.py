import asyncio
from datetime import UTC, datetime

from backend.knowledge_graph.service import KnowledgeGraphService


class SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_):
        return None


class SessionFactory:
    def __call__(self):
        return SessionContext()


class Repository:
    async def student(self, session, student_id):
        return {
            "student_id": student_id,
            "student_code": "TAKER001",
            "display_name": "Sinh viên 1",
        }

    async def abilities(self, session, student_id):
        return [
            {
                "subject_code": "DATABASE",
                "subject_name": "Cơ sở dữ liệu",
                "unit_code": "SQL",
                "unit_name": "SQL",
                "unit_type": "skill",
                "parent_code": "DB_CORE",
                "parent_name": "Nền tảng CSDL",
                "parent_type": "topic",
                "knowledge_unit_id": 2,
                "theta": -0.4,
                "standard_error": 0.5,
                "mastery_probability": 0.4,
                "evidence_count": 3,
            }
        ]

    async def attempts(self, session, student_id):
        return [
            {
                "exam_item_id": 7,
                "question_code": "DB_01",
                "stem": "Technical question text",
                "is_correct": False,
                "answered_at": datetime(2026, 1, 1, tzinfo=UTC),
                "subject_code": "DATABASE",
                "unit_codes": ["SQL"],
            }
        ]

    async def recommendations(self, session, student_code):
        return [
            {
                "unit_code": "SQL",
                "action": "remediate",
                "inference_trace_id": 12,
                "derived_by_rule_code": "R_LEARNING_REMEDIATE",
            }
        ]


def test_knowledge_graph_has_evidence_and_role_specific_visibility() -> None:
    service = KnowledgeGraphService(Repository(), SessionFactory())
    taker = asyncio.run(service.graph(1, technical=False))
    staff = asyncio.run(service.graph(1, technical=True))

    assert taker is not None and staff is not None
    assert any(node.type == "evidence" for node in taker.nodes)
    assert any(edge.relation == "recommended_next" for edge in taker.edges)
    assert any(edge.relation == "prerequisite_of" for edge in taker.edges)
    assert {"Student 1", "Database Systems", "Core", "SQL"}.issubset(
        {node.label for node in taker.nodes}
    )
    assert all("_" not in node.label for node in taker.nodes)
    assert all(node.label.isascii() for node in taker.nodes)
    taker_payload = taker.model_dump_json()
    staff_payload = staff.model_dump_json()
    assert all(
        value not in taker_payload
        for value in ("theta", "standard_error", "reasoning_trace", "reasoning_rule", "Technical question text")
    )
    assert all(
        value in staff_payload
        for value in (
            "theta",
            "standard_error",
            "reasoning_trace",
            "reasoning_rule",
            "Technical question text",
            "Review weak foundational knowledge",
        )
    )
