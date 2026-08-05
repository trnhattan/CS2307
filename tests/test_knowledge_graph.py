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

    async def subjects(self, session, student_id):
        return [
            {
                "subject_id": 1,
                "subject_code": "DATABASE",
                "subject_name": "Cơ sở dữ liệu",
                "completed_tests": 3,
                "mastery_probability": 0.8,
                "evidence_count": 60,
            }
        ]

    async def config(self, session):
        return {
            "PROFILE_GRAPH_MIN_TESTS": 3,
            "PROFILE_NEEDS_REVIEW_THRESHOLD": 0.45,
            "PROFILE_DEVELOPING_THRESHOLD": 0.60,
            "PROFILE_MASTERY_THRESHOLD": 0.75,
        }

    async def criteria(self, session, student_id):
        return [
            {
                "criterion_id": 2,
                "criterion_code": "SQL_INDEX",
                "criterion_name": "Index design",
                "learning_objective": "Choose an index for a query workload.",
                "success_statement": "The learner can justify a suitable index.",
                "mastery_threshold": 0.75,
                "display_order": 1,
                "subject_code": "DATABASE",
                "subject_name": "Cơ sở dữ liệu",
                "theta": -0.4,
                "standard_error": 0.5,
                "mastery_probability": 0.4,
                "evidence_count": 3,
                "accuracy_percent": 33.3,
            }
        ]

    async def attempts(self, session, student_id):
        return [
            {
                "exam_item_id": 7,
                "question_code": "DB_01",
                "stem": "Which index best supports this query?",
                "is_correct": False,
                "answered_at": datetime(2026, 1, 1, tzinfo=UTC),
                "subject_code": "DATABASE",
                "difficulty_label": "medium",
                "bloom_level": "apply",
                "criterion_codes": ["SQL_INDEX"],
            }
        ]


def test_knowledge_graph_uses_requested_progressive_hierarchy() -> None:
    service = KnowledgeGraphService(Repository(), SessionFactory())
    taker = asyncio.run(service.graph(1, technical=False))
    staff = asyncio.run(service.graph(1, technical=True))

    assert taker is not None and staff is not None
    assert {node.type for node in taker.nodes} == {
        "student",
        "subject",
        "criterion",
        "question",
    }
    relations = {edge.relation for edge in taker.edges}
    assert relations == {
        "subject_mastered",
        "criterion_needs_review",
        "answered_question",
    }
    assert {"Student 1", "Database Systems", "Index design"}.issubset(
        {node.label for node in taker.nodes}
    )
    question = next(node for node in taker.nodes if node.type == "question")
    assert question.label == "Which index best supports this query?"
    assert question.attributes["difficulty"] == "Medium"
    assert "bloom_level" not in question.attributes
    staff_question = next(node for node in staff.nodes if node.type == "question")
    assert staff_question.attributes["bloom_level"] == "Apply"
    subject_edge = next(edge for edge in taker.edges if edge.relation == "subject_mastered")
    assert subject_edge.display_label == "Proficient · 80%"
    criterion_edge = next(
        edge for edge in taker.edges if edge.relation == "criterion_needs_review"
    )
    assert criterion_edge.display_label == "Needs review · 40%"
    assert criterion_edge.provenance["understanding"] == "Needs review"
    assert criterion_edge.provenance["evidence_count"] == 3
    assert "theta" not in taker.model_dump_json()
    assert "standard_error" not in taker.model_dump_json()
    assert "theta" in staff.model_dump_json()
    assert "standard_error" in staff.model_dump_json()


def test_graph_keeps_structural_relationships_until_three_tests() -> None:
    subject_relation = KnowledgeGraphService._mastery_relation(
        0.9,
        evidence_count=40,
        completed_tests=2,
        minimum_tests=3,
        needs_review=0.45,
        developing=0.60,
        mastered=0.75,
        subject=True,
    )
    criterion_relation = KnowledgeGraphService._mastery_relation(
        0.9,
        evidence_count=2,
        completed_tests=3,
        minimum_tests=3,
        needs_review=0.45,
        developing=0.60,
        mastered=0.75,
        subject=False,
    )

    assert subject_relation == ("has_subject", "Has learning profile for")
    assert criterion_relation == ("has_criterion", "Requires understanding of")


def test_graph_omits_answered_questions_without_an_active_criterion() -> None:
    class RepositoryWithUnmappedAttempt(Repository):
        async def attempts(self, session, student_id):
            rows = await super().attempts(session, student_id)
            rows.append(
                {
                    **rows[0],
                    "exam_item_id": 8,
                    "question_code": "OLD_QUESTION",
                    "criterion_codes": ["RETIRED_CRITERION"],
                }
            )
            return rows

    service = KnowledgeGraphService(RepositoryWithUnmappedAttempt(), SessionFactory())
    graph = asyncio.run(service.graph(1, technical=False))

    assert graph is not None
    question_ids = {node.id for node in graph.nodes if node.type == "question"}
    assert question_ids == {"question:7"}
