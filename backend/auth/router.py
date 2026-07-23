from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import get_current_user
from backend.auth.errors import AuthenticationError
from backend.auth.repository import AuthRepository
from backend.auth.schemas import AuthenticatedUser, LoginRequest, LoginResponse
from backend.auth.service import AuthService
from backend.core.config import get_settings
from backend.db.session import async_session_factory


router = APIRouter()


def get_auth_service() -> AuthService:
    return AuthService(AuthRepository(), async_session_factory, get_settings())


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    try:
        return await get_auth_service().login(request.username, request.password)
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error


@router.get("/me", response_model=AuthenticatedUser)
async def current_user(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    return user
