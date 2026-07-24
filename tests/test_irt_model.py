import pytest

from backend.irt.model import (
    IRTResponse,
    estimate_ability_eap,
    fisher_information_3pl,
    probability_3pl,
)


def test_probability_is_monotonic_and_respects_guessing_floor() -> None:
    low = probability_3pl(-6, 1.2, 0, 0.25)
    middle = probability_3pl(0, 1.2, 0, 0.25)
    high = probability_3pl(6, 1.2, 0, 0.25)

    assert 0.25 <= low < middle < high < 1


def test_information_is_largest_near_item_difficulty() -> None:
    near = fisher_information_3pl(0, 1.4, 0, 0.2)
    far = fisher_information_3pl(-4, 1.4, 0, 0.2)

    assert near > 0
    assert near > far


def test_eap_moves_theta_in_response_direction() -> None:
    correct = estimate_ability_eap([IRTResponse(1.4, 0, 0.2, True)])
    incorrect = estimate_ability_eap([IRTResponse(1.4, 0, 0.2, False)])

    assert correct.theta > 0
    assert incorrect.theta < 0
    assert correct.standard_error > 0
    assert incorrect.standard_error > 0


def test_weighted_response_has_less_influence() -> None:
    full = estimate_ability_eap([IRTResponse(1.5, 1.0, 0.2, True)])
    partial = estimate_ability_eap([IRTResponse(1.5, 1.0, 0.2, True, weight=0.2)])

    assert 0 < partial.theta < full.theta
