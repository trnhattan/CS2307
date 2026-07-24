import re
import unicodedata

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.admin.errors import (
    AccountConflictError,
    AccountNotFoundError,
    AdminError,
    QuestionNotFoundError,
    QuestionValidationError,
)
from backend.admin.repository import AdminRepository
from backend.admin.schemas import (
    AccountCreateRequest,
    AccountItem,
    AccountUpdateRequest,
    BulkQuestionActivationResponse,
    QuestionBankResponse,
    QuestionDetail,
    QuestionMetadataUpdate,
    QuestionReadinessResponse,
    QuestionReviewResponse,
    QuestionValidationIssue,
    SubjectReadiness,
    SystemOverview,
)
from backend.auth.passwords import hash_password
from backend.system_config.repository import SystemConfigRepository
from backend.system_config.schemas import ConfigItem
from backend.system_config.service import SystemConfigService


class AdminService:
    async def bulk_activate_questions(
        self, question_codes: list[str], reviewer: str
    ) -> BulkQuestionActivationResponse:
        activated = []
        rejected = {}
        async with self._session_factory() as session:
            for question_code in question_codes:
                data = await self._repository.validation_data(session, question_code)
                if data is None:
                    rejected[question_code] = [
                        QuestionValidationIssue(
                            code="not_found",
                            message="Question not found",
                            severity="blocking",
                        )
                    ]
                    continue
                issues = self._validation_issues(data)
                blockers = [issue for issue in issues if issue.severity == "blocking"]
                report = {
                    "valid": not blockers,
                    "issues": [issue.model_dump() for issue in issues],
                    "validator": "deterministic-v1",
                }
                await self._repository.mark_reviewed(
                    session, question_code, reviewer, report, not blockers
                )
                if blockers:
                    rejected[question_code] = blockers
                    continue
                await self._repository.activate_question(session, question_code, reviewer)
                activated.append(question_code)
            await session.commit()
        return BulkQuestionActivationResponse(activated=activated, rejected=rejected)

    async def question_detail(self, question_code: str) -> QuestionDetail:
        async with self._session_factory() as session:
            row = await self._repository.question_detail(session, question_code)
        if row is None:
            raise QuestionNotFoundError("Question not found")
        return QuestionDetail(**row)

    async def update_question(
        self, question_code: str, request: QuestionMetadataUpdate, actor: str
    ) -> QuestionDetail:
        async with self._session_factory() as session:
            if await self._repository.question_detail(session, question_code) is None:
                raise QuestionNotFoundError("Question not found")
            await self._repository.update_question_metadata(
                session,
                question_code,
                request.model_dump(exclude_unset=True),
                actor,
            )
            await session.commit()
        return await self.question_detail(question_code)

    async def review_question(
        self, question_code: str, reviewer: str
    ) -> QuestionReviewResponse:
        async with self._session_factory() as session:
            data = await self._repository.validation_data(session, question_code)
            if data is None:
                raise QuestionNotFoundError("Question not found")
            issues = self._validation_issues(data)
            valid = not any(issue.severity == "blocking" for issue in issues)
            report = {
                "valid": valid,
                "issues": [issue.model_dump() for issue in issues],
                "validator": "deterministic-v1",
            }
            row = await self._repository.mark_reviewed(
                session, question_code, reviewer, report, valid
            )
            await session.commit()
        return QuestionReviewResponse(
            question_code=question_code,
            valid=valid,
            issues=issues,
            **row,
        )

    async def activate_question(
        self, question_code: str, reviewer: str
    ) -> QuestionReviewResponse:
        review = await self.review_question(question_code, reviewer)
        if not review.valid:
            raise QuestionValidationError("The question has blocking issues and cannot be activated")
        async with self._session_factory() as session:
            await self._repository.activate_question(session, question_code, reviewer)
            await session.commit()
        return review.model_copy(update={"status": "active"})

    async def readiness(self) -> QuestionReadinessResponse:
        async with self._session_factory() as session:
            data = await self._repository.readiness(session)
            validation_rows = [
                await self._repository.validation_data(session, question_code)
                for question_code in await self._repository.question_codes(session)
            ]
        subjects = [
            SubjectReadiness(
                **row,
                cat_minimum=data["cat_minimum"],
                cat_feasible=row["active_questions"] >= data["cat_minimum"],
            )
            for row in data["subjects"]
        ]
        invalid_questions = sum(
            bool(
                row
                and any(
                    issue.severity == "blocking"
                    for issue in self._validation_issues(row)
                )
            )
            for row in validation_rows
        )
        gap = max(0, data["target"] - data["total_questions"])
        limitations = []
        if gap:
            limitations.append(
                f"The bank has {data['total_questions']} questions and is {gap} below the "
                "coursework target; the system does not silently pad the bank."
            )
        pending_review = data["total_questions"] - data["active_questions"]
        if pending_review:
            limitations.append(
                f"{pending_review} questions are not active and require explicit administrator review."
            )
        if any(not subject.cat_feasible for subject in subjects):
            limitations.append("One or more subjects lack enough active questions for the CAT minimum.")
        return QuestionReadinessResponse(
            total_questions=data["total_questions"],
            active_questions=data["active_questions"],
            target_questions=data["target"],
            target_gap=gap,
            invalid_questions=invalid_questions,
            subjects=subjects,
            limitations=limitations,
        )

    @staticmethod
    def _validation_issues(data: dict) -> list[QuestionValidationIssue]:
        issues = []
        def add(code: str, message: str, severity: str = "blocking") -> None:
            issues.append(QuestionValidationIssue(code=code, message=message, severity=severity))

        if not data["is_pool_valid"]:
            add("invalid_answer_pool", "The answer pool or best answer is invalid")
        if data.get("invalid_option_count", 0):
            add("invalid_option_metadata", "Answer content or score weights are invalid")
        if data.get("duplicate_option_count", 0):
            add("duplicate_options", "Answer options contain duplicate text")
        if not data["explanation"] or not str(data["explanation"]).strip():
            add("missing_explanation", "The answer explanation is missing")
        if not data["source"] or not str(data["source"]).strip():
            add("missing_source", "The question source is missing")
        if not isinstance(data.get("provenance"), dict) or not data["provenance"]:
            add("missing_provenance", "Question provenance is missing")
        if data["topic_count"] != 1:
            add("invalid_topic", "A question must have exactly one topic")
        if data["primary_skill_count"] != 1:
            add("invalid_primary_skill", "A question must have exactly one primary skill")
        if data["duplicate_stem"]:
            add("duplicate_stem", "The stem duplicates another question")
        elif any(
            AdminService._stem_similarity(data["stem"], other) >= 0.85
            for other in data.get("other_stems") or []
        ):
            add("near_duplicate_stem", "The stem is too similar to another question")
        if float(data["irt_a"]) <= 0 or not -4 <= float(data["irt_b"]) <= 4 or not 0 <= float(data["irt_c"]) <= 0.5:
            add("invalid_irt_parameters", "IRT parameters are outside the valid domain")
        norm = float(data["difficulty_norm"])
        label = data["difficulty_label"]
        if (label == "easy" and norm > 0.4) or (label == "medium" and not 0.3 <= norm <= 0.75) or (label == "hard" and norm < 0.65):
            add("difficulty_mismatch", "The difficulty label does not match difficulty_norm")
        if data["bloom_level"] == "remember" and label == "hard":
            add("bloom_difficulty_warning", "A remember-level item is labeled hard", "warning")
        if data["bloom_level"] == "evaluate" and label == "easy":
            add("bloom_difficulty_warning", "An evaluate-level item is labeled easy", "warning")
        return issues

    @staticmethod
    def _stem_similarity(left: str, right: str) -> float:
        def tokens(value: str) -> set[str]:
            normalized = unicodedata.normalize("NFKC", value).lower()
            return set(re.sub(r"[^\w]+", " ", normalized).split())

        left_tokens = tokens(left)
        right_tokens = tokens(right)
        union = left_tokens | right_tokens
        return len(left_tokens & right_tokens) / len(union) if union else 0.0

    def __init__(
        self,
        repository: AdminRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._repository = repository
        self._session_factory = session_factory

    async def overview(self) -> SystemOverview:
        async with self._session_factory() as session:
            row = await self._repository.system_overview(session)
        return SystemOverview(**row)

    async def question_bank(self) -> QuestionBankResponse:
        async with self._session_factory() as session:
            subjects = await self._repository.question_bank_subjects(session)
            questions = await self._repository.questions(session)
        return QuestionBankResponse(
            total_questions=sum(row["total_questions"] for row in subjects),
            subjects=subjects,
            questions=questions,
        )

    async def accounts(self) -> list[AccountItem]:
        async with self._session_factory() as session:
            rows = await self._repository.accounts(session)
        return [AccountItem(**row) for row in rows]

    async def create_account(self, request: AccountCreateRequest) -> AccountItem:
        username = request.username.strip().lower()
        student_code = (
            request.student_code.strip().upper() if request.student_code else None
        )
        async with self._session_factory() as session:
            if await self._repository.account_exists(session, username):
                raise AccountConflictError("The username already exists")
            student_id = None
            if student_code:
                student_id = await self._repository.ensure_student(
                    session,
                    student_code,
                    request.display_name.strip(),
                )
            try:
                row = await self._repository.create_account(
                    session,
                    username=username,
                    password_hash=hash_password(request.password),
                    display_name=request.display_name.strip(),
                    role=request.role,
                    student_id=student_id,
                )
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise AccountConflictError(
                    "The student code is already linked to another account"
                ) from error
        return AccountItem(**row, student_code=student_code)

    async def update_account(
        self,
        username: str,
        request: AccountUpdateRequest,
        actor: str,
    ) -> AccountItem:
        normalized = username.strip().lower()
        if normalized == actor and request.is_active is False:
            raise AdminError("You cannot deactivate the account currently signed in")
        async with self._session_factory() as session:
            row = await self._repository.update_account(
                session,
                username=normalized,
                display_name=(
                    request.display_name.strip() if request.display_name else None
                ),
                password_hash=(
                    hash_password(request.password) if request.password else None
                ),
                is_active=request.is_active,
            )
            if row is None:
                raise AccountNotFoundError("Account not found")
            if request.display_name and row["student_id"] is not None:
                await self._repository.update_student_name(
                    session,
                    row["student_id"],
                    request.display_name.strip(),
                )
            student_code = await self._repository.student_code(
                session,
                row["student_id"],
            )
            await session.commit()
        return AccountItem(**row, student_code=student_code)

    async def config_items(self) -> list[ConfigItem]:
        return await self._config_service().list_items()

    async def update_config(
        self,
        updates: list[tuple[str, object]],
        actor: str,
    ) -> list[ConfigItem]:
        return await self._config_service().update_items(updates, actor)

    def _config_service(self) -> SystemConfigService:
        return SystemConfigService(SystemConfigRepository(), self._session_factory)
