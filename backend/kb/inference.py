from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from backend.kb.models import (
    Clause,
    Fact,
    InferenceResult,
    RelationSpec,
    Rule,
    Strategy,
    TraceStep,
    canonical_value,
)


class InferenceEngine:
    def __init__(
        self,
        rules: Iterable[Rule],
        relations: Iterable[RelationSpec] = (),
        *,
        max_iterations: int = 100,
        max_facts: int = 10_000,
    ) -> None:
        self.rules = tuple(sorted(rules, key=lambda rule: (rule.priority, rule.weight, rule.code)))
        self.relations = {relation.predicate: relation for relation in relations}
        self.max_iterations = max_iterations
        self.max_facts = max_facts

    def infer(
        self,
        facts: Iterable[Fact],
        *,
        goal: Fact | None = None,
        strategy: Strategy = "forward",
    ) -> InferenceResult:
        rules = self.rules
        if strategy == "backward" and goal is not None:
            rules = self._goal_relevant_rules(goal.predicate)
        result = self._forward(tuple(facts), rules, goal, strategy)
        if strategy in {"backward", "hybrid"} and goal is not None:
            reduced = self._reduce_trace(result.steps, result.facts, goal)
            return InferenceResult(
                strategy=strategy,
                facts=result.facts,
                derived_facts=result.derived_facts,
                solved=result.solved,
                steps=result.steps,
                reduced_steps=reduced,
            )
        return result

    def _forward(
        self,
        initial: tuple[Fact, ...],
        rules: tuple[Rule, ...],
        goal: Fact | None,
        strategy: Strategy,
    ) -> InferenceResult:
        facts: list[Fact] = []
        index: dict[tuple[str, str, tuple[str, ...]], Fact] = {}
        derived: list[Fact] = []
        steps: list[TraceStep] = []

        for fact in initial:
            self._add_fact(fact, facts, index)
        self._expand_relations(facts, index, derived, steps)

        for _ in range(self.max_iterations):
            changed = False
            for rule in rules:
                for bindings, evidence in self._matching_bindings(rule.hypothesis, facts):
                    output_ids: list[str] = []
                    for clause in rule.goals:
                        produced = self._instantiate(clause, bindings)
                        if produced is None:
                            continue
                        fact_id = f"derived:{len(derived) + 1}"
                        produced = Fact(
                            predicate=produced.predicate,
                            arguments=produced.arguments,
                            fact_type=produced.fact_type,
                            fact_id=fact_id,
                            confidence=min((item.confidence for item in evidence), default=1.0),
                            source=rule.source or "inference_engine",
                            provenance={
                                "rule_code": rule.code,
                                "evidence_fact_ids": [self._fact_id(item, facts) for item in evidence],
                            },
                        )
                        if self._add_fact(produced, facts, index):
                            derived.append(produced)
                            output_ids.append(fact_id)
                            changed = True
                    if output_ids:
                        steps.append(
                            TraceStep(
                                step_no=len(steps) + 1,
                                rule_code=rule.code,
                                input_fact_ids=tuple(self._fact_id(item, facts) for item in evidence),
                                output_fact_ids=tuple(output_ids),
                                explanation=self._explain(rule, bindings),
                                bindings=dict(bindings),
                            )
                        )
                        self._expand_relations(facts, index, derived, steps)
                    if len(facts) >= self.max_facts:
                        changed = False
                        break
                if len(facts) >= self.max_facts:
                    break
            if goal is not None and self._find_goal(facts, goal) is not None:
                break
            if not changed:
                break

        solved = goal is None or self._find_goal(facts, goal) is not None
        reduced = self._reduce_trace(tuple(steps), tuple(facts), goal) if goal else tuple(steps)
        return InferenceResult(
            strategy=strategy,
            facts=tuple(facts),
            derived_facts=tuple(derived),
            solved=solved,
            steps=tuple(steps),
            reduced_steps=reduced,
        )

    def _matching_bindings(
        self,
        clauses: tuple[Clause, ...],
        facts: list[Fact],
    ) -> list[tuple[dict[str, Any], tuple[Fact, ...]]]:
        states: list[tuple[dict[str, Any], tuple[Fact, ...]]] = [({}, ())]
        predicates = [clause for clause in clauses if clause.operator is None]
        conditions = [clause for clause in clauses if clause.operator is not None]
        for clause in predicates:
            next_states: list[tuple[dict[str, Any], tuple[Fact, ...]]] = []
            for bindings, evidence in states:
                for fact in facts:
                    unified = self._unify_clause(clause, fact, bindings)
                    if unified is not None:
                        next_states.append((unified, evidence + (fact,)))
            states = self._unique_states(next_states)
            if not states:
                return []
        return [
            (bindings, evidence)
            for bindings, evidence in states
            if all(self._evaluate(clause, bindings) for clause in conditions)
        ]

    def _unify_clause(
        self,
        clause: Clause,
        fact: Fact,
        bindings: dict[str, Any],
    ) -> dict[str, Any] | None:
        if clause.predicate != fact.predicate or len(clause.arguments) != len(fact.arguments):
            return None
        if clause.fact_type is not None and clause.fact_type != fact.fact_type:
            return None
        unified = self._unify_arguments(clause.arguments, fact.arguments, bindings)
        if unified is not None:
            return unified
        relation = self.relations.get(fact.predicate)
        if relation and relation.symmetric and len(fact.arguments) == 2:
            return self._unify_arguments(clause.arguments, tuple(reversed(fact.arguments)), bindings)
        return None

    @staticmethod
    def _unify_arguments(
        patterns: tuple[Any, ...],
        values: tuple[Any, ...],
        bindings: dict[str, Any],
    ) -> dict[str, Any] | None:
        result = dict(bindings)
        for pattern, value in zip(patterns, values):
            if isinstance(pattern, str) and pattern.startswith("?"):
                if pattern in result and canonical_value(result[pattern]) != canonical_value(value):
                    return None
                result[pattern] = value
            elif canonical_value(pattern) != canonical_value(value):
                return None
        return result

    @staticmethod
    def _resolve(value: Any, bindings: dict[str, Any]) -> tuple[bool, Any]:
        if isinstance(value, str) and value.startswith("?"):
            return value in bindings, bindings.get(value)
        return True, value

    def _evaluate(self, clause: Clause, bindings: dict[str, Any]) -> bool:
        left_bound, left = self._resolve(clause.left, bindings)
        right_bound, right = self._resolve(clause.right, bindings)
        if not left_bound or not right_bound:
            return False
        operators = {
            "eq": lambda: canonical_value(left) == canonical_value(right),
            "ne": lambda: canonical_value(left) != canonical_value(right),
            "lt": lambda: left < right,
            "lte": lambda: left <= right,
            "gt": lambda: left > right,
            "gte": lambda: left >= right,
        }
        try:
            return bool(operators[clause.operator or ""]())
        except (KeyError, TypeError, ValueError):
            return False

    @staticmethod
    def _instantiate(clause: Clause, bindings: dict[str, Any]) -> Fact | None:
        if clause.predicate is None or clause.operator is not None:
            return None
        args: list[Any] = []
        for argument in clause.arguments:
            if isinstance(argument, str) and argument.startswith("?"):
                if argument not in bindings:
                    return None
                args.append(bindings[argument])
            else:
                args.append(argument)
        return Fact(
            predicate=clause.predicate,
            arguments=tuple(args),
            fact_type=clause.fact_type or "binary_relation",
        )

    def _add_fact(
        self,
        fact: Fact,
        facts: list[Fact],
        index: dict[tuple[str, str, tuple[str, ...]], Fact],
    ) -> bool:
        relation = self.relations.get(fact.predicate)
        key = fact.key(bool(relation and relation.symmetric))
        if key in index:
            return False
        if fact.fact_id is None:
            fact = Fact(
                predicate=fact.predicate,
                arguments=fact.arguments,
                fact_type=fact.fact_type,
                fact_id=f"fact:{len(facts) + 1}",
                confidence=fact.confidence,
                source=fact.source,
                provenance=fact.provenance,
            )
        index[key] = fact
        facts.append(fact)
        return True

    def _expand_relations(
        self,
        facts: list[Fact],
        index: dict[tuple[str, str, tuple[str, ...]], Fact],
        derived: list[Fact],
        steps: list[TraceStep],
    ) -> None:
        for predicate, spec in self.relations.items():
            if not spec.transitive:
                continue
            changed = True
            while changed and len(facts) < self.max_facts:
                changed = False
                edges = [fact for fact in facts if fact.predicate == predicate and len(fact.arguments) == 2]
                for left in edges:
                    for right in edges:
                        if canonical_value(left.arguments[1]) != canonical_value(right.arguments[0]):
                            continue
                        candidate = Fact(
                            predicate=predicate,
                            arguments=(left.arguments[0], right.arguments[1]),
                            fact_type="binary_relation",
                            fact_id=f"derived:{len(derived) + 1}",
                            confidence=min(left.confidence, right.confidence),
                            source="relation_closure",
                            provenance={
                                "rule_code": f"REL_TRANSITIVE_{predicate}",
                                "evidence_fact_ids": [self._fact_id(left, facts), self._fact_id(right, facts)],
                            },
                        )
                        if self._add_fact(candidate, facts, index):
                            derived.append(candidate)
                            changed = True
                            steps.append(
                                TraceStep(
                                    step_no=len(steps) + 1,
                                    rule_code=f"REL_TRANSITIVE_{predicate}",
                                    input_fact_ids=(self._fact_id(left, facts), self._fact_id(right, facts)),
                                    output_fact_ids=(candidate.fact_id or "",),
                                    explanation=f"Applied transitivity for relation {predicate}.",
                                    bindings={},
                                )
                            )

    def _goal_relevant_rules(self, goal_predicate: str) -> tuple[Rule, ...]:
        needed = {goal_predicate}
        selected: set[str] = set()
        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                if rule.code in selected:
                    continue
                if any(goal.predicate in needed for goal in rule.goals):
                    selected.add(rule.code)
                    needed.update(
                        clause.predicate
                        for clause in rule.hypothesis
                        if clause.predicate is not None
                    )
                    changed = True
        return tuple(rule for rule in self.rules if rule.code in selected)

    def _find_goal(self, facts: Iterable[Fact], goal: Fact) -> Fact | None:
        clause = Clause(predicate=goal.predicate, arguments=goal.arguments, fact_type=goal.fact_type)
        return next((fact for fact in facts if self._unify_clause(clause, fact, {}) is not None), None)

    def _reduce_trace(
        self,
        steps: tuple[TraceStep, ...],
        facts: tuple[Fact, ...],
        goal: Fact | None,
    ) -> tuple[TraceStep, ...]:
        if goal is None:
            return steps
        matched = self._find_goal(facts, goal)
        if matched is None or matched.fact_id is None:
            return ()
        needed = {matched.fact_id}
        selected: list[TraceStep] = []
        for step in reversed(steps):
            if needed.intersection(step.output_fact_ids):
                selected.append(step)
                needed.update(step.input_fact_ids)
        return tuple(reversed(selected))

    @staticmethod
    def _fact_id(fact: Fact, facts: list[Fact] | tuple[Fact, ...]) -> str:
        return fact.fact_id or f"fact:{facts.index(fact) + 1}"

    @staticmethod
    def _unique_states(
        states: list[tuple[dict[str, Any], tuple[Fact, ...]]],
    ) -> list[tuple[dict[str, Any], tuple[Fact, ...]]]:
        seen: set[tuple[tuple[str, str], ...]] = set()
        result = []
        for bindings, evidence in states:
            key = tuple(sorted((name, canonical_value(value)) for name, value in bindings.items()))
            if key not in seen:
                seen.add(key)
                result.append((bindings, evidence))
        return result

    @staticmethod
    def _explain(rule: Rule, bindings: dict[str, Any]) -> str:
        values = {name.lstrip("?"): value for name, value in bindings.items()}
        try:
            return rule.explanation_template.format(**values)
        except (KeyError, ValueError):
            return rule.explanation_template or rule.name
