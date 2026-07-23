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


@dataclass(frozen=True, slots=True)
class SelectedQuestion:
    candidate: QuestionCandidate
    information: float
    reason: str


def allocate_difficulty_quotas(
    count: int,
    distribution: dict[str, float],
    availability: Counter[str],
) -> dict[str, int]:
    labels = ("easy", "medium", "hard")
    raw = {label: count * max(0.0, distribution.get(label, 0.0)) for label in labels}
    quotas = {label: min(availability[label], math.floor(raw[label])) for label in labels}

    while sum(quotas.values()) < min(count, sum(availability.values())):
        choices = [label for label in labels if quotas[label] < availability[label]]
        if not choices:
            break
        label = max(
            choices,
            key=lambda item: (raw[item] - quotas[item], availability[item] - quotas[item]),
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
) -> list[SelectedQuestion]:
    if count <= 0:
        return []

    rng = random.Random(seed)
    availability = Counter(item.difficulty_label for item in candidates)
    quotas = allocate_difficulty_quotas(count, distribution, availability)
    topic_usage: Counter[str] = Counter()
    selected: list[SelectedQuestion] = []
    remaining = list(candidates)

    for label in ("easy", "medium", "hard"):
        for _ in range(quotas[label]):
            pool = [item for item in remaining if item.difficulty_label == label]
            if not pool:
                break
            chosen = _best_candidate(pool, topic_usage, theta, scale, rng)
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
                        f"Phù hợp mức {label}, cung cấp Fisher information "
                        f"{information:.3f} tại theta={theta:.2f}, đồng thời cân bằng "
                        f"chủ đề {chosen.topic_name}."
                    ),
                )
            )
            topic_usage[chosen.topic_name] += 1
            remaining.remove(chosen)

    while len(selected) < min(count, len(candidates)) and remaining:
        chosen = _best_candidate(remaining, topic_usage, theta, scale, rng)
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
                    f"Bổ sung để đủ blueprint; Fisher information {information:.3f} "
                    f"tại theta={theta:.2f}."
                ),
            )
        )
        topic_usage[chosen.topic_name] += 1
        remaining.remove(chosen)

    rng.shuffle(selected)
    return selected


def _best_candidate(
    candidates: list[QuestionCandidate],
    topic_usage: Counter[str],
    theta: float,
    scale: float,
    rng: random.Random,
) -> QuestionCandidate:
    return max(
        candidates,
        key=lambda item: (
            fisher_information_3pl(theta, item.irt_a, item.irt_b, item.irt_c, scale)
            + 0.12 / (1 + topic_usage[item.topic_name])
            + rng.random() * 0.01
        ),
    )
