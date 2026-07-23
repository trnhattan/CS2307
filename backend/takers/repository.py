from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TakerRepository:
    async def summary(
        self,
        session: AsyncSession,
        student_id: int,
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_tests,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed_tests,
                    COALESCE(
                        AVG(100 * total_score / NULLIF(max_score, 0))
                            FILTER (WHERE status = 'completed'),
                        0
                    ) AS average_score_percent,
                    COALESCE(
                        MAX(100 * total_score / NULLIF(max_score, 0))
                            FILTER (WHERE status = 'completed'),
                        0
                    ) AS best_score_percent
                FROM exam_sessions
                WHERE student_id = :student_id
                """
            ),
            {"student_id": student_id},
        )
        return dict(result.one()._mapping)

    async def subject_progress(
        self,
        session: AsyncSession,
        student_id: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    subject.subject_code,
                    subject.subject_name,
                    COUNT(exam.session_id) AS completed_tests,
                    COALESCE(
                        AVG(100 * exam.total_score / NULLIF(exam.max_score, 0)),
                        0
                    ) AS average_score_percent,
                    COALESCE(
                        MAX(100 * exam.total_score / NULLIF(exam.max_score, 0)),
                        0
                    ) AS best_score_percent,
                    latest.score_percent AS latest_score_percent
                FROM subjects subject
                LEFT JOIN exam_sessions exam
                    ON exam.subject_id = subject.subject_id
                    AND exam.student_id = :student_id
                    AND exam.status = 'completed'
                LEFT JOIN LATERAL (
                    SELECT 100 * recent.total_score /
                        NULLIF(recent.max_score, 0) AS score_percent
                    FROM exam_sessions recent
                    WHERE recent.subject_id = subject.subject_id
                      AND recent.student_id = :student_id
                      AND recent.status = 'completed'
                    ORDER BY recent.finished_at DESC
                    LIMIT 1
                ) latest ON TRUE
                WHERE subject.is_active = TRUE
                GROUP BY
                    subject.subject_id,
                    subject.subject_code,
                    subject.subject_name,
                    latest.score_percent
                ORDER BY subject.subject_name
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]

    async def recent_tests(
        self,
        session: AsyncSession,
        student_id: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    exam.session_id,
                    subject.subject_code,
                    subject.subject_name,
                    100 * exam.total_score / NULLIF(exam.max_score, 0)
                        AS score_percent,
                    exam.finished_at
                FROM exam_sessions exam
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                WHERE exam.student_id = :student_id
                  AND exam.status = 'completed'
                ORDER BY exam.finished_at DESC
                LIMIT 50
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]

    async def unit_evidence(
        self,
        session: AsyncSession,
        student_id: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    subject.subject_code,
                    subject.subject_name,
                    unit.unit_code,
                    unit.unit_name,
                    unit.unit_type,
                    COUNT(item.exam_item_id) AS evidence_count,
                    100 * AVG(CASE WHEN item.is_correct THEN 1.0 ELSE 0.0 END)
                        AS accuracy_percent
                FROM exam_sessions exam
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                JOIN exam_items item ON item.session_id = exam.session_id
                JOIN question_knowledge_units question_unit
                    ON question_unit.question_id = item.question_id
                JOIN knowledge_units unit ON unit.unit_id = question_unit.unit_id
                WHERE exam.student_id = :student_id
                  AND exam.status = 'completed'
                  AND item.answered_at IS NOT NULL
                  AND unit.is_active = TRUE
                GROUP BY
                    subject.subject_id,
                    unit.unit_id,
                    subject.subject_code,
                    subject.subject_name,
                    unit.unit_code,
                    unit.unit_name,
                    unit.unit_type
                ORDER BY accuracy_percent, evidence_count DESC, unit.unit_name
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]
