from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.kb.models import Clause, Fact, FactType, RelationSpec, Rule


class FactPayload(BaseModel):
    fact_id: str | None = None
    fact_type: FactType = "binary_relation"
    predicate: str = Field(min_length=1, max_length=100)
    args: list[Any] = Field(min_length=1, max_length=12)
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: str = Field(default="api", min_length=1, max_length=255)
    provenance: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> Fact:
        return Fact(
            fact_id=self.fact_id,
            fact_type=self.fact_type,
            predicate=self.predicate,
            arguments=tuple(self.args),
            confidence=self.confidence,
            source=self.source,
            provenance=self.provenance,
        )


class ClausePayload(BaseModel):
    predicate: str | None = Field(default=None, min_length=1, max_length=100)
    args: list[Any] = Field(default_factory=list, max_length=12)
    fact_type: FactType | None = None
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte"] | None = None
    left: Any = None
    right: Any = None

    @model_validator(mode="after")
    def validate_shape(self):
        if self.operator is None and self.predicate is None:
            raise ValueError("Predicate clauses require a predicate")
        if self.operator is not None and self.predicate is not None:
            raise ValueError("Comparison clauses cannot also have a predicate")
        return self

    def to_domain(self) -> Clause:
        return Clause(
            predicate=self.predicate,
            arguments=tuple(self.args),
            fact_type=self.fact_type,
            operator=self.operator,
            left=self.left,
            right=self.right,
        )


class RulePayload(BaseModel):
    rule_code: str = Field(min_length=1, max_length=80)
    rule_name: str = Field(min_length=1, max_length=255)
    hypothesis: list[ClausePayload] = Field(min_length=1)
    goal: list[ClausePayload] = Field(min_length=1)
    priority: int = 100
    weight: float = Field(default=1.0, ge=0)
    explanation_template: str = ""
    source: str | None = None

    @model_validator(mode="after")
    def validate_variables(self):
        hypothesis_variables = {
            value
            for clause in self.hypothesis
            for value in [*clause.args, clause.left, clause.right]
            if isinstance(value, str) and value.startswith("?")
        }
        goal_variables = {
            value
            for clause in self.goal
            for value in clause.args
            if isinstance(value, str) and value.startswith("?")
        }
        missing = sorted(goal_variables - hypothesis_variables)
        if missing:
            raise ValueError(f"Goal variables must be bound by hypotheses: {', '.join(missing)}")
        if any(clause.operator is not None for clause in self.goal):
            raise ValueError("Rule goals must produce facts")
        return self

    def to_domain(self) -> Rule:
        return Rule(
            code=self.rule_code,
            name=self.rule_name,
            hypothesis=tuple(clause.to_domain() for clause in self.hypothesis),
            goals=tuple(clause.to_domain() for clause in self.goal),
            priority=self.priority,
            weight=self.weight,
            explanation_template=self.explanation_template,
            source=self.source,
        )


class ClosureRequest(BaseModel):
    facts: list[FactPayload] = Field(min_length=1, max_length=2000)
    goal: FactPayload | None = None
    strategy: Literal["forward", "backward", "hybrid"] = "forward"
    persist: bool = False


class TraceStepPayload(BaseModel):
    step_no: int
    rule_code: str
    input_fact_ids: list[str]
    output_fact_ids: list[str]
    explanation: str
    bindings: dict[str, Any]


class ClosureResponse(BaseModel):
    strategy: str
    solved: bool
    trace_id: int | None = None
    facts: list[FactPayload]
    derived_facts: list[FactPayload]
    steps: list[TraceStepPayload]
    reduced_steps: list[TraceStepPayload]


class RuleValidationResponse(BaseModel):
    valid: bool
    normalized_rule: RulePayload
    warnings: list[str] = Field(default_factory=list)


class StoredTraceResponse(BaseModel):
    trace_id: int
    session_id: int | None
    strategy: str
    goal: dict[str, Any] | None
    initial_facts: list[dict[str, Any]]
    derived_facts: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    status: str


def parse_rule(row: dict[str, Any]) -> Rule:
    def parse_clause(value: dict[str, Any]) -> ClausePayload:
        return ClausePayload.model_validate(value)

    payload = RulePayload(
        rule_code=row["rule_code"],
        rule_name=row["rule_name"],
        hypothesis=[parse_clause(value) for value in row["hypothesis"]],
        goal=[parse_clause(value) for value in row["goal"]],
        priority=row["priority"],
        weight=float(row["weight"]),
        explanation_template=row["explanation_template"],
        source=row.get("source"),
    )
    return payload.to_domain()


def parse_relation(row: dict[str, Any]) -> RelationSpec:
    return RelationSpec(
        predicate=row["definition_code"],
        symmetric=bool(row["is_symmetric"]),
        transitive=bool(row["is_transitive"]),
    )
