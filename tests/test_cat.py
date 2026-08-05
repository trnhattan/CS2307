from backend.cat.schemas import CATPublicResult, CATStartResponse
from backend.cat.selector import CATCandidate, select_next_question
from backend.cat.stopping import evaluate_stopping


def candidate(
    code: str,
    *,
    difficulty: str = "medium",
    unit: str = "sql",
    b: float = 0.0,
    exposure: int = 0,
) -> CATCandidate:
    return CATCandidate(
        question_id=int(code.removeprefix("q")),
        question_code=code,
        difficulty_label=difficulty,
        topic_code=unit,
        unit_codes=(unit,),
        irt_a=1.3,
        irt_b=b,
        irt_c=0.2,
        exposure_count=exposure,
    )


def test_selector_combines_information_weakness_balance_and_exposure() -> None:
    selected = select_next_question(
        [
            candidate("q1", unit="known", exposure=20),
            candidate("q2", unit="weak", exposure=0),
        ],
        theta=0,
        unit_mastery={"known": 0.9, "weak": 0.2},
        difficulty_usage={"medium": 1},
        target_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
    )
    assert selected is not None
    assert selected.candidate.question_code == "q2"
    assert set(selected.components) == {
        "information",
        "weak_unit",
        "content_balance",
        "exposure",
        "criterion_coverage",
    }


def test_selector_is_deterministic_on_ties() -> None:
    selected = select_next_question(
        [candidate("q2"), candidate("q1")],
        theta=0,
        unit_mastery={},
        difficulty_usage={},
        target_distribution={"medium": 1.0},
    )
    assert selected is not None
    assert selected.candidate.question_code == "q1"


def test_stopping_respects_minimum_and_all_terminal_conditions() -> None:
    before_minimum = evaluate_stopping(
        answered_count=4,
        minimum=5,
        maximum=10,
        standard_error=0.1,
        se_threshold=0.3,
        theta_history=[0, 0, 0, 0],
        epsilon=0.05,
        stability_window=3,
        candidates_remaining=2,
    )
    assert not before_minimum.should_stop

    assert evaluate_stopping(
        answered_count=5,
        minimum=5,
        maximum=10,
        standard_error=0.2,
        se_threshold=0.3,
        theta_history=[0, 0.2],
        epsilon=0.05,
        stability_window=3,
        candidates_remaining=2,
    ).reason == "standard_error"

    assert evaluate_stopping(
        answered_count=6,
        minimum=5,
        maximum=10,
        standard_error=0.5,
        se_threshold=0.3,
        theta_history=[0.1, 0.12, 0.11, 0.10],
        epsilon=0.05,
        stability_window=3,
        candidates_remaining=2,
    ).reason == "theta_stable"

    assert evaluate_stopping(
        answered_count=2,
        minimum=5,
        maximum=10,
        standard_error=0.8,
        se_threshold=0.3,
        theta_history=[0.1],
        epsilon=0.05,
        stability_window=3,
        candidates_remaining=0,
    ).reason == "question_pool_exhausted"


def test_taker_cat_schemas_do_not_expose_technical_metrics() -> None:
    forbidden = {
        "theta",
        "standard_error",
        "fisher",
        "bloom",
        "selection_reason",
        "rule_code",
        "trace_id",
        "stop_reason",
        "was_correct",
    }
    assert forbidden.isdisjoint(CATStartResponse.model_fields)
    assert forbidden.isdisjoint(CATPublicResult.model_fields)
