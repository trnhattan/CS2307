from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeGraphRepository:
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
                       COALESCE(
                           ARRAY_AGG(DISTINCT unit.unit_code) FILTER (
                               WHERE unit.unit_code IS NOT NULL
                           ), ARRAY[]::VARCHAR[]
                       ) AS unit_codes
                FROM exam_sessions exam
                JOIN exam_items item ON item.session_id = exam.session_id
                JOIN questions question ON question.question_id = item.question_id
                JOIN subjects subject ON subject.subject_id = question.subject_id
                LEFT JOIN question_knowledge_units link
                  ON link.question_id = question.question_id
                LEFT JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                WHERE exam.student_id = :student_id
                  AND item.answered_at IS NOT NULL
                GROUP BY item.exam_item_id, question.question_id, subject.subject_id
                ORDER BY item.answered_at DESC
                LIMIT 200
                """
            ),
            {"student_id": student_id},
        )
        return [dict(row._mapping) for row in result]
