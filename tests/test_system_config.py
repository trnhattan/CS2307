import pytest

from backend.system_config.errors import ConfigurationError
from backend.system_config.schemas import DifficultyDistribution
from backend.system_config.service import SystemConfigService


def test_difficulty_distribution_is_normalized() -> None:
    distribution = DifficultyDistribution(easy=0.6, medium=0.8, hard=0.6)

    assert distribution.easy == pytest.approx(0.3)
    assert distribution.medium == pytest.approx(0.4)
    assert distribution.hard == pytest.approx(0.3)


def test_config_validation_rejects_unsupported_strategy() -> None:
    with pytest.raises(ConfigurationError):
        SystemConfigService.validate_value(
            "EXAM_GENERATION_STRATEGY",
            "unimplemented_strategy",
        )


def test_config_validation_checks_bloom_pool_shape() -> None:
    with pytest.raises(ConfigurationError):
        SystemConfigService.validate_value(
            "ANSWER_POOL_SIZE_BY_BLOOM",
            {"remember": 4},
        )
