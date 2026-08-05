from dataclasses import dataclass
from typing import Mapping

from backend.irt.model import fisher_information_3pl


@dataclass(frozen=True, slots=True)
class CATCandidate:
    question_id: int
    question_code: str
    difficulty_label: str
    topic_code: str
    unit_codes: tuple[str, ...]
    irt_a: float
    irt_b: float
    irt_c: float
    exposure_count: int = 0


@dataclass(frozen=True, slots=True)
class CATSelection:
    candidate: CATCandidate
    score: float
    information: float
    components: dict[str, float]
    reason: str


def select_next_question(
    candidates: list[CATCandidate],
    *,
    theta: float,
    unit_mastery: Mapping[str, float],
    criterion_evidence: Mapping[str, int] | None = None,
    difficulty_usage: Mapping[str, int],
    target_distribution: Mapping[str, float],
    information_weight: float = 1.0,
    weak_unit_weight: float = 0.35,
    content_balance_weight: float = 0.2,
    exposure_penalty: float = 0.15,
    criterion_coverage_weight: float = 0.3,
    scale: float = 1.7,
) -> CATSelection | None:
    if not candidates:
        return None
    max_exposure = max((candidate.exposure_count for candidate in candidates), default=0)
    criterion_evidence = criterion_evidence or {}
    total_used = sum(difficulty_usage.values())
    selections = []
    for candidate in candidates:
        information = fisher_information_3pl(
            theta, candidate.irt_a, candidate.irt_b, candidate.irt_c, scale
        )
        information_score = information / (1 + information)
        mastery_values = [unit_mastery[code] for code in candidate.unit_codes if code in unit_mastery]
        weak_score = max((1 - value for value in mastery_values), default=0.0)
        coverage_score = max(
            (1 / (1 + criterion_evidence.get(code, 0)) for code in candidate.unit_codes),
            default=0.0,
        )
        expected = target_distribution.get(candidate.difficulty_label, 0.0) * (total_used + 1)
        balance_score = max(
            0.0,
            min(1.0, expected - difficulty_usage.get(candidate.difficulty_label, 0)),
        )
        exposure_score = (
            candidate.exposure_count / max_exposure if max_exposure > 0 else 0.0
        )
        components = {
            "information": information_score,
            "weak_unit": weak_score,
            "content_balance": balance_score,
            "exposure": exposure_score,
            "criterion_coverage": coverage_score,
        }
        score = (
            information_weight * information_score
            + weak_unit_weight * weak_score
            + content_balance_weight * balance_score
            + criterion_coverage_weight * coverage_score
            - exposure_penalty * exposure_score
        )
        reason = (
            f"Fisher={information:.3f}; weak-unit priority={weak_score:.3f}; "
            f"content balance={balance_score:.3f}; exposure={exposure_score:.3f}."
            f" criterion coverage={coverage_score:.3f}."
        )
        selections.append(
            CATSelection(candidate, score, information, components, reason)
        )
    return min(selections, key=lambda item: (-item.score, item.candidate.question_code))
