from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.abilities.repository import AbilityRepository
from backend.irt.model import IRTResponse, estimate_ability_eap, mastery_probability
from backend.kb.inference import InferenceEngine
from backend.kb.models import Fact
from backend.kb.repository import KnowledgeBaseRepository
from backend.kb.schemas import parse_relation, parse_rule


@dataclass(frozen=True, slots=True)
class AbilityRefreshResult:
    theta: float
    standard_error: float
    mastery: float
    evidence_count: int
    trace_id: int | None


class AbilityService:
    def __init__(
        self,
        repository: AbilityRepository | None = None,
        kb_repository: KnowledgeBaseRepository | None = None,
    ) -> None:
        self.repository = repository or AbilityRepository()
        self.kb_repository = kb_repository or KnowledgeBaseRepository()

    async def refresh(
        self,
        session: AsyncSession,
        *,
        student_id: int,
        subject_id: int,
        session_id: int,
        scale: float = 1.7,
    ) -> AbilityRefreshResult:
        responses = await self.repository.subject_responses(session, student_id, subject_id)
        estimate = self._estimate(responses, scale=scale)
        mastery = mastery_probability(estimate.theta)
        await self.repository.upsert(
            session,
            student_id=student_id,
            subject_id=subject_id,
            unit_id=None,
            theta=estimate.theta,
            standard_error=estimate.standard_error,
            mastery=mastery,
            evidence_count=len(responses),
        )

        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        units: dict[int, dict[str, Any]] = {}
        for row in await self.repository.unit_responses(session, student_id, subject_id):
            grouped[row["unit_id"]].append(row)
            units[row["unit_id"]] = row

        student_code = await self.repository.student_code(session, student_id)
        evidence_facts: list[Fact] = []
        for unit_id, rows in grouped.items():
            unit_estimate = self._estimate(rows, scale=scale, weighted=True)
            await self.repository.upsert(
                session,
                student_id=student_id,
                subject_id=subject_id,
                unit_id=unit_id,
                theta=unit_estimate.theta,
                standard_error=unit_estimate.standard_error,
                mastery=mastery_probability(unit_estimate.theta),
                evidence_count=len(rows),
            )
            accuracy = sum(1 for row in rows if row["is_correct"]) / len(rows)
            evidence_facts.append(
                Fact(
                    predicate="unit_accuracy",
                    arguments=(student_code, units[unit_id]["unit_code"], accuracy),
                    source="response_history",
                    provenance={"session_id": session_id, "evidence_count": len(rows)},
                )
            )

        trace_id = await self._infer_learning_path(session, session_id, evidence_facts)
        return AbilityRefreshResult(
            theta=estimate.theta,
            standard_error=estimate.standard_error,
            mastery=mastery,
            evidence_count=len(responses),
            trace_id=trace_id,
        )

    @staticmethod
    def _estimate(
        rows: list[dict[str, Any]],
        *,
        scale: float,
        weighted: bool = False,
    ):
        return estimate_ability_eap(
            [
                IRTResponse(
                    a=float(row["irt_a"]),
                    b=float(row["irt_b"]),
                    c=float(row["irt_c"]),
                    correct=bool(row["is_correct"]),
                    weight=float(row.get("measurement_weight", 1.0)) if weighted else 1.0,
                )
                for row in rows
            ],
            scale=scale,
        )

    async def _infer_learning_path(
        self,
        session: AsyncSession,
        session_id: int,
        facts: list[Fact],
    ) -> int | None:
        if not facts:
            return None
        rules = [parse_rule(row) for row in await self.kb_repository.rules(session)]
        relations = [
            parse_relation(row) for row in await self.kb_repository.relations(session)
        ]
        result = InferenceEngine(rules, relations).infer(facts)
        trace_id = await self.repository.save_learning_trace(
            session,
            session_id=session_id,
            initial_facts=[fact.as_dict() for fact in facts],
            derived_facts=[fact.as_dict() for fact in result.derived_facts],
            steps=[step.as_dict() for step in result.steps],
        )
        definitions = await self.kb_repository.definition_codes(session)
        await self.kb_repository.save_asserted_facts(
            session, facts, trace_id, definitions
        )
        await self.kb_repository.save_derived_facts(
            session, result, trace_id, definitions
        )
        return trace_id
