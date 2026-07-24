from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


FactType = Literal[
    "type",
    "determined_object",
    "constant_assignment",
    "equality",
    "binary_relation",
]
Strategy = Literal["forward", "backward", "hybrid"]


def canonical_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class Fact:
    predicate: str
    arguments: tuple[Any, ...]
    fact_type: FactType = "binary_relation"
    fact_id: str | None = None
    confidence: float = 1.0
    source: str = "api"
    provenance: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def key(self, symmetric: bool = False) -> tuple[str, str, tuple[str, ...]]:
        values = tuple(canonical_value(value) for value in self.arguments)
        if symmetric and len(values) == 2:
            values = tuple(sorted(values))
        return self.fact_type, self.predicate, values

    def as_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "predicate": self.predicate,
            "args": list(self.arguments),
            "confidence": self.confidence,
            "source": self.source,
            "provenance": self.provenance,
        }


@dataclass(frozen=True, slots=True)
class Clause:
    predicate: str | None = None
    arguments: tuple[Any, ...] = ()
    fact_type: FactType | None = None
    operator: str | None = None
    left: Any = None
    right: Any = None


@dataclass(frozen=True, slots=True)
class Rule:
    code: str
    name: str
    hypothesis: tuple[Clause, ...]
    goals: tuple[Clause, ...]
    priority: int = 100
    weight: float = 1.0
    explanation_template: str = ""
    source: str | None = None


@dataclass(frozen=True, slots=True)
class RelationSpec:
    predicate: str
    symmetric: bool = False
    transitive: bool = False


@dataclass(frozen=True, slots=True)
class TraceStep:
    step_no: int
    rule_code: str
    input_fact_ids: tuple[str, ...]
    output_fact_ids: tuple[str, ...]
    explanation: str
    bindings: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_no": self.step_no,
            "rule_code": self.rule_code,
            "input_fact_ids": list(self.input_fact_ids),
            "output_fact_ids": list(self.output_fact_ids),
            "explanation": self.explanation,
            "bindings": self.bindings,
        }


@dataclass(frozen=True, slots=True)
class InferenceResult:
    strategy: Strategy
    facts: tuple[Fact, ...]
    derived_facts: tuple[Fact, ...]
    solved: bool
    steps: tuple[TraceStep, ...]
    reduced_steps: tuple[TraceStep, ...]
