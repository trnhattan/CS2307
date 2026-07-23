from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    message: str


class BundleValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        super().__init__("Question bundle validation failed")
        self.issues = issues


class ImportFileError(ValueError):
    pass


class DatabaseUnavailableError(RuntimeError):
    pass


class DatabaseContractError(ValueError):
    pass
