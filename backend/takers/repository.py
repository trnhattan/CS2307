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

    async def criterion_mastery(
        self,
        session: AsyncSession,
        student_id: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                WITH response_evidence AS (
                    SELECT criterion.criterion_id,
                           COUNT(item.exam_item_id) AS evidence_count
                    FROM exam_sessions exam
                    JOIN exam_items item ON item.session_id = exam.session_id
                    JOIN question_knowledge_units link
                      ON link.question_id = item.question_id
                     AND link.unit_role IN ('primary_skill', 'supporting_skill')
                    JOIN assessment_criteria criterion
                      ON criterion.knowledge_unit_id = link.unit_id
                    WHERE exam.student_id = :student_id
                      AND exam.status = 'completed'
                      AND item.answered_at IS NOT NULL
                    GROUP BY criterion.criterion_id
                )
                SELECT
                    subject.subject_code,
                    subject.subject_name,
                    criterion.criterion_code AS unit_code,
                    criterion.criterion_name AS unit_name,
                    'criterion' AS unit_type,
                    COALESCE(evidence.evidence_count, 0) AS evidence_count,
                    ability.mastery_probability,
                    criterion.mastery_threshold
                FROM assessment_criteria criterion
                JOIN subjects subject ON subject.subject_id = criterion.subject_id
                JOIN knowledge_units unit
                  ON unit.unit_id = criterion.knowledge_unit_id
                LEFT JOIN student_abilities ability
                  ON ability.student_id = :student_id
                 AND ability.knowledge_unit_id = criterion.knowledge_unit_id
                LEFT JOIN response_evidence evidence
                  ON evidence.criterion_id = criterion.criterion_id
                WHERE criterion.is_active = TRUE
                  AND subject.is_active = TRUE
                  AND unit.is_active = TRUE
                ORDER BY subject.subject_name, ability.mastery_probability NULLS FIRST,
                         criterion.display_order, criterion.criterion_name
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
        return await self.criterion_mastery(session, student_id)
