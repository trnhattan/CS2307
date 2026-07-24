import math
import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.abilities.service import AbilityService
from backend.auth.schemas import AuthenticatedUser
from backend.exams.errors import ExamError, ExamNotFoundError, ExamStateError
from backend.exams.options import prepare_display_options
from backend.exams.repository import ExamRepository
from backend.exams.schemas import (
    AnswerFeedback,
    ExamRuntimeConfig,
    ExamOption,
    ExamQuestion,
    GenerateExamRequest,
    GenerateExamResponse,
    GeneratedSession,
    SubjectListResponse,
    SubjectSummary,
    SubmitExamRequest,
    SubmitExamResponse,
    TakerExamConfig,
)
from backend.exams.selection import QuestionCandidate, select_fixed_exam
from backend.irt.model import IRTResponse, estimate_ability_eap


class ExamService:
    def __init__(
        self,
        repository: ExamRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory

    async def list_subjects(self) -> SubjectListResponse:
        async with self._session_factory() as session:
            config = await self._repository.get_config(session)
            statuses = self._statuses(config)
            subjects = await self._repository.list_subjects(session, statuses)
        return SubjectListResponse(
            subjects=[SubjectSummary(**subject) for subject in subjects],
            config=TakerExamConfig(
                default_question_count=int(
                    config.get("DEFAULT_EXAM_QUESTION_COUNT", 20)
                ),
                difficulty_distribution={
                    key: float(value)
                    for key, value in config.get(
                        "FIXED_EXAM_DIFFICULTY_DISTRIBUTION",
                        {"easy": 0.3, "medium": 0.4, "hard": 0.3},
                    ).items()
                },
            ),
        )

    async def generate(
        self,
        request: GenerateExamRequest,
        user: AuthenticatedUser,
    ) -> GenerateExamResponse:
        if user.student_id is None or user.student_code is None:
            raise ExamError("The authenticated account is not linked to a student")
        async with self._session_factory() as session:
            config = await self._repository.get_config(session)
            runtime_config = self._runtime_config(config)
            statuses = self._statuses(config)
            count = request.question_count or runtime_config.default_question_count
            distribution = (
                request.difficulty_distribution or runtime_config.difficulty_distribution
            )
            base_seed = request.seed if request.seed is not None else secrets.randbits(31)
            student_id = user.student_id
            generated_sessions: list[GeneratedSession] = []

            for subject_index, subject_code in enumerate(request.subject_codes):
                subject = await self._repository.get_subject(session, subject_code)
                if not subject:
                    raise ExamNotFoundError(f"Subject '{subject_code}' was not found")

                ability = await self._repository.get_ability(
                    session,
                    student_id,
                    subject["subject_id"],
                )
                theta = float(
                    ability["theta"]
                    if ability
                    else config.get("CAT_INITIAL_THETA", 0.0)
                )
                standard_error = float(ability["standard_error"] if ability else 1.0)
                rows = await self._repository.get_candidates(
                    session,
                    subject["subject_id"],
                    statuses,
                    request.topic_codes,
                    request.skill_codes,
                    request.bloom_levels,
                )
                if len(rows) < count:
                    raise ExamError(
                        f"Subject '{subject_code}' has {len(rows)} valid questions, "
                        f"but the blueprint requests {count}"
                    )

                candidates = [self._candidate(row) for row in rows]
                subject_seed = base_seed + subject_index * 100_003
                selected = select_fixed_exam(
                    candidates,
                    count=count,
                    theta=theta,
                    distribution=distribution,
                    seed=subject_seed,
                    scale=float(config.get("IRT_SCALE_CONSTANT", 1.7)),
                    max_estimated_seconds=(
                        request.max_estimated_minutes * 60
                        if request.max_estimated_minutes is not None
                        else None
                    ),
                )
                if len(selected) < count:
                    raise ExamError(
                        f"Subject '{subject_code}' cannot satisfy the exact blueprint of "
                        f"{count} questions with the requested difficulty, content, and "
                        "time constraints; no questions were substituted or generated"
                    )
                selected_ids = [item.candidate.question_id for item in selected]
                options_by_question = await self._repository.get_options(
                    session,
                    selected_ids,
                )
                rows_by_id = {row["question_id"]: row for row in rows}
                generation_snapshot = {
                    "strategy": runtime_config.selection_strategy,
                    "question_count": count,
                    "difficulty_distribution": distribution,
                    "display_option_count": runtime_config.display_option_count,
                    "allowed_statuses": statuses,
                    "irt_model": runtime_config.irt_model,
                    "theta_at_generation": theta,
                    "central_config_source": "sys_props",
                    "topic_codes": request.topic_codes,
                    "skill_codes": request.skill_codes,
                    "bloom_levels": request.bloom_levels,
                    "max_estimated_minutes": request.max_estimated_minutes,
                }
                session_id = await self._repository.create_session(
                    session,
                    student_id=student_id,
                    subject_id=subject["subject_id"],
                    generation_config=generation_snapshot,
                    seed=subject_seed,
                    theta=theta,
                    standard_error=standard_error,
                    question_count=count,
                )
                questions: list[ExamQuestion] = []
                trace_steps: list[dict[str, Any]] = []
                estimated_seconds = 0

                for order_no, selected_item in enumerate(selected, start=1):
                    candidate = selected_item.candidate
                    question = rows_by_id[candidate.question_id]
                    displayed = prepare_display_options(
                        options_by_question[candidate.question_id],
                        runtime_config.display_option_count,
                        seed=subject_seed + candidate.question_id,
                        randomize=bool(config.get("RANDOMIZE_OPTION_ORDER", True)),
                    )
                    exam_item_id = await self._repository.create_item(
                        session,
                        session_id=session_id,
                        question=question,
                        order_no=order_no,
                        displayed_options=displayed,
                        selection_reason=selected_item.reason,
                        information=selected_item.information,
                        theta=theta,
                    )
                    questions.append(
                        ExamQuestion(
                            exam_item_id=exam_item_id,
                            order_no=order_no,
                            question_code=candidate.question_code,
                            stem=question["stem"],
                            options=[
                                ExamOption(
                                    option_code=option["option_code"],
                                    option_text=option["option_text"],
                                )
                                for option in displayed
                            ],
                        )
                    )
                    estimated_seconds += candidate.avg_time_sec
                    trace_steps.append(
                        {
                            "step_no": order_no,
                            "rule_code": "R_GEN_IRT_BALANCED",
                            "input_fact_ids": [],
                            "output_fact_ids": [],
                            "question_code": candidate.question_code,
                            "explanation": selected_item.reason,
                        }
                    )

                await self._repository.create_generation_trace(
                    session,
                    session_id=session_id,
                    subject_code=subject_code,
                    question_count=count,
                    theta=theta,
                    steps=trace_steps,
                )
                generated_sessions.append(
                    GeneratedSession(
                        session_id=session_id,
                        subject_code=subject_code,
                        subject_name=subject["subject_name"],
                        question_count=count,
                        estimated_minutes=max(1, math.ceil(estimated_seconds / 60)),
                        questions=questions,
                    )
                )

            await session.commit()
            return GenerateExamResponse(
                student_code=user.student_code,
                sessions=generated_sessions,
            )

    async def submit(
        self,
        session_id: int,
        request: SubmitExamRequest,
        user: AuthenticatedUser,
    ) -> SubmitExamResponse:
        async with self._session_factory() as session:
            config = await self._repository.get_config(session)
            exam = await self._repository.get_session_for_update(session, session_id)
            if not exam:
                raise ExamNotFoundError(f"Exam session {session_id} was not found")
            if user.student_id is None or exam["student_id"] != user.student_id:
                raise ExamNotFoundError(f"Exam session {session_id} was not found")
            if exam["status"] != "in_progress":
                raise ExamStateError("This exam session has already been completed")

            items = await self._repository.get_session_items(session, session_id)
            answers = {answer.exam_item_id: answer for answer in request.answers}
            expected_ids = {item["exam_item_id"] for item in items}
            if set(answers) != expected_ids:
                missing = len(expected_ids - set(answers))
                extra = len(set(answers) - expected_ids)
                raise ExamError(
                    f"Submission must answer every question (missing={missing}, extra={extra})"
                )

            irt_responses: list[IRTResponse] = []
            feedback: list[AnswerFeedback] = []
            total_score = 0.0
            initial_theta = float(exam["theta_initial"])
            initial_se = float(exam["standard_error_current"])
            scale = float(config.get("IRT_SCALE_CONSTANT", 1.7))
            final_theta = initial_theta
            final_se = initial_se
            trace_steps: list[dict[str, Any]] = []

            for step_no, item in enumerate(items, start=1):
                answer = answers[item["exam_item_id"]]
                option = next(
                    (
                        value
                        for value in item["displayed_options"]
                        if value["option_code"] == answer.selected_option_code
                    ),
                    None,
                )
                if option is None:
                    raise ExamError(
                        f"Option '{answer.selected_option_code}' is not displayed for "
                        f"item {item['exam_item_id']}"
                    )
                best = next(
                    value
                    for value in item["displayed_options"]
                    if value["is_best_answer"]
                )
                is_correct = bool(option["is_best_answer"])
                awarded_score = float(option["score_weight"])
                total_score += awarded_score
                irt_responses.append(
                    IRTResponse(
                        a=float(item["irt_a"]),
                        b=float(item["irt_b"]),
                        c=float(item["irt_c"]),
                        correct=is_correct,
                    )
                )
                estimate = estimate_ability_eap(
                    irt_responses,
                    prior_mean=initial_theta,
                    prior_standard_error=initial_se,
                    scale=scale,
                )
                final_theta = estimate.theta
                final_se = estimate.standard_error
                await self._repository.update_item_response(
                    session,
                    exam_item_id=item["exam_item_id"],
                    option_code=answer.selected_option_code,
                    is_correct=is_correct,
                    awarded_score=awarded_score,
                    response_time_sec=answer.response_time_sec,
                    theta_after=final_theta,
                    standard_error_after=final_se,
                    scoring_detail={
                        "model": "IRT-3PL-EAP",
                        "theta_after": final_theta,
                        "binary_irt_response": int(is_correct),
                        "partial_credit": awarded_score,
                    },
                )
                await self._repository.record_selected_option_fact(
                    session,
                    student_code=exam["student_code"],
                    session_id=session_id,
                    question_code=item["question_code"],
                    option_code=answer.selected_option_code,
                )
                feedback.append(
                    AnswerFeedback(
                        exam_item_id=item["exam_item_id"],
                        question_code=item["question_code"],
                        stem=item["stem"],
                        selected_option_code=answer.selected_option_code,
                        selected_option_text=option["option_text"],
                        correct_option_code=best["option_code"],
                        correct_option_text=best["option_text"],
                        is_correct=is_correct,
                        awarded_score=awarded_score,
                        explanation=item["explanation"],
                    )
                )
                trace_steps.append(
                    {
                        "step_no": step_no,
                        "rule_code": "R_UPDATE_ABILITY_3PL",
                        "question_code": item["question_code"],
                        "irt_response": int(is_correct),
                        "theta_after": round(final_theta, 6),
                        "standard_error_after": round(final_se, 6),
                        "explanation": (
                            f"Updated theta after question {item['question_code']} "
                            "with IRT 3PL EAP."
                        ),
                    }
                )

            refreshed = await AbilityService().refresh(
                session,
                student_id=exam["student_id"],
                subject_id=exam["subject_id"],
                session_id=session_id,
                scale=scale,
            )
            final_theta = refreshed.theta
            final_se = refreshed.standard_error
            await self._repository.complete_session(
                session,
                session_id=session_id,
                total_score=total_score,
                theta=final_theta,
                standard_error=final_se,
            )
            await self._repository.create_scoring_trace(
                session,
                session_id=session_id,
                theta_before=initial_theta,
                theta_after=final_theta,
                steps=trace_steps,
            )
            await session.commit()

            max_score = float(len(items))
            return SubmitExamResponse(
                session_id=session_id,
                subject_code=exam["subject_code"],
                total_score=round(total_score, 5),
                max_score=max_score,
                percentage=round(100.0 * total_score / max_score, 2),
                understanding_label=self._understanding_label(
                    100.0 * total_score / max_score
                ),
                feedback=feedback,
            )

    @staticmethod
    def _candidate(row: dict[str, Any]) -> QuestionCandidate:
        return QuestionCandidate(
            question_id=row["question_id"],
            question_code=row["question_code"],
            difficulty_label=row["difficulty_label"],
            bloom_level=row["bloom_level"],
            topic_name=row["topic_name"],
            topic_code=row["topic_code"],
            skill_codes=tuple(row["skill_codes"]),
            irt_a=float(row["irt_a"]),
            irt_b=float(row["irt_b"]),
            irt_c=float(row["irt_c"]),
            avg_time_sec=row["avg_time_sec"],
        )

    @staticmethod
    def _statuses(config: dict[str, Any]) -> list[str]:
        value = config.get(
            "EXAM_ALLOWED_QUESTION_STATUSES",
            ["active", "reviewed", "draft"],
        )
        return [str(status) for status in value]

    @staticmethod
    def _runtime_config(config: dict[str, Any]) -> ExamRuntimeConfig:
        distribution = config.get(
            "FIXED_EXAM_DIFFICULTY_DISTRIBUTION",
            {"easy": 0.3, "medium": 0.4, "hard": 0.3},
        )
        return ExamRuntimeConfig(
            default_question_count=int(config.get("DEFAULT_EXAM_QUESTION_COUNT", 20)),
            display_option_count=int(config.get("DISPLAY_OPTION_COUNT", 4)),
            difficulty_distribution={
                key: float(value) for key, value in distribution.items()
            },
            selection_strategy=str(
                config.get("EXAM_GENERATION_STRATEGY", "irt_information_balanced")
            ),
            irt_model=str(config.get("IRT_MODEL", "3PL")),
        )

    @staticmethod
    def _understanding_label(percentage: float) -> str:
        if percentage < 50:
            return "Needs review"
        if percentage < 70:
            return "Foundational understanding"
        if percentage < 85:
            return "Good understanding"
        return "Strong understanding"
