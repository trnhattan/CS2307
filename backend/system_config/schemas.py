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
