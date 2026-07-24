from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.auth.errors import AuthenticationError
from backend.auth.passwords import hash_password, verify_password
from backend.auth.repository import AuthRepository
from backend.auth.schemas import AuthenticatedUser, LoginResponse
from backend.auth.tokens import create_access_token
from backend.core.config import Settings


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory
        self._settings = settings
        self._dummy_hash = hash_password(
            "invalid-password",
            salt="cs2307-dummy-auth-salt",
        )

    async def login(self, username: str, password: str) -> LoginResponse:
        normalized_username = username.strip().lower()
        async with self._session_factory() as session:
            record = await self._repository.get_user_by_username(
                session,
                normalized_username,
            )

        stored_hash = record["password_hash"] if record else self._dummy_hash
        valid = verify_password(password, stored_hash)
        if not record or not valid or not record["is_active"]:
            raise AuthenticationError("The username or password is incorrect")

        user = AuthenticatedUser(
            user_id=record["user_id"],
            username=record["username"],
            display_name=record["display_name"],
            role=record["role"],
            student_id=record["student_id"],
            student_code=record["student_code"],
        )
        token = create_access_token(
            user.model_dump(),
            secret=self._settings.auth_secret,
            ttl_minutes=self._settings.auth_token_ttl_minutes,
        )
        return LoginResponse(access_token=token, user=user)
