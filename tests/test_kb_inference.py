from backend.kb.inference import InferenceEngine
from backend.kb.models import Clause, Fact, RelationSpec, Rule


def recommendation_rules() -> tuple[Rule, ...]:
    return (
        Rule(
            code="R_LOW",
            name="Low mastery",
            hypothesis=(
                Clause(predicate="unit_accuracy", arguments=("?student", "?unit", "?value")),
                Clause(operator="lt", left="?value", right=0.5),
            ),
            goals=(
                Clause(predicate="weak_unit", arguments=("?student", "?unit")),
                Clause(
                    predicate="recommended_next",
                    arguments=("?student", "?unit", "remediate"),
                ),
            ),
            explanation_template="{student} should remediate {unit}.",
        ),
        Rule(
            code="R_PLAN",
            name="Build plan",
            hypothesis=(Clause(predicate="weak_unit", arguments=("?student", "?unit")),),
            goals=(Clause(predicate="has_learning_plan", arguments=("?student",)),),
        ),
    )


def test_five_fact_types_are_canonical_and_deduplicated() -> None:
    facts = [
        Fact("is_a", ("q1", "Question"), "type"),
        Fact("exists", ("q1",), "determined_object"),
        Fact("difficulty", ("q1", 0.8), "constant_assignment"),
        Fact("same_as", ("q1", "q-one"), "equality"),
        Fact("measures", ("q1", "sql"), "binary_relation"),
        Fact("measures", ("q1", "sql"), "binary_relation"),
    ]
    result = InferenceEngine(()).infer(facts)
    assert len(result.facts) == 5
    assert {fact.fact_type for fact in result.facts} == {
        "type",
        "determined_object",
        "constant_assignment",
        "equality",
        "binary_relation",
    }


def test_forward_closure_conditions_and_reduced_trace() -> None:
    result = InferenceEngine(recommendation_rules()).infer(
        [Fact("unit_accuracy", ("student-1", "sql", 0.4))],
        goal=Fact("has_learning_plan", ("student-1",)),
        strategy="hybrid",
    )
    assert result.solved
    assert any(fact.predicate == "recommended_next" for fact in result.derived_facts)
    assert [step.rule_code for step in result.reduced_steps] == ["R_LOW", "R_PLAN"]
    assert all(fact.provenance.get("rule_code") for fact in result.derived_facts)


def test_backward_strategy_ignores_unrelated_rules() -> None:
    unrelated = Rule(
        code="R_UNUSED",
        name="Unused",
        hypothesis=(Clause(predicate="unrelated", arguments=("?x",)),),
        goals=(Clause(predicate="unused_goal", arguments=("?x",)),),
    )
    result = InferenceEngine((*recommendation_rules(), unrelated)).infer(
        [
            Fact("unit_accuracy", ("student-1", "sql", 0.4)),
            Fact("unrelated", ("value",)),
        ],
        goal=Fact("has_learning_plan", ("student-1",)),
        strategy="backward",
    )
    assert result.solved
    assert all(step.rule_code != "R_UNUSED" for step in result.steps)


def test_symmetric_and_transitive_relations() -> None:
    engine = InferenceEngine(
        (),
        (
            RelationSpec("similar_to", symmetric=True),
            RelationSpec("prerequisite_of", transitive=True),
        ),
    )
    result = engine.infer(
        [
            Fact("similar_to", ("q1", "q2")),
            Fact("similar_to", ("q2", "q1")),
            Fact("prerequisite_of", ("a", "b")),
            Fact("prerequisite_of", ("b", "c")),
        ]
    )
    assert len([fact for fact in result.facts if fact.predicate == "similar_to"]) == 1
    assert any(
        fact.predicate == "prerequisite_of" and fact.arguments == ("a", "c")
        for fact in result.facts
    )


def test_cycles_terminate_without_duplicate_facts() -> None:
    rules = (
        Rule(
            code="R_AB",
            name="A to B",
            hypothesis=(Clause(predicate="a", arguments=("?x",)),),
            goals=(Clause(predicate="b", arguments=("?x",)),),
        ),
        Rule(
            code="R_BA",
            name="B to A",
            hypothesis=(Clause(predicate="b", arguments=("?x",)),),
            goals=(Clause(predicate="a", arguments=("?x",)),),
        ),
    )
    result = InferenceEngine(rules, max_iterations=10).infer([Fact("a", (1,))])
    assert {(fact.predicate, fact.arguments) for fact in result.facts} == {
        ("a", (1,)),
        ("b", (1,)),
    }
