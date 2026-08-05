from fastapi import APIRouter

from backend.admin.router import router as admin_router
from backend.auth.router import router as auth_router
from backend.cat.router import router as cat_router, staff_router as cat_staff_router
from backend.calibration.router import router as calibration_router
from backend.exams.router import router as exams_router
from backend.explanations.router import router as explanations_router
from backend.generation.router import router as generation_router
from backend.kb.router import router as kb_router
from backend.knowledge_graph.router import router as graph_router
from backend.learner_profiles.router import router as learner_profiles_router
from backend.learner_chat.router import router as learner_chat_router
from backend.placement.router import router as placement_router
from backend.questions.router import router as questions_router
from backend.supervisor.router import router as supervisor_router
from backend.takers.router import router as takers_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(cat_router, prefix="/cat", tags=["cat"])
api_router.include_router(cat_staff_router, tags=["cat"])
api_router.include_router(calibration_router, prefix="/calibration", tags=["irt-calibration"])
api_router.include_router(questions_router, prefix="/questions", tags=["questions"])
api_router.include_router(exams_router, prefix="/exams", tags=["exams"])
api_router.include_router(explanations_router, tags=["llm-explanations"])
api_router.include_router(generation_router, prefix="/generation", tags=["llm-generation"])
api_router.include_router(kb_router, prefix="/kb", tags=["knowledge-base"])
api_router.include_router(graph_router, tags=["knowledge-graph"])
api_router.include_router(learner_profiles_router, tags=["learner-profile"])
api_router.include_router(learner_chat_router, tags=["learner-chat"])
api_router.include_router(placement_router, tags=["placement"])
api_router.include_router(supervisor_router, tags=["dashboards"])
api_router.include_router(takers_router, prefix="/taker", tags=["taker"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
