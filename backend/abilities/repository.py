import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AbilityRepository:
    async def subject_responses(
        self,
        session: AsyncSession,
        student_id: int,
        subject_id: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT item.exam_item_id, question.irt_a, question.irt_b,
                       question.irt_c, item.is_correct
                FROM exam_sessions exam
                JOIN exam_items item ON item.session_id = exam.session_id
                JOIN questions question ON question.question_id = item.question_id
                WHERE exam.student_id = :student_id
                  AND exam.subject_id = :subject_id
                  AND item.answered_at IS NOT NULL
                ORDER BY item.answered_at, item.exam_item_id
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        return [dict(row._mapping) for row in result]

    async def unit_responses(
        self,
        session: AsyncSession,
        student_id: int,
        subject_id: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT unit.unit_id, unit.unit_code, unit.unit_name, unit.unit_type,
                       link.measurement_weight, question.irt_a, question.irt_b,
                       question.irt_c, item.is_correct
                FROM exam_sessions exam
                JOIN exam_items item ON item.session_id = exam.session_id
                JOIN questions question ON question.question_id = item.question_id
                JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                WHERE exam.student_id = :student_id
                  AND exam.subject_id = :subject_id
                  AND item.answered_at IS NOT NULL
                  AND unit.is_active = TRUE
                ORDER BY unit.unit_id, item.answered_at, item.exam_item_id
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        return [dict(row._mapping) for row in result]

    async def upsert(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int,
        unit_id: int | None,
        theta: float,
        standard_error: float,
        mastery: float,
        evidence_count: int,
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO student_abilities (
                    student_id, subject_id, knowledge_unit_id, theta,
                    standard_error, mastery_probability, evidence_count
                )
                VALUES (
                    :student_id, :subject_id, :unit_id, :theta,
                    :standard_error, :mastery, :evidence_count
                )
                ON CONFLICT (student_id, subject_id, knowledge_unit_id)
                DO UPDATE SET
                    theta = EXCLUDED.theta,
                    standard_error = EXCLUDED.standard_error,
                    mastery_probability = EXCLUDED.mastery_probability,
                    evidence_count = EXCLUDED.evidence_count,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "unit_id": unit_id,
                "theta": theta,
                "standard_error": standard_error,
                "mastery": mastery,
                "evidence_count": evidence_count,
            },
        )

    async def student_code(self, session: AsyncSession, student_id: int) -> str:
        result = await session.execute(
            text("SELECT student_code FROM students WHERE student_id = :student_id"),
            {"student_id": student_id},
        )
        return result.scalar_one()

    async def save_learning_trace(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        initial_facts: list[dict[str, Any]],
        derived_facts: list[dict[str, Any]],
        steps: list[dict[str, Any]],
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO inference_traces (
                    session_id, strategy, goal, initial_facts, derived_facts,
                    steps, status, finished_at
                )
                VALUES (
                    :session_id, 'forward',
                    '{"predicate":"recommended_next"}'::JSONB,
                    CAST(:initial AS JSONB), CAST(:derived AS JSONB),
                    CAST(:steps AS JSONB), 'completed', CURRENT_TIMESTAMP
                )
                RETURNING inference_trace_id
                """
            ),
            {
                "session_id": session_id,
                "initial": self._json(initial_facts),
                "derived": self._json(derived_facts),
                "steps": self._json(steps),
            },
        )
        return result.scalar_one()

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
