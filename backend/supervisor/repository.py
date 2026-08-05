from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SupervisorRepository:
    async def summary(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_sessions,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed_sessions,
                    COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_sessions,
                    COUNT(DISTINCT student_id) AS exam_takers,
                    COALESCE(
                        AVG(100 * total_score / NULLIF(max_score, 0))
                            FILTER (WHERE status = 'completed'),
                        0
                    ) AS average_score_percent
                FROM exam_sessions
                """
            )
        )
        return dict(result.one()._mapping)

    async def sessions(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    exam.session_id,
                    student.student_code,
                    student.display_name AS student_name,
                    subject.subject_code,
                    subject.subject_name,
                    exam.status,
                    exam.mode,
                    exam.assessment_purpose,
                    COUNT(item.exam_item_id) AS question_count,
                    COUNT(item.exam_item_id) FILTER (
                        WHERE item.answered_at IS NOT NULL
                    ) AS answered_count,
                    exam.total_score,
                    exam.max_score,
                    CASE
                        WHEN exam.max_score > 0 THEN 100 * exam.total_score / exam.max_score
                        ELSE 0
                    END AS score_percent,
                    exam.theta_initial,
                    exam.theta_current,
                    exam.standard_error_current AS standard_error,
                    COALESCE(AVG(item.item_information), 0) AS average_item_information,
                    jsonb_build_object(
                        'easy', COUNT(*) FILTER (WHERE question.difficulty_label = 'easy'),
                        'medium', COUNT(*) FILTER (WHERE question.difficulty_label = 'medium'),
                        'hard', COUNT(*) FILTER (WHERE question.difficulty_label = 'hard')
                    ) AS difficulty_distribution,
                    jsonb_build_object(
                        'remember', COUNT(*) FILTER (WHERE question.bloom_level = 'remember'),
                        'understand', COUNT(*) FILTER (WHERE question.bloom_level = 'understand'),
                        'apply', COUNT(*) FILTER (WHERE question.bloom_level = 'apply'),
                        'analyze', COUNT(*) FILTER (WHERE question.bloom_level = 'analyze'),
                        'evaluate', COUNT(*) FILTER (WHERE question.bloom_level = 'evaluate')
                    ) AS bloom_distribution,
                    exam.generation_config,
                    exam.started_at,
                    exam.finished_at
                FROM exam_sessions exam
                JOIN students student ON student.student_id = exam.student_id
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                LEFT JOIN exam_items item ON item.session_id = exam.session_id
                LEFT JOIN questions question ON question.question_id = item.question_id
                GROUP BY exam.session_id, student.student_id, subject.subject_id
                ORDER BY exam.started_at DESC
                LIMIT 200
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def abilities(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    student.student_code,
                    student.display_name AS student_name,
                    subject.subject_code,
                    subject.subject_name,
                    ability.theta,
                    ability.standard_error,
                    ability.mastery_probability,
                    ability.evidence_count,
                    ability.updated_at
                FROM student_abilities ability
                JOIN students student ON student.student_id = ability.student_id
                JOIN subjects subject ON subject.subject_id = ability.subject_id
                WHERE ability.knowledge_unit_id IS NULL
                ORDER BY ability.updated_at DESC
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def takers(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    app_user.username,
                    student.student_id,
                    student.student_code,
                    student.display_name AS student_name,
                    COALESCE(test_stats.completed_tests, 0) AS completed_tests,
                    COALESCE(test_stats.subjects_assessed, 0) AS subjects_assessed,
                    COALESCE(test_stats.average_score_percent, 0)
                        AS average_score_percent,
                    COALESCE(test_stats.best_score_percent, 0) AS best_score_percent,
                    latest.score_percent AS latest_score_percent,
                    ability_stats.average_theta,
                    ability_stats.average_mastery_probability,
                    latest.finished_at AS latest_test_at
                FROM app_users app_user
                JOIN students student ON student.student_id = app_user.student_id
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) AS completed_tests,
                        COUNT(DISTINCT exam.subject_id) AS subjects_assessed,
                        AVG(100 * exam.total_score / NULLIF(exam.max_score, 0))
                            AS average_score_percent,
                        MAX(100 * exam.total_score / NULLIF(exam.max_score, 0))
                            AS best_score_percent
                    FROM exam_sessions exam
                    WHERE exam.student_id = student.student_id
                      AND exam.status = 'completed'
                ) test_stats ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        100 * exam.total_score / NULLIF(exam.max_score, 0)
                            AS score_percent,
                        exam.finished_at
                    FROM exam_sessions exam
                    WHERE exam.student_id = student.student_id
                      AND exam.status = 'completed'
                    ORDER BY exam.finished_at DESC
                    LIMIT 1
                ) latest ON TRUE
                LEFT JOIN LATERAL (
                    SELECT
                        AVG(ability.theta) AS average_theta,
                        AVG(ability.mastery_probability)
                            AS average_mastery_probability
                    FROM student_abilities ability
                    WHERE ability.student_id = student.student_id
                      AND ability.knowledge_unit_id IS NULL
                ) ability_stats ON TRUE
                WHERE app_user.role = 'exam_taker'
                ORDER BY student.display_name
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def accounts(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    app_user.username,
                    app_user.display_name,
                    app_user.role,
                    student.student_code,
                    app_user.is_active
                FROM app_users app_user
                LEFT JOIN students student ON student.student_id = app_user.student_id
                ORDER BY app_user.role, app_user.username
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def system_config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text("SELECT prop_key, prop_value FROM sys_props ORDER BY prop_key")
        )
        return {row.prop_key: row.prop_value for row in result}
