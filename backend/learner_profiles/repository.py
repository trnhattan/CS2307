from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class LearnerProfileRepository:
    async def student(
        self, session: AsyncSession, student_id: int
    ) -> dict[str, Any] | None:
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

    async def criteria(
        self, session: AsyncSession, subject_code: str | None = None
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT criterion.criterion_id, criterion.criterion_code,
                       criterion.criterion_name, subject.subject_id,
                       subject.subject_code, subject.subject_name,
                       topic.unit_code AS topic_code, topic.unit_name AS topic_name,
                       criterion.learning_objective, criterion.success_statement,
                       criterion.mastery_threshold, criterion.importance_weight,
                       criterion.display_order,
                       COUNT(DISTINCT link.question_id) FILTER (
                           WHERE question.status IN ('active', 'reviewed')
                       ) AS mapped_question_count
                FROM assessment_criteria criterion
                JOIN subjects subject ON subject.subject_id = criterion.subject_id
                JOIN knowledge_units skill
                  ON skill.unit_id = criterion.knowledge_unit_id
                LEFT JOIN knowledge_units topic ON topic.unit_id = skill.parent_unit_id
                LEFT JOIN question_knowledge_units link
                  ON link.unit_id = skill.unit_id
                 AND link.unit_role IN ('primary_skill', 'supporting_skill')
                LEFT JOIN questions question ON question.question_id = link.question_id
                WHERE criterion.is_active = TRUE AND subject.is_active = TRUE
                  AND (
                    CAST(:subject_code AS VARCHAR) IS NULL OR
                    subject.subject_code = CAST(:subject_code AS VARCHAR)
                  )
                GROUP BY criterion.criterion_id, subject.subject_id,
                         skill.unit_id, topic.unit_id
                ORDER BY subject.subject_name, criterion.display_order,
                         criterion.criterion_name
                """
            ),
            {"subject_code": subject_code},
        )
        return [dict(row._mapping) for row in result]

    async def states(
        self,
        session: AsyncSession,
        student_id: int,
        subject_code: str | None = None,
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                WITH response_evidence AS (
                    SELECT criterion.criterion_id,
                           COUNT(item.exam_item_id) AS evidence_count,
                           100 * AVG(CASE WHEN item.is_correct THEN 1.0 ELSE 0.0 END)
                               AS accuracy_percent,
                           MAX(item.answered_at) AS last_assessed_at
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
                ), latest_snapshot AS (
                    SELECT DISTINCT ON (snapshot.criterion_id)
                           snapshot.criterion_id, snapshot.mastery_delta
                    FROM student_ability_snapshots snapshot
                    JOIN exam_sessions exam ON exam.session_id = snapshot.session_id
                    WHERE snapshot.student_id = :student_id
                      AND snapshot.criterion_id IS NOT NULL
                      AND exam.status = 'completed'
                    ORDER BY snapshot.criterion_id, snapshot.created_at DESC,
                             snapshot.snapshot_id DESC
                )
                SELECT criterion.criterion_id, criterion.criterion_code,
                       criterion.criterion_name, subject.subject_id,
                       subject.subject_code, subject.subject_name,
                       topic.unit_code AS topic_code, topic.unit_name AS topic_name,
                       criterion.learning_objective, criterion.success_statement,
                       criterion.mastery_threshold, criterion.importance_weight,
                       criterion.display_order,
                       COUNT(DISTINCT mapping.question_id) FILTER (
                           WHERE mapped_question.status IN ('active', 'reviewed')
                       ) AS mapped_question_count,
                       ability.theta, ability.standard_error,
                       ability.mastery_probability,
                       COALESCE(evidence.evidence_count, 0) AS evidence_count,
                       evidence.accuracy_percent, evidence.last_assessed_at,
                       snapshot.mastery_delta
                FROM assessment_criteria criterion
                JOIN subjects subject ON subject.subject_id = criterion.subject_id
                JOIN knowledge_units skill
                  ON skill.unit_id = criterion.knowledge_unit_id
                LEFT JOIN knowledge_units topic ON topic.unit_id = skill.parent_unit_id
                LEFT JOIN student_abilities ability
                  ON ability.student_id = :student_id
                 AND ability.knowledge_unit_id = criterion.knowledge_unit_id
                LEFT JOIN response_evidence evidence
                  ON evidence.criterion_id = criterion.criterion_id
                LEFT JOIN latest_snapshot snapshot
                  ON snapshot.criterion_id = criterion.criterion_id
                LEFT JOIN question_knowledge_units mapping
                  ON mapping.unit_id = criterion.knowledge_unit_id
                 AND mapping.unit_role IN ('primary_skill', 'supporting_skill')
                LEFT JOIN questions mapped_question
                  ON mapped_question.question_id = mapping.question_id
                WHERE criterion.is_active = TRUE AND subject.is_active = TRUE
                  AND (
                    CAST(:subject_code AS VARCHAR) IS NULL OR
                    subject.subject_code = CAST(:subject_code AS VARCHAR)
                  )
                GROUP BY criterion.criterion_id, subject.subject_id, topic.unit_id,
                         ability.ability_id, evidence.criterion_id,
                         evidence.evidence_count, evidence.accuracy_percent,
                         evidence.last_assessed_at, snapshot.criterion_id,
                         snapshot.mastery_delta
                ORDER BY subject.subject_name, criterion.display_order,
                         criterion.criterion_name
                """
            ),
            {"student_id": student_id, "subject_code": subject_code},
        )
        return [dict(row._mapping) for row in result]

    async def subject_states(
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
                SELECT subject.subject_code, subject.subject_name,
                       COALESCE(completed.completed_tests, 0) AS completed_tests,
                       ability.mastery_probability,
                       COALESCE(ability.evidence_count, 0) AS evidence_count
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
                WHERE prop_key IN ('PROFILE_IMPROVEMENT_DELTA')
                """
            )
        )
        return {row.prop_key: row.prop_value for row in result}
