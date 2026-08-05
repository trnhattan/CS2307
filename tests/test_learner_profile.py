import asyncio
from datetime import UTC, datetime

from backend.learner_profiles.service import LearnerProfileService


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
        return {"student_id": student_id, "student_code": "T1", "display_name": "Student 1"}

    async def config(self, session):
        return {"PROFILE_IMPROVEMENT_DELTA": 0.05}

    async def states(self, session, student_id, subject_code):
        common = {
            "subject_id": 1,
            "subject_code": "DATABASE",
            "subject_name": "Database Systems",
            "topic_code": "DB_INDEX",
            "topic_name": "Indexing and Performance",
            "learning_objective": "Choose an index for a workload.",
            "success_statement": "The learner can justify a suitable index.",
            "mastery_threshold": 0.75,
            "importance_weight": 1,
            "mapped_question_count": 5,
            "theta": None,
            "standard_error": None,
        }
        return [
            {
                **common,
                "criterion_id": 1,
                "criterion_code": "INDEX",
                "criterion_name": "Index design",
                "display_order": 1,
                "mastery_probability": 0.8,
                "accuracy_percent": 80,
                "evidence_count": 5,
                "mastery_delta": 0.12,
                "last_assessed_at": datetime(2026, 1, 1, tzinfo=UTC),
            },
            {
                **common,
                "criterion_id": 2,
                "criterion_code": "PRIMARY_KEY",
                "criterion_name": "Primary key",
                "display_order": 2,
                "mastery_probability": None,
                "accuracy_percent": None,
                "evidence_count": 0,
                "mastery_delta": None,
                "last_assessed_at": None,
            },
        ]

    async def subject_states(self, session, student_id):
        return [
            {
                "subject_code": "DATABASE",
                "subject_name": "Database Systems",
                "completed_tests": 3,
                "mastery_probability": 0.82,
                "evidence_count": 60,
            },
            {
                "subject_code": "NETWORK",
                "subject_name": "Computer Networks",
                "completed_tests": 0,
                "mastery_probability": None,
                "evidence_count": 0,
            },
        ]


def test_profile_tracks_strength_improvement_and_unknown_radar_axis() -> None:
    service = LearnerProfileService(Repository(), SessionFactory())
    profile = asyncio.run(service.profile(1, "DATABASE"))
    radar = asyncio.run(service.radar(1, "DATABASE"))

    assert profile is not None and radar is not None
    subject = profile.subjects[0]
    assert subject.strengths == ["Index design"]
    assert subject.improved == ["Index design"]
    assert subject.insufficient_evidence == ["Primary key"]
    assert radar.axes[0].value_percent == 80
    assert radar.axes[1].value_percent is None
    assert radar.assessed_criteria == 1
    assert "not converted to zero" in radar.note


def test_overall_radar_uses_subject_mastery_and_preserves_unknowns() -> None:
    service = LearnerProfileService(Repository(), SessionFactory())
    radar = asyncio.run(service.radar(1, "OVERALL"))

    assert radar is not None
    assert radar.scope == "overall"
    assert radar.axes[0].criterion_name == "Database Systems"
    assert radar.axes[0].value_percent == 82
    assert radar.axes[1].value_percent is None
    assert radar.assessed_criteria == 1
