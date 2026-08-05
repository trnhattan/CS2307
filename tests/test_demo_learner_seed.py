from scripts.seed_demo_learner import STAGES, _mastered_order


def test_demo_learner_has_realistic_growth_profile() -> None:
    database = [stage.score_percent for stage in STAGES if stage.subject_code == "DATABASE"]
    network = [stage.score_percent for stage in STAGES if stage.subject_code == "NETWORK"]

    assert database == [65, 75, 85, 90, 95]
    assert network == [45, 55, 65]
    assert database == sorted(database)
    assert network == sorted(network)
    assert database[-1] >= 90
    assert 55 <= network[-1] < 75


def test_demo_mastery_order_is_deterministic_and_subject_specific() -> None:
    database = _mastered_order("DATABASE", 20)
    network = _mastered_order("NETWORK", 20)

    assert database == _mastered_order("DATABASE", 20)
    assert len(database) == len(set(database)) == 20
    assert set(database) == set(network)
    assert database != network
