import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ExamExplanationRepository:
    async def config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text("SELECT prop_key, prop_value FROM sys_props WHERE prop_key LIKE 'LLM_%'")
        )
        return {row.prop_key: row.prop_value for row in result}

    async def context(
        self,
        session: AsyncSession,
        session_id: int,
        student_id: int | None,
        technical: bool,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT exam.session_id, exam.student_id, student.display_name AS student_name,
                       subject.subject_name, exam.mode, exam.status,
                       exam.total_score, exam.max_score,
                       CASE WHEN exam.max_score > 0
                            THEN ROUND(100 * exam.total_score / exam.max_score, 2)
                            ELSE 0 END AS percentage,
                       exam.theta_initial, exam.theta_current,
                       exam.standard_error_current,
                       COUNT(item.exam_item_id) AS question_count,
                       COUNT(item.exam_item_id) FILTER (WHERE item.is_correct) AS correct_count
                FROM exam_sessions exam
                JOIN students student ON student.student_id = exam.student_id
                JOIN subjects subject ON subject.subject_id = exam.subject_id
                LEFT JOIN exam_items item ON item.session_id = exam.session_id
                WHERE exam.session_id = :session_id
                  AND (
                      CAST(:student_id AS BIGINT) IS NULL OR
                      exam.student_id = CAST(:student_id AS BIGINT)
                  )
                GROUP BY exam.session_id, student.student_id, subject.subject_id
                """
            ),
            {"session_id": session_id, "student_id": student_id},
        )
        row = result.one_or_none()
        if row is None or row.status != "completed":
            return None
        summary = dict(row._mapping)
        item_result = await session.execute(
            text(
                """
                SELECT unit.unit_code, unit.unit_name, unit.unit_type,
                       COUNT(*) AS evidence_count,
                       ROUND(100 * AVG(CASE WHEN item.is_correct THEN 1.0 ELSE 0 END), 2)
                           AS accuracy_percent
                FROM exam_items item
                JOIN question_knowledge_units link ON link.question_id = item.question_id
                JOIN knowledge_units unit ON unit.unit_id = link.unit_id
                WHERE item.session_id = :session_id AND item.answered_at IS NOT NULL
                GROUP BY unit.unit_id
                ORDER BY accuracy_percent, evidence_count DESC, unit.unit_name
                """
            ),
            {"session_id": session_id},
        )
        units = [dict(value._mapping) for value in item_result]
        context: dict[str, Any] = {
            "session_id": session_id,
            "student_name": summary["student_name"],
            "subject_name": summary["subject_name"],
            "mode": summary["mode"],
            "score": {
                "earned": float(summary["total_score"]),
                "maximum": float(summary["max_score"]),
                "percentage": float(summary["percentage"]),
                "correct": int(summary["correct_count"]),
                "questions": int(summary["question_count"]),
            },
            "unit_evidence": [
                {
                    "unit": value["unit_name"],
                    "type": value["unit_type"],
                    "evidence_count": int(value["evidence_count"]),
                    "accuracy_percent": float(value["accuracy_percent"]),
                    "recommendation": (
                        "remediate" if float(value["accuracy_percent"]) < 50 else
                        "reinforce" if float(value["accuracy_percent"]) < 75 else
                        "advance"
                    ),
                }
                for value in units
            ],
        }
        if technical:
            trace_result = await session.execute(
                text(
                    """
                    SELECT inference_trace_id AS trace_id, strategy, status
                    FROM inference_traces
                    WHERE session_id = :session_id
                    ORDER BY started_at
                    """
                ),
                {"session_id": session_id},
            )
            context["ability"] = {
                "theta_before": float(summary["theta_initial"]),
                "theta_after": float(summary["theta_current"]),
                "standard_error": float(summary["standard_error_current"]),
            }
            context["inference_traces"] = [
                dict(value._mapping) for value in trace_result
            ]
        return context

    async def cached(
        self,
        session: AsyncSession,
        session_id: int,
        audience: str,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT artifact_id, session_id, audience, model, response_payload,
                       created_at AS generated_at
                FROM llm_artifacts
                WHERE artifact_type = 'exam_explanation'
                  AND session_id = :session_id AND audience = :audience
                  AND status = 'success'
                  AND response_payload ->> 'grounding_version' = 'deterministic-evidence-v1'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"session_id": session_id, "audience": audience},
        )
        row = result.one_or_none()
        if row is None:
            return None
        value = dict(row._mapping)
        value.update(value.pop("response_payload"))
        return value

    async def create_artifact(
        self,
        session: AsyncSession,
        *,
        session_id: int,
        audience: str,
        model: str,
        context: dict[str, Any],
        actor: str,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO llm_artifacts (
                    artifact_type, session_id, audience, provider, model,
                    request_payload, created_by
                ) VALUES (
                    'exam_explanation', :session_id, :audience,
                    'vlai-openai-compatible', :model, CAST(:context AS JSONB), :actor
                ) RETURNING artifact_id
                """
            ),
            {
                "session_id": session_id,
                "audience": audience,
                "model": model,
                "context": self._json(context),
                "actor": actor,
            },
        )
        return int(result.scalar_one())

    async def mark_success(
        self,
        session: AsyncSession,
        artifact_id: int,
        model: str,
        payload: dict[str, Any],
        usage: dict[str, Any],
    ) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                UPDATE llm_artifacts
                SET status = 'success', model = :model,
                    response_payload = CAST(:payload AS JSONB),
                    usage = CAST(:usage AS JSONB), error_message = NULL
                WHERE artifact_id = :artifact_id
                RETURNING created_at AS generated_at
                """
            ),
            {
                "artifact_id": artifact_id,
                "model": model,
                "payload": self._json(payload),
                "usage": self._json(usage),
            },
        )
        row = result.one_or_none()
        return {
            "generated_at": row.generated_at if row else datetime.now(timezone.utc)
        }

    async def mark_failed(
        self, session: AsyncSession, artifact_id: int, error_message: str
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE llm_artifacts SET status = 'failed', error_message = :error
                WHERE artifact_id = :artifact_id
                """
            ),
            {"artifact_id": artifact_id, "error": error_message[:2000]},
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
