from typing import Literal

from pydantic import BaseModel, Field


class ImportIssue(BaseModel):
    path: str
    message: str


class ImportLineResult(BaseModel):
    line: int
    question_code: str | None = None
    status: Literal["created", "updated", "validated", "error"]
    errors: list[ImportIssue] = Field(default_factory=list)


class QuestionImportResponse(BaseModel):
    filename: str
    dry_run: bool
    processed_lines: int
    succeeded: int
    failed: int
    results: list[ImportLineResult]
