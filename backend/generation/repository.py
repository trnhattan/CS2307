import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.generation.schemas import (
    GeneratedQuestionPayload,
    InitialIRT,
    QuestionGenerationRequest,
)


class QuestionGenerationRepository:
    async def config(self, session: AsyncSession) -> dict[str, Any]:
        result = await session.execute(
            text(
                """
                SELECT prop_key, prop_value
                FROM sys_props
                WHERE prop_key LIKE 'LLM_%'
                   OR prop_key IN ('ANSWER_POOL_SIZE_BY_BLOOM', 'DISPLAY_OPTION_COUNT')
                """
            )
        )
        return {row.prop_key: row.prop_value for row in result}

    async def catalog(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT subject.subject_code, subject.subject_name,
                       unit.unit_code, unit.unit_name, unit.unit_type
                FROM subjects subject
                LEFT JOIN knowledge_units unit
                  ON unit.subject_id = subject.subject_id AND unit.is_active = TRUE
                WHERE subject.is_active = TRUE
                ORDER BY subject.subject_name, unit.unit_type, unit.unit_name
                """
            )
        )
        subjects: dict[str, dict[str, Any]] = {}
        for row in result:
            subject = subjects.setdefault(
                row.subject_code,
                {"code": row.subject_code, "name": row.subject_name, "units": []},
            )
            if row.unit_code:
                subject["units"].append(
                    {"code": row.unit_code, "name": row.unit_name, "type": row.unit_type}
                )
        return list(subjects.values())

    async def resolve_units(
        self,
        session: AsyncSession,
        request: QuestionGenerationRequest,
    ) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT subject.subject_id, subject.subject_code,
                       jsonb_object_agg(unit.unit_code, jsonb_build_object(
                           'unit_id', unit.unit_id,
                           'unit_type', unit.unit_type,
                           'unit_name', unit.unit_name
                       )) AS units
                FROM subjects subject
                JOIN knowledge_units unit ON unit.subject_id = subject.subject_id
                WHERE subject.subject_code = :subject_code
                  AND subject.is_active = TRUE AND unit.is_active = TRUE
                GROUP BY subject.subject_id
                """
            ),
            {"subject_code": request.subject_code},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    async def existing_stems(self, session: AsyncSession) -> list[str]:
        result = await session.execute(text("SELECT stem FROM questions"))
        return list(result.scalars())

    async def create_artifact(
        self,
        session: AsyncSession,
        *,
        artifact_type: str,
        audience: str,
        provider: str,
        model: str,
        request_payload: dict[str, Any],
        created_by: str,
        session_id: int | None = None,
    ) -> int:
        result = await session.execute(
            text(
                """
                INSERT INTO llm_artifacts (
                    artifact_type, session_id, audience, provider, model,
                    request_payload, created_by
                ) VALUES (
                    :artifact_type, :session_id, :audience, :provider,
                    :model, CAST(:request_payload AS JSONB), :created_by
                )
                RETURNING artifact_id
                """
            ),
            {
                "artifact_type": artifact_type,
                "session_id": session_id,
                "audience": audience,
                "provider": provider,
                "model": model,
                "request_payload": self._json(request_payload),
                "created_by": created_by,
            },
        )
        return int(result.scalar_one())

    async def mark_failed(
        self, session: AsyncSession, artifact_id: int, error_message: str
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE llm_artifacts
                SET status = 'failed', error_message = :error_message
                WHERE artifact_id = :artifact_id
                """
            ),
            {"artifact_id": artifact_id, "error_message": error_message[:2000]},
        )

    async def save_question(
        self,
        session: AsyncSession,
        *,
        artifact_id: int,
        request: QuestionGenerationRequest,
        generated: GeneratedQuestionPayload,
        irt: InitialIRT,
        validation_issues: list[dict[str, Any]],
        units: dict[str, Any],
        model: str,
        completion_id: str | None,
        usage: dict[str, Any],
        actor: str,
        display_option_count: int,
    ) -> str:
        question_code = f"LLM-{artifact_id:08d}"
        source = request.source_title or f"LLM draft via {model}"
        provenance = {
            "generator": "llm-question-generation-v1",
            "artifact_id": artifact_id,
            "model": model,
            "completion_id": completion_id,
            "bloom_rationale": generated.bloom_rationale,
            "irt_rubric": irt.rubric_version,
            "source_supplied": bool(request.source_context),
            "validation_issues": validation_issues,
            "review_required": True,
        }
        result = await session.execute(
            text(
                """
                INSERT INTO questions (
                    question_code, subject_id, stem, bloom_level, difficulty_label,
                    difficulty_norm, avg_time_sec, explanation, display_option_count,
                    must_include_best, randomize_options, irt_a, irt_b, irt_c,
                    irt_status, status, source, created_by, provenance
                ) VALUES (
                    :question_code, :subject_id, :stem, :bloom_level, :difficulty_label,
                    :difficulty_norm, :avg_time_sec, :explanation, :display_option_count,
                    TRUE, TRUE, :irt_a, :irt_b, :irt_c,
                    'estimated', 'draft', :source, :created_by, CAST(:provenance AS JSONB)
                )
                RETURNING question_id
                """
            ),
            {
                "question_code": question_code,
                "subject_id": units["subject_id"],
                "stem": generated.stem,
                "bloom_level": request.bloom_level,
                "difficulty_label": request.difficulty_label,
                "difficulty_norm": irt.difficulty_norm,
                "avg_time_sec": irt.avg_time_sec,
                "explanation": generated.explanation,
                "display_option_count": min(
                    max(2, display_option_count), len(generated.options)
                ),
                "irt_a": irt.a,
                "irt_b": irt.b,
                "irt_c": irt.c,
                "source": source,
                "created_by": actor,
                "provenance": self._json(provenance),
            },
        )
        question_id = int(result.scalar_one())
        option_rows = []
        for index, option in enumerate(generated.options):
            code = chr(ord("A") + index)
            best = index == generated.correct_index
            option_rows.append(
                {
                    "question_id": question_id,
                    "option_code": code,
                    "option_text": option.text,
                    "score_weight": 1 if best else 0,
                    "is_best_answer": best,
                    "distractor_type": "best" if best else option.distractor_type,
                    "diagnosis": option.diagnosis,
                    "explanation": generated.explanation if best else option.diagnosis,
                    "source": source,
                    "provenance": self._json({"artifact_id": artifact_id, "model": model}),
                }
            )
        await session.execute(
            text(
                """
                INSERT INTO answer_options (
                    question_id, option_code, option_text, score_weight,
                    is_best_answer, distractor_type, diagnosis, explanation,
                    source, provenance
                ) VALUES (
                    :question_id, :option_code, :option_text, :score_weight,
                    :is_best_answer, :distractor_type, :diagnosis, :explanation,
                    :source, CAST(:provenance AS JSONB)
                )
                """
            ),
            option_rows,
        )
        selected_codes = [request.topic_code, *request.skill_codes]
        for index, unit_code in enumerate(selected_codes):
            unit = units["units"][unit_code]
            role = "topic" if index == 0 else ("primary_skill" if index == 1 else "supporting_skill")
            await session.execute(
                text(
                    """
                    INSERT INTO question_knowledge_units (
                        question_id, unit_id, unit_role, measurement_weight
                    ) VALUES (:question_id, :unit_id, :unit_role, :weight)
                    """
                ),
                {
                    "question_id": question_id,
                    "unit_id": unit["unit_id"],
                    "unit_role": role,
                    "weight": 1 if role != "supporting_skill" else 0.5,
                },
            )
        await session.execute(
            text(
                """
                UPDATE llm_artifacts
                SET question_id = :question_id, status = 'success', model = :model,
                    response_payload = CAST(:response AS JSONB),
                    usage = CAST(:usage AS JSONB), error_message = NULL
                WHERE artifact_id = :artifact_id
                """
            ),
            {
                "artifact_id": artifact_id,
                "question_id": question_id,
                "model": model,
                "response": self._json(
                    {
                        **generated.model_dump(),
                        "question_code": question_code,
                        "validation_issues": validation_issues,
                    }
                ),
                "usage": self._json(usage),
            },
        )
        return question_code

    async def recent(self, session: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT artifact.artifact_id, question.question_code, artifact.status,
                       artifact.model, artifact.request_payload ->> 'subject_code' AS subject_code,
                       artifact.request_payload ->> 'bloom_level' AS bloom_level,
                       artifact.request_payload ->> 'difficulty_label' AS difficulty_label,
                       artifact.created_by, artifact.created_at, artifact.error_message
                FROM llm_artifacts artifact
                LEFT JOIN questions question ON question.question_id = artifact.question_id
                WHERE artifact.artifact_type = 'question_generation'
                ORDER BY artifact.created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [dict(row._mapping) for row in result]

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
