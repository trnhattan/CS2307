from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.kb.inference import InferenceEngine
from backend.kb.repository import KnowledgeBaseRepository
from backend.kb.schemas import (
    ClosureRequest,
    ClosureResponse,
    FactPayload,
    RulePayload,
    RuleValidationResponse,
    StoredTraceResponse,
    parse_relation,
    parse_rule,
)


class KnowledgeBaseService:
    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.repository = repository
        self.session_factory = session_factory

    async def closure(self, request: ClosureRequest) -> ClosureResponse:
        async with self.session_factory() as session:
            rules = [parse_rule(row) for row in await self.repository.rules(session)]
            relations = [
                parse_relation(row) for row in await self.repository.relations(session)
            ]
            result = InferenceEngine(rules, relations).infer(
                [fact.to_domain() for fact in request.facts],
                goal=request.goal.to_domain() if request.goal else None,
                strategy=request.strategy,
            )
            trace_id = None
            if request.persist:
                trace_id = await self.repository.save_trace(
                    session,
                    result,
                    [fact.model_dump() for fact in request.facts],
                    request.goal.model_dump() if request.goal else None,
                )
                definitions = await self.repository.definition_codes(session)
                await self.repository.save_derived_facts(
                    session, result, trace_id, definitions
                )
                await session.commit()
        return ClosureResponse(
            strategy=result.strategy,
            solved=result.solved,
            trace_id=trace_id,
            facts=[FactPayload.model_validate(fact.as_dict()) for fact in result.facts],
            derived_facts=[
                FactPayload.model_validate(fact.as_dict()) for fact in result.derived_facts
            ],
            steps=[step.as_dict() for step in result.steps],
            reduced_steps=[step.as_dict() for step in result.reduced_steps],
        )

    async def validate_rule(self, rule: RulePayload) -> RuleValidationResponse:
        warnings = []
        predicates = {
            clause.predicate
            for clause in [*rule.hypothesis, *rule.goal]
            if clause.predicate is not None
        }
        async with self.session_factory() as session:
            definitions = await self.repository.definition_codes(session)
        missing = sorted(predicates - definitions)
        if missing:
            warnings.append(
                "Predicates without active definitions: " + ", ".join(missing)
            )
        rule.to_domain()
        return RuleValidationResponse(
            valid=not missing,
            normalized_rule=rule,
            warnings=warnings,
        )

    async def trace(self, trace_id: int) -> StoredTraceResponse | None:
        async with self.session_factory() as session:
            row = await self.repository.trace(session, trace_id)
        return StoredTraceResponse(**row) if row else None
