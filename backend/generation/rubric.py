from backend.generation.schemas import InitialIRT


BLOOM_OFFSET = {
    "remember": -0.08,
    "understand": -0.04,
    "apply": 0.0,
    "analyze": 0.06,
    "evaluate": 0.10,
}

BASE_DIFFICULTY = {"easy": 0.28, "medium": 0.55, "hard": 0.80}
BASE_TIME = {
    "remember": 45,
    "understand": 60,
    "apply": 90,
    "analyze": 120,
    "evaluate": 150,
}
TIME_FACTOR = {"easy": 0.9, "medium": 1.0, "hard": 1.15}


def initial_irt(
    bloom_level: str,
    difficulty_label: str,
    option_count: int,
) -> InitialIRT:
    norm = min(
        0.95,
        max(0.05, BASE_DIFFICULTY[difficulty_label] + BLOOM_OFFSET[bloom_level]),
    )
    rank = list(BLOOM_OFFSET).index(bloom_level)
    discrimination = min(1.8, 0.95 + rank * 0.12)
    guessing = min(0.25, max(0.08, 1 / option_count))
    return InitialIRT(
        a=round(discrimination, 5),
        b=round(norm * 6 - 3, 5),
        c=round(guessing, 5),
        difficulty_norm=round(norm, 5),
        avg_time_sec=round(BASE_TIME[bloom_level] * TIME_FACTOR[difficulty_label]),
        rubric_version="deterministic-initial-irt-v1",
    )
