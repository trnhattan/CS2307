from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AdminRepository:
    async def system_overview(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM subjects) AS subjects,
                    (SELECT COUNT(*) FROM questions) AS questions,
                    (SELECT COUNT(*) FROM questions WHERE status = 'active')
                        AS active_questions,
                    (SELECT COUNT(*) FROM knowledge_units) AS knowledge_units,
                    (SELECT COUNT(*) FROM kb_facts) AS knowledge_facts,
                    (SELECT COUNT(*) FROM kb_rules WHERE is_active = TRUE)
                        AS knowledge_rules,
                    (SELECT COUNT(*) FROM app_users) AS users,
                    COALESCE(
                        (SELECT (prop_value #>> '{}')::INTEGER
                         FROM sys_props
                         WHERE prop_key = 'QUESTION_BANK_TARGET_SIZE'),
                        200
                    ) AS question_bank_target
                """
            )
        )
        row = dict(result.one()._mapping)
        target = max(1, row["question_bank_target"])
        row["question_bank_completion_percent"] = min(
            100.0,
            100.0 * row["questions"] / target,
        )
        return row

    async def question_bank_subjects(
        self,
        session: AsyncSession,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    subject.subject_code,
                    subject.subject_name,
                    COUNT(question.question_id) AS total_questions,
                    jsonb_build_object(
                        'easy', COUNT(*) FILTER (
                            WHERE question.difficulty_label = 'easy'
                        ),
                        'medium', COUNT(*) FILTER (
                            WHERE question.difficulty_label = 'medium'
                        ),
                        'hard', COUNT(*) FILTER (
                            WHERE question.difficulty_label = 'hard'
                        )
                    ) AS difficulty_distribution,
                    jsonb_build_object(
                        'remember', COUNT(*) FILTER (
                            WHERE question.bloom_level = 'remember'
                        ),
                        'understand', COUNT(*) FILTER (
                            WHERE question.bloom_level = 'understand'
                        ),
                        'apply', COUNT(*) FILTER (
                            WHERE question.bloom_level = 'apply'
                        ),
                        'analyze', COUNT(*) FILTER (
                            WHERE question.bloom_level = 'analyze'
                        ),
                        'evaluate', COUNT(*) FILTER (
                            WHERE question.bloom_level = 'evaluate'
                        )
                    ) AS bloom_distribution,
                    jsonb_build_object(
                        'draft', COUNT(*) FILTER (WHERE question.status = 'draft'),
                        'reviewed', COUNT(*) FILTER (
                            WHERE question.status = 'reviewed'
                        ),
                        'active', COUNT(*) FILTER (WHERE question.status = 'active'),
                        'retired', COUNT(*) FILTER (
                            WHERE question.status = 'retired'
                        )
                    ) AS status_distribution
                FROM subjects subject
                LEFT JOIN questions question ON question.subject_id = subject.subject_id
                GROUP BY subject.subject_id
                ORDER BY subject.subject_name
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def questions(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    question.question_code,
                    subject.subject_code,
                    subject.subject_name,
                    question.stem,
                    question.bloom_level,
                    question.difficulty_label,
                    question.status,
                    question.irt_status,
                    COUNT(DISTINCT option.answer_option_id) FILTER (
                        WHERE option.is_active = TRUE
                    ) AS option_count,
                    COALESCE(
                        ARRAY_AGG(DISTINCT unit.unit_name) FILTER (
                            WHERE unit.unit_name IS NOT NULL
                        ),
                        ARRAY[]::VARCHAR[]
                    ) AS knowledge_units
                FROM questions question
                JOIN subjects subject ON subject.subject_id = question.subject_id
                LEFT JOIN answer_options option
                    ON option.question_id = question.question_id
                LEFT JOIN question_knowledge_units question_unit
                    ON question_unit.question_id = question.question_id
                LEFT JOIN knowledge_units unit ON unit.unit_id = question_unit.unit_id
                GROUP BY question.question_id, subject.subject_id
                ORDER BY subject.subject_name, question.question_code
                LIMIT 1000
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

    async def account_exists(self, session: AsyncSession, username: str) -> bool:
        result = await session.execute(
            text("SELECT EXISTS(SELECT 1 FROM app_users WHERE username = :username)"),
            {"username": username},
        )
        return bool(result.scalar_one())

    async def ensure_student(
        self,
        session: AsyncSession,
        student_code: str,
        display_name: str,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO students (student_code, display_name, is_active)
                VALUES (:student_code, :display_name, TRUE)
                ON CONFLICT (student_code) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    is_active = TRUE
                RETURNING student_id
                """
            ),
            {"student_code": student_code, "display_name": display_name},
        )
        return result.scalar_one()

    async def create_account(
        self,
        session: AsyncSession,
        *,
        username: str,
        password_hash: str,
        display_name: str,
        role: str,
        student_id: int | None,
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                INSERT INTO app_users (
                    username, password_hash, display_name, role, student_id
                )
                VALUES (
                    :username, :password_hash, :display_name, :role, :student_id
                )
                RETURNING username, display_name, role, is_active
                """
            ),
            {
                "username": username,
                "password_hash": password_hash,
                "display_name": display_name,
                "role": role,
                "student_id": student_id,
            },
        )
        return dict(result.one()._mapping)

    async def update_account(
        self,
        session: AsyncSession,
        *,
        username: str,
        display_name: str | None,
        password_hash: str | None,
        is_active: bool | None,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                UPDATE app_users
                SET
                    display_name = COALESCE(:display_name, display_name),
                    password_hash = COALESCE(:password_hash, password_hash),
                    is_active = COALESCE(:is_active, is_active)
                WHERE username = :username
                RETURNING username, display_name, role, student_id, is_active
                """
            ),
            {
                "username": username,
                "display_name": display_name,
                "password_hash": password_hash,
                "is_active": is_active,
            },
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def student_code(
        self,
        session: AsyncSession,
        student_id: int | None,
    ) -> str | None:
        if student_id is None:
            return None
        result = await session.execute(
            text("SELECT student_code FROM students WHERE student_id = :student_id"),
            {"student_id": student_id},
        )
        return result.scalar_one_or_none()

    async def update_student_name(
        self,
        session: AsyncSession,
        student_id: int,
        display_name: str,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE students
                SET display_name = :display_name
                WHERE student_id = :student_id
                """
            ),
            {"student_id": student_id, "display_name": display_name},
        )
