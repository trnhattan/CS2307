import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from backend.cat.selector import CATCandidate, select_next_question
from backend.cat.stopping import evaluate_stopping
from backend.irt.model import IRTResponse, estimate_ability_eap, probability_3pl


@dataclass(frozen=True, slots=True)
class EvaluationItem:
    question_id: int
    question_code: str
    difficulty_label: str
    difficulty_norm: float
    bloom_level: str
    topic_code: str
    unit_codes: tuple[str, ...]
    irt_a: float
    irt_b: float
    irt_c: float
    avg_time_sec: int

    def candidate(self) -> CATCandidate:
        return CATCandidate(
            question_id=self.question_id,
            question_code=self.question_code,
            difficulty_label=self.difficulty_label,
            topic_code=self.topic_code,
            unit_codes=self.unit_codes,
            irt_a=self.irt_a,
            irt_b=self.irt_b,
            irt_c=self.irt_c,
        )


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    simulations: int
    question_count: int
    rmse: float
    mae: float
    bias: float
    mean_questions: float
    convergence_rate: float
    mean_se_by_step: dict[int, float]
    item_fit: list[dict]
    discrimination: list[dict]
    bank_summary: dict
    limitations: list[str]

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_cat(
    items: list[EvaluationItem],
    *,
    simulations: int = 100,
    seed: int = 2307,
    minimum: int = 10,
    maximum: int = 30,
    se_threshold: float = 0.3,
    epsilon: float = 0.05,
    stability_window: int = 3,
    scale: float = 1.7,
    difficulty_distribution: dict[str, float] | None = None,
    information_weight: float = 1.0,
    weak_unit_weight: float = 0.35,
    content_balance_weight: float = 0.2,
    exposure_penalty: float = 0.15,
) -> EvaluationResult:
    if not items:
        raise ValueError("At least one active item is required for CAT evaluation")
    rng = random.Random(seed)
    maximum = min(maximum, len(items))
    minimum = min(minimum, maximum)
    sessions = []
    se_steps: dict[int, list[float]] = defaultdict(list)
    item_observations: dict[str, list[tuple[float, bool, float]]] = defaultdict(list)
    true_values = [(-3 + 6 * index / max(1, simulations - 1)) for index in range(simulations)]
    target_distribution = difficulty_distribution or {
        "easy": 0.3,
        "medium": 0.4,
        "hard": 0.3,
    }

    for true_theta in true_values:
        remaining = list(items)
        responses: list[IRTResponse] = []
        theta_history = [0.0]
        difficulty_usage: Counter[str] = Counter()
        stop_reason = "maximum_questions"
        for step in range(1, maximum + 1):
            selection = select_next_question(
                [item.candidate() for item in remaining],
                theta=theta_history[-1],
                unit_mastery={},
                difficulty_usage=difficulty_usage,
                target_distribution=target_distribution,
                information_weight=information_weight,
                weak_unit_weight=weak_unit_weight,
                content_balance_weight=content_balance_weight,
                exposure_penalty=exposure_penalty,
                scale=scale,
            )
            if selection is None:
                stop_reason = "question_pool_exhausted"
                break
            item = next(
                value for value in remaining if value.question_id == selection.candidate.question_id
            )
            expected = probability_3pl(true_theta, item.irt_a, item.irt_b, item.irt_c, scale)
            correct = rng.random() < expected
            responses.append(IRTResponse(item.irt_a, item.irt_b, item.irt_c, correct))
            estimate = estimate_ability_eap(responses, scale=scale)
            theta_history.append(estimate.theta)
            se_steps[step].append(estimate.standard_error)
            item_observations[item.question_code].append((true_theta, correct, expected))
            difficulty_usage[item.difficulty_label] += 1
            remaining.remove(item)
            decision = evaluate_stopping(
                answered_count=step,
                minimum=minimum,
                maximum=maximum,
                standard_error=estimate.standard_error,
                se_threshold=se_threshold,
                theta_history=theta_history,
                epsilon=epsilon,
                stability_window=stability_window,
                candidates_remaining=len(remaining),
            )
            if decision.should_stop:
                stop_reason = decision.reason or "completed"
                break
        sessions.append(
            {
                "true": true_theta,
                "estimated": theta_history[-1],
                "questions": len(responses),
                "stop_reason": stop_reason,
            }
        )

    errors = [row["estimated"] - row["true"] for row in sessions]
    limitations = []
    if len(items) < 200:
        limitations.append(
            f"Evaluation uses the current {len(items)} provided questions; no questions were generated to reach 200."
        )
    if len({item.topic_code for item in items}) < 5:
        limitations.append("Topic diversity is below the assignment recommendation of five topics.")
    if len(items) < 50:
        limitations.append(
            "RMSE, MAE, bias, and convergence are exploratory because the subject pool has fewer than 50 items."
        )
    limitations.append(
        "Item-fit and discrimination are simulation diagnostics, not empirical calibration from real student responses."
    )
    observed_per_item = [len(values) for values in item_observations.values()]
    if observed_per_item and min(observed_per_item) < 20:
        limitations.append(
            "Item-fit and empirical discrimination are unreliable for items with fewer than 20 simulated responses."
        )
    b_values = [item.irt_b for item in items]
    if max(b_values) - min(b_values) < 3:
        limitations.append(
            "The IRT difficulty range is narrow relative to the simulated theta range [-3, 3]."
        )
    return EvaluationResult(
        simulations=simulations,
        question_count=len(items),
        rmse=math.sqrt(sum(error * error for error in errors) / len(errors)),
        mae=sum(abs(error) for error in errors) / len(errors),
        bias=sum(errors) / len(errors),
        mean_questions=sum(row["questions"] for row in sessions) / len(sessions),
        convergence_rate=sum(
            row["stop_reason"] in {"standard_error", "theta_stable"} for row in sessions
        ) / len(sessions),
        mean_se_by_step={
            step: sum(values) / len(values) for step, values in sorted(se_steps.items())
        },
        item_fit=_item_fit(item_observations),
        discrimination=_discrimination(item_observations),
        bank_summary=_bank_summary(items),
        limitations=limitations,
    )


def _item_fit(observations: dict[str, list[tuple[float, bool, float]]]) -> list[dict]:
    return [
        {
            "question_code": code,
            "responses": len(values),
            "observed_correct": sum(correct for _, correct, _ in values) / len(values),
            "expected_correct": sum(expected for _, _, expected in values) / len(values),
            "absolute_gap": abs(
                sum(correct for _, correct, _ in values) / len(values)
                - sum(expected for _, _, expected in values) / len(values)
            ),
        }
        for code, values in sorted(observations.items())
    ]


def _discrimination(
    observations: dict[str, list[tuple[float, bool, float]]]
) -> list[dict]:
    rows = []
    for code, values in sorted(observations.items()):
        low = [correct for theta, correct, _ in values if theta < 0]
        high = [correct for theta, correct, _ in values if theta >= 0]
        rows.append(
            {
                "question_code": code,
                "high_minus_low": (
                    sum(high) / len(high) - sum(low) / len(low) if high and low else None
                ),
                "high_responses": len(high),
                "low_responses": len(low),
            }
        )
    return rows


def _bank_summary(items: list[EvaluationItem]) -> dict:
    difficulty = Counter(item.difficulty_label for item in items)
    bloom = Counter(item.bloom_level for item in items)
    average_b = sum(item.irt_b for item in items) / len(items)
    average_time = {
        label: sum(item.avg_time_sec for item in items if item.difficulty_label == label)
        / max(1, difficulty[label])
        for label in ("easy", "medium", "hard")
    }
    return {
        "difficulty_distribution": dict(difficulty),
        "bloom_distribution": dict(bloom),
        "average_irt_b": average_b,
        "average_time_by_difficulty": average_time,
        "bloom_difficulty_pairs": [
            {"bloom": item.bloom_level, "difficulty_norm": item.difficulty_norm}
            for item in items
        ],
    }
