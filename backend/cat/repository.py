import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CATRepository:
    async def config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(text("SELECT prop_key, prop_value FROM sys_props"))
        return {row.prop_key: row.prop_value for row in result}

    async def subject(self, session: AsyncSession, subject_code: str) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT subject_id, subject_code, subject_name
                FROM subjects
                WHERE subject_code = :code AND is_active = TRUE
                """
            ),
            {"code": subject_code},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def lock_start(
        self, session: AsyncSession, student_id: int, subject_id: int
    ) -> None:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"cat:{student_id}:{subject_id}"},
        )

    async def ability(
        self, session: AsyncSession, student_id: int, subject_id: int
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT theta, standard_error
                FROM student_abilities
                WHERE student_id = :student_id AND subject_id = :subject_id
                  AND knowledge_unit_id IS NULL
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def active_session(
        self, session: AsyncSession, student_id: int, subject_id: int
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT session_id
                FROM exam_sessions
                WHERE student_id = :student_id AND subject_id = :subject_id
                  AND mode = 'adaptive' AND status = 'in_progress'
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def candidates(
        self,
        session: AsyncSession,
        subject_id: int,
        excluded_ids: list[int],
        topic_codes: list[str] | None = None,
        skill_codes: list[str] | None = None,
        bloom_levels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT
                    question.question_id, question.question_code, question.stem,
                    question.version_no, question.difficulty_label,
                    question.difficulty_norm, question.bloom_level,
                    question.avg_time_sec, question.irt_a, question.irt_b,
                    question.irt_c,
                    COALESCE(
                        MAX(unit.unit_code) FILTER (WHERE link.unit_role = 'topic'),
                        'GENERAL'
                    ) AS topic_code,
                    COALESCE(
                        ARRAY_AGG(DISTINCT unit.unit_code) FILTER (
                            WHERE unit.unit_code IS NOT NULL
                              AND link.unit_role IN ('primary_skill', 'supporting_skill')
                        ), ARRAY[]::VARCHAR[]
                    ) AS unit_codes,
                    (SELECT COUNT(*) FROM exam_items exposure
                     WHERE exposure.question_id = question.question_id) AS exposure_count
                FROM questions question
                JOIN v_question_pool_validation validation
                  ON validation.question_id = question.question_id
                 AND validation.is_pool_valid = TRUE
                LEFT JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                LEFT JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                WHERE question.subject_id = :subject_id
                  AND question.status = 'active'
                  AND NOT (question.question_id = ANY(CAST(:excluded AS BIGINT[])))
                  AND (
                    COALESCE(cardinality(CAST(:bloom_levels AS VARCHAR[])), 0) = 0
                    OR question.bloom_level = ANY(CAST(:bloom_levels AS VARCHAR[]))
                  )
                  AND (
                    COALESCE(cardinality(CAST(:topic_codes AS VARCHAR[])), 0) = 0
                    OR EXISTS (
                        SELECT 1 FROM question_knowledge_units topic_link
                        JOIN knowledge_units topic_unit ON topic_unit.unit_id = topic_link.unit_id
                        WHERE topic_link.question_id = question.question_id
                          AND topic_link.unit_role = 'topic'
                          AND topic_unit.unit_code = ANY(CAST(:topic_codes AS VARCHAR[]))
                    )
                  )
                  AND (
                    COALESCE(cardinality(CAST(:skill_codes AS VARCHAR[])), 0) = 0
                    OR EXISTS (
                        SELECT 1 FROM question_knowledge_units skill_link
                        JOIN knowledge_units skill_unit ON skill_unit.unit_id = skill_link.unit_id
                        WHERE skill_link.question_id = question.question_id
                          AND skill_link.unit_role IN ('primary_skill', 'supporting_skill')
                          AND skill_unit.unit_code = ANY(CAST(:skill_codes AS VARCHAR[]))
                    )
                  )
                GROUP BY question.question_id
                ORDER BY question.question_code
                """
            ),
            {
                "subject_id": subject_id,
                "excluded": excluded_ids,
                "topic_codes": topic_codes or [],
                "skill_codes": skill_codes or [],
                "bloom_levels": bloom_levels or [],
            },
        )
        return [dict(row._mapping) for row in result]

    async def unit_mastery(
        self, session: AsyncSession, student_id: int, subject_id: int
    ) -> dict[str, float]:
        result = await session.execute(
            text(
                """
                SELECT unit.unit_code, ability.mastery_probability
                FROM student_abilities ability
                JOIN knowledge_units unit ON unit.unit_id = ability.knowledge_unit_id
                WHERE ability.student_id = :student_id
                  AND ability.subject_id = :subject_id
                  AND ability.knowledge_unit_id IS NOT NULL
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        return {
            row.unit_code: float(row.mastery_probability)
            for row in result
            if row.mastery_probability is not None
        }

    async def criterion_evidence(
        self, session: AsyncSession, student_id: int, subject_id: int
    ) -> dict[str, int]:
        result = await session.execute(
            text(
                """
                SELECT criterion.criterion_code,
                       COUNT(item.exam_item_id) FILTER (
                           WHERE exam.session_id IS NOT NULL
                       ) AS evidence_count
                FROM assessment_criteria criterion
                LEFT JOIN question_knowledge_units link
                  ON link.unit_id = criterion.knowledge_unit_id
                 AND link.unit_role IN ('primary_skill', 'supporting_skill')
                LEFT JOIN exam_items item ON item.question_id = link.question_id
                 AND item.answered_at IS NOT NULL
                LEFT JOIN exam_sessions exam ON exam.session_id = item.session_id
                 AND exam.student_id = :student_id
                 AND exam.status = 'completed'
                WHERE criterion.subject_id = :subject_id
                  AND criterion.is_active = TRUE
                GROUP BY criterion.criterion_id
                """
            ),
            {"student_id": student_id, "subject_id": subject_id},
        )
        return {row.criterion_code: int(row.evidence_count) for row in result}

    async def options(
        self, session: AsyncSession, question_id: int
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT option_code, option_text, score_weight, is_best_answer,
                       distractor_type, explanation, diagnosis
                FROM answer_options
                WHERE question_id = :question_id AND is_active = TRUE
                ORDER BY option_code
                """
            ),
            {"question_id": question_id},
        )
        return [dict(row._mapping) for row in result]

    async def create_session(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int,
        generation_config: dict[str, Any],
        theta: float,
        standard_error: float,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO exam_sessions (
                    student_id, subject_id, mode, generation_config,
                    theta_initial, theta_current, standard_error_current,
                    total_score, max_score
                )
                VALUES (
                    :student_id, :subject_id, 'adaptive',
                    CAST(:config AS JSONB), :theta, :theta, :se, 0, 0
                )
                RETURNING session_id
                """
            ),
            {
                "student_id": student_id,
                "subject_id": subject_id,
                "config": self._json(generation_config),
                "theta": theta,
                "se": standard_error,
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
        theta: float,
        information: float,
        reason: str,
        components: dict[str, float],
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO exam_items (
                    session_id, question_id, question_version, order_no,
                    stem_snapshot, displayed_options, selection_rule_code,
                    selection_reason, item_information, theta_before, scoring_detail
                )
                VALUES (
                    :session_id, :question_id, :version_no, :order_no,
                    :stem, CAST(:options AS JSONB), 'R_CAT_WEIGHTED_SELECTION',
                    :reason, :information, :theta,
                    CAST(:components AS JSONB)
                )
                RETURNING exam_item_id
                """
            ),
            {
                "session_id": session_id,
                "question_id": question["question_id"],
                "version_no": question["version_no"],
                "order_no": order_no,
                "stem": question["stem"],
                "options": self._json(displayed_options),
                "reason": reason,
                "information": information,
                "theta": theta,
                "components": self._json({"selection_components": components}),
            },
        )
        return result.scalar_one()

    async def session_for_update(
        self, session: AsyncSession, session_id: int
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT exam.session_id, exam.student_id, exam.subject_id,
                       exam.status, exam.mode, exam.generation_config,
                       exam.theta_initial, exam.theta_current,
                       exam.standard_error_current, exam.total_score,
                       student.student_code, student.display_name AS student_name,
                       subject.subject_code, subject.subject_name
                FROM exam_sessions exam
                JOIN students student ON student.student_id = exam.student_id
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                WHERE exam.session_id = :session_id
                FOR UPDATE OF exam
                """
            ),
            {"session_id": session_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def current_item(
        self, session: AsyncSession, session_id: int, *, lock: bool = False
    ) -> dict[str, Any] | None:
        suffix = " FOR UPDATE OF item" if lock else ""
        result = await session.execute(
            text(
                """
                SELECT item.exam_item_id, item.question_id, item.order_no,
                       item.stem_snapshot AS stem, item.displayed_options,
                       question.question_code, question.irt_a, question.irt_b,
                       question.irt_c
                FROM exam_items item
                JOIN questions question ON question.question_id = item.question_id
                WHERE item.session_id = :session_id AND item.answered_at IS NULL
                ORDER BY item.order_no
                LIMIT 1
                """ + suffix
            ),
            {"session_id": session_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def responses(self, session: AsyncSession, session_id: int) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT question.irt_a, question.irt_b, question.irt_c,
                       item.is_correct
                FROM exam_items item
                JOIN questions question ON question.question_id = item.question_id
                WHERE item.session_id = :session_id AND item.answered_at IS NOT NULL
                ORDER BY item.order_no
                """
            ),
            {"session_id": session_id},
        )
        return [dict(row._mapping) for row in result]

    async def answer_item(
        self,
        session: AsyncSession,
        *,
        item: dict[str, Any],
        selected_option_code: str,
        is_correct: bool,
        awarded_score: float,
        response_time_sec: int,
        theta: float,
        standard_error: float,
    ) -> bool:
        detail = {
            "model": "IRT-3PL-EAP",
            "binary_irt_response": int(is_correct),
            "awarded_score": awarded_score,
        }
        result = await session.execute(
            text(
                """
                UPDATE exam_items
                SET selected_option_code = :option_code,
                    is_correct = :is_correct,
                    awarded_score = :score,
                    irt_response = :irt_response,
                    response_time_sec = :response_time,
                    theta_after = :theta,
                    standard_error_after = :se,
                    scoring_detail = scoring_detail || CAST(:detail AS JSONB),
                    answered_at = CURRENT_TIMESTAMP
                WHERE exam_item_id = :item_id AND answered_at IS NULL
                """
            ),
            {
                "item_id": item["exam_item_id"],
                "option_code": selected_option_code,
                "is_correct": is_correct,
                "score": awarded_score,
                "irt_response": int(is_correct),
                "response_time": response_time_sec,
                "theta": theta,
                "se": standard_error,
                "detail": self._json(detail),
            },
        )
        return result.rowcount == 1

    async def used_question_ids(self, session: AsyncSession, session_id: int) -> list[int]:
        result = await session.execute(
            text("SELECT question_id FROM exam_items WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        return list(result.scalars())

    async def difficulty_usage(self, session: AsyncSession, session_id: int) -> dict[str, int]:
        result = await session.execute(
            text(
                """
                SELECT question.difficulty_label, COUNT(*) AS count
                FROM exam_items item
                JOIN questions question ON question.question_id = item.question_id
                WHERE item.session_id = :session_id
                GROUP BY question.difficulty_label
                """
            ),
            {"session_id": session_id},
        )
        return {row.difficulty_label: row.count for row in result}

    async def theta_history(self, session: AsyncSession, session_id: int) -> list[float]:
        result = await session.execute(
            text(
                """
                SELECT theta_after
                FROM exam_items
                WHERE session_id = :session_id AND theta_after IS NOT NULL
                ORDER BY order_no
                """
            ),
            {"session_id": session_id},
        )
        return [float(value) for value in result.scalars()]

    async def counts(self, session: AsyncSession, session_id: int) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*) FILTER (WHERE answered_at IS NOT NULL) AS answered,
                       COALESCE(SUM(awarded_score) FILTER (
                           WHERE answered_at IS NOT NULL
                       ), 0) AS total_score
                FROM exam_items
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        return dict(result.one()._mapping)

    async def update_progress(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        theta: float,
        standard_error: float,
        total_score: float,
        answered_count: int,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE exam_sessions
                SET theta_current = :theta, standard_error_current = :se,
                    total_score = :score, max_score = :answered_count
                WHERE session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
                "theta": theta,
                "se": standard_error,
                "score": total_score,
                "answered_count": answered_count,
            },
        )

    async def complete(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        total_score: float,
        answered_count: int,
        theta: float,
        standard_error: float,
        stop_reason: str,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE exam_sessions
                SET status = 'completed', total_score = :score,
                    max_score = :maximum, theta_current = :theta,
                    standard_error_current = :se, finished_at = CURRENT_TIMESTAMP,
                    generation_config = generation_config ||
                        jsonb_build_object('stop_reason', CAST(:reason AS TEXT))
                WHERE session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
                "score": total_score,
                "maximum": answered_count,
                "theta": theta,
                "se": standard_error,
                "reason": stop_reason,
            },
        )

    async def result(self, session: AsyncSession, session_id: int) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT exam.session_id, exam.student_id, exam.status,
                       subject.subject_code, subject.subject_name,
                       exam.total_score, exam.max_score,
                       exam.generation_config ->> 'stop_reason' AS stop_reason,
                       COUNT(item.exam_item_id) FILTER (
                           WHERE item.answered_at IS NOT NULL
                       ) AS answered_count
                FROM exam_sessions exam
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                LEFT JOIN exam_items item ON item.session_id = exam.session_id
                WHERE exam.session_id = :session_id AND exam.mode = 'adaptive'
                GROUP BY exam.session_id, subject.subject_id
                """
            ),
            {"session_id": session_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def staff_detail(self, session: AsyncSession, session_id: int) -> dict[str, Any] | None:
        exam = await self.session_for_update(session, session_id)
        if exam is None or exam["mode"] != "adaptive":
            return None
        result = await session.execute(
            text(
                """
                SELECT item.order_no, question.question_code, item.is_correct,
                       item.theta_before, item.theta_after,
                       item.standard_error_after,
                       COALESCE(item.item_information, 0) AS item_information,
                       COALESCE(item.selection_reason, '') AS selection_reason,
                       item.scoring_detail
                FROM exam_items item
                JOIN questions question ON question.question_id = item.question_id
                WHERE item.session_id = :session_id
                ORDER BY item.order_no
                """
            ),
            {"session_id": session_id},
        )
        exam["standard_error"] = exam.pop("standard_error_current")
        exam["items"] = [dict(row._mapping) for row in result]
        return exam

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
