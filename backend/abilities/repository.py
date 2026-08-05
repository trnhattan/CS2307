import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AbilityRepository:
    async def criteria_by_unit(
        self, session: AsyncSession, subject_id: int
    ) -> dict[int, int]:
        result = await session.execute(
            text(
                """
                SELECT knowledge_unit_id, criterion_id
                FROM assessment_criteria
                WHERE subject_id = :subject_id AND is_active = TRUE
                """
            ),
            {"subject_id": subject_id},
        )
        return {int(row.knowledge_unit_id): int(row.criterion_id) for row in result}

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

    async def previous_snapshot(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int,
        session_id: int,
        criterion_id: int | None,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT snapshot.theta, snapshot.mastery_probability
                FROM student_ability_snapshots snapshot
                JOIN exam_sessions exam ON exam.session_id = snapshot.session_id
                WHERE snapshot.student_id = :student_id
                  AND snapshot.subject_id = :subject_id
                  AND snapshot.session_id <> :session_id
                  AND snapshot.criterion_id IS NOT DISTINCT FROM
                      CAST(:criterion_id AS BIGINT)
                  AND snapshot.model_version = 'IRT-3PL-EAP-v1'
                  AND exam.status = 'completed'
                ORDER BY snapshot.created_at DESC, snapshot.snapshot_id DESC
                LIMIT 1
                """
            ),
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "session_id": session_id,
                "criterion_id": criterion_id,
            },
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def save_snapshot(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        student_id: int,
        subject_id: int,
        criterion_id: int | None,
        theta: float,
        standard_error: float,
        mastery: float,
        accuracy_percent: float,
        evidence_count: int,
        previous: dict[str, Any] | None,
    ) -> None:
        previous_theta = float(previous["theta"]) if previous else None
        previous_mastery = (
            float(previous["mastery_probability"])
            if previous and previous["mastery_probability"] is not None
            else None
        )
        await session.execute(
            text(
                """
                INSERT INTO student_ability_snapshots (
                    session_id, student_id, subject_id, criterion_id,
                    theta, standard_error, mastery_probability,
                    accuracy_percent, evidence_count,
                    previous_theta, previous_mastery, theta_delta, mastery_delta
                ) VALUES (
                    :session_id, :student_id, :subject_id, :criterion_id,
                    :theta, :standard_error, :mastery,
                    :accuracy_percent, :evidence_count,
                    :previous_theta, :previous_mastery,
                    CASE WHEN CAST(:previous_theta AS NUMERIC) IS NULL THEN NULL
                         ELSE :theta - :previous_theta END,
                    CASE WHEN CAST(:previous_mastery AS NUMERIC) IS NULL THEN NULL
                         ELSE :mastery - :previous_mastery END
                )
                ON CONFLICT (session_id, criterion_id) DO UPDATE SET
                    theta = EXCLUDED.theta,
                    standard_error = EXCLUDED.standard_error,
                    mastery_probability = EXCLUDED.mastery_probability,
                    accuracy_percent = EXCLUDED.accuracy_percent,
                    evidence_count = EXCLUDED.evidence_count,
                    previous_theta = EXCLUDED.previous_theta,
                    previous_mastery = EXCLUDED.previous_mastery,
                    theta_delta = EXCLUDED.theta_delta,
                    mastery_delta = EXCLUDED.mastery_delta,
                    created_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "session_id": session_id,
                "student_id": student_id,
                "subject_id": subject_id,
                "criterion_id": criterion_id,
                "theta": theta,
                "standard_error": standard_error,
                "mastery": mastery,
                "accuracy_percent": accuracy_percent,
                "evidence_count": evidence_count,
                "previous_theta": previous_theta,
                "previous_mastery": previous_mastery,
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
