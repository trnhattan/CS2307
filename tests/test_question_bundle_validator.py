import copy
import json
from pathlib import Path

import pytest

from backend.questions.errors import BundleValidationError
from backend.questions.validator import QuestionBundleValidator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "scripts" / "adaptive_exam_question_bundle.schema.json"
SAMPLE_PATH = ROOT / "data" / "database_bloom_5_questions.jsonl"


@pytest.fixture(scope="module")
def validator() -> QuestionBundleValidator:
    return QuestionBundleValidator(SCHEMA_PATH)


@pytest.fixture(scope="module")
def bundles() -> list[dict]:
    return [json.loads(line) for line in SAMPLE_PATH.read_text().splitlines()]


def test_all_sample_bundles_are_valid(validator, bundles) -> None:
    for bundle in bundles:
        validator.validate(bundle)


def test_rejects_duplicate_skill_codes(validator, bundles) -> None:
    bundle = copy.deepcopy(bundles[0])
    duplicate = copy.deepcopy(bundle["skills"][0])
    duplicate["is_primary"] = False
    bundle["skills"].append(duplicate)

    with pytest.raises(BundleValidationError) as captured:
        validator.validate(bundle)

    assert any("duplicate skill_code" in issue.message for issue in captured.value.issues)


def test_rejects_bloom_fact_mismatch(validator, bundles) -> None:
    bundle = copy.deepcopy(bundles[0])
    bundle["kb_facts"][1]["object_value"] = "evaluate"

    with pytest.raises(BundleValidationError) as captured:
        validator.validate(bundle)

    assert any("bloom.bloom_code" in issue.message for issue in captured.value.issues)
