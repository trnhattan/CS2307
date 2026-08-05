from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PlacementRepository:
    async def status(
        self, session: AsyncSession, student_id: int
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT subject.subject_code, subject.subject_name,
                       COALESCE(latest.status, 'not_started') AS status,
                       latest.session_id, latest.finished_at AS completed_at,
                       CASE WHEN latest.max_score > 0
                            THEN 100 * latest.total_score / latest.max_score
                            ELSE NULL END AS score_percent
                FROM subjects subject
                LEFT JOIN LATERAL (
                    SELECT exam.session_id, exam.status, exam.finished_at,
                           exam.total_score, exam.max_score
                    FROM exam_sessions exam
                    WHERE exam.student_id = :student_id
                      AND exam.subject_id = subject.subject_id
                      AND exam.assessment_purpose = 'placement'
                    ORDER BY exam.started_at DESC, exam.session_id DESC
                    LIMIT 1
                ) latest ON TRUE
                WHERE subject.is_active = TRUE
                ORDER BY subject.subject_name
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]
