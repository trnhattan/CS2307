from scripts.seed_english_question_bank import build_bank


def test_operational_source_bank_contains_200_complete_english_questions() -> None:
    bank = build_bank()

    assert len(bank) == 200
    assert sum(item["subject_code"] == "DATABASE" for item in bank) == 100
    assert sum(item["subject_code"] == "NETWORK" for item in bank) == 100
    assert len({item["question_code"] for item in bank}) == 200
    assert all(len(item["stem"].split()) >= 8 for item in bank)
    assert all(len(item["explanation"].split()) >= 8 for item in bank)
    assert all(sum(option[1] for option in item["options"]) == 1 for item in bank)
