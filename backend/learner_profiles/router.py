from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.dependencies import get_current_user, require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.learner_profiles.repository import LearnerProfileRepository
from backend.learner_profiles.schemas import (
    CriteriaCatalogResponse,
    CriterionRadarResponse,
    LearnerProfileResponse,
)
from backend.learner_profiles.service import LearnerProfileService


router = APIRouter()


def get_profile_service() -> LearnerProfileService:
    return LearnerProfileService(LearnerProfileRepository(), async_session_factory)


@router.get(
    "/subjects/{subject_code}/criteria",
    response_model=CriteriaCatalogResponse,
)
async def criteria_catalog(
    subject_code: str,
    _: AuthenticatedUser = Depends(get_current_user),
) -> CriteriaCatalogResponse:
    payload = await get_profile_service().catalog(subject_code)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return payload


@router.get("/taker/profile", response_model=LearnerProfileResponse)
async def taker_profile(
    subject_code: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> LearnerProfileResponse:
    if user.student_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    payload = await get_profile_service().profile(user.student_id, subject_code)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return payload


@router.get(
    "/taker/radar/{subject_code}",
    response_model=CriterionRadarResponse,
)
async def taker_radar(
    subject_code: str,
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> CriterionRadarResponse:
    if user.student_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    payload = await get_profile_service().radar(user.student_id, subject_code)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return payload


@router.get(
    "/students/{student_id}/profile",
    response_model=LearnerProfileResponse,
)
async def staff_profile(
    student_id: int,
    subject_code: str | None = Query(default=None),
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> LearnerProfileResponse:
    payload = await get_profile_service().profile(student_id, subject_code)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return payload
