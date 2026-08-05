from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from backend.auth.errors import AuthenticationError
from backend.auth.tokens import decode_access_token
from backend.core.config import get_settings
from backend.db.session import async_session_factory
from backend.learner_mcp.tools import LearnerToolset


class ApplicationTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = decode_access_token(token, secret=get_settings().auth_secret)
            if claims.get("role") != "exam_taker" or claims.get("student_id") is None:
                return None
            return AccessToken(
                token=token,
                client_id=str(claims.get("username") or claims["user_id"]),
                scopes=["learner:read"],
                subject=str(claims["student_id"]),
                claims=claims,
            )
        except (AuthenticationError, KeyError, TypeError, ValueError):
            return None


settings = get_settings()
learner_mcp = FastMCP(
    "CS2307 Learner Knowledge",
    instructions=(
        "Read-only tools for the authenticated learner's progress, completed questions, "
        "assessment criteria, subjects, and curated course knowledge."
    ),
    token_verifier=ApplicationTokenVerifier(),
    auth=AuthSettings(
        issuer_url=settings.mcp_issuer_url,
        resource_server_url=settings.mcp_public_url,
        required_scopes=["learner:read"],
    ),
    stateless_http=True,
    json_response=True,
    host=settings.backend_host,
    port=settings.backend_port,
)


def _tools() -> LearnerToolset:
    token = get_access_token()
    claims = token.claims if token else None
    if not claims or claims.get("student_id") is None:
        raise PermissionError("Authenticated learner context is required")
    return LearnerToolset(
        student_id=int(claims["student_id"]),
        session_factory=async_session_factory,
    )


@learner_mcp.tool()
async def get_my_learning_profile(subject_code: str | None = None) -> dict[str, Any]:
    """Get the current learner's criterion mastery, strengths, weaknesses, and trends."""
    return await _tools().learning_profile(subject_code)


@learner_mcp.tool()
async def get_my_test_history(subject_code: str | None = None) -> dict[str, Any]:
    """Get the current learner's completed-test history by subject."""
    return await _tools().test_history(subject_code)


@learner_mcp.tool()
async def search_my_completed_questions(
    query: str,
    subject_code: str | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Search questions owned by the learner from completed tests only."""
    return await _tools().completed_questions(query, subject_code, limit)


@learner_mcp.tool()
async def review_my_completed_question(question_code: str) -> dict[str, Any]:
    """Retrieve one completed question for safe answer review."""
    return await _tools().completed_question_review(question_code)


@learner_mcp.tool()
async def search_subject_knowledge(
    query: str,
    subject_code: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search curated subject knowledge, criteria, topics, and safe question metadata."""
    return await _tools().subject_knowledge(query, subject_code, limit)


class RestartableMCPApplication:
    def __init__(self, server: FastMCP) -> None:
        self.server = server
        self.current = server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        try:
            async with self.current.router.lifespan_context(self.current):
                yield
        finally:
            self.server._session_manager = None
            self.current = self.server.streamable_http_app()

    async def __call__(self, scope, receive, send) -> None:
        await self.current(scope, receive, send)


learner_mcp_app = RestartableMCPApplication(learner_mcp)
