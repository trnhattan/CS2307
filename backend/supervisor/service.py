from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.supervisor.repository import SupervisorRepository
from backend.supervisor.schemas import (
    AdminDashboardResponse,
    SupervisorDashboardResponse,
)
from backend.system_config.repository import SystemConfigRepository
from backend.system_config.schemas import DifficultyConfigResponse, DifficultyDistribution
from backend.system_config.service import SystemConfigService


class SupervisorService:
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
