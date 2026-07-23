import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IRTResponse:
    a: float
    b: float
    c: float
    correct: bool


@dataclass(frozen=True, slots=True)
class AbilityEstimate:
    theta: float
    standard_error: float


def probability_3pl(
    theta: float,
    a: float,
    b: float,
    c: float,
    scale: float = 1.7,
) -> float:
    exponent = max(-60.0, min(60.0, -scale * a * (theta - b)))
    return c + (1.0 - c) / (1.0 + math.exp(exponent))


def fisher_information_3pl(
    theta: float,
    a: float,
    b: float,
    c: float,
    scale: float = 1.7,
) -> float:
    probability = probability_3pl(theta, a, b, c, scale)
    denominator = probability * (1.0 - c) ** 2
    if denominator <= 0:
        return 0.0
    return (
        scale**2
        * a**2
        * (1.0 - probability)
        * (probability - c) ** 2
        / denominator
    )


def estimate_ability_eap(
    responses: list[IRTResponse],
    *,
    prior_mean: float = 0.0,
    prior_standard_error: float = 1.0,
    scale: float = 1.7,
) -> AbilityEstimate:
    grid = [(-4.0 + index * 0.05) for index in range(161)]
    prior_sd = max(0.15, prior_standard_error)
    log_weights: list[float] = []

    for theta in grid:
        log_weight = -0.5 * ((theta - prior_mean) / prior_sd) ** 2
        for response in responses:
            probability = probability_3pl(
                theta,
                response.a,
                response.b,
                response.c,
                scale,
            )
            probability = min(1.0 - 1e-12, max(1e-12, probability))
            log_weight += (
                math.log(probability)
                if response.correct
                else math.log1p(-probability)
            )
        log_weights.append(log_weight)

    maximum = max(log_weights)
    weights = [math.exp(value - maximum) for value in log_weights]
    total = sum(weights)
    theta = sum(value * weight for value, weight in zip(grid, weights)) / total
    variance = sum(
        weight * (value - theta) ** 2 for value, weight in zip(grid, weights)
    ) / total
    return AbilityEstimate(
        theta=max(-6.0, min(6.0, theta)),
        standard_error=max(0.05, math.sqrt(variance)),
    )


def mastery_probability(theta: float) -> float:
    exponent = max(-60.0, min(60.0, -theta))
    return 1.0 / (1.0 + math.exp(exponent))
