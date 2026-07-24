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
            f"Cần {expected_option_count} phương án cho mức Bloom này, nhận được {len(generated.options)}.",
        )
    option_texts = [_normalize(option.text) for option in generated.options]
    if len(option_texts) != len(set(option_texts)):
        add("duplicate_options", "Các phương án trả lời phải khác nhau.")
    normalized_stem = _normalize(generated.stem)
    if any(normalized_stem == _normalize(stem) for stem in existing_stems):
        add("duplicate_stem", "Nội dung câu hỏi trùng hoàn toàn với ngân hàng hiện có.")
    elif any(_jaccard(normalized_stem, _normalize(stem)) >= 0.85 for stem in existing_stems):
        add("near_duplicate_stem", "Nội dung câu hỏi quá giống một câu hiện có.")
    if len(generated.explanation.strip()) < 30:
        add("short_explanation", "Giải thích quá ngắn để phục vụ review.")
    if not request.source_context:
        add(
            "missing_source_context",
            "Không có đoạn nguồn; reviewer cần kiểm chứng nội dung bằng nguồn ngoài.",
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
