import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ExamRepository:
    async def get_config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(text("SELECT prop_key, prop_value FROM sys_props"))
        return {row.prop_key: row.prop_value for row in result}

    async def list_subjects(
        self,
        session: AsyncSession,
        statuses: list[str],
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    s.subject_code,
                    s.subject_name,
                    s.description,
                    COUNT(q.question_id) FILTER (
                        WHERE q.status = ANY(CAST(:statuses AS VARCHAR[]))
                          AND validation.is_pool_valid
                    ) AS available_questions
                FROM subjects s
                LEFT JOIN questions q ON q.subject_id = s.subject_id
                LEFT JOIN v_question_pool_validation validation
                    ON validation.question_id = q.question_id
                WHERE s.is_active
                GROUP BY s.subject_id
                ORDER BY s.subject_name
                """
            ),
            {"statuses": statuses},
        )
        return [dict(row._mapping) for row in result]

    async def ensure_student(
        self,
        session: AsyncSession,
        student_code: str,
        display_name: str,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO students (student_code, display_name)
                VALUES (:student_code, :display_name)
                ON CONFLICT (student_code) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    is_active = TRUE
                RETURNING student_id
                """
            ),
            {"student_code": student_code, "display_name": display_name},
        )
        return result.scalar_one()

    async def get_subject(
        self,
        session: AsyncSession,
        subject_code: str,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT subject_id, subject_code, subject_name
                FROM subjects
                WHERE subject_code = :subject_code AND is_active
                """
            ),
            {"subject_code": subject_code},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def get_ability(
        self,
        session: AsyncSession,
        student_id: int,
        subject_id: int,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT theta, standard_error, evidence_count
                FROM student_abilities
                WHERE student_id = :student_id
                  AND subject_id = :subject_id
                  AND knowledge_unit_id IS NULL
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def get_candidates(
        self,
        session: AsyncSession,
        subject_id: int,
        statuses: list[str],
        topic_codes: list[str] | None = None,
        skill_codes: list[str] | None = None,
        bloom_levels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    q.question_id,
                    q.question_code,
                    q.stem,
                    q.bloom_level,
                    q.difficulty_label,
                    q.avg_time_sec,
                    q.irt_a,
                    q.irt_b,
                    q.irt_c,
                    q.version_no,
                    COALESCE(
                        MAX(unit.unit_name) FILTER (WHERE link.unit_role = 'topic'),
                        'Combined topic'
                    ) AS topic_name,
                    COALESCE(
                        MAX(unit.unit_code) FILTER (WHERE link.unit_role = 'topic'),
                        'GENERAL'
                    ) AS topic_code,
                    COALESCE(
                        ARRAY_AGG(DISTINCT unit.unit_code) FILTER (
                            WHERE link.unit_role IN ('primary_skill', 'supporting_skill')
                        ), ARRAY[]::VARCHAR[]
                    ) AS skill_codes
                FROM questions q
                JOIN v_question_pool_validation validation
                    ON validation.question_id = q.question_id
                   AND validation.is_pool_valid
                LEFT JOIN question_knowledge_units link
                    ON link.question_id = q.question_id
                LEFT JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                WHERE q.subject_id = :subject_id
                  AND q.status = ANY(CAST(:statuses AS VARCHAR[]))
                  AND (
                    COALESCE(cardinality(CAST(:bloom_levels AS VARCHAR[])), 0) = 0
                    OR q.bloom_level = ANY(CAST(:bloom_levels AS VARCHAR[]))
                  )
                  AND (
                    COALESCE(cardinality(CAST(:topic_codes AS VARCHAR[])), 0) = 0
                    OR EXISTS (
                        SELECT 1 FROM question_knowledge_units topic_link
                        JOIN knowledge_units topic_unit ON topic_unit.unit_id = topic_link.unit_id
                        WHERE topic_link.question_id = q.question_id
                          AND topic_link.unit_role = 'topic'
                          AND topic_unit.unit_code = ANY(CAST(:topic_codes AS VARCHAR[]))
                    )
                  )
                  AND (
                    COALESCE(cardinality(CAST(:skill_codes AS VARCHAR[])), 0) = 0
                    OR EXISTS (
                        SELECT 1 FROM question_knowledge_units skill_link
                        JOIN knowledge_units skill_unit ON skill_unit.unit_id = skill_link.unit_id
                        WHERE skill_link.question_id = q.question_id
                          AND skill_link.unit_role IN ('primary_skill', 'supporting_skill')
                          AND skill_unit.unit_code = ANY(CAST(:skill_codes AS VARCHAR[]))
                    )
                  )
                GROUP BY q.question_id
                ORDER BY q.question_code
                """
            ),
            {
                "subject_id": subject_id,
                "statuses": statuses,
                "topic_codes": topic_codes or [],
                "skill_codes": skill_codes or [],
                "bloom_levels": bloom_levels or [],
            },
        )
        return [dict(row._mapping) for row in result]

    async def get_options(
        self,
        session: AsyncSession,
        question_ids: list[int],
    ) -> dict[int, list[dict[str, Any]]]:
        result = await session.execute(
            text(
                """
                SELECT
                    question_id,
                    option_code,
                    option_text,
                    score_weight,
                    is_best_answer,
                    distractor_type,
                    explanation,
                    diagnosis
                FROM answer_options
                WHERE question_id = ANY(CAST(:question_ids AS BIGINT[]))
                  AND is_active
                ORDER BY question_id, option_code
                """
            ),
            {"question_ids": question_ids},
        )
        options: dict[int, list[dict[str, Any]]] = {}
        for row in result:
            options.setdefault(row.question_id, []).append(dict(row._mapping))
        return options

    async def create_session(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int,
        generation_config: dict[str, Any],
        seed: int,
        theta: float,
        standard_error: float,
        question_count: int,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO exam_sessions (
                    student_id, subject_id, mode, generation_config, random_seed,
                    theta_initial, theta_current, standard_error_current,
                    max_score
                )
                VALUES (
                    :student_id, :subject_id, 'fixed', CAST(:generation_config AS JSONB),
                    :random_seed, :theta, :theta, :standard_error, :max_score
                )
                RETURNING session_id
                """
            ),
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "generation_config": self._json(generation_config),
                "random_seed": seed,
                "theta": theta,
                "standard_error": standard_error,
                "max_score": question_count,
            },
        )
        return result.scalar_one()

    async def create_item(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        question: dict[str, Any],
        order_no: int,
        displayed_options: list[dict[str, Any]],
        selection_reason: str,
        information: float,
        theta: float,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO exam_items (
                    session_id, question_id, question_version, order_no,
                    stem_snapshot, displayed_options, selection_rule_code,
                    selection_reason, item_information, theta_before
                )
                VALUES (
                    :session_id, :question_id, :question_version, :order_no,
                    :stem, CAST(:displayed_options AS JSONB), 'R_GEN_IRT_BALANCED',
                    :selection_reason, :information, :theta
                )
                RETURNING exam_item_id
                """
            ),
            {
                "session_id": session_id,
                "question_id": question["question_id"],
                "question_version": question["version_no"],
                "order_no": order_no,
                "stem": question["stem"],
                "displayed_options": self._json(displayed_options),
                "selection_reason": selection_reason,
                "information": information,
                "theta": theta,
            },
        )
        return result.scalar_one()

    async def create_generation_trace(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        subject_code: str,
        question_count: int,
        theta: float,
        steps: list[dict[str, Any]],
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO inference_traces (
                    session_id, strategy, goal, initial_facts, derived_facts,
                    steps, status, finished_at
                )
                VALUES (
                    :session_id, 'forward', CAST(:goal AS JSONB),
                    CAST(:initial_facts AS JSONB), CAST(:derived_facts AS JSONB),
                    CAST(:steps AS JSONB), 'completed', CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "session_id": session_id,
                "goal": self._json(
                    {
                        "predicate": "exam_generated_with_constraints",
                        "subject_code": subject_code,
                    }
                ),
                "initial_facts": self._json(
                    [
                        {"predicate": "requested_count", "value": question_count},
                        {"predicate": "student_theta", "value": theta},
                    ]
                ),
                "derived_facts": self._json(
                    [
                        {
                            "predicate": "exam_generated_with_constraints",
                            "value": True,
                        }
                    ]
                ),
                "steps": self._json(steps),
            },
        )

    async def get_session_for_update(
        self,
        session: AsyncSession,
        session_id: int,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT
                    exam.session_id,
                    exam.student_id,
                    exam.subject_id,
                    exam.status,
                    exam.theta_initial,
                    exam.standard_error_current,
                    student.student_code,
                    subject.subject_code
                FROM exam_sessions exam
                JOIN students student ON student.student_id = exam.student_id
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                WHERE exam.session_id = :session_id
                FOR UPDATE
                """
            ),
            {"session_id": session_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def get_session_items(
        self,
        session: AsyncSession,
        session_id: int,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    item.exam_item_id,
                    item.question_id,
                    item.displayed_options,
                    question.question_code,
                    question.stem,
                    question.explanation,
                    question.irt_a,
                    question.irt_b,
                    question.irt_c
                FROM exam_items item
                JOIN questions question ON question.question_id = item.question_id
                WHERE item.session_id = :session_id
                ORDER BY item.order_no
                """
            ),
            {"session_id": session_id},
        )
        return [dict(row._mapping) for row in result]

    async def update_item_response(
        self,
        session: AsyncSession,
        *,
        exam_item_id: int,
        option_code: str,
        is_correct: bool,
        awarded_score: float,
        response_time_sec: int,
        theta_after: float,
        standard_error_after: float,
        scoring_detail: dict[str, Any],
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE exam_items
                SET selected_option_code = :option_code,
                    is_correct = :is_correct,
                    awarded_score = :awarded_score,
                    irt_response = :irt_response,
                    response_time_sec = :response_time_sec,
                    theta_after = :theta_after,
                    standard_error_after = :standard_error_after,
                    scoring_detail = CAST(:scoring_detail AS JSONB),
                    answered_at = CURRENT_TIMESTAMP
                WHERE exam_item_id = :exam_item_id
                """
            ),
            {
                "exam_item_id": exam_item_id,
                "option_code": option_code,
                "is_correct": is_correct,
                "awarded_score": awarded_score,
                "irt_response": int(is_correct),
                "response_time_sec": response_time_sec,
                "theta_after": theta_after,
                "standard_error_after": standard_error_after,
                "scoring_detail": self._json(scoring_detail),
            },
        )

    async def complete_session(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        total_score: float,
        theta: float,
        standard_error: float,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE exam_sessions
                SET status = 'completed',
                    total_score = :total_score,
                    theta_current = :theta,
                    standard_error_current = :standard_error,
                    finished_at = CURRENT_TIMESTAMP
                WHERE session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
                "total_score": total_score,
                "theta": theta,
                "standard_error": standard_error,
            },
        )

    async def create_scoring_trace(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        theta_before: float,
        theta_after: float,
        steps: list[dict[str, Any]],
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO inference_traces (
                    session_id, strategy, goal, initial_facts, derived_facts,
                    steps, status, finished_at
                )
                VALUES (
                    :session_id, 'forward', CAST(:goal AS JSONB),
                    CAST(:initial_facts AS JSONB), CAST(:derived_facts AS JSONB),
                    CAST(:steps AS JSONB), 'completed', CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "session_id": session_id,
                "goal": self._json({"predicate": "updated_theta"}),
                "initial_facts": self._json(
                    [{"predicate": "theta_before", "value": theta_before}]
                ),
                "derived_facts": self._json(
                    [{"predicate": "updated_theta", "value": theta_after}]
                ),
                "steps": self._json(steps),
            },
        )

    async def upsert_ability(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int,
        theta: float,
        standard_error: float,
        mastery: float,
        evidence_increment: int,
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO student_abilities (
                    student_id, subject_id, knowledge_unit_id, theta,
                    standard_error, mastery_probability, evidence_count
                )
                VALUES (
                    :student_id, :subject_id, NULL, :theta,
                    :standard_error, :mastery, :evidence_increment
                )
                ON CONFLICT (student_id, subject_id, knowledge_unit_id)
                DO UPDATE SET
                    theta = EXCLUDED.theta,
                    standard_error = EXCLUDED.standard_error,
                    mastery_probability = EXCLUDED.mastery_probability,
                    evidence_count = student_abilities.evidence_count + :evidence_increment
                """
            ),
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "theta": theta,
                "standard_error": standard_error,
                "mastery": mastery,
                "evidence_increment": evidence_increment,
            },
        )

    async def record_selected_option_fact(
        self,
        session: AsyncSession,
        *,
        student_code: str,
        session_id: int,
        question_code: str,
        option_code: str,
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO kb_facts (
                    fact_type, subject_ref, predicate_code, object_ref,
                    fact_args, confidence, is_inferred, source, created_by, provenance
                )
                VALUES (
                    'binary_relation', :subject_ref, 'selected_option', :object_ref,
                    CAST(:fact_args AS JSONB), 1, FALSE, 'exam_response', :student_code,
                    CAST(:provenance AS JSONB)
                )
                ON CONFLICT (fact_type, predicate_code, (fact_args::TEXT))
                DO UPDATE SET provenance = EXCLUDED.provenance
                """
            ),
            {
                "subject_ref": f"{student_code}@{session_id}",
                "object_ref": f"{question_code}:{option_code}",
                "fact_args": self._json(
                    [f"{student_code}@{session_id}", f"{question_code}:{option_code}"]
                ),
                "student_code": student_code,
                "provenance": self._json(
                    {
                        "session_id": session_id,
                        "question_code": question_code,
                        "option_code": option_code,
                    }
                ),
            },
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
