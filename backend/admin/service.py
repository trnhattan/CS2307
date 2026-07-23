from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.admin.errors import AccountConflictError, AccountNotFoundError, AdminError
from backend.admin.repository import AdminRepository
from backend.admin.schemas import (
    AccountCreateRequest,
    AccountItem,
    AccountUpdateRequest,
    QuestionBankResponse,
    SystemOverview,
)
from backend.auth.passwords import hash_password
from backend.system_config.repository import SystemConfigRepository
from backend.system_config.schemas import ConfigItem
from backend.system_config.service import SystemConfigService


class AdminService:
    def __init__(
        self,
        repository: AdminRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory

    async def overview(self) -> SystemOverview:
        async with self._session_factory() as session:
            row = await self._repository.system_overview(session)
        return SystemOverview(**row)

    async def question_bank(self) -> QuestionBankResponse:
        async with self._session_factory() as session:
            subjects = await self._repository.question_bank_subjects(session)
            questions = await self._repository.questions(session)
        return QuestionBankResponse(
            total_questions=sum(row["total_questions"] for row in subjects),
            subjects=subjects,
            questions=questions,
        )

    async def accounts(self) -> list[AccountItem]:
        async with self._session_factory() as session:
            rows = await self._repository.accounts(session)
        return [AccountItem(**row) for row in rows]

    async def create_account(self, request: AccountCreateRequest) -> AccountItem:
        username = request.username.strip().lower()
        student_code = (
            request.student_code.strip().upper() if request.student_code else None
        )
        async with self._session_factory() as session:
            if await self._repository.account_exists(session, username):
                raise AccountConflictError("Tên đăng nhập đã tồn tại")
            student_id = None
            if student_code:
                student_id = await self._repository.ensure_student(
                    session,
                    student_code,
                    request.display_name.strip(),
                )
            try:
                row = await self._repository.create_account(
                    session,
                    username=username,
                    password_hash=hash_password(request.password),
                    display_name=request.display_name.strip(),
                    role=request.role,
                    student_id=student_id,
                )
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise AccountConflictError(
                    "Mã sinh viên đã được liên kết với tài khoản khác"
                ) from error
        return AccountItem(**row, student_code=student_code)

    async def update_account(
        self,
        username: str,
        request: AccountUpdateRequest,
        actor: str,
    ) -> AccountItem:
        normalized = username.strip().lower()
        if normalized == actor and request.is_active is False:
            raise AdminError("Bạn không thể vô hiệu hóa tài khoản đang đăng nhập")
        async with self._session_factory() as session:
            row = await self._repository.update_account(
                session,
                username=normalized,
                display_name=(
                    request.display_name.strip() if request.display_name else None
                ),
                password_hash=(
                    hash_password(request.password) if request.password else None
                ),
                is_active=request.is_active,
            )
            if row is None:
                raise AccountNotFoundError("Không tìm thấy tài khoản")
            if request.display_name and row["student_id"] is not None:
                await self._repository.update_student_name(
                    session,
                    row["student_id"],
                    request.display_name.strip(),
                )
            student_code = await self._repository.student_code(
                session,
                row["student_id"],
            )
            await session.commit()
        return AccountItem(**row, student_code=student_code)

    async def config_items(self) -> list[ConfigItem]:
        return await self._config_service().list_items()

    async def update_config(
        self,
        updates: list[tuple[str, object]],
        actor: str,
    ) -> list[ConfigItem]:
        return await self._config_service().update_items(updates, actor)

    def _config_service(self) -> SystemConfigService:
        return SystemConfigService(SystemConfigRepository(), self._session_factory)
