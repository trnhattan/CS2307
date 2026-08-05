from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeGraphRepository:
    async def subjects(
        self, session: AsyncSession, student_id: int
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                WITH completed AS (
                    SELECT subject_id, COUNT(*) AS completed_tests
                    FROM exam_sessions
                    WHERE student_id = :student_id AND status = 'completed'
                    GROUP BY subject_id
                )
                SELECT subject.subject_id, subject.subject_code,
                       subject.subject_name,
                       COALESCE(completed.completed_tests, 0) AS completed_tests,
                       ability.mastery_probability,
                       ability.evidence_count
                FROM subjects subject
                LEFT JOIN completed ON completed.subject_id = subject.subject_id
                LEFT JOIN student_abilities ability
                  ON ability.student_id = :student_id
                 AND ability.subject_id = subject.subject_id
                 AND ability.knowledge_unit_id IS NULL
                WHERE subject.is_active = TRUE
                ORDER BY subject.subject_name
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]

    async def config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT prop_key, prop_value
                FROM sys_props
                WHERE prop_key IN (
                    'PROFILE_GRAPH_MIN_TESTS',
                    'PROFILE_NEEDS_REVIEW_THRESHOLD',
                    'PROFILE_DEVELOPING_THRESHOLD',
                    'PROFILE_MASTERY_THRESHOLD'
                )
                """
            )
        )
        return {row.prop_key: row.prop_value for row in result}

    async def criteria(
        self, session: AsyncSession, student_id: int
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                WITH evidence AS (
                    SELECT criterion.criterion_id,
                           COUNT(item.exam_item_id) AS evidence_count,
                           100 * AVG(CASE WHEN item.is_correct THEN 1.0 ELSE 0.0 END)
                               AS accuracy_percent
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
                SELECT criterion.criterion_id, criterion.criterion_code,
                       criterion.criterion_name, criterion.learning_objective,
                       criterion.success_statement, criterion.mastery_threshold,
                       criterion.display_order, subject.subject_code,
                       subject.subject_name, ability.theta, ability.standard_error,
                       ability.mastery_probability,
                       COALESCE(evidence.evidence_count, 0) AS evidence_count,
                       evidence.accuracy_percent
                FROM assessment_criteria criterion
                JOIN subjects subject ON subject.subject_id = criterion.subject_id
                LEFT JOIN student_abilities ability
                  ON ability.student_id = :student_id
                 AND ability.knowledge_unit_id = criterion.knowledge_unit_id
                LEFT JOIN evidence ON evidence.criterion_id = criterion.criterion_id
                WHERE criterion.is_active = TRUE AND subject.is_active = TRUE
                ORDER BY subject.subject_name, criterion.display_order,
                         criterion.criterion_name
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]

    async def student(self, session: AsyncSession, student_id: int) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT student_id, student_code, display_name
                FROM students
                WHERE student_id = :student_id AND is_active = TRUE
                """
            ),
            {"student_id": student_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def abilities(self, session: AsyncSession, student_id: int) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT ability.ability_id, ability.subject_id,
                       subject.subject_code, subject.subject_name,
                       ability.knowledge_unit_id, unit.unit_code, unit.unit_name,
                       unit.unit_type, unit.parent_unit_id, parent.unit_code AS parent_code,
                       parent.unit_name AS parent_name, parent.unit_type AS parent_type,
                       ability.theta, ability.standard_error,
                       ability.mastery_probability, ability.evidence_count,
                       ability.updated_at
                FROM student_abilities ability
                JOIN subjects subject ON subject.subject_id = ability.subject_id
                LEFT JOIN knowledge_units unit
                  ON unit.unit_id = ability.knowledge_unit_id
                LEFT JOIN knowledge_units parent ON parent.unit_id = unit.parent_unit_id
                WHERE ability.student_id = :student_id
                ORDER BY subject.subject_code, unit.unit_type, unit.unit_code
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]

    async def recommendations(
        self, session: AsyncSession, student_code: str
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT DISTINCT ON (fact_args ->> 1)
                       fact_args ->> 1 AS unit_code,
                       fact_args ->> 2 AS action,
                       inference_trace_id, derived_by_rule_code,
                       provenance, created_at
                FROM kb_facts
                WHERE predicate_code = 'recommended_next'
                  AND fact_args ->> 0 = :student_code
                ORDER BY fact_args ->> 1, created_at DESC, fact_id DESC
                """
            ),
            {"student_code": student_code},
        )
        return [dict(row._mapping) for row in result]

    async def attempts(self, session: AsyncSession, student_id: int) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT item.exam_item_id, item.question_id, question.question_code,
                       question.stem, question.subject_id, subject.subject_code,
                       item.is_correct, item.answered_at,
                       question.difficulty_label, question.bloom_level,
                       COALESCE(
                           ARRAY_AGG(DISTINCT criterion.criterion_code) FILTER (
                               WHERE criterion.criterion_code IS NOT NULL
                           ), ARRAY[]::VARCHAR[]
                       ) AS criterion_codes
                FROM exam_sessions exam
                JOIN exam_items item ON item.session_id = exam.session_id
                JOIN questions question ON question.question_id = item.question_id
                JOIN subjects subject ON subject.subject_id = question.subject_id
                LEFT JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                LEFT JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                LEFT JOIN assessment_criteria criterion
                  ON criterion.knowledge_unit_id = unit.unit_id
                WHERE exam.student_id = :student_id
                  AND exam.status = 'completed'
                  AND item.answered_at IS NOT NULL
                GROUP BY item.exam_item_id, question.question_id, subject.subject_id
                ORDER BY item.answered_at DESC
                LIMIT 200
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]
