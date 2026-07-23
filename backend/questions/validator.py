import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from backend.core.config import get_settings
from backend.questions.errors import BundleValidationError, ValidationIssue


class QuestionBundleValidator:
    def __init__(self, schema_path: Path) -> None:
        with schema_path.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file)
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    def validate(self, bundle: dict[str, Any]) -> None:
        issues = [
            ValidationIssue(path=error.json_path, message=error.message)
            for error in sorted(
                self._validator.iter_errors(bundle),
                key=lambda item: (
                    tuple(str(part) for part in item.absolute_path),
                    item.message,
                ),
            )
        ]
        issues.extend(self._semantic_issues(bundle))
        if issues:
            raise BundleValidationError(issues)

    def _semantic_issues(self, bundle: dict[str, Any]) -> list[ValidationIssue]:
        if not isinstance(bundle, dict):
            return []

        issues: list[ValidationIssue] = []
        question = bundle.get("question")
        bloom = bundle.get("bloom")
        options = bundle.get("answer_options")
        skills = bundle.get("skills")
        facts = bundle.get("kb_facts")
        topic = bundle.get("topic")

        if isinstance(options, list):
            issues.extend(self._unique_code_issues(options, "option_code", "$.answer_options"))
        if isinstance(skills, list):
            issues.extend(self._unique_code_issues(skills, "skill_code", "$.skills"))
        if isinstance(facts, list):
            issues.extend(self._fact_issues(facts, question, bloom))

        if isinstance(question, dict) and isinstance(options, list):
            expected = question.get("answer_pool_size")
            active_count = sum(
                1
                for option in options
                if isinstance(option, dict) and option.get("is_active", True)
            )
            if isinstance(expected, int) and active_count != expected:
                issues.append(
                    ValidationIssue(
                        path="$.question.answer_pool_size",
                        message=f"must equal the active answer option count ({active_count})",
                    )
                )

        if isinstance(topic, dict):
            if topic.get("parent_topic_code") == topic.get("topic_code"):
                issues.append(
                    ValidationIssue(
                        path="$.topic.parent_topic_code",
                        message="must differ from topic_code",
                    )
                )
        return issues

    @staticmethod
    def _unique_code_issues(
        values: list[Any],
        field: str,
        path: str,
    ) -> list[ValidationIssue]:
        seen: set[str] = set()
        duplicate_codes: set[str] = set()
        for value in values:
            if not isinstance(value, dict) or not isinstance(value.get(field), str):
                continue
            code = value[field]
            if code in seen:
                duplicate_codes.add(code)
            seen.add(code)
        return [
            ValidationIssue(path=path, message=f"duplicate {field}: {code}")
            for code in sorted(duplicate_codes)
        ]

    @staticmethod
    def _fact_issues(
        facts: list[Any],
        question: Any,
        bloom: Any,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        question_code = question.get("question_code") if isinstance(question, dict) else None
        bloom_code = bloom.get("bloom_code") if isinstance(bloom, dict) else None

        for index, fact in enumerate(facts):
            if not isinstance(fact, dict):
                continue
            key = (
                str(fact.get("fact_type", "")),
                str(fact.get("subject_ref", "")),
                str(fact.get("relation_code") or fact.get("predicate", "")),
                str(fact.get("object_ref", "")),
                json.dumps(fact.get("object_value"), sort_keys=True, ensure_ascii=False),
            )
            if key in seen:
                issues.append(
                    ValidationIssue(
                        path=f"$.kb_facts[{index}]",
                        message="duplicates an earlier canonical fact",
                    )
                )
            seen.add(key)

            if fact.get("predicate") in {"is_a", "has_bloom_level"}:
                if question_code and fact.get("subject_ref") != question_code:
                    issues.append(
                        ValidationIssue(
                            path=f"$.kb_facts[{index}].subject_ref",
                            message="must match question.question_code for a core fact",
                        )
                    )
            if fact.get("predicate") == "has_bloom_level":
                if bloom_code and fact.get("object_value") != bloom_code:
                    issues.append(
                        ValidationIssue(
                            path=f"$.kb_facts[{index}].object_value",
                            message="must match bloom.bloom_code",
                        )
                    )
        return issues

@lru_cache
def get_question_bundle_validator() -> QuestionBundleValidator:
    return QuestionBundleValidator(get_settings().question_bundle_schema_path)
