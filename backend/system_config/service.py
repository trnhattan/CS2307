from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.system_config.errors import ConfigurationError
from backend.system_config.repository import SystemConfigRepository
from backend.system_config.schemas import ConfigItem, DifficultyDistribution


class SystemConfigService:
    def __init__(
        self,
        repository: SystemConfigRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory

    async def list_items(self) -> list[ConfigItem]:
        async with self._session_factory() as session:
            rows = await self._repository.list_items(session)
        return [ConfigItem(**row) for row in rows]

    async def update_items(
        self,
        updates: list[tuple[str, Any]],
        updated_by: str,
    ) -> list[ConfigItem]:
        async with self._session_factory() as session:
            current_rows = await self._repository.list_items(session)
            current = {row["prop_key"]: row for row in current_rows}
            normalized: list[tuple[str, Any]] = []
            for key, value in updates:
                item = current.get(key)
                if item is None:
                    raise ConfigurationError(f"Unknown configuration key: {key}")
                if not item["is_editable"]:
                    raise ConfigurationError(f"Configuration is read-only: {key}")
                normalized.append((key, self.validate_value(key, value)))

            merged = {key: row["prop_value"] for key, row in current.items()}
            merged.update(dict(normalized))
            self._validate_cross_fields(merged)

            updated: list[ConfigItem] = []
            for key, value in normalized:
                row = await self._repository.update_item(
                    session,
                    prop_key=key,
                    prop_value=value,
                    updated_by=updated_by,
                )
                if row is None:
                    raise ConfigurationError(f"Unable to update configuration: {key}")
                updated.append(ConfigItem(**row))
            await session.commit()
        return updated

    @classmethod
    def validate_value(cls, key: str, value: Any) -> Any:
        integer_ranges = {
            "QUESTION_BANK_TARGET_SIZE": (1, 100_000),
            "DEFAULT_EXAM_QUESTION_COUNT": (1, 100),
            "DISPLAY_OPTION_COUNT": (2, 10),
            "CAT_MIN_QUESTION_COUNT": (1, 100),
            "CAT_MAX_QUESTION_COUNT": (1, 100),
        }
        if key in integer_ranges:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConfigurationError(f"{key} must be an integer")
            lower, upper = integer_ranges[key]
            if not lower <= value <= upper:
                raise ConfigurationError(f"{key} must be between {lower} and {upper}")
            return value

        if key in {"MUST_INCLUDE_BEST_ANSWER", "RANDOMIZE_OPTION_ORDER"}:
            if not isinstance(value, bool):
                raise ConfigurationError(f"{key} must be true or false")
            return value

        if key == "CAT_INITIAL_THETA":
            return cls._number_in_range(key, value, -6, 6)
        if key == "CAT_STOP_STANDARD_ERROR":
            return cls._number_in_range(key, value, 0.05, 3)
        if key == "FIXED_EXAM_DIFFICULTY_DISTRIBUTION":
            distribution = DifficultyDistribution.model_validate(value)
            return distribution.model_dump()
        if key == "ANSWER_POOL_SIZE_BY_BLOOM":
            expected = {"remember", "understand", "apply", "analyze", "evaluate"}
            if not isinstance(value, dict) or set(value) != expected:
                raise ConfigurationError(f"{key} requires all five Bloom levels")
            if any(
                isinstance(item, bool) or not isinstance(item, int) or not 2 <= item <= 20
                for item in value.values()
            ):
                raise ConfigurationError(f"{key} values must be integers from 2 to 20")
            return value
        if key == "EXAM_ALLOWED_QUESTION_STATUSES":
            allowed = {"draft", "reviewed", "active", "retired"}
            if (
                not isinstance(value, list)
                or not value
                or len(value) != len(set(value))
                or any(item not in allowed for item in value)
            ):
                raise ConfigurationError(f"{key} contains invalid statuses")
            return value
        if key == "EXAM_GENERATION_STRATEGY":
            if value != "irt_information_balanced":
                raise ConfigurationError("Only irt_information_balanced is implemented")
            return value
        raise ConfigurationError(f"Updates are not supported for {key}")

    @staticmethod
    def _number_in_range(key: str, value: Any, lower: float, upper: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigurationError(f"{key} must be numeric")
        number = float(value)
        if not lower <= number <= upper:
            raise ConfigurationError(f"{key} must be between {lower} and {upper}")
        return number

    @staticmethod
    def _validate_cross_fields(values: dict[str, Any]) -> None:
        minimum = int(values["CAT_MIN_QUESTION_COUNT"])
        maximum = int(values["CAT_MAX_QUESTION_COUNT"])
        if minimum > maximum:
            raise ConfigurationError(
                "CAT_MIN_QUESTION_COUNT cannot exceed CAT_MAX_QUESTION_COUNT"
            )
