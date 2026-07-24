from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.supervisor.repository import SupervisorRepository
from backend.supervisor.schemas import (
    AdminDashboardResponse,
    SupervisorDashboardResponse,
)
from backend.system_config.repository import SystemConfigRepository
from backend.system_config.schemas import (
    CATConfigResponse,
    CATConfigUpdate,
    DifficultyConfigResponse,
    DifficultyDistribution,
)
from backend.system_config.service import SystemConfigService


class SupervisorService:
    async def cat_config(self) -> CATConfigResponse:
        items = await self._config_service().list_items()
        values = {item.prop_key: item.prop_value for item in items}
        return self._cat_config_response(values)

    async def update_cat_config(
        self, request: CATConfigUpdate, updated_by: str
    ) -> CATConfigResponse:
        values = {
            "CAT_MIN_QUESTION_COUNT": request.minimum,
            "CAT_MAX_QUESTION_COUNT": request.maximum,
            "CAT_STOP_STANDARD_ERROR": request.standard_error_threshold,
            "CAT_STABILITY_EPSILON": request.stability_epsilon,
            "CAT_STABILITY_WINDOW": request.stability_window,
            "CAT_INFORMATION_WEIGHT": request.information_weight,
            "CAT_WEAK_UNIT_WEIGHT": request.weak_unit_weight,
            "CAT_CONTENT_BALANCE_WEIGHT": request.content_balance_weight,
            "CAT_EXPOSURE_PENALTY": request.exposure_penalty,
            "CAT_DIFFICULTY_DISTRIBUTION": request.difficulty_distribution.model_dump(),
            "CAT_TOPIC_CODES": request.topic_codes,
            "CAT_SKILL_CODES": request.skill_codes,
            "CAT_BLOOM_LEVELS": request.bloom_levels,
        }
        await self._config_service().update_items(list(values.items()), updated_by)
        return self._cat_config_response(values)

    def _config_service(self) -> SystemConfigService:
        return SystemConfigService(SystemConfigRepository(), self._session_factory)

    @staticmethod
    def _cat_config_response(values: dict) -> CATConfigResponse:
        return CATConfigResponse(
            minimum=int(values["CAT_MIN_QUESTION_COUNT"]),
            maximum=int(values["CAT_MAX_QUESTION_COUNT"]),
            standard_error_threshold=float(values["CAT_STOP_STANDARD_ERROR"]),
            stability_epsilon=float(values["CAT_STABILITY_EPSILON"]),
            stability_window=int(values["CAT_STABILITY_WINDOW"]),
            information_weight=float(values["CAT_INFORMATION_WEIGHT"]),
            weak_unit_weight=float(values["CAT_WEAK_UNIT_WEIGHT"]),
            content_balance_weight=float(values["CAT_CONTENT_BALANCE_WEIGHT"]),
            exposure_penalty=float(values["CAT_EXPOSURE_PENALTY"]),
            difficulty_distribution=values["CAT_DIFFICULTY_DISTRIBUTION"],
            topic_codes=values.get("CAT_TOPIC_CODES", []),
            skill_codes=values.get("CAT_SKILL_CODES", []),
            bloom_levels=values.get("CAT_BLOOM_LEVELS", []),
        )

    def __init__(
        self,
        repository: SupervisorRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory

    async def dashboard(self) -> SupervisorDashboardResponse:
        async with self._session_factory() as session:
            summary = await self._repository.summary(session)
            takers = await self._repository.takers(session)
            sessions = await self._repository.sessions(session)
            abilities = await self._repository.abilities(session)
        return SupervisorDashboardResponse(
            summary=summary,
            takers=takers,
            sessions=sessions,
            abilities=abilities,
        )

    async def difficulty_config(self) -> DifficultyConfigResponse:
        config_service = SystemConfigService(
            SystemConfigRepository(),
            self._session_factory,
        )
        items = await config_service.list_items()
        item = next(
            value
            for value in items
            if value.prop_key == "FIXED_EXAM_DIFFICULTY_DISTRIBUTION"
        )
        return DifficultyConfigResponse(
            distribution=DifficultyDistribution.model_validate(item.prop_value),
            updated_by=item.updated_by,
            updated_at=item.updated_at,
        )

    async def update_difficulty_config(
        self,
        distribution: DifficultyDistribution,
        updated_by: str,
    ) -> DifficultyConfigResponse:
        config_service = SystemConfigService(
            SystemConfigRepository(),
            self._session_factory,
        )
        items = await config_service.update_items(
            [
                (
                    "FIXED_EXAM_DIFFICULTY_DISTRIBUTION",
                    distribution.model_dump(),
                )
            ],
            updated_by,
        )
        item = items[0]
        return DifficultyConfigResponse(
            distribution=DifficultyDistribution.model_validate(item.prop_value),
            updated_by=item.updated_by,
            updated_at=item.updated_at,
        )

    async def admin_dashboard(self) -> AdminDashboardResponse:
        async with self._session_factory() as session:
            summary = await self._repository.summary(session)
            takers = await self._repository.takers(session)
            sessions = await self._repository.sessions(session)
            abilities = await self._repository.abilities(session)
            accounts = await self._repository.accounts(session)
            system_config = await self._repository.system_config(session)
        return AdminDashboardResponse(
            assessment=SupervisorDashboardResponse(
                summary=summary,
                takers=takers,
                sessions=sessions,
                abilities=abilities,
            ),
            accounts=accounts,
            system_config=system_config,
        )
