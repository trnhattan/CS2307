import math
import random
from collections import Counter
from dataclasses import dataclass

from backend.irt.model import fisher_information_3pl


@dataclass(frozen=True, slots=True)
class QuestionCandidate:
    question_id: int
    question_code: str
    difficulty_label: str
    bloom_level: str
    topic_name: str
    irt_a: float
    irt_b: float
    irt_c: float
    avg_time_sec: int
    topic_code: str = "GENERAL"
    skill_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SelectedQuestion:
    candidate: QuestionCandidate
    information: float
    reason: str


def allocate_difficulty_quotas(
    count: int,
    distribution: dict[str, float],
) -> dict[str, int]:
    labels = ("easy", "medium", "hard")
    raw = {label: count * max(0.0, distribution.get(label, 0.0)) for label in labels}
    quotas = {label: math.floor(raw[label]) for label in labels}

    while sum(quotas.values()) < count:
        choices = list(labels)
        label = max(
            choices,
            key=lambda item: (raw[item] - quotas[item], -labels.index(item)),
        )
        quotas[label] += 1
    return quotas


def select_fixed_exam(
    candidates: list[QuestionCandidate],
    *,
    count: int,
    theta: float,
    distribution: dict[str, float],
    seed: int,
    scale: float = 1.7,
    max_estimated_seconds: int | None = None,
    prioritize_skill_coverage: bool = False,
) -> list[SelectedQuestion]:
    if count <= 0:
        return []

    rng = random.Random(seed)
    quotas = allocate_difficulty_quotas(count, distribution)
    availability = Counter(item.difficulty_label for item in candidates)
    if any(availability[label] < quota for label, quota in quotas.items()):
        return []
    if max_estimated_seconds is not None:
        minimum_duration = sum(
            sum(
                item.avg_time_sec
                for item in sorted(
                    (candidate for candidate in candidates if candidate.difficulty_label == label),
                    key=lambda candidate: candidate.avg_time_sec,
                )[:quota]
            )
            for label, quota in quotas.items()
        )
        if minimum_duration > max_estimated_seconds:
            return []
    topic_usage: Counter[str] = Counter()
    skill_usage: Counter[str] = Counter()
    selected: list[SelectedQuestion] = []
    remaining = list(candidates)
    estimated_seconds = 0
    outstanding = Counter(quotas)

    for label in ("easy", "medium", "hard"):
        for _ in range(quotas[label]):
            pool = [
                item
                for item in remaining
                if item.difficulty_label == label
                and _preserves_time_feasibility(
                    item,
                    remaining,
                    outstanding,
                    estimated_seconds,
                    max_estimated_seconds,
                )
            ]
            if not pool:
                return selected
            chosen = _best_candidate(
                pool,
                topic_usage,
                skill_usage,
                theta,
                scale,
                rng,
                prioritize_skill_coverage,
            )
            information = fisher_information_3pl(
                theta,
                chosen.irt_a,
                chosen.irt_b,
                chosen.irt_c,
                scale,
            )
            selected.append(
                SelectedQuestion(
                    candidate=chosen,
                    information=information,
                    reason=(
                        f"Matches the {label} target, provides Fisher information "
                        f"{information:.3f} at theta={theta:.2f}, and balances "
                        f"topic {chosen.topic_name}"
                        + (
                            ", while maximizing assessment-criterion coverage."
                            if prioritize_skill_coverage
                            else "."
                        )
                    ),
                )
            )
            estimated_seconds += chosen.avg_time_sec
            topic_usage[chosen.topic_name] += 1
            skill_usage.update(chosen.skill_codes)
            remaining.remove(chosen)
            outstanding[label] -= 1

    rng.shuffle(selected)
    return selected


def _preserves_time_feasibility(
    candidate: QuestionCandidate,
    remaining: list[QuestionCandidate],
    outstanding: Counter[str],
    elapsed: int,
    maximum: int | None,
) -> bool:
    if maximum is None:
        return True
    future = list(remaining)
    future.remove(candidate)
    quotas = outstanding.copy()
    quotas[candidate.difficulty_label] -= 1
    minimum_remaining = 0
    for label, quota in quotas.items():
        if quota <= 0:
            continue
        durations = sorted(
            item.avg_time_sec for item in future if item.difficulty_label == label
        )
        if len(durations) < quota:
            return False
        minimum_remaining += sum(durations[:quota])
    return elapsed + candidate.avg_time_sec + minimum_remaining <= maximum


def _best_candidate(
    candidates: list[QuestionCandidate],
    topic_usage: Counter[str],
    skill_usage: Counter[str],
    theta: float,
    scale: float,
    rng: random.Random,
    prioritize_skill_coverage: bool,
) -> QuestionCandidate:
    return max(
        candidates,
        key=lambda item: (
            (
                max(
                    (1 if skill_usage[code] == 0 else 0 for code in item.skill_codes),
                    default=0,
                )
                if prioritize_skill_coverage
                else 0
            ),
            fisher_information_3pl(theta, item.irt_a, item.irt_b, item.irt_c, scale)
            + 0.12 / (1 + topic_usage[item.topic_name])
            + (
                0.35 * max(
                    (1 / (1 + skill_usage[code]) for code in item.skill_codes),
                    default=0,
                )
                if prioritize_skill_coverage
                else 0
            )
            + rng.random() * 0.01
        ),
    )
