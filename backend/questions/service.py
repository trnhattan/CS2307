import json
from typing import Any

from fastapi import UploadFile
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.core.config import Settings
from backend.questions.errors import (
    BundleValidationError,
    DatabaseContractError,
    DatabaseUnavailableError,
    ImportFileError,
)
from backend.questions.repository import QuestionBundleRepository
from backend.questions.schemas import ImportIssue, ImportLineResult, QuestionImportResponse
from backend.questions.validator import QuestionBundleValidator


class QuestionImportService:
    def __init__(
        self,
        settings: Settings,
        validator: QuestionBundleValidator,
        repository: QuestionBundleRepository,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._validator = validator
        self._repository = repository
        self._session_factory = session_factory

    async def import_jsonl(
        self,
        upload: UploadFile,
        *,
        dry_run: bool,
    ) -> QuestionImportResponse:
        filename = upload.filename or "upload.jsonl"
        if not filename.lower().endswith(".jsonl"):
            raise ImportFileError("Only .jsonl files are accepted")

        content = await upload.read(self._settings.max_upload_bytes + 1)
        if len(content) > self._settings.max_upload_bytes:
            raise ImportFileError(
                f"File exceeds the {self._settings.max_upload_bytes}-byte limit"
            )
        if not content:
            raise ImportFileError("The uploaded file is empty")

        lines = content.splitlines()
        if len(lines) > self._settings.max_import_lines:
            raise ImportFileError(
                f"File exceeds the {self._settings.max_import_lines}-line limit"
            )
        oversized_line = next(
            (
                index
                for index, line in enumerate(lines, start=1)
                if len(line) > self._settings.max_line_bytes
            ),
            None,
        )
        if oversized_line is not None:
            raise ImportFileError(
                f"Line {oversized_line} exceeds the "
                f"{self._settings.max_line_bytes}-byte limit"
            )

        results: list[ImportLineResult] = []
        for line_number, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                continue
            result = await self._process_line(
                line_number,
                raw_line,
                dry_run=dry_run,
            )
            results.append(result)

        if not results:
            raise ImportFileError("The uploaded file contains no JSON records")

        succeeded = sum(result.status != "error" for result in results)
        return QuestionImportResponse(
            filename=filename,
            dry_run=dry_run,
            processed_lines=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            results=results,
        )

    async def _process_line(
        self,
        line_number: int,
        raw_line: bytes,
        *,
        dry_run: bool,
    ) -> ImportLineResult:
        try:
            bundle: Any = json.loads(raw_line.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            return self._error_result(line_number, "$", str(error))

        question_code = self._question_code(bundle)
        try:
            self._validator.validate(bundle)
        except BundleValidationError as error:
            return ImportLineResult(
                line=line_number,
                question_code=question_code,
                status="error",
                errors=[
                    ImportIssue(path=issue.path, message=issue.message)
                    for issue in error.issues
                ],
            )

        if dry_run:
            return ImportLineResult(
                line=line_number,
                question_code=question_code,
                status="validated",
            )

        async with self._session_factory() as session:
            try:
                operation = await self._repository.upsert_bundle(session, bundle)
                await session.commit()
            except OperationalError as error:
                await session.rollback()
                raise DatabaseUnavailableError("PostgreSQL is unavailable") from error
            except DatabaseContractError as error:
                await session.rollback()
                return self._error_result(line_number, "$", str(error), question_code)
            except SQLAlchemyError as error:
                await session.rollback()
                detail = str(getattr(error, "orig", error)).splitlines()[0]
                return self._error_result(line_number, "$", detail, question_code)

        return ImportLineResult(
            line=line_number,
            question_code=question_code,
            status=operation,
        )

    @staticmethod
    def _question_code(bundle: Any) -> str | None:
        if not isinstance(bundle, dict) or not isinstance(bundle.get("question"), dict):
            return None
        value = bundle["question"].get("question_code")
        return value if isinstance(value, str) else None

    @staticmethod
    def _error_result(
        line: int,
        path: str,
        message: str,
        question_code: str | None = None,
    ) -> ImportLineResult:
        return ImportLineResult(
            line=line,
            question_code=question_code,
            status="error",
            errors=[ImportIssue(path=path, message=message)],
        )
