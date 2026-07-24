import json

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.auth.schemas import AuthenticatedUser
from backend.core.config import Settings
from backend.explanations.errors import (
    ExplanationNotFoundError,
    ExplanationUnavailableError,
)
from backend.explanations.repository import ExamExplanationRepository
from backend.explanations.schemas import ExamExplanationResponse, ExplanationPayload
from backend.llm.client import OpenAICompatibleClient
from backend.llm.errors import LLMError


class ExamExplanationService:
    def __init__(
        self,
        repository: ExamExplanationRepository,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        client: OpenAICompatibleClient,
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory
        self._settings = settings
        self._client = client

    async def explain(
        self,
        session_id: int,
        user: AuthenticatedUser,
        *,
        technical: bool,
        refresh: bool,
    ) -> ExamExplanationResponse:
        audience = "staff" if technical else "taker"
        student_id = None if technical else user.student_id
        async with self._session_factory() as session:
            context = await self._repository.context(
                session, session_id, student_id, technical
            )
            if context is None:
                raise ExplanationNotFoundError(
                    "Không tìm thấy phiên đã hoàn thành thuộc phạm vi tài khoản"
                )
            if not refresh:
                cached = await self._repository.cached(session, session_id, audience)
                if cached:
                    return ExamExplanationResponse(
                        **cached, cached=True
                    )
            config = await self._repository.config(session)
            model = config.get("LLM_MODEL")
            if not isinstance(model, str) or not model.strip():
                raise ExplanationUnavailableError(
                    "LLM_MODEL is not configured in sys_props"
                )
            model = model.strip()
            artifact_id = await self._repository.create_artifact(
                session,
                session_id=session_id,
                audience=audience,
                model=model,
                context=context,
                actor=user.username,
            )
            await session.commit()
        try:
            if not config.get("LLM_ENABLED", False):
                raise ExplanationUnavailableError("LLM features are disabled in sys_props")
            if not self._settings.llm_api_key:
                raise ExplanationUnavailableError("LLM_API_KEY is not configured")
            completion = await self._client.complete_json(
                model=model,
                messages=self._messages(context, technical),
                max_tokens=int(config.get("LLM_EXPLANATION_MAX_TOKENS", 350)),
                temperature=0.1,
            )
            payload = ExplanationPayload.model_validate(completion.data)
            async with self._session_factory() as session:
                saved = await self._repository.mark_success(
                    session,
                    artifact_id,
                    completion.model,
                    payload.model_dump(),
                    completion.usage,
                )
                await session.commit()
        except (LLMError, ExplanationUnavailableError, ValidationError) as error:
            async with self._session_factory() as session:
                await self._repository.mark_failed(
                    session, artifact_id, f"{type(error).__name__}: {error}"
                )
                await session.commit()
            raise ExplanationUnavailableError(str(error)) from error
        return ExamExplanationResponse(
            artifact_id=artifact_id,
            session_id=session_id,
            audience=audience,
            model=completion.model,
            cached=False,
            generated_at=saved["generated_at"],
            **payload.model_dump(),
        )

    @staticmethod
    def _messages(context: dict, technical: bool) -> list[dict[str, str]]:
        audience_rule = (
            "Dùng thuật ngữ IRT khi cần và luôn gắn nhận định với số liệu đã cho."
            if technical
            else "Không nhắc theta, Bloom, Fisher, sai số chuẩn, luật hay mã trace. Viết thân thiện cho thí sinh."
        )
        return [
            {
                "role": "system",
                "content": (
                    "Bạn diễn giải kết quả thi từ ngữ cảnh xác định. Không tính lại điểm, "
                    "không bịa dữ kiện, không chẩn đoán vượt quá bằng chứng. Chỉ trả JSON gồm "
                    "explanation, evidence_used, limitations. " + audience_rule
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, ensure_ascii=False, default=str),
            },
        ]
