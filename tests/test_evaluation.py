from backend.evaluation.simulator import EvaluationItem, evaluate_cat


def bank() -> list[EvaluationItem]:
    labels = ["easy", "medium", "hard"]
    return [
        EvaluationItem(
            question_id=index,
            question_code=f"Q{index:02d}",
            difficulty_label=labels[index % 3],
            difficulty_norm=(index % 3 + 1) / 4,
            bloom_level="apply",
            topic_code=f"T{index % 5}",
            unit_codes=(f"T{index % 5}",),
            irt_a=1.0 + index / 100,
            irt_b=(-1, 0, 1)[index % 3],
            irt_c=0.2,
            avg_time_sec=60 + index,
        )
        for index in range(1, 16)
    ]


def test_evaluation_is_deterministic_and_reports_required_metrics() -> None:
    first = evaluate_cat(bank(), simulations=20, seed=7, minimum=5, maximum=10)
    second = evaluate_cat(bank(), simulations=20, seed=7, minimum=5, maximum=10)
    assert first == second
    assert first.rmse >= 0
    assert first.mae >= 0
    assert 0 <= first.convergence_rate <= 1
    assert first.mean_se_by_step
    assert first.item_fit
    assert first.discrimination
    assert first.limitations
