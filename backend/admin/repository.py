from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AdminRepository:
    async def question_detail(
        self, session: AsyncSession, question_code: str
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT question.question_id, question.question_code,
                       subject.subject_code, question.stem, question.bloom_level,
                       question.difficulty_label, question.difficulty_norm,
                       question.avg_time_sec, question.explanation,
                       question.irt_a, question.irt_b, question.irt_c,
                       question.irt_status, question.status, question.source,
                       question.reviewed_by, question.reviewed_at,
                       question.provenance
                FROM questions question
                JOIN subjects subject ON subject.subject_id = question.subject_id
                WHERE question.question_code = :question_code
                """
            ),
            {"question_code": question_code},
        )
        row = result.one_or_none()
        if row is None:
            return None
        question = dict(row._mapping)
        question_id = question.pop("question_id")
        options = await session.execute(
            text(
                """
                SELECT option_code, option_text, score_weight,
                       is_best_answer, is_active
                FROM answer_options
                WHERE question_id = :question_id
                ORDER BY option_code
                """
            ),
            {"question_id": question_id},
        )
        units = await session.execute(
            text(
                """
                SELECT unit.unit_code, unit.unit_name, unit.unit_type,
                       link.unit_role, link.measurement_weight
                FROM question_knowledge_units link
                JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                WHERE link.question_id = :question_id
                ORDER BY link.unit_role, unit.unit_code
                """
            ),
            {"question_id": question_id},
        )
        question["options"] = [dict(value._mapping) for value in options]
        question["knowledge_units"] = [dict(value._mapping) for value in units]
        return question

    async def validation_data(
        self, session: AsyncSession, question_code: str
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT question.question_id, question.question_code,
                       question.stem, question.bloom_level,
                       question.difficulty_label, question.difficulty_norm,
                       question.avg_time_sec, question.explanation,
                       question.irt_a, question.irt_b, question.irt_c,
                       question.irt_status, question.source, question.provenance,
                       validation.actual_pool_size,
                       validation.expected_pool_size,
                       validation.active_best_count,
                       validation.is_pool_valid,
                       (
                           SELECT COUNT(*)
                           FROM answer_options option
                           WHERE option.question_id = question.question_id
                             AND option.is_active
                             AND (
                                 trim(option.option_text) = '' OR
                                 (option.is_best_answer AND option.score_weight <> 1)
                             )
                       ) AS invalid_option_count,
                       COUNT(DISTINCT link.unit_id) FILTER (
                           WHERE link.unit_role = 'topic'
                       ) AS topic_count,
                       COUNT(DISTINCT link.unit_id) FILTER (
                           WHERE link.unit_role = 'primary_skill'
                       ) AS primary_skill_count,
                       EXISTS (
                           SELECT 1 FROM questions duplicate
                           WHERE duplicate.question_id <> question.question_id
                             AND lower(regexp_replace(trim(duplicate.stem), '\\s+', ' ', 'g')) =
                                 lower(regexp_replace(trim(question.stem), '\\s+', ' ', 'g'))
                       ) AS duplicate_stem
                       ,(
                           SELECT ARRAY_AGG(duplicate.stem)
                           FROM questions duplicate
                           WHERE duplicate.question_id <> question.question_id
                       ) AS other_stems
                       ,(
                           SELECT COUNT(*) - COUNT(DISTINCT lower(
                               regexp_replace(trim(option.option_text), '\\s+', ' ', 'g')
                           ))
                           FROM answer_options option
                           WHERE option.question_id = question.question_id
                             AND option.is_active
                       ) AS duplicate_option_count
                FROM questions question
                LEFT JOIN v_question_pool_validation validation
                  ON validation.question_id = question.question_id
                LEFT JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                WHERE question.question_code = :question_code
                GROUP BY question.question_id, validation.question_id,
                         validation.actual_pool_size, validation.expected_pool_size,
                         validation.active_best_count, validation.is_pool_valid
                """
            ),
            {"question_code": question_code},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def question_codes(self, session: AsyncSession) -> list[str]:
        result = await session.execute(
            text("SELECT question_code FROM questions ORDER BY question_code")
        )
        return list(result.scalars())

    async def update_question_metadata(
        self,
        session: AsyncSession,
        question_code: str,
        changes: dict[str, Any],
        actor: str,
    ) -> None:
        allowed = {
            "stem", "bloom_level", "difficulty_label", "difficulty_norm",
            "avg_time_sec", "explanation", "irt_a", "irt_b", "irt_c",
            "irt_status", "source",
        }
        fields = [name for name in changes if name in allowed]
        assignments = ", ".join(f"{name} = :{name}" for name in fields)
        await session.execute(
            text(
                f"""
                UPDATE questions
                SET {assignments}, status = 'draft', reviewed_by = NULL,
                    reviewed_at = NULL, version_no = version_no + 1,
                    provenance = provenance || jsonb_build_object(
                        'last_admin_edit', jsonb_build_object(
                            'actor', CAST(:actor AS TEXT),
                            'at', CURRENT_TIMESTAMP
                        )
                    )
                WHERE question_code = :question_code
                """
            ),
            {
                "question_code": question_code,
                "actor": actor,
                **{name: changes[name] for name in fields},
            },
        )

    async def mark_reviewed(
        self,
        session: AsyncSession,
        question_code: str,
        reviewer: str,
        validation_report: dict[str, Any],
        valid: bool,
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                UPDATE questions
                SET status = CASE WHEN :valid THEN 'reviewed' ELSE 'draft' END,
                    reviewed_by = :reviewer,
                    reviewed_at = CURRENT_TIMESTAMP,
                    provenance = provenance || jsonb_build_object(
                        'deterministic_review', CAST(:report AS JSONB)
                    )
                WHERE question_code = :question_code
                RETURNING status, reviewed_by, reviewed_at
                """
            ),
            {
                "question_code": question_code,
                "reviewer": reviewer,
                "valid": valid,
                "report": self._json(validation_report),
            },
        )
        return dict(result.one()._mapping)

    async def activate_question(
        self, session: AsyncSession, question_code: str, reviewer: str
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE questions
                SET status = 'active', reviewed_by = :reviewer,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE question_code = :question_code
                """
            ),
            {"question_code": question_code, "reviewer": reviewer},
        )

    async def readiness(self, session: AsyncSession) -> dict[str, Any]:
        config = await session.execute(
            text(
                """
                SELECT
                    COALESCE(MAX((prop_value #>> '{}')::INTEGER) FILTER (
                        WHERE prop_key = 'QUESTION_BANK_TARGET_SIZE'
                    ), 200) AS target,
                    COALESCE(MAX((prop_value #>> '{}')::INTEGER) FILTER (
                        WHERE prop_key = 'CAT_MIN_QUESTION_COUNT'
                    ), 10) AS cat_minimum
                FROM sys_props
                """
            )
        )
        settings = config.one()
        totals = await session.execute(
            text(
                """
                SELECT COUNT(*) AS total_questions,
                       COUNT(*) FILTER (WHERE status = 'active') AS active_questions,
                       COUNT(*) FILTER (
                           WHERE validation.is_pool_valid IS NOT TRUE
                              OR explanation IS NULL OR trim(explanation) = ''
                              OR source IS NULL OR trim(source) = ''
                       ) AS invalid_questions
                FROM questions question
                LEFT JOIN v_question_pool_validation validation
                  ON validation.question_id = question.question_id
                """
            )
        )
        summary = dict(totals.one()._mapping)
        subjects = await session.execute(
            text(
                """
                SELECT subject.subject_code,
                       COUNT(DISTINCT question.question_id) AS total_questions,
                       COUNT(DISTINCT question.question_id) FILTER (
                           WHERE question.status = 'active' AND validation.is_pool_valid
                       ) AS active_questions,
                       COUNT(DISTINCT unit.unit_id) FILTER (
                           WHERE unit.unit_type = 'topic'
                       ) AS topic_count,
                       COUNT(DISTINCT question.bloom_level) AS bloom_coverage,
                       COUNT(DISTINCT question.difficulty_label) AS difficulty_coverage
                FROM subjects subject
                LEFT JOIN questions question ON question.subject_id = subject.subject_id
                LEFT JOIN v_question_pool_validation validation
                  ON validation.question_id = question.question_id
                LEFT JOIN knowledge_units unit ON unit.subject_id = subject.subject_id
                GROUP BY subject.subject_id
                ORDER BY subject.subject_code
                """
            )
        )
        summary["target"] = int(settings.target)
        summary["cat_minimum"] = int(settings.cat_minimum)
        summary["subjects"] = [dict(row._mapping) for row in subjects]
        return summary

    @staticmethod
    def _json(value: Any) -> str:
        import json

        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

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
