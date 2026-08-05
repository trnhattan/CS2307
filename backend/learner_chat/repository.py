import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class LearnerChatRepository:
    async def config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text("SELECT prop_key, prop_value FROM sys_props WHERE prop_key LIKE 'LLM_%'")
        )
        return {row.prop_key: row.prop_value for row in result}

    async def subject_id(
        self, session: AsyncSession, subject_code: str | None
    ) -> int | None:
        if not subject_code:
            return None
        result = await session.execute(
            text(
                """
                SELECT subject_id FROM subjects
                WHERE subject_code = :subject_code AND is_active = TRUE
                """
            ),
            {"subject_code": subject_code.upper()},
        )
        return result.scalar_one_or_none()

    async def create_thread(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int | None,
        title: str,
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                INSERT INTO learner_chat_threads (student_id, subject_id, title)
                VALUES (:student_id, :subject_id, :title)
                RETURNING thread_id, title, status, created_at, updated_at
                """
            ),
            {"student_id": student_id, "subject_id": subject_id, "title": title},
        )
        return dict(result.one()._mapping)

    async def threads(
        self, session: AsyncSession, student_id: int
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT thread.thread_id, thread.title, subject.subject_code,
                       subject.subject_name, thread.status,
                       thread.created_at, thread.updated_at
                FROM learner_chat_threads thread
                LEFT JOIN subjects subject ON subject.subject_id = thread.subject_id
                WHERE thread.student_id = :student_id
                ORDER BY thread.updated_at DESC, thread.thread_id DESC
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]

    async def thread(
        self, session: AsyncSession, thread_id: int, student_id: int
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT thread.thread_id, thread.student_id, thread.subject_id,
                       thread.title, subject.subject_code, subject.subject_name,
                       thread.status, thread.created_at, thread.updated_at
                FROM learner_chat_threads thread
                LEFT JOIN subjects subject ON subject.subject_id = thread.subject_id
                WHERE thread.thread_id = :thread_id
                  AND thread.student_id = :student_id
                """
            ),
            {"thread_id": thread_id, "student_id": student_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def delete_thread(
        self,
        session: AsyncSession,
        *,
        thread_id: int,
        student_id: int,
    ) -> bool:
        result = await session.execute(
            text(
                """
                DELETE FROM learner_chat_threads
                WHERE thread_id = :thread_id
                  AND student_id = :student_id
                RETURNING thread_id
                """
            ),
            {"thread_id": thread_id, "student_id": student_id},
        )
        return result.scalar_one_or_none() is not None

    async def messages(
        self, session: AsyncSession, thread_id: int, limit: int | None = None
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT message.message_id, message.role, message.content,
                       message.intent, message.session_id, question.question_code,
                       message.evidence, message.limitations, message.model,
                       message.used_llm, message.provider_content,
                       message.reasoning_details, message.created_at
                FROM learner_chat_messages message
                LEFT JOIN questions question ON question.question_id = message.question_id
                WHERE message.thread_id = :thread_id
                ORDER BY message.created_at DESC, message.message_id DESC
                LIMIT COALESCE(CAST(:limit AS INTEGER), 2147483647)
                """
            ),
            {"thread_id": thread_id, "limit": limit},
        )
        return [dict(row._mapping) for row in reversed(result.all())]

    async def save_message(
        self,
        session: AsyncSession,
        *,
        thread_id: int,
        role: str,
        content: str,
        intent: str | None = None,
        session_id: int | None = None,
        question_id: int | None = None,
        evidence: list[str] | None = None,
        limitations: list[str] | None = None,
        model: str | None = None,
        used_llm: bool = False,
        provider_content: str | None = None,
        reasoning_details: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                INSERT INTO learner_chat_messages (
                    thread_id, role, content, intent, session_id, question_id,
                    evidence, limitations, model, used_llm,
                    provider_content, reasoning_details
                ) VALUES (
                    :thread_id, :role, :content, :intent, :session_id, :question_id,
                    CAST(:evidence AS JSONB), CAST(:limitations AS JSONB),
                    :model, :used_llm, :provider_content,
                    CAST(:reasoning_details AS JSONB)
                )
                RETURNING message_id, role, content, intent, session_id,
                          evidence, limitations, model, used_llm, created_at
                """
            ),
            {
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "intent": intent,
                "session_id": session_id,
                "question_id": question_id,
                "evidence": self._json(evidence or []),
                "limitations": self._json(limitations or []),
                "model": model,
                "used_llm": used_llm,
                "provider_content": provider_content,
                "reasoning_details": self._json(reasoning_details or []),
            },
        )
        await session.execute(
            text(
                """
                UPDATE learner_chat_threads SET updated_at = CURRENT_TIMESTAMP
                WHERE thread_id = :thread_id
                """
            ),
            {"thread_id": thread_id},
        )
        value = dict(result.one()._mapping)
        value["question_code"] = None
        return value

    async def answered_question(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        session_id: int | None,
        question_code: str | None,
    ) -> dict[str, Any] | None:
        if session_id is None and not question_code:
            return None
        result = await session.execute(
            text(
                """
                SELECT item.exam_item_id, item.session_id, item.order_no,
                       question.question_id,
                       question.question_code, item.stem_snapshot AS stem,
                       item.displayed_options, item.selected_option_code,
                       item.is_correct, question.explanation,
                       ARRAY_AGG(DISTINCT criterion.criterion_name) FILTER (
                           WHERE criterion.criterion_name IS NOT NULL
                       ) AS criteria
                FROM exam_sessions exam
                JOIN exam_items item ON item.session_id = exam.session_id
                JOIN questions question ON question.question_id = item.question_id
                LEFT JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                 AND link.unit_role IN ('primary_skill', 'supporting_skill')
                LEFT JOIN assessment_criteria criterion
                  ON criterion.knowledge_unit_id = link.unit_id
                WHERE exam.student_id = :student_id
                  AND exam.status = 'completed'
                  AND item.answered_at IS NOT NULL
                  AND (
                    CAST(:session_id AS BIGINT) IS NULL OR
                    exam.session_id = CAST(:session_id AS BIGINT)
                  )
                  AND (
                    CAST(:question_code AS VARCHAR) IS NULL OR
                    question.question_code = CAST(:question_code AS VARCHAR)
                  )
                GROUP BY item.exam_item_id, question.question_id
                ORDER BY item.answered_at DESC
                LIMIT 1
                """
            ),
            {
                "student_id": student_id,
                "session_id": session_id,
                "question_code": question_code.upper() if question_code else None,
            },
        )
        row = result.one_or_none()
        if row is None:
            return None
        value = dict(row._mapping)
        options = value.pop("displayed_options")
        selected = next(
            (
                option for option in options
                if option["option_code"] == value["selected_option_code"]
            ),
            None,
        )
        best = next((option for option in options if option["is_best_answer"]), None)
        value["answer_options"] = [
            {
                "option_code": option.get("option_code"),
                "option_text": option.get("option_text"),
            }
            for option in options
        ]
        value["selected_answer"] = selected["option_text"] if selected else None
        value["best_answer"] = best["option_text"] if best else None
        value["review_allowed"] = True
        return value

    async def learner_history(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int | None,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT subject.subject_code, subject.subject_name,
                       COUNT(DISTINCT exam.session_id) AS completed_tests,
                       ROUND(
                           100 * AVG(exam.total_score / NULLIF(exam.max_score, 0)), 1
                       ) AS average_score_percent,
                       ROUND(
                           100 * MAX(exam.total_score / NULLIF(exam.max_score, 0)), 1
                       ) AS best_score_percent,
                       ROUND(
                           100 * (
                               ARRAY_AGG(
                                   exam.total_score / NULLIF(exam.max_score, 0)
                                   ORDER BY exam.finished_at DESC NULLS LAST,
                                            exam.session_id DESC
                               ) FILTER (WHERE exam.session_id IS NOT NULL)
                           )[1], 1
                       ) AS latest_score_percent,
                       ability.mastery_probability,
                       ability.evidence_count AS answered_questions
                FROM subjects subject
                LEFT JOIN exam_sessions exam
                  ON exam.subject_id = subject.subject_id
                 AND exam.student_id = :student_id
                 AND exam.status = 'completed'
                LEFT JOIN student_abilities ability
                  ON ability.student_id = :student_id
                 AND ability.subject_id = subject.subject_id
                 AND ability.knowledge_unit_id IS NULL
                WHERE subject.is_active = TRUE
                  AND (
                    CAST(:subject_id AS BIGINT) IS NULL OR
                    subject.subject_id = CAST(:subject_id AS BIGINT)
                  )
                GROUP BY subject.subject_id, ability.ability_id
                ORDER BY subject.subject_name
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        return [dict(row._mapping) for row in result]

    async def completed_questions(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT item.exam_item_id, item.session_id, question.question_id,
                       question.question_code, item.stem_snapshot AS stem,
                       item.displayed_options, item.selected_option_code,
                       item.is_correct, question.explanation,
                       question.difficulty_label, item.answered_at,
                       subject.subject_code, subject.subject_name,
                       COALESCE(
                           ARRAY_AGG(DISTINCT criterion.criterion_code) FILTER (
                               WHERE criterion.criterion_code IS NOT NULL
                           ), ARRAY[]::VARCHAR[]
                       ) AS criterion_codes,
                       COALESCE(
                           ARRAY_AGG(DISTINCT criterion.criterion_name) FILTER (
                               WHERE criterion.criterion_name IS NOT NULL
                           ), ARRAY[]::VARCHAR[]
                       ) AS criteria
                FROM exam_sessions exam
                JOIN exam_items item ON item.session_id = exam.session_id
                JOIN questions question ON question.question_id = item.question_id
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                LEFT JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                 AND link.unit_role IN ('primary_skill', 'supporting_skill')
                LEFT JOIN assessment_criteria criterion
                  ON criterion.knowledge_unit_id = link.unit_id
                WHERE exam.student_id = :student_id
                  AND exam.status = 'completed'
                  AND item.answered_at IS NOT NULL
                  AND (
                    CAST(:subject_id AS BIGINT) IS NULL OR
                    exam.subject_id = CAST(:subject_id AS BIGINT)
                  )
                GROUP BY item.exam_item_id, question.question_id,
                         subject.subject_id
                ORDER BY item.answered_at DESC, item.exam_item_id DESC
                LIMIT :limit
                """
            ),
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "limit": limit,
            },
        )
        return [self._question_context(dict(row._mapping)) for row in result]

    async def knowledge_resources(
        self,
        session: AsyncSession,
        *,
        subject_id: int | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                WITH resources AS (
                    SELECT
                        'subject:' || subject.subject_code AS resource_id,
                        'subject' AS resource_type,
                        subject.subject_code,
                        subject.subject_name,
                        subject.subject_name AS title,
                        'An active assessment subject with structured topics, criteria, and questions.'
                            AS content,
                        NULL::VARCHAR AS question_code,
                        NULL::VARCHAR AS criterion_code,
                        NULL::VARCHAR AS difficulty_label,
                        NULL::VARCHAR AS bloom_level
                    FROM subjects subject
                    WHERE subject.is_active = TRUE
                      AND (
                        CAST(:subject_id AS BIGINT) IS NULL OR
                        subject.subject_id = CAST(:subject_id AS BIGINT)
                      )

                    UNION ALL

                    SELECT
                        'knowledge:' || document.document_code,
                        'subject_knowledge',
                        subject.subject_code,
                        subject.subject_name,
                        document.title,
                        document.content,
                        NULL::VARCHAR,
                        NULL::VARCHAR,
                        NULL::VARCHAR,
                        NULL::VARCHAR
                    FROM subject_knowledge_documents document
                    JOIN subjects subject ON subject.subject_id = document.subject_id
                    WHERE document.is_active = TRUE AND subject.is_active = TRUE
                      AND (
                        CAST(:subject_id AS BIGINT) IS NULL OR
                        subject.subject_id = CAST(:subject_id AS BIGINT)
                      )

                    UNION ALL

                    SELECT
                        'unit:' || unit.unit_code,
                        unit.unit_type,
                        subject.subject_code,
                        subject.subject_name,
                        unit.unit_name,
                        COALESCE(NULLIF(unit.description, ''),
                                 'Knowledge unit in ' || subject.subject_name),
                        NULL::VARCHAR,
                        NULL::VARCHAR,
                        NULL::VARCHAR,
                        NULL::VARCHAR
                    FROM knowledge_units unit
                    JOIN subjects subject ON subject.subject_id = unit.subject_id
                    WHERE unit.is_active = TRUE AND subject.is_active = TRUE
                      AND (
                        CAST(:subject_id AS BIGINT) IS NULL OR
                        subject.subject_id = CAST(:subject_id AS BIGINT)
                      )

                    UNION ALL

                    SELECT
                        'criterion:' || criterion.criterion_code,
                        'assessment_criterion',
                        subject.subject_code,
                        subject.subject_name,
                        criterion.criterion_name,
                        criterion.learning_objective || ' Success criterion: ' ||
                            criterion.success_statement,
                        NULL::VARCHAR,
                        criterion.criterion_code,
                        NULL::VARCHAR,
                        NULL::VARCHAR
                    FROM assessment_criteria criterion
                    JOIN subjects subject ON subject.subject_id = criterion.subject_id
                    WHERE criterion.is_active = TRUE AND subject.is_active = TRUE
                      AND (
                        CAST(:subject_id AS BIGINT) IS NULL OR
                        subject.subject_id = CAST(:subject_id AS BIGINT)
                      )

                    UNION ALL

                    SELECT
                        'question:' || question.question_code,
                        'question',
                        subject.subject_code,
                        subject.subject_name,
                        'Question ' || question.question_code,
                        question.stem || ' Measures: ' || COALESCE(
                            STRING_AGG(DISTINCT criterion.criterion_name, '; '),
                            'general subject knowledge'
                        ),
                        question.question_code,
                        NULL::VARCHAR,
                        question.difficulty_label,
                        question.bloom_level
                    FROM questions question
                    JOIN subjects subject ON subject.subject_id = question.subject_id
                    LEFT JOIN question_knowledge_units link
                      ON link.question_id = question.question_id
                     AND link.unit_role IN ('primary_skill', 'supporting_skill')
                    LEFT JOIN assessment_criteria criterion
                      ON criterion.knowledge_unit_id = link.unit_id
                    WHERE question.status IN ('active', 'reviewed')
                      AND subject.is_active = TRUE
                      AND (
                        CAST(:subject_id AS BIGINT) IS NULL OR
                        subject.subject_id = CAST(:subject_id AS BIGINT)
                      )
                    GROUP BY question.question_id, subject.subject_id
                )
                SELECT resource_id, resource_type, subject_code, subject_name,
                       title, content, question_code, criterion_code,
                       difficulty_label, bloom_level
                FROM resources
                ORDER BY
                    CASE resource_type
                        WHEN 'subject_knowledge' THEN 0
                        WHEN 'subject' THEN 1
                        WHEN 'topic' THEN 2
                        WHEN 'skill' THEN 3
                        WHEN 'assessment_criterion' THEN 4
                        ELSE 5
                    END,
                    subject_name,
                    title
                LIMIT :limit
                """
            ),
            {"subject_id": subject_id, "limit": limit},
        )
        return [dict(row._mapping) for row in result]

    @staticmethod
    def _question_context(value: dict[str, Any]) -> dict[str, Any]:
        options = value.pop("displayed_options") or []
        selected = next(
            (
                option for option in options
                if option.get("option_code") == value["selected_option_code"]
            ),
            None,
        )
        best = next((option for option in options if option.get("is_best_answer")), None)
        value["answer_options"] = [
            {
                "option_code": option.get("option_code"),
                "option_text": option.get("option_text"),
            }
            for option in options
        ]
        value["selected_answer"] = selected.get("option_text") if selected else None
        value["selected_answer_diagnosis"] = (
            selected.get("diagnosis") or selected.get("explanation")
            if selected else None
        )
        value["best_answer"] = best.get("option_text") if best else None
        value["best_answer_explanation"] = (
            best.get("explanation") if best else None
        )
        value["review_allowed"] = True
        return value

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
