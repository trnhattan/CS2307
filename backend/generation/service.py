import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.config import Settings
from backend.generation.errors import (
    GenerationCatalogError,
    GenerationUnavailableError,
)
from backend.generation.repository import QuestionGenerationRepository
from backend.generation.rubric import initial_irt
from backend.generation.schemas import (
    CatalogSubject,
    GeneratedQuestion,
    GeneratedQuestionPayload,
    GenerationCatalog,
    GenerationStatus,
    QuestionGenerationRequest,
    RecentGeneratedQuestion,
)
from backend.generation.validator import validate_generated_question
from backend.llm.client import OpenAICompatibleClient
from backend.llm.errors import LLMError


class QuestionGenerationService:
    def __init__(
        self,
        repository: QuestionGenerationRepository,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        client: OpenAICompatibleClient,
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory
        self._settings = settings
        self._client = client

    async def status(self) -> GenerationStatus:
        config = await self._config()
        return GenerationStatus(
            enabled=bool(config.get("LLM_ENABLED", False)),
            configured=bool(self._settings.llm_api_key),
            model=self._model(config),
            provider=self._settings.llm_base_url,
        )

    async def catalog(self) -> GenerationCatalog:
        async with self._session_factory() as session:
            rows = await self._repository.catalog(session)
        return GenerationCatalog(
            subjects=[CatalogSubject(**row) for row in rows],
            bloom_levels=["remember", "understand", "apply", "analyze", "evaluate"],
            difficulty_labels=["easy", "medium", "hard"],
        )

    async def recent(self) -> list[RecentGeneratedQuestion]:
        async with self._session_factory() as session:
            rows = await self._repository.recent(session)
        return [RecentGeneratedQuestion(**row) for row in rows]

    async def generate(
        self, request: QuestionGenerationRequest, actor: str
    ) -> GeneratedQuestion:
        async with self._session_factory() as session:
            config = await self._repository.config(session)
            units = await self._repository.resolve_units(session, request)
            if units is None:
                raise GenerationCatalogError("Không tìm thấy môn học đang hoạt động")
            self._validate_units(request, units["units"])
            existing_stems = await self._repository.existing_stems(session)
            model = self._model(config)
            artifact_id = await self._repository.create_artifact(
                session,
                artifact_type="question_generation",
                audience="reviewer",
                model=model,
                request_payload={
                    **request.model_dump(),
                    "source_context": (request.source_context or "")[: int(
                        config.get("LLM_MAX_SOURCE_CHARS", 6000)
                    )] or None,
                },
                created_by=actor,
            )
            await session.commit()

        try:
            self._ensure_available(config)
            max_source_chars = int(config.get("LLM_MAX_SOURCE_CHARS", 6000))
            expected_count = int(
                config.get("ANSWER_POOL_SIZE_BY_BLOOM", {}).get(
                    request.bloom_level, 4
                )
            )
            completion = await self._client.complete_json(
                model=model,
                messages=self._messages(
                    request,
                    units["units"],
                    expected_count,
                    max_source_chars,
                ),
                max_tokens=int(config.get("LLM_QUESTION_MAX_TOKENS", 1600)),
                temperature=float(config.get("LLM_TEMPERATURE", 0.2)),
            )
            generated = GeneratedQuestionPayload.model_validate(completion.data)
            issues = validate_generated_question(
                generated,
                request,
                expected_option_count=expected_count,
                existing_stems=existing_stems,
            )
            irt = initial_irt(
                request.bloom_level,
                request.difficulty_label,
                len(generated.options),
            )
            issue_data = [issue.model_dump() for issue in issues]
            async with self._session_factory() as session:
                question_code = await self._repository.save_question(
                    session,
                    artifact_id=artifact_id,
                    request=request,
                    generated=generated,
                    irt=irt,
                    validation_issues=issue_data,
                    units=units,
                    model=completion.model,
                    completion_id=completion.completion_id,
                    usage=completion.usage,
                    actor=actor,
                    display_option_count=int(config.get("DISPLAY_OPTION_COUNT", 4)),
                )
                await session.commit()
        except (
            LLMError,
            GenerationUnavailableError,
            ValidationError,
            ValueError,
            KeyError,
            SQLAlchemyError,
        ) as error:
            async with self._session_factory() as session:
                await self._repository.mark_failed(
                    session, artifact_id, f"{type(error).__name__}: {error}"
                )
                await session.commit()
            if isinstance(error, (LLMError, GenerationUnavailableError)):
                raise GenerationUnavailableError(str(error)) from error
            raise GenerationUnavailableError("LLM output failed deterministic validation") from error

        options = []
        for index, option in enumerate(generated.options):
            options.append(
                {
                    "code": chr(ord("A") + index),
                    "text": option.text,
                    "is_best_answer": index == generated.correct_index,
                    "distractor_type": (
                        "best" if index == generated.correct_index else option.distractor_type
                    ),
                    "diagnosis": option.diagnosis,
                }
            )
        return GeneratedQuestion(
            artifact_id=artifact_id,
            question_code=question_code,
            status="draft",
            subject_code=request.subject_code,
            topic_code=request.topic_code,
            skill_codes=request.skill_codes,
            bloom_level=request.bloom_level,
            difficulty_label=request.difficulty_label,
            stem=generated.stem,
            options=options,
            correct_option_code=chr(ord("A") + generated.correct_index),
            explanation=generated.explanation,
            bloom_rationale=generated.bloom_rationale,
            irt=irt,
            validation_issues=issues,
            model=completion.model,
        )

    async def _config(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            return await self._repository.config(session)

    def _ensure_available(self, config: dict[str, Any]) -> None:
        if not config.get("LLM_ENABLED", False):
            raise GenerationUnavailableError("LLM features are disabled in sys_props")
        if not self._settings.llm_api_key:
            raise GenerationUnavailableError("LLM_API_KEY is not configured")

    @staticmethod
    def _model(config: dict[str, Any]) -> str:
        model = config.get("LLM_MODEL")
        if not isinstance(model, str) or not model.strip():
            raise GenerationUnavailableError("LLM_MODEL is not configured in sys_props")
        return model.strip()

    @staticmethod
    def _validate_units(request: QuestionGenerationRequest, units: dict[str, Any]) -> None:
        topic = units.get(request.topic_code)
        if not topic or topic["unit_type"] != "topic":
            raise GenerationCatalogError("Chủ đề không thuộc môn học đã chọn")
        for skill_code in request.skill_codes:
            skill = units.get(skill_code)
            if not skill or skill["unit_type"] != "skill":
                raise GenerationCatalogError(
                    f"Kỹ năng {skill_code} không thuộc môn học đã chọn"
                )

    @staticmethod
    def _messages(
        request: QuestionGenerationRequest,
        units: dict[str, Any],
        expected_option_count: int,
        max_source_chars: int,
    ) -> list[dict[str, str]]:
        target = {
            "subject_code": request.subject_code,
            "topic": units[request.topic_code]["unit_name"],
            "skills": [units[code]["unit_name"] for code in request.skill_codes],
            "bloom_level": request.bloom_level,
            "difficulty": request.difficulty_label,
            "learning_objective": request.learning_objective,
            "option_count": expected_option_count,
            "source": (request.source_context or "")[:max_source_chars],
        }
        schema = {
            "stem": "string",
            "options": [
                {
                    "text": "string",
                    "distractor_type": "near_correct|misconception|clear_wrong",
                    "diagnosis": "string or null",
                }
            ],
            "correct_index": "zero-based integer",
            "explanation": "string",
            "bloom_rationale": "string",
        }
        return [
            {
                "role": "system",
                "content": (
                    "Bạn tạo MỘT bản nháp câu hỏi trắc nghiệm tiếng Việt để chuyên gia duyệt. "
                    "Chỉ trả JSON hợp lệ, không Markdown. Không tự gán IRT. Có đúng một đáp án "
                    "tốt nhất; các phương án khác phải hợp lý và không trùng nhau. Không nói rằng "
                    "câu hỏi đã được xác minh hay kích hoạt."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Mục tiêu:\n"
                    + json.dumps(target, ensure_ascii=False)
                    + "\nĐịnh dạng bắt buộc:\n"
                    + json.dumps(schema, ensure_ascii=False)
                ),
            },
        ]
