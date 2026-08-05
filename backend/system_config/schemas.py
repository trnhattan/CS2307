from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DifficultyDistribution(BaseModel):
    easy: float = Field(ge=0, le=1)
    medium: float = Field(ge=0, le=1)
    hard: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def normalize(self):
        total = self.easy + self.medium + self.hard
        if total <= 0:
            raise ValueError("At least one difficulty weight must be positive")
        self.easy /= total
        self.medium /= total
        self.hard /= total
        return self


class ConfigItem(BaseModel):
    prop_key: str
    prop_value: Any
    description: str
    is_editable: bool
    updated_by: str | None
    updated_at: datetime


class ConfigUpdateItem(BaseModel):
    prop_key: str = Field(min_length=1, max_length=100)
    prop_value: Any


class ConfigUpdateRequest(BaseModel):
    updates: list[ConfigUpdateItem] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_keys(self):
        keys = [item.prop_key for item in self.updates]
        if len(keys) != len(set(keys)):
            raise ValueError("Configuration keys must be unique")
        return self


class DifficultyConfigResponse(BaseModel):
    distribution: DifficultyDistribution
    updated_by: str | None
    updated_at: datetime


class CATConfigUpdate(BaseModel):
    minimum: int = Field(ge=1, le=100)
    maximum: int = Field(ge=1, le=100)
    standard_error_threshold: float = Field(ge=0.05, le=3)
    stability_epsilon: float = Field(gt=0, le=1)
    stability_window: int = Field(ge=1, le=20)
    information_weight: float = Field(ge=0, le=10)
    weak_unit_weight: float = Field(ge=0, le=10)
    content_balance_weight: float = Field(ge=0, le=10)
    exposure_penalty: float = Field(ge=0, le=10)
    criterion_coverage_weight: float = Field(default=0.3, ge=0, le=10)
    difficulty_distribution: DifficultyDistribution
    topic_codes: list[str] = Field(default_factory=list, max_length=100)
    skill_codes: list[str] = Field(default_factory=list, max_length=100)
    bloom_levels: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_lengths(self):
        if self.minimum > self.maximum:
            raise ValueError("Minimum cannot exceed maximum")
        self.topic_codes = sorted({value.strip().upper() for value in self.topic_codes if value.strip()})
        self.skill_codes = sorted({value.strip().upper() for value in self.skill_codes if value.strip()})
        self.bloom_levels = sorted({value.strip().lower() for value in self.bloom_levels if value.strip()})
        allowed = {"remember", "understand", "apply", "analyze", "evaluate"}
        if not set(self.bloom_levels) <= allowed:
            raise ValueError("Unsupported Bloom level")
        return self


class CATConfigResponse(CATConfigUpdate):
    source: str = "sys_props"
