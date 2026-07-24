import math
import secrets
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.abilities.service import AbilityService
from backend.auth.schemas import AuthenticatedUser
from backend.cat.repository import CATRepository
from backend.cat.schemas import (
    CATAnswerRequest,
    CATAnswerResponse,
    CATProgress,
    CATPublicResult,
    CATQuestion,
    CATStaffDetail,
    CATStartRequest,
    CATStartResponse,
)
from backend.cat.selector import CATCandidate, CATSelection, select_next_question
from backend.cat.stopping import evaluate_stopping
from backend.exams.errors import ExamError, ExamNotFoundError, ExamStateError
from backend.exams.options import prepare_display_options
from backend.exams.schemas import ExamOption
from backend.irt.model import IRTResponse, estimate_ability_eap


@dataclass(frozen=True, slots=True)
class CATConfig:
    minimum: int
    maximum: int
    se_threshold: float
    epsilon: float
    stability_window: int
    information_weight: float
    weak_unit_weight: float
    content_balance_weight: float
    exposure_penalty: float
    difficulty_distribution: dict[str, float]
    display_option_count: int
    randomize_options: bool
    scale: float
    topic_codes: tuple[str, ...]
    skill_codes: tuple[str, ...]
    bloom_levels: tuple[str, ...]
    estimated_minutes: int


class CATService:
    def __init__(
        self,
        repository: CATRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.repository = repository
        self.session_factory = session_factory

    async def start(
        self, request: CATStartRequest, user: AuthenticatedUser
    ) -> CATStartResponse:
        if user.student_id is None:
            raise ExamError("The authenticated account is not linked to a student")
        async with self.session_factory() as session:
            subject = await self.repository.subject(session, request.subject_code)
            if subject is None:
                raise ExamNotFoundError(f"Subject '{request.subject_code}' was not found")
            await self.repository.lock_start(
                session, user.student_id, subject["subject_id"]
            )
            existing = await self.repository.active_session(
                session, user.student_id, subject["subject_id"]
            )
            if existing:
                exam = await self.repository.session_for_update(session, existing["session_id"])
                item = await self.repository.current_item(session, existing["session_id"])
                if exam and item:
                    config = self._config(exam["generation_config"])
                    counts = await self.repository.counts(session, exam["session_id"])
                    return self._start_response(exam, item, config, int(counts["answered"]))

            raw_config = await self.repository.config(session)
            config = self._config(raw_config)
            candidates = await self.repository.candidates(
                session,
                subject["subject_id"],
                [],
                config.topic_codes,
                config.skill_codes,
                config.bloom_levels,
            )
            if not candidates:
                raise ExamError(
                    f"Subject '{request.subject_code}' has no active, validated CAT questions"
                )
            ability = await self.repository.ability(
                session, user.student_id, subject["subject_id"]
            )
            theta = float(ability["theta"] if ability else raw_config.get("CAT_INITIAL_THETA", 0))
            standard_error = float(ability["standard_error"] if ability else 1.0)
            effective_minimum = min(config.minimum, len(candidates))
            effective_maximum = min(config.maximum, len(candidates))
            estimated_minutes = max(
                1,
                math.ceil(
                    effective_maximum
                    * sum(int(row["avg_time_sec"]) for row in candidates)
                    / len(candidates)
                    / 60
                ),
            )
            snapshot = {
                "minimum": effective_minimum,
                "maximum": effective_maximum,
                "se_threshold": config.se_threshold,
                "epsilon": config.epsilon,
                "stability_window": config.stability_window,
                "information_weight": config.information_weight,
                "weak_unit_weight": config.weak_unit_weight,
                "content_balance_weight": config.content_balance_weight,
                "exposure_penalty": config.exposure_penalty,
                "difficulty_distribution": config.difficulty_distribution,
                "display_option_count": config.display_option_count,
                "randomize_options": config.randomize_options,
                "scale": config.scale,
                "active_only": True,
                "topic_codes": list(config.topic_codes),
                "skill_codes": list(config.skill_codes),
                "bloom_levels": list(config.bloom_levels),
                "estimated_minutes": estimated_minutes,
            }
            session_id = await self.repository.create_session(
                session,
                student_id=user.student_id,
                subject_id=subject["subject_id"],
                generation_config=snapshot,
                theta=theta,
                standard_error=standard_error,
            )
            selection = await self._selection(
                session,
                candidates,
                user.student_id,
                subject["subject_id"],
                session_id,
                theta,
                self._config(snapshot),
            )
            item = await self._create_question(
                session, session_id, candidates, selection, theta, 1, config
            )
            await session.commit()
            exam = {
                "session_id": session_id,
                "subject_code": subject["subject_code"],
                "subject_name": subject["subject_name"],
            }
            return self._start_response(exam, item, self._config(snapshot), 0)

    async def answer(
        self,
        session_id: int,
        request: CATAnswerRequest,
        user: AuthenticatedUser,
    ) -> CATAnswerResponse:
        async with self.session_factory() as session:
            exam = await self.repository.session_for_update(session, session_id)
            self._validate_owner(exam, user, session_id)
            if exam["status"] != "in_progress":
                raise ExamStateError("This adaptive session is already completed")
            item = await self.repository.current_item(session, session_id, lock=True)
            if item is None or item["exam_item_id"] != request.exam_item_id:
                raise ExamStateError("The submitted question is stale or already answered")
            option = next(
                (
                    value
                    for value in item["displayed_options"]
                    if value["option_code"] == request.selected_option_code
                ),
                None,
            )
            if option is None:
                raise ExamError("The selected option was not displayed for this question")

            config = self._config(exam["generation_config"])
            previous = await self.repository.responses(session, session_id)
            irt_responses = [
                IRTResponse(
                    float(row["irt_a"]),
                    float(row["irt_b"]),
                    float(row["irt_c"]),
                    bool(row["is_correct"]),
                )
                for row in previous
            ]
            is_correct = bool(option["is_best_answer"])
            awarded_score = float(option["score_weight"])
            irt_responses.append(
                IRTResponse(
                    float(item["irt_a"]),
                    float(item["irt_b"]),
                    float(item["irt_c"]),
                    is_correct,
                )
            )
            estimate = estimate_ability_eap(
                irt_responses,
                prior_mean=float(exam["theta_initial"]),
                prior_standard_error=1.0,
                scale=config.scale,
            )
            updated = await self.repository.answer_item(
                session,
                item=item,
                selected_option_code=request.selected_option_code,
                is_correct=is_correct,
                awarded_score=awarded_score,
                response_time_sec=request.response_time_sec,
                theta=estimate.theta,
                standard_error=estimate.standard_error,
            )
            if not updated:
                raise ExamStateError("This question has already been answered")

            refreshed = await AbilityService().refresh(
                session,
                student_id=exam["student_id"],
                subject_id=exam["subject_id"],
                session_id=session_id,
                scale=config.scale,
            )
            counts = await self.repository.counts(session, session_id)
            answered_count = int(counts["answered"])
            total_score = float(counts["total_score"])
            await self.repository.update_progress(
                session,
                session_id=session_id,
                theta=refreshed.theta,
                standard_error=refreshed.standard_error,
                total_score=total_score,
                answered_count=answered_count,
            )
            used_ids = await self.repository.used_question_ids(session, session_id)
            candidates = await self.repository.candidates(
                session,
                exam["subject_id"],
                used_ids,
                config.topic_codes,
                config.skill_codes,
                config.bloom_levels,
            )
            theta_history = [float(exam["theta_initial"])] + await self.repository.theta_history(
                session, session_id
            )
            decision = evaluate_stopping(
                answered_count=answered_count,
                minimum=config.minimum,
                maximum=config.maximum,
                standard_error=refreshed.standard_error,
                se_threshold=config.se_threshold,
                theta_history=theta_history,
                epsilon=config.epsilon,
                stability_window=config.stability_window,
                candidates_remaining=len(candidates),
            )
            progress = CATProgress(
                answered=answered_count,
                minimum=config.minimum,
                maximum=config.maximum,
            )
            if decision.should_stop:
                await self.repository.complete(
                    session,
                    session_id=session_id,
                    total_score=total_score,
                    answered_count=answered_count,
                    theta=refreshed.theta,
                    standard_error=refreshed.standard_error,
                    stop_reason=decision.reason or "completed",
                )
                await session.commit()
                public = await self._result_from_values(
                    exam, total_score, answered_count
                )
                return CATAnswerResponse(
                    session_id=session_id,
                    completed=True,
                    progress=progress,
                    result=public,
                )

            selection = await self._selection(
                session,
                candidates,
                exam["student_id"],
                exam["subject_id"],
                session_id,
                refreshed.theta,
                config,
            )
            next_item = await self._create_question(
                session,
                session_id,
                candidates,
                selection,
                refreshed.theta,
                answered_count + 1,
                config,
            )
            await session.commit()
            return CATAnswerResponse(
                session_id=session_id,
                completed=False,
                progress=progress,
                question=self._public_question(next_item),
            )

    async def result(self, session_id: int, user: AuthenticatedUser) -> CATPublicResult:
        async with self.session_factory() as session:
            row = await self.repository.result(session, session_id)
        if row is None or user.student_id is None or row["student_id"] != user.student_id:
            raise ExamNotFoundError(f"Adaptive session {session_id} was not found")
        if row["status"] != "completed":
            raise ExamStateError("This adaptive session is not completed")
        return await self._result_from_values(
            row,
            float(row["total_score"]),
            int(row["answered_count"]),
        )

    async def staff_detail(self, session_id: int) -> CATStaffDetail:
        async with self.session_factory() as session:
            row = await self.repository.staff_detail(session, session_id)
        if row is None:
            raise ExamNotFoundError(f"Adaptive session {session_id} was not found")
        return CATStaffDetail(**row)

    async def _selection(
        self,
        session: AsyncSession,
        rows: list[dict[str, Any]],
        student_id: int,
        subject_id: int,
        session_id: int,
        theta: float,
        config: CATConfig,
    ) -> CATSelection:
        mastery = await self.repository.unit_mastery(session, student_id, subject_id)
        usage = await self.repository.difficulty_usage(session, session_id)
        selected = select_next_question(
            [self._candidate(row) for row in rows],
            theta=theta,
            unit_mastery=mastery,
            difficulty_usage=usage,
            target_distribution=config.difficulty_distribution,
            information_weight=config.information_weight,
            weak_unit_weight=config.weak_unit_weight,
            content_balance_weight=config.content_balance_weight,
            exposure_penalty=config.exposure_penalty,
            scale=config.scale,
        )
        if selected is None:
            raise ExamError("No eligible adaptive question remains")
        return selected

    async def _create_question(
        self,
        session: AsyncSession,
        session_id: int,
        rows: list[dict[str, Any]],
        selection: CATSelection,
        theta: float,
        order_no: int,
        config: CATConfig,
    ) -> dict[str, Any]:
        row = next(value for value in rows if value["question_id"] == selection.candidate.question_id)
        options = await self.repository.options(session, row["question_id"])
        displayed = prepare_display_options(
            options,
            config.display_option_count,
            seed=secrets.randbits(31),
            randomize=config.randomize_options,
        )
        item_id = await self.repository.create_item(
            session,
            session_id=session_id,
            question=row,
            order_no=order_no,
            displayed_options=displayed,
            theta=theta,
            information=selection.information,
            reason=selection.reason,
            components=selection.components,
        )
        return {
            "exam_item_id": item_id,
            "order_no": order_no,
            "question_code": row["question_code"],
            "stem": row["stem"],
            "displayed_options": displayed,
        }

    def _start_response(
        self,
        exam: dict[str, Any],
        item: dict[str, Any],
        config: CATConfig,
        answered: int,
    ) -> CATStartResponse:
        return CATStartResponse(
            session_id=exam["session_id"],
            subject_code=exam["subject_code"],
            subject_name=exam["subject_name"],
            estimated_minutes=config.estimated_minutes,
            progress=CATProgress(
                answered=answered,
                minimum=config.minimum,
                maximum=config.maximum,
            ),
            question=self._public_question(item),
        )

    @staticmethod
    def _public_question(item: dict[str, Any]) -> CATQuestion:
        return CATQuestion(
            exam_item_id=item["exam_item_id"],
            order_no=item["order_no"],
            question_code=item["question_code"],
            stem=item["stem"],
            options=[
                ExamOption(option_code=value["option_code"], option_text=value["option_text"])
                for value in item["displayed_options"]
            ],
        )

    @staticmethod
    async def _result_from_values(
        exam: dict[str, Any], total_score: float, answered_count: int
    ) -> CATPublicResult:
        percentage = 100 * total_score / answered_count if answered_count else 0.0
        if percentage < 50:
            label = "Needs review"
        elif percentage < 70:
            label = "Foundational understanding"
        elif percentage < 85:
            label = "Good understanding"
        else:
            label = "Strong understanding"
        return CATPublicResult(
            session_id=exam["session_id"],
            subject_code=exam["subject_code"],
            subject_name=exam["subject_name"],
            total_score=round(total_score, 5),
            max_score=float(answered_count),
            percentage=round(percentage, 2),
            understanding_label=label,
            answered_count=answered_count,
        )

    @staticmethod
    def _candidate(row: dict[str, Any]) -> CATCandidate:
        return CATCandidate(
            question_id=row["question_id"],
            question_code=row["question_code"],
            difficulty_label=row["difficulty_label"],
            topic_code=row["topic_code"],
            unit_codes=tuple(row["unit_codes"]),
            irt_a=float(row["irt_a"]),
            irt_b=float(row["irt_b"]),
            irt_c=float(row["irt_c"]),
            exposure_count=int(row["exposure_count"]),
        )

    @staticmethod
    def _config(values: dict[str, Any]) -> CATConfig:
        return CATConfig(
            minimum=int(values.get("minimum", values.get("CAT_MIN_QUESTION_COUNT", 10))),
            maximum=int(values.get("maximum", values.get("CAT_MAX_QUESTION_COUNT", 30))),
            se_threshold=float(values.get("se_threshold", values.get("CAT_STOP_STANDARD_ERROR", 0.3))),
            epsilon=float(values.get("epsilon", values.get("CAT_STABILITY_EPSILON", 0.05))),
            stability_window=int(values.get("stability_window", values.get("CAT_STABILITY_WINDOW", 3))),
            information_weight=float(values.get("information_weight", values.get("CAT_INFORMATION_WEIGHT", 1.0))),
            weak_unit_weight=float(values.get("weak_unit_weight", values.get("CAT_WEAK_UNIT_WEIGHT", 0.35))),
            content_balance_weight=float(values.get("content_balance_weight", values.get("CAT_CONTENT_BALANCE_WEIGHT", 0.2))),
            exposure_penalty=float(values.get("exposure_penalty", values.get("CAT_EXPOSURE_PENALTY", 0.15))),
            difficulty_distribution={
                key: float(value)
                for key, value in values.get(
                    "difficulty_distribution",
                    values.get("CAT_DIFFICULTY_DISTRIBUTION", {"easy": 0.3, "medium": 0.4, "hard": 0.3}),
                ).items()
            },
            display_option_count=int(values.get("display_option_count", values.get("DISPLAY_OPTION_COUNT", 4))),
            randomize_options=bool(values.get("randomize_options", values.get("RANDOMIZE_OPTION_ORDER", True))),
            scale=float(values.get("scale", values.get("IRT_SCALE_CONSTANT", 1.7))),
            topic_codes=tuple(values.get("topic_codes", values.get("CAT_TOPIC_CODES", []))),
            skill_codes=tuple(values.get("skill_codes", values.get("CAT_SKILL_CODES", []))),
            bloom_levels=tuple(values.get("bloom_levels", values.get("CAT_BLOOM_LEVELS", []))),
            estimated_minutes=int(
                values.get(
                    "estimated_minutes",
                    max(
                        1,
                        math.ceil(
                            int(values.get("maximum", values.get("CAT_MAX_QUESTION_COUNT", 30)))
                            * 75
                            / 60
                        ),
                    ),
                )
            ),
        )

    @staticmethod
    def _validate_owner(
        exam: dict[str, Any] | None, user: AuthenticatedUser, session_id: int
    ) -> None:
        if (
            exam is None
            or exam.get("mode") != "adaptive"
            or user.student_id is None
            or exam.get("student_id") != user.student_id
        ):
            raise ExamNotFoundError(f"Adaptive session {session_id} was not found")
