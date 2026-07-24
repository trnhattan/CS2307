from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth.dependencies import require_roles
from backend.auth.schemas import AuthenticatedUser
from backend.db.session import async_session_factory
from backend.knowledge_graph.repository import KnowledgeGraphRepository
from backend.knowledge_graph.schemas import KnowledgeGraphResponse
from backend.knowledge_graph.service import KnowledgeGraphService


router = APIRouter()


def get_graph_service() -> KnowledgeGraphService:
    return KnowledgeGraphService(KnowledgeGraphRepository(), async_session_factory)


@router.get(
    "/students/{student_id}/knowledge-graph",
    response_model=KnowledgeGraphResponse,
)
async def staff_graph(
    student_id: int,
    _: AuthenticatedUser = Depends(require_roles("supervisor", "admin")),
) -> KnowledgeGraphResponse:
    graph = await get_graph_service().graph(student_id, technical=True)
    if graph is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return graph


@router.get("/taker/knowledge-graph", response_model=KnowledgeGraphResponse)
async def taker_graph(
    user: AuthenticatedUser = Depends(require_roles("exam_taker")),
) -> KnowledgeGraphResponse:
    if user.student_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    graph = await get_graph_service().graph(user.student_id, technical=False)
    if graph is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return graph
