import json
import re
import unicodedata
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.auth.schemas import AuthenticatedUser
from backend.core.config import Settings
from backend.learner_chat.errors import LearnerChatError, LearnerChatNotFoundError
from backend.learner_chat.repository import LearnerChatRepository
from backend.learner_chat.schemas import (
    ChatAssistantPayload,
    ChatMessage,
    ChatThreadDetail,
    ChatThreadSummary,
    CreateChatThreadRequest,
    DeleteChatThreadResponse,
    SendChatMessageRequest,
    SendChatMessageResponse,
)
from backend.learner_mcp.tools import LearnerToolset, learner_tool_definitions
from backend.learner_profiles.repository import LearnerProfileRepository
from backend.learner_profiles.service import LearnerProfileService
from backend.llm.client import LLMClient, MultiProviderClient
from backend.llm.errors import LLMError
from backend.prompts import load_prompt


class LearnerChatService:
    _STOP_WORDS = {
        "a", "about", "and", "are", "can", "do", "for", "have", "how",
        "i", "in", "is", "it", "me", "my", "of", "on", "or", "should",
        "the", "this", "to", "what", "where", "why", "with", "you",
        "cua", "cho", "co", "gi", "la", "minh", "nao", "nhung", "tai",
        "toi", "va", "ve",
    }

    def __init__(
        self,
        repository: LearnerChatRepository,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        client: LLMClient,
    ) -> None:
        self.repository = repository
        self.session_factory = session_factory
        self.settings = settings
        self.client = client

    async def create_thread(
        self, request: CreateChatThreadRequest, user: AuthenticatedUser
    ) -> ChatThreadSummary:
        student_id = self._student_id(user)
        async with self.session_factory() as session:
            subject_id = await self.repository.subject_id(session, request.subject_code)
            if request.subject_code and subject_id is None:
                raise LearnerChatNotFoundError("Subject not found")
            row = await self.repository.create_thread(
                session,
                student_id=student_id,
                subject_id=subject_id,
                title=request.title.strip(),
            )
            await session.commit()
        row["subject_code"] = request.subject_code.upper() if request.subject_code else None
        row["subject_name"] = None
        return ChatThreadSummary(**row)

    async def threads(self, user: AuthenticatedUser) -> list[ChatThreadSummary]:
        async with self.session_factory() as session:
            rows = await self.repository.threads(session, self._student_id(user))
        return [ChatThreadSummary(**row) for row in rows]

    async def detail(
        self, thread_id: int, user: AuthenticatedUser
    ) -> ChatThreadDetail:
        async with self.session_factory() as session:
            thread = await self.repository.thread(
                session, thread_id, self._student_id(user)
            )
            if thread is None:
                raise LearnerChatNotFoundError("Conversation not found")
            messages = await self.repository.messages(session, thread_id)
        return ChatThreadDetail(
            **thread,
            messages=[ChatMessage(**message) for message in messages],
        )

    async def delete_thread(
        self, thread_id: int, user: AuthenticatedUser
    ) -> DeleteChatThreadResponse:
        async with self.session_factory() as session:
            deleted = await self.repository.delete_thread(
                session,
                thread_id=thread_id,
                student_id=self._student_id(user),
            )
            if not deleted:
                raise LearnerChatNotFoundError("Conversation not found")
            await session.commit()
        return DeleteChatThreadResponse(thread_id=thread_id)

    async def send(
        self,
        thread_id: int,
        request: SendChatMessageRequest,
        user: AuthenticatedUser,
    ) -> SendChatMessageResponse:
        student_id = self._student_id(user)
        async with self.session_factory() as session:
            thread = await self.repository.thread(session, thread_id, student_id)
            if thread is None or thread["status"] != "active":
                raise LearnerChatNotFoundError("Conversation not found")
            explicit_question = await self.repository.answered_question(
                session,
                student_id=student_id,
                session_id=request.session_id,
                question_code=request.question_code,
            )
            if (request.session_id or request.question_code) and explicit_question is None:
                raise LearnerChatNotFoundError(
                    "Only questions from this learner's completed tests can be reviewed"
                )
            config = await self.repository.config(session)
            history_limit = int(config.get("LLM_CHAT_HISTORY_LIMIT", 10))
            retrieval_limit = int(config.get("LLM_CHAT_RETRIEVAL_LIMIT", 200))
            knowledge_limit = int(config.get("LLM_CHAT_KNOWLEDGE_LIMIT", 300))
            history = await self.repository.messages(session, thread_id, history_limit)
            completed_questions = await self.repository.completed_questions(
                session,
                student_id=student_id,
                subject_id=thread.get("subject_id"),
                limit=retrieval_limit,
            )
            intent = self._intent(request.message, explicit_question)
            knowledge_resources = (
                []
                if intent == "security_refusal"
                else await self.repository.knowledge_resources(
                    session,
                    subject_id=thread.get("subject_id"),
                    limit=knowledge_limit,
                )
            )
            relevant_questions = self._relevant_questions(
                completed_questions,
                request.message,
                intent=intent,
            )
            if explicit_question is not None:
                relevant_questions = self._deduplicate_questions(
                    [explicit_question, *relevant_questions]
                )[:3]
            learner_history = await self.repository.learner_history(
                session,
                student_id=student_id,
                subject_id=thread.get("subject_id"),
            )
            await self.repository.save_message(
                session,
                thread_id=thread_id,
                role="user",
                content=request.message.strip(),
                intent=intent,
                session_id=(
                    explicit_question["session_id"]
                    if explicit_question else request.session_id
                ),
                question_id=(
                    explicit_question["question_id"] if explicit_question else None
                ),
            )
            await session.commit()

        profile_service = LearnerProfileService(
            LearnerProfileRepository(), self.session_factory
        )
        profile = await profile_service.profile(student_id, thread.get("subject_code"))
        context = self._context(
            profile,
            relevant_questions,
            learner_history,
            self._relevant_knowledge(knowledge_resources, request.message),
            request.message,
            intent,
        )
        model = str(config.get("LLM_MODEL") or "").strip()
        provider = self._provider(config)
        payload: ChatAssistantPayload
        used_llm = False
        actual_model = "deterministic-fallback"
        provider_content = None
        reasoning_details = []
        try:
            if intent == "security_refusal":
                actual_model = "policy-guard"
                raise LearnerChatError("Direct answer requests are blocked")
            if not config.get("LLM_ENABLED", False):
                raise LearnerChatError("LLM features are disabled")
            if not model:
                raise LearnerChatError("LLM_MODEL is not configured")
            if not self._is_configured(model, provider):
                raise LearnerChatError(self._configuration_message(model, provider))
            toolset = LearnerToolset(
                student_id=student_id,
                session_factory=self.session_factory,
                thread_subject_id=thread.get("subject_id"),
            )
            completion = await self.client.complete_json_with_tools(
                model=model,
                messages=self._messages(context, history),
                tools=learner_tool_definitions(),
                tool_executor=toolset.execute,
                max_tokens=int(config.get("LLM_CHAT_MAX_TOKENS", 450)),
                temperature=0.2,
                reasoning_enabled=bool(config.get("LLM_REASONING_ENABLED", True)),
                max_tool_rounds=int(config.get("LLM_CHAT_TOOL_ROUNDS", 4)),
                web_search_enabled=(
                    bool(config.get("LLM_CHAT_WEB_SEARCH_ENABLED", False))
                    and intent in {"concept_help", "learner_support"}
                ),
                web_search_max_results=int(
                    config.get("LLM_CHAT_WEB_SEARCH_MAX_RESULTS", 3)
                ),
                provider=provider,
            )
            payload = ChatAssistantPayload.model_validate(completion.data)
            used_llm = True
            actual_model = completion.model
            provider_content = completion.content
            reasoning_details = completion.reasoning_details
        except (LLMError, LearnerChatError, ValidationError):
            payload = self._fallback(context)

        linked_question = relevant_questions[0] if relevant_questions else None
        async with self.session_factory() as session:
            stored = await self.repository.save_message(
                session,
                thread_id=thread_id,
                role="assistant",
                content=payload.answer.strip(),
                intent=intent,
                session_id=(
                    linked_question["session_id"]
                    if linked_question else request.session_id
                ),
                question_id=(
                    linked_question["question_id"] if linked_question else None
                ),
                evidence=payload.evidence_used,
                limitations=payload.limitations,
                model=actual_model,
                used_llm=used_llm,
                provider_content=provider_content,
                reasoning_details=reasoning_details,
            )
            stored["question_code"] = (
                linked_question["question_code"] if linked_question else None
            )
            await session.commit()
        return SendChatMessageResponse(**stored)

    def _is_configured(self, model: str, provider: str) -> bool:
        if isinstance(self.client, MultiProviderClient):
            return self.client.is_configured(model, provider)
        return bool(
            getattr(
                self.settings,
                "gemini_api_key" if provider == "gemini" else "openrouter_api_key",
                None,
            )
        )

    def _configuration_message(self, model: str, provider: str) -> str:
        if isinstance(self.client, MultiProviderClient):
            return self.client.configuration_message(model, provider)
        return (
            "GEMINI_API_KEY is not configured"
            if provider == "gemini"
            else "OPENROUTER_API_KEY is not configured"
        )

    @staticmethod
    def _provider(config: dict[str, Any]) -> str:
        provider = str(config.get("LLM_PROVIDER") or "openrouter").strip().lower()
        if provider not in {"openrouter", "gemini"}:
            raise LearnerChatError("LLM_PROVIDER must be openrouter or gemini")
        return provider

    @classmethod
    def _context(
        cls,
        profile,
        questions: list[dict[str, Any]],
        learner_history: list[dict[str, Any]],
        knowledge_resources: list[dict[str, Any]],
        message: str,
        intent: str,
    ) -> dict[str, Any]:
        subjects = []
        matching_criteria = []
        query_tokens = cls._tokens(message)
        if profile:
            for subject in profile.subjects:
                criteria = [
                    {
                        "code": item.criterion_code,
                        "name": item.criterion_name,
                        "learning_objective": item.learning_objective,
                        "success_statement": item.success_statement,
                        "understanding": item.understanding_label,
                        "evidence_count": item.evidence_count,
                        "accuracy_percent": item.accuracy_percent,
                        "trend": item.trend,
                    }
                    for item in subject.criteria
                ]
                subjects.append(
                    {
                        "subject_code": subject.subject_code,
                        "subject": subject.subject_name,
                        "strengths": subject.strengths,
                        "weaknesses": subject.weaknesses,
                        "improved": subject.improved,
                        "regressed": subject.regressed,
                        "insufficient_evidence": subject.insufficient_evidence,
                        "criteria": criteria,
                        "recommendations": [
                            item.model_dump() for item in subject.recommendations
                        ],
                    }
                )
                for criterion in criteria:
                    searchable = " ".join(
                        str(criterion.get(key) or "")
                        for key in ("code", "name", "learning_objective", "success_statement")
                    )
                    score = len(query_tokens & cls._tokens(searchable))
                    if score:
                        matching_criteria.append(
                            {"score": score, "subject": subject.subject_name, **criterion}
                        )
        matching_criteria.sort(
            key=lambda item: (-item["score"], item["evidence_count"], item["name"])
        )
        history = [
            {
                **row,
                "average_score_percent": cls._number(row.get("average_score_percent")),
                "best_score_percent": cls._number(row.get("best_score_percent")),
                "latest_score_percent": cls._number(row.get("latest_score_percent")),
                "mastery_probability": cls._number(row.get("mastery_probability")),
            }
            for row in learner_history
        ]
        return {
            "intent": intent,
            "learner_message": message,
            "learner": {
                "student_code": profile.student_code if profile else None,
                "display_name": profile.student_name if profile else None,
            },
            "assessment_history": history,
            "learner_profile": subjects,
            "matching_criteria": [
                {key: value for key, value in item.items() if key != "score"}
                for item in matching_criteria[:5]
            ],
            "relevant_completed_questions": questions[:3],
            "answered_question": questions[0] if questions else None,
            "knowledge_base": knowledge_resources[:8],
            "security": {
                "ownership_verified": True,
                "completed_tests_only": True,
                "direct_answer_request_blocked": intent == "security_refusal",
                "review_allowed_only_for_retrieved_questions": True,
                "knowledge_base_excludes_answer_options": True,
            },
        }

    @staticmethod
    def _messages(context: dict, history: list[dict]) -> list[dict]:
        messages = [
            {
                "role": "system",
                "content": load_prompt("learner_chat_system_vi.txt"),
            }
        ]
        for item in history:
            message = {
                "role": item["role"],
                "content": item.get("provider_content") or item["content"],
            }
            reasoning_details = item.get("reasoning_details") or []
            if item["role"] == "assistant" and reasoning_details:
                message["reasoning_details"] = reasoning_details
            messages.append(message)
        model_context = {
            "intent": context.get("intent"),
            "learner_message": context.get("learner_message"),
            "learner": context.get("learner"),
            "requested_completed_question": (
                (context.get("answered_question") or {}).get("question_code")
            ),
            "security": context.get("security"),
            "tool_policy": (
                "Use the learner MCP tools for system facts and subject knowledge. "
                "Do not guess when a tool can answer the question."
            ),
        }
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    model_context, ensure_ascii=False, default=str
                ),
            }
        )
        return messages

    @classmethod
    def _fallback(cls, context: dict) -> ChatAssistantPayload:
        intent = context.get("intent") or (
            "question_review" if context.get("answered_question")
            else "learning_improvement"
        )
        if intent == "security_refusal":
            return ChatAssistantPayload(
                answer=(
                    "Mình không thể cung cấp đáp án trực tiếp hoặc chọn phương án thay bạn. "
                    "Mình có thể giải thích khái niệm, đưa gợi ý từng bước, hoặc cùng bạn xem lại "
                    "một câu hỏi sau khi bài kiểm tra đã hoàn thành."
                ),
                evidence_used=["Chính sách bảo vệ tính toàn vẹn của bài kiểm tra"],
                limitations=["Không tiết lộ đáp án trực tiếp."],
            )

        profiles = context.get("learner_profile") or []
        history = [
            row for row in context.get("assessment_history") or []
            if int(row.get("completed_tests") or 0) > 0
        ]
        questions = context.get("relevant_completed_questions") or []
        if not questions and context.get("answered_question"):
            questions = [context["answered_question"]]

        if intent == "progress_summary":
            if not history:
                return cls._no_evidence()
            lines = []
            for row in history:
                latest = cls._percent(row.get("latest_score_percent"))
                average = cls._percent(row.get("average_score_percent"))
                lines.append(
                    f"{row['subject_name']}: {row['completed_tests']} bài, "
                    f"gần nhất {latest}, trung bình {average}"
                )
            strengths = [
                name for profile in profiles for name in profile.get("strengths", [])
            ][:3]
            improved = [
                name for profile in profiles for name in profile.get("improved", [])
            ][:3]
            answer = "Qua dữ liệu hiện có, " + "; ".join(lines) + "."
            if strengths:
                answer += f" Bạn đang làm tốt ở {', '.join(strengths)}."
            if improved:
                answer += f" Những điểm tiến bộ rõ nhất là {', '.join(improved)}."
            return ChatAssistantPayload(
                answer=answer,
                evidence_used=[f"{sum(int(row['completed_tests']) for row in history)} bài đã hoàn thành"],
                limitations=[],
            )

        if intent == "question_review":
            if not questions:
                return ChatAssistantPayload(
                    answer=(
                        "Mình chưa xác định được câu đã hoàn thành mà bạn đang nhắc tới. "
                        "Hãy nêu mã câu hỏi hoặc một cụm từ trong nội dung câu; mình sẽ tìm lại "
                        "trong lịch sử bài làm của bạn."
                    ),
                    evidence_used=[],
                    limitations=["Chưa tìm thấy câu hỏi phù hợp trong lịch sử đã hoàn thành."],
                )
            question = questions[0]
            explanation = (
                question.get("selected_answer_diagnosis")
                if not question.get("is_correct")
                else question.get("best_answer_explanation")
            ) or question.get("explanation")
            criteria = ", ".join(question.get("criteria") or [])
            if question.get("is_correct"):
                answer = (
                    f"Ở câu “{question.get('stem')}”, bạn đã trả lời đúng. "
                    f"Ý chính là: {explanation or 'lựa chọn của bạn phù hợp với yêu cầu của câu hỏi.'}"
                )
            else:
                answer = (
                    f"Ở câu “{question.get('stem')}”, lựa chọn “{question.get('selected_answer')}” "
                    f"chưa phù hợp. Điểm mấu chốt là: {explanation or question.get('explanation')}."
                )
                if question.get("best_answer"):
                    answer += (
                        f" Sau khi bài đã hoàn thành, đáp án được chấm phù hợp nhất là "
                        f"“{question.get('best_answer')}”."
                    )
            if criteria:
                answer += f" Câu này đang kiểm tra {criteria}."
            return ChatAssistantPayload(
                answer=answer,
                evidence_used=[f"Câu đã hoàn thành {question.get('question_code')}"],
                limitations=[],
            )

        matched = context.get("matching_criteria") or []
        knowledge = context.get("knowledge_base") or []
        if intent == "concept_help" and (matched or knowledge):
            criterion = matched[0] if matched else None
            resource = knowledge[0] if knowledge else None
            concept = cls._concept_name(
                (criterion or {}).get("name") or (resource or {}).get("title") or "chủ đề này"
            )
            foundation = (
                (resource or {}).get("content")
                if (resource or {}).get("resource_type") == "subject_knowledge"
                else None
            ) or (criterion or {}).get("learning_objective") or (
                resource or {}
            ).get("content")
            foundation = str(
                foundation or "khái niệm, mục đích và tình huống áp dụng của nó"
            ).strip().rstrip(".")
            answer = (
                f"Có. Với {concept}, ý chính bạn nên nắm trước là: "
                f"{foundation}. "
                "Bạn muốn mình giải thích bằng một ví dụ ngắn hay cùng bạn làm một bài tập gợi ý?"
            )
            if criterion and int(criterion.get("evidence_count") or 0) > 0:
                answer += (
                    f" Hiện hệ thống đánh giá mức hiểu của bạn là "
                    f"{cls._understanding_vi(criterion.get('understanding'))} dựa trên "
                    f"{criterion['evidence_count']} câu đã làm."
                )
            return ChatAssistantPayload(
                answer=answer,
                evidence_used=[
                    f"Knowledge base: {(criterion or resource or {}).get('name') or (resource or {}).get('title')}"
                ],
                limitations=[],
            )

        if not profiles:
            return cls._no_evidence()
        criterion = matched[0] if matched else None
        if criterion is not None:
            evidence_count = int(criterion.get("evidence_count") or 0)
            if evidence_count < 3:
                next_step = "làm thêm vài câu chẩn đoán trước khi kết luận mức độ thành thạo"
            elif str(criterion.get("understanding")) == "Needs review":
                next_step = "ôn lại phần nền tảng, xem một ví dụ mẫu rồi làm bài tập có hướng dẫn"
            else:
                next_step = "làm bài tập vận dụng và tự giải thích vì sao từng lựa chọn đúng hoặc sai"
            return ChatAssistantPayload(
                answer=(
                    f"Với {criterion['name']}, bạn nên {next_step}. "
                    f"Hiện kết luận dựa trên {evidence_count} câu đã trả lời."
                ),
                evidence_used=[f"Tiêu chí {criterion['name']}"],
                limitations=[],
            )

        recommendation = next(
            (
                item
                for profile in profiles
                for item in profile.get("recommendations") or []
            ),
            None,
        )
        if recommendation:
            return ChatAssistantPayload(
                answer=(
                    f"Bước tiếp theo phù hợp nhất là {recommendation['criterion_name']}. "
                    "Hãy ôn lại ý chính, xem một ví dụ có lời giải, rồi làm 3–5 câu cùng dạng "
                    "và tự giải thích lỗi sai sau mỗi câu."
                ),
                evidence_used=[f"Đề xuất học tập {recommendation['criterion_name']}"],
                limitations=[],
            )
        return ChatAssistantPayload(
            answer=(
                "Bạn có thể hỏi mình về tiến bộ theo từng môn, điểm mạnh, điểm cần cải thiện, "
                "hoặc nhắc một câu đã hoàn thành để xem lại lý do đúng sai."
            ),
            evidence_used=[],
            limitations=[],
        )

    @classmethod
    def _relevant_knowledge(
        cls,
        resources: list[dict[str, Any]],
        message: str,
        *,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        query = cls._normalize(message)
        tokens = cls._tokens(message)
        ranked = []
        for index, resource in enumerate(resources):
            searchable = " ".join(
                str(resource.get(key) or "")
                for key in (
                    "resource_id", "resource_type", "subject_code", "subject_name",
                    "title", "content", "question_code", "criterion_code",
                )
            )
            overlap = len(tokens & cls._tokens(searchable))
            score = overlap * 5
            if overlap and resource.get("resource_type") == "subject_knowledge":
                score += 20
            for key in ("question_code", "criterion_code"):
                code = cls._normalize(resource.get(key) or "")
                if code and code in query:
                    score += 100
            if score:
                ranked.append((score, -index, resource))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        matches = [item[2] for item in ranked[:limit]]
        if matches:
            return matches
        return [
            item for item in resources
            if item.get("resource_type") in {"subject", "assessment_criterion"}
        ][:limit]

    @classmethod
    def _relevant_questions(
        cls,
        questions: list[dict[str, Any]],
        message: str,
        *,
        intent: str,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        query = cls._normalize(message)
        query_tokens = cls._tokens(message)
        ranked = []
        for index, question in enumerate(questions):
            code = str(question.get("question_code") or "")
            criteria = " ".join(question.get("criteria") or [])
            text = " ".join(
                str(question.get(key) or "")
                for key in ("stem", "explanation", "subject_name", "order_no")
            ) + f" {code} {criteria}"
            searchable = cls._normalize(text)
            overlap = len(query_tokens & cls._tokens(searchable))
            score = overlap * 5
            if code and cls._normalize(code) in query:
                score += 100
            for criterion in question.get("criteria") or []:
                if cls._normalize(criterion) in query:
                    score += 30
            if any(word in query_tokens for word in {"wrong", "incorrect", "sai"}):
                score += 20 if not question.get("is_correct") else 0
            if any(word in query_tokens for word in {"correct", "right", "dung"}):
                score += 20 if question.get("is_correct") else 0
            if score:
                ranked.append((score, -index, question))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        matches = [item[2] for item in ranked[:limit]]
        if not matches and intent == "question_review" and questions:
            return questions[:1]
        return matches

    @classmethod
    def _intent(cls, message: str, question: dict | None = None) -> str:
        normalized = cls._normalize(message)
        direct_patterns = (
            r"\bwhat is the (?:correct )?answer\b",
            r"\bwhich (?:answer|option|choice) (?:is|should i choose)\b",
            r"\b(?:which|what) (?:answer|option|choice) should i (?:pick|select|choose)\b",
            r"\bgive me the (?:correct )?answer\b",
            r"\b(?:tell|show) me the (?:correct )?(?:answer|option|choice)\b",
            r"\bchoose (?:the )?(?:answer|option|choice) for me\b",
            r"\banswer this question\b",
            r"\bdap an (?:la gi|dung)\b",
            r"\bchon dap an (?:nao|gi)\b",
            r"\bphuong an (?:nao|dung)\b",
            r"\bcho toi dap an\b",
        )
        if any(re.search(pattern, normalized) for pattern in direct_patterns):
            return "security_refusal"
        if any(
            phrase in normalized
            for phrase in (
                "what have i learnt", "what have i learned", "what did i learn",
                "what did i learnt", "my progress",
                "how am i doing", "my strengths", "learned so far", "learnt so far",
                "tien bo", "diem manh", "da hoc duoc",
            )
        ):
            return "progress_summary"
        if question or any(
            phrase in normalized
            for phrase in (
                "why was", "why is this answer", "why is my answer", "why did i get",
                "wrong answer", "incorrect answer", "my mistake", "review question",
                "tai sao", "giai thich cau", "sai o dau",
            )
        ):
            return "question_review"
        if any(
            phrase in normalized
            for phrase in (
                "keyword", "key word", "explain", "where should i start",
                "what is", "what does", "how does", "khai niem", "tu khoa",
                "bat dau tu dau",
            )
        ):
            return "concept_help"
        if any(
            phrase in normalized
            for phrase in (
                "learn next", "improve", "need to learn", "should i study",
                "what to learn", "hoc gi", "cai thien", "on tap",
            )
        ):
            return "learning_improvement"
        return "learner_support"

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9]+", cls._normalize(value))
            if len(token) > 1 and token not in cls._STOP_WORDS
        }

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or ""))
        return " ".join(
            normalized.encode("ascii", "ignore").decode("ascii").lower().split()
        )

    @staticmethod
    def _deduplicate_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for question in questions:
            key = question.get("exam_item_id") or (
                question.get("session_id"), question.get("question_id")
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(question)
        return result

    @staticmethod
    def _number(value: Any) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _percent(value: Any) -> str:
        return f"{float(value):.1f}%" if value is not None else "chưa có"

    @staticmethod
    def _concept_name(value: str) -> str:
        words = str(value or "").split()
        if words and words[0].lower() in {
            "analyze", "apply", "choose", "configure", "design", "determine",
            "explain", "identify", "implement", "use",
        }:
            words = words[1:]
        return " ".join(words) or str(value)

    @staticmethod
    def _understanding_vi(value: Any) -> str:
        return {
            "Not assessed": "chưa được đánh giá",
            "Needs review": "cần ôn lại",
            "Developing": "đang phát triển",
            "Understands": "đã hiểu",
            "Mastered": "đã thành thạo",
        }.get(str(value), "đang được theo dõi")

    @staticmethod
    def _no_evidence() -> ChatAssistantPayload:
        return ChatAssistantPayload(
            answer=(
                "Mình chưa có đủ dữ liệu bài làm đã hoàn thành để đánh giá chính xác. "
                "Bạn nên làm bài kiểm tra đầu vào cho một môn; sau đó mình có thể phân tích "
                "điểm mạnh, điểm cần cải thiện và từng câu trả lời."
            ),
            evidence_used=[],
            limitations=["Chưa có đủ bằng chứng đánh giá."],
        )

    @staticmethod
    def _student_id(user: AuthenticatedUser) -> int:
        if user.student_id is None:
            raise LearnerChatNotFoundError("Student not found")
        return user.student_id
