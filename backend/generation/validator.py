import re
import unicodedata

from backend.generation.schemas import (
    GeneratedQuestionPayload,
    GenerationValidationIssue,
    QuestionGenerationRequest,
)


def validate_generated_question(
    generated: GeneratedQuestionPayload,
    request: QuestionGenerationRequest,
    *,
    expected_option_count: int,
    existing_stems: list[str],
) -> list[GenerationValidationIssue]:
    issues: list[GenerationValidationIssue] = []

    def add(code: str, message: str, severity: str = "blocking") -> None:
        issues.append(
            GenerationValidationIssue(code=code, message=message, severity=severity)
        )

    if len(generated.options) != expected_option_count:
        add(
            "answer_pool_size",
            f"This Bloom level requires {expected_option_count} options; received {len(generated.options)}.",
        )
    option_texts = [_normalize(option.text) for option in generated.options]
    if len(option_texts) != len(set(option_texts)):
        add("duplicate_options", "Answer options must be distinct.")
    normalized_stem = _normalize(generated.stem)
    if any(normalized_stem == _normalize(stem) for stem in existing_stems):
        add("duplicate_stem", "The stem exactly duplicates an existing question.")
    elif any(_jaccard(normalized_stem, _normalize(stem)) >= 0.85 for stem in existing_stems):
        add("near_duplicate_stem", "The stem is too similar to an existing question.")
    if len(generated.explanation.strip()) < 30:
        add("short_explanation", "The explanation is too short for review.")
    if not request.source_context:
        add(
            "missing_source_context",
            "No source excerpt was supplied; the reviewer must verify the content independently.",
            "warning",
        )
    return issues


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[^\w]+", " ", value).strip()


def _jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 0.0
