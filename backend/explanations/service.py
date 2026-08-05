import json
import re

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
from backend.llm.client import LLMClient, MultiProviderClient
from backend.llm.errors import LLMError
from backend.prompts import load_prompt


class ExamExplanationService:
    GROUNDING_VERSION = "deterministic-evidence-v1"

    def __init__(
        self,
        repository: ExamExplanationRepository,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        client: LLMClient,
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
                    "No completed session is available within this account's scope"
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
            provider = self._provider(config)
            artifact_id = await self._repository.create_artifact(
                session,
                session_id=session_id,
                audience=audience,
                provider=provider,
                model=model,
                context=context,
                actor=user.username,
            )
            await session.commit()
        try:
            if not config.get("LLM_ENABLED", False):
                raise ExplanationUnavailableError("LLM features are disabled in sys_props")
            if not self._is_configured(model, provider):
                raise ExplanationUnavailableError(
                    self._configuration_message(model, provider)
                )
            completion = await self._client.complete_json(
                model=model,
                messages=self._messages(context, technical),
                max_tokens=int(config.get("LLM_EXPLANATION_MAX_TOKENS", 350)),
                temperature=0.1,
                reasoning_enabled=bool(config.get("LLM_REASONING_ENABLED", True)),
                provider=provider,
            )
            generated_payload = ExplanationPayload.model_validate(completion.data)
            payload = self._ground_payload(generated_payload, context, technical)
            stored_payload = payload.model_dump()
            stored_payload["grounding_version"] = self.GROUNDING_VERSION
            response_model = completion.model
            async with self._session_factory() as session:
                saved = await self._repository.mark_success(
                    session,
                    artifact_id,
                    response_model,
                    stored_payload,
                    completion.usage,
                )
                await session.commit()
        except (LLMError, ExplanationUnavailableError, ValidationError) as error:
            payload = self._fallback_payload(context, technical)
            stored_payload = payload.model_dump()
            stored_payload["grounding_version"] = self.GROUNDING_VERSION
            response_model = "deterministic-fallback"
            async with self._session_factory() as session:
                saved = await self._repository.mark_success(
                    session,
                    artifact_id,
                    response_model,
                    stored_payload,
                    {
                        "fallback": True,
                        "provider_error_type": type(error).__name__,
                    },
                )
                await session.commit()
        return ExamExplanationResponse(
            artifact_id=artifact_id,
            session_id=session_id,
            audience=audience,
            model=response_model,
            cached=False,
            generated_at=saved["generated_at"],
            **payload.model_dump(),
        )

    def _is_configured(self, model: str, provider: str) -> bool:
        if isinstance(self._client, MultiProviderClient):
            return self._client.is_configured(model, provider)
        return bool(
            getattr(
                self._settings,
                "gemini_api_key" if provider == "gemini" else "openrouter_api_key",
                None,
            )
        )

    def _configuration_message(self, model: str, provider: str) -> str:
        if isinstance(self._client, MultiProviderClient):
            return self._client.configuration_message(model, provider)
        return (
            "GEMINI_API_KEY is not configured"
            if provider == "gemini"
            else "OPENROUTER_API_KEY is not configured"
        )

    @staticmethod
    def _provider(config: dict) -> str:
        provider = str(config.get("LLM_PROVIDER") or "openrouter").strip().lower()
        if provider not in {"openrouter", "gemini"}:
            raise ExplanationUnavailableError("LLM_PROVIDER must be openrouter or gemini")
        return provider

    @classmethod
    def _fallback_payload(
        cls, context: dict, technical: bool
    ) -> ExplanationPayload:
        return ExplanationPayload(
            explanation=cls._fallback_explanation(context, technical),
            evidence_used=cls._deterministic_evidence(context, technical),
            limitations=[
                "Phản hồi được tạo trực tiếp từ kết quả đã chấm vì mô hình ngôn ngữ "
                "tạm thời không khả dụng."
            ],
        )

    @staticmethod
    def _messages(context: dict, technical: bool) -> list[dict[str, str]]:
        audience_rule = (
            "Đối tượng là giảng viên hoặc quản trị viên: có thể dùng thuật ngữ IRT, theta, "
            "sai số chuẩn, Bloom và mã luật khi cần; luôn gắn nhận định kỹ thuật với số liệu đã cho."
            if technical
            else "Đối tượng là thí sinh: không nhắc theta, Bloom, Fisher, sai số chuẩn, luật, "
            "mã trace hoặc chẩn đoán kỹ thuật nội bộ; dùng ngôn ngữ động viên nhưng chính xác."
        )
        return [
            {
                "role": "system",
                "content": load_prompt("exam_explanation_system_vi.txt").format(
                    audience_instruction=audience_rule
                ),
            },
            {
                "role": "user",
                "content": json.dumps(context, ensure_ascii=False, default=str),
            },
        ]

    @classmethod
    def _ground_payload(
        cls,
        payload: ExplanationPayload,
        context: dict,
        technical: bool,
    ) -> ExplanationPayload:
        has_conflict = cls._has_conflicting_numeric_claim(payload.explanation, context)
        explanation = (
            cls._fallback_explanation(context, technical)
            if has_conflict
            else payload.explanation.strip()
        )
        limitations = [
            value.strip()
            for value in payload.limitations
            if value.strip() and not cls._has_conflicting_numeric_claim(value, context)
        ]
        if has_conflict:
            limitations.append(
                "Hệ thống đã thay phần diễn giải có số liệu không khớp bằng bản tóm tắt xác định."
            )
        return ExplanationPayload(
            explanation=explanation,
            evidence_used=cls._deterministic_evidence(context, technical),
            limitations=limitations[:10],
        )

    @classmethod
    def _has_conflicting_numeric_claim(cls, text: str, context: dict) -> bool:
        score = context.get("score") or {}
        allowed_pairs = {
            (
                round(float(score.get("earned", 0)), 2),
                round(float(score.get("maximum", 0)), 2),
            ),
            (
                round(float(score.get("correct", 0)), 2),
                round(float(score.get("questions", 0)), 2),
            ),
        }
        for left, right in re.findall(
            r"(?<!\w)(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)(?!\w)",
            text,
        ):
            pair = (cls._parse_number(left), cls._parse_number(right))
            if pair not in allowed_pairs:
                return True

        allowed_percentages = {
            round(float(score.get("percentage", 0)), 2),
            *{
                round(float(item.get("accuracy_percent", 0)), 2)
                for item in context.get("unit_evidence") or []
            },
        }
        for value in re.findall(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*%", text):
            percentage = cls._parse_number(value)
            if percentage not in allowed_percentages:
                return True
        return False

    @classmethod
    def _deterministic_evidence(
        cls, context: dict, technical: bool
    ) -> list[str]:
        score = context["score"]
        evidence = [
            "Điểm đã chấm: "
            f"{cls._number(score['earned'])}/{cls._number(score['maximum'])} "
            f"({float(score['percentage']):.1f}%); "
            f"đúng {int(score['correct'])}/{int(score['questions'])} câu."
        ]
        units = sorted(
            context.get("unit_evidence") or [],
            key=lambda item: (
                float(item["accuracy_percent"]),
                -int(item["evidence_count"]),
                str(item["unit"]),
            ),
        )
        selected_units = units[:2]
        if units and units[-1] not in selected_units:
            selected_units.append(units[-1])
        action_labels = {
            "remediate": "ôn lại kiến thức nền",
            "reinforce": "luyện tập củng cố",
            "advance": "chuyển sang vận dụng nâng cao",
        }
        for item in selected_units:
            action = action_labels.get(item.get("recommendation"), "tiếp tục luyện tập")
            evidence.append(
                f"{item['unit']}: {float(item['accuracy_percent']):.1f}% qua "
                f"{int(item['evidence_count'])} bằng chứng; đề xuất {action}."
            )
        if technical and context.get("ability"):
            ability = context["ability"]
            evidence.append(
                "Ước lượng năng lực IRT: "
                f"{float(ability['theta_before']):.3f} → "
                f"{float(ability['theta_after']):.3f}; "
                f"sai số chuẩn {float(ability['standard_error']):.3f}."
            )
        return evidence[:8]

    @classmethod
    def _fallback_explanation(cls, context: dict, technical: bool) -> str:
        score = context["score"]
        opening = (
            f"Kết quả đã chấm là {cls._number(score['earned'])}/"
            f"{cls._number(score['maximum'])} ({float(score['percentage']):.1f}%)."
        )
        units = sorted(
            context.get("unit_evidence") or [],
            key=lambda item: float(item["accuracy_percent"]),
        )
        if not units:
            return opening + " Chưa có đủ bằng chứng theo kỹ năng để đề xuất bước học cụ thể."
        weakest = units[0]
        action = {
            "remediate": "ôn lại kiến thức nền và làm bài tập có hướng dẫn",
            "reinforce": "luyện thêm bài tập củng cố",
            "advance": "tiếp tục với bài tập vận dụng cao hơn",
        }.get(weakest.get("recommendation"), "tiếp tục luyện tập")
        result = (
            f"{opening} Bằng chứng hiện tại cho thấy {weakest['unit']} cần được ưu tiên; "
            f"bước tiếp theo phù hợp là {action}."
        )
        if technical and context.get("ability"):
            result += " Các tham số IRT chi tiết được giữ trong phần bằng chứng kỹ thuật."
        return result

    @staticmethod
    def _parse_number(value: str) -> float:
        return round(float(value.replace(",", ".")), 2)

    @staticmethod
    def _number(value) -> str:
        number = float(value)
        return str(int(number)) if number.is_integer() else f"{number:.1f}"
