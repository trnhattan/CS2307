from fastapi import APIRouter

from backend.admin.router import router as admin_router
from backend.auth.router import router as auth_router
from backend.exams.router import router as exams_router
from backend.questions.router import router as questions_router
from backend.supervisor.router import router as supervisor_router
from backend.takers.router import router as takers_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(questions_router, prefix="/questions", tags=["questions"])
api_router.include_router(exams_router, prefix="/exams", tags=["exams"])
api_router.include_router(supervisor_router, tags=["dashboards"])
api_router.include_router(takers_router, prefix="/taker", tags=["taker"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
