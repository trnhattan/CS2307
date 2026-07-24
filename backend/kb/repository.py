import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.kb.models import Fact, InferenceResult


class KnowledgeBaseRepository:
    async def rules(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT rule_code, rule_name, hypothesis, goal, priority, weight,
                       explanation_template, source
                FROM kb_rules
                WHERE is_active = TRUE
                ORDER BY priority, weight, rule_code
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def relations(self, session: AsyncSession) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT definition_code, is_symmetric, is_transitive
                FROM kb_definitions
                WHERE definition_type = 'relation' AND is_active = TRUE
                ORDER BY definition_code
                """
            )
        )
        return [dict(row._mapping) for row in result]

    async def definition_codes(self, session: AsyncSession) -> set[str]:
        result = await session.execute(
            text("SELECT definition_code FROM kb_definitions WHERE is_active = TRUE")
        )
        return set(result.scalars())

    async def save_trace(
        self,
        session: AsyncSession,
        result: InferenceResult,
        initial_facts: list[dict[str, Any]],
        goal: dict[str, Any] | None,
    ) -> int:
        query = await session.execute(
            text(
                """
                INSERT INTO inference_traces (
                    strategy, goal, initial_facts, derived_facts, steps,
                    status, finished_at
                )
                VALUES (
                    :strategy, CAST(:goal AS JSONB), CAST(:initial AS JSONB),
                    CAST(:derived AS JSONB), CAST(:steps AS JSONB),
                    :status, CURRENT_TIMESTAMP
                )
                RETURNING inference_trace_id
                """
            ),
            {
                "strategy": result.strategy,
                "goal": self._json(goal) if goal else None,
                "initial": self._json(initial_facts),
                "derived": self._json([fact.as_dict() for fact in result.derived_facts]),
                "steps": self._json([step.as_dict() for step in result.steps]),
                "status": "completed" if result.solved else "no_solution",
            },
        )
        return query.scalar_one()

    async def save_derived_facts(
        self,
        session: AsyncSession,
        result: InferenceResult,
        trace_id: int,
        known_predicates: set[str],
    ) -> None:
        statement = text(
            """
            INSERT INTO kb_facts (
                fact_type, subject_ref, predicate_code, object_ref, object_value,
                fact_args, confidence, is_inferred, derived_by_rule_code,
                inference_trace_id, source, created_by, provenance
            )
            VALUES (
                :fact_type, :subject_ref, :predicate, :object_ref,
                CAST(:object_value AS JSONB), CAST(:fact_args AS JSONB),
                :confidence, TRUE, :rule_code, :trace_id, :source,
                'inference_engine', CAST(:provenance AS JSONB)
            )
            ON CONFLICT (
                fact_type, predicate_code, (fact_args::TEXT)
            ) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                derived_by_rule_code = EXCLUDED.derived_by_rule_code,
                inference_trace_id = EXCLUDED.inference_trace_id,
                source = EXCLUDED.source,
                provenance = EXCLUDED.provenance,
                created_at = CURRENT_TIMESTAMP
            """
        )
        rows = []
        for fact in result.derived_facts:
            if fact.predicate not in known_predicates:
                continue
            arguments = list(fact.arguments)
            rows.append(
                {
                    "fact_type": fact.fact_type,
                    "subject_ref": str(arguments[0]),
                    "predicate": fact.predicate,
                    "object_ref": str(arguments[1]) if len(arguments) == 2 else None,
                    "object_value": self._json(arguments[-1]) if len(arguments) > 2 else None,
                    "fact_args": self._json(arguments),
                    "confidence": fact.confidence,
                    "rule_code": fact.provenance.get("rule_code"),
                    "trace_id": trace_id,
                    "source": fact.source,
                    "provenance": self._json(fact.provenance),
                }
            )
        if rows:
            await session.execute(statement, rows)

    async def save_asserted_facts(
        self,
        session: AsyncSession,
        facts: list[Fact],
        trace_id: int,
        known_predicates: set[str],
    ) -> None:
        statement = text(
            """
            INSERT INTO kb_facts (
                fact_type, subject_ref, predicate_code, object_ref, object_value,
                fact_args, confidence, is_inferred, inference_trace_id,
                source, created_by, provenance
            )
            VALUES (
                :fact_type, :subject_ref, :predicate, :object_ref,
                CAST(:object_value AS JSONB), CAST(:fact_args AS JSONB),
                :confidence, FALSE, :trace_id, :source,
                'ability_service', CAST(:provenance AS JSONB)
            )
            ON CONFLICT (fact_type, predicate_code, (fact_args::TEXT))
            DO UPDATE SET
                confidence = EXCLUDED.confidence,
                inference_trace_id = EXCLUDED.inference_trace_id,
                source = EXCLUDED.source,
                provenance = EXCLUDED.provenance
            """
        )
        rows = []
        for fact in facts:
            if fact.predicate not in known_predicates or not fact.arguments:
                continue
            arguments = list(fact.arguments)
            rows.append(
                {
                    "fact_type": fact.fact_type,
                    "subject_ref": str(arguments[0]),
                    "predicate": fact.predicate,
                    "object_ref": str(arguments[1]) if len(arguments) == 2 else None,
                    "object_value": self._json(arguments[-1]) if len(arguments) > 2 else None,
                    "fact_args": self._json(arguments),
                    "confidence": fact.confidence,
                    "trace_id": trace_id,
                    "source": fact.source,
                    "provenance": self._json(fact.provenance),
                }
            )
        if rows:
            await session.execute(statement, rows)

    async def trace(self, session: AsyncSession, trace_id: int) -> dict[str, Any] | None:
        result = await session.execute(
            text(
                """
                SELECT inference_trace_id AS trace_id, session_id, strategy, goal,
                       initial_facts, derived_facts, steps, status
                FROM inference_traces
                WHERE inference_trace_id = :trace_id
                """
            ),
            {"trace_id": trace_id},
        )
        row = result.one_or_none()
        return dict(row._mapping) if row else None

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
