import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CalibrationRepository:
    async def config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT prop_key, prop_value
                FROM sys_props
                WHERE prop_key IN (
                    'IRT_SCALE_CONSTANT',
                    'IRT_CALIBRATION_MIN_RESPONSES',
                    'IRT_CALIBRATION_APPLY_MIN_RESPONSES'
                )
                """
            )
        )
        return {row.prop_key: row.prop_value for row in result}

    async def responses(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT question.question_id, question.question_code,
                       subject.subject_code, question.irt_a, question.irt_b,
                       question.irt_c, item.is_correct, item.theta_before,
                       item.response_time_sec
                FROM exam_items item
                JOIN questions question ON question.question_id = item.question_id
                JOIN subjects subject ON subject.subject_id = question.subject_id
                WHERE item.answered_at IS NOT NULL
                  AND item.is_correct IS NOT NULL
                ORDER BY question.question_id, item.answered_at, item.exam_item_id
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def create_run(
        self,
        session: AsyncSession,
        *,
        actor: str,
        minimum_sample: int,
        minimum_apply_sample: int,
        total_responses: int,
        evaluated_items: int,
        eligible_items: int,
        applied_items: int,
        limitations: list[str],
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        summary = {
            "minimum_evaluation_sample": minimum_sample,
            "minimum_apply_sample": minimum_apply_sample,
            "limitations": limitations,
            "items": items,
        }
        result = await session.execute(
            text(
                """
                INSERT INTO irt_calibration_runs (
                    method, total_responses, evaluated_items, eligible_items,
                    applied_items, summary, created_by
                ) VALUES (
                    'conditional-mle-grid-v1', :total_responses, :evaluated_items,
                    :eligible_items, :applied_items, CAST(:summary AS JSONB), :created_by
                )
                RETURNING run_id, created_at
                """
            ),
            {
                "total_responses": total_responses,
                "evaluated_items": evaluated_items,
                "eligible_items": eligible_items,
                "applied_items": applied_items,
                "summary": json.dumps(summary, separators=(",", ":"), default=str),
                "created_by": actor,
            },
        )
        return dict(result.one()._mapping)

    async def apply_item(
        self,
        session: AsyncSession,
        *,
        question_id: int,
        suggested_b: float,
        sample_size: int,
        actor: str,
    ) -> None:
        difficulty_norm = min(1.0, max(0.0, (suggested_b + 3.0) / 6.0))
        label = "easy" if difficulty_norm <= 0.4 else "hard" if difficulty_norm >= 0.65 else "medium"
        await session.execute(
            text(
                """
                UPDATE questions
                SET irt_b = :irt_b,
                    difficulty_norm = :difficulty_norm,
                    difficulty_label = :difficulty_label,
                    irt_status = 'calibrated',
                    irt_sample_size = :sample_size,
                    irt_model_version = '3PL-conditional-MLE-v1',
                    provenance = provenance || jsonb_build_object(
                        'empirical_calibration', jsonb_build_object(
                            'method', 'conditional-mle-grid-v1',
                            'sample_size', :sample_size,
                            'applied_by', :actor,
                            'applied_at', CURRENT_TIMESTAMP
                        )
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE question_id = :question_id
                """
            ),
            {
                "question_id": question_id,
                "irt_b": suggested_b,
                "difficulty_norm": difficulty_norm,
                "difficulty_label": label,
                "sample_size": sample_size,
                "actor": actor,
            },
        )

    async def latest(self, session: AsyncSession) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT run_id, method, total_responses, evaluated_items,
                       eligible_items, applied_items, summary, created_by, created_at
                FROM irt_calibration_runs
                ORDER BY created_at DESC, run_id DESC
                LIMIT 1
                """
            )
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None
