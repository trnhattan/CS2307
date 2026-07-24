from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StopDecision:
    should_stop: bool
    reason: str | None = None


def evaluate_stopping(
    *,
    answered_count: int,
    minimum: int,
    maximum: int,
    standard_error: float,
    se_threshold: float,
    theta_history: list[float],
    epsilon: float,
    stability_window: int,
    candidates_remaining: int,
) -> StopDecision:
    if answered_count >= maximum:
        return StopDecision(True, "maximum_questions")
    if candidates_remaining == 0:
        return StopDecision(True, "question_pool_exhausted")
    if answered_count < minimum:
        return StopDecision(False)
    if standard_error <= se_threshold:
        return StopDecision(True, "standard_error")
    if stability_window > 0 and len(theta_history) >= stability_window + 1:
        recent = theta_history[-(stability_window + 1) :]
        if all(abs(right - left) <= epsilon for left, right in zip(recent, recent[1:])):
            return StopDecision(True, "theta_stable")
    return StopDecision(False)
