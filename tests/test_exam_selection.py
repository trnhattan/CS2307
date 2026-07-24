from collections import Counter
from dataclasses import replace

from backend.exams.selection import QuestionCandidate, select_fixed_exam


def make_candidate(index: int, difficulty: str) -> QuestionCandidate:
    difficulty_b = {"easy": -1.0, "medium": 0.0, "hard": 1.0}
    return QuestionCandidate(
        question_id=index,
        question_code=f"Q_{index}",
        difficulty_label=difficulty,
        bloom_level="apply",
        topic_name=f"Topic {index % 4}",
        irt_a=1.0 + index / 100,
        irt_b=difficulty_b[difficulty],
        irt_c=0.25,
        avg_time_sec=60,
    )


def test_fixed_selection_respects_blueprint_and_has_no_repeats() -> None:
    candidates = [
        make_candidate(index, difficulty)
        for index, difficulty in enumerate(
            ["easy"] * 8 + ["medium"] * 8 + ["hard"] * 8,
            start=1,
        )
    ]
    selected = select_fixed_exam(
        candidates,
        count=10,
        theta=0,
        distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
        seed=2307,
    )

    ids = [item.candidate.question_id for item in selected]
    counts = Counter(item.candidate.difficulty_label for item in selected)
    assert len(ids) == len(set(ids)) == 10
    assert counts == {"easy": 3, "medium": 4, "hard": 3}


def test_fixed_selection_is_reproducible_with_seed() -> None:
    candidates = [make_candidate(index, "medium") for index in range(1, 11)]
    arguments = {
        "count": 5,
        "theta": 0.2,
        "distribution": {"easy": 0, "medium": 1, "hard": 0},
        "seed": 99,
    }

    first = select_fixed_exam(candidates, **arguments)
    second = select_fixed_exam(candidates, **arguments)

    assert [item.candidate.question_id for item in first] == [
        item.candidate.question_id for item in second
    ]


def test_fixed_selection_does_not_substitute_missing_difficulty() -> None:
    candidates = [make_candidate(index, "medium") for index in range(1, 11)]

    selected = select_fixed_exam(
        candidates,
        count=5,
        theta=0,
        distribution={"easy": 0.2, "medium": 0.6, "hard": 0.2},
        seed=1,
    )

    assert selected == []


def test_fixed_selection_reserves_short_items_for_time_constraint() -> None:
    candidates = [make_candidate(index, "medium") for index in range(1, 7)]
    candidates[0] = replace(candidates[0], avg_time_sec=300)

    selected = select_fixed_exam(
        candidates,
        count=5,
        theta=0,
        distribution={"easy": 0, "medium": 1, "hard": 0},
        seed=1,
        max_estimated_seconds=300,
    )

    assert len(selected) == 5
    assert sum(item.candidate.avg_time_sec for item in selected) <= 300
