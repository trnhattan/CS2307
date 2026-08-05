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


def test_admin_llm_provider_and_model_must_be_compatible() -> None:
    assert SystemConfigService.validate_value("LLM_PROVIDER", "gemini") == "gemini"
    with pytest.raises(ConfigurationError, match="LLM_PROVIDER"):
        SystemConfigService.validate_value("LLM_PROVIDER", "unknown")
    with pytest.raises(ConfigurationError, match="Gemini requires"):
        SystemConfigService._validate_cross_fields(
            {
                "CAT_MIN_QUESTION_COUNT": 5,
                "CAT_MAX_QUESTION_COUNT": 20,
                "LLM_PROVIDER": "gemini",
                "LLM_MODEL": "~deepseek/deepseek-v4-flash-latest",
            }
        )


def test_profile_relationship_thresholds_must_be_ordered() -> None:
    with pytest.raises(ConfigurationError):
        SystemConfigService._validate_cross_fields(
            {
                "CAT_MIN_QUESTION_COUNT": 5,
                "CAT_MAX_QUESTION_COUNT": 20,
                "LEARNING_REMEDIATE_THRESHOLD": 0.5,
                "LEARNING_ADVANCE_THRESHOLD": 0.75,
                "PROFILE_NEEDS_REVIEW_THRESHOLD": 0.7,
                "PROFILE_DEVELOPING_THRESHOLD": 0.6,
                "PROFILE_MASTERY_THRESHOLD": 0.75,
            }
        )
