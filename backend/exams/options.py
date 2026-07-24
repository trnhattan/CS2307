import random
from typing import Any

from backend.exams.errors import ExamError


def prepare_display_options(
    options: list[dict[str, Any]],
    display_count: int,
    *,
    seed: int,
    randomize: bool,
) -> list[dict[str, Any]]:
    best = [option for option in options if option["is_best_answer"]]
    distractors = [option for option in options if not option["is_best_answer"]]
    if len(best) != 1 or len(options) < display_count:
        raise ExamError("Question has an invalid active answer pool")
    rng = random.Random(seed)
    chosen = best + rng.sample(distractors, display_count - 1)
    if randomize:
        rng.shuffle(chosen)
    return [
        {
            "option_code": option["option_code"],
            "option_text": option["option_text"],
            "score_weight": float(option["score_weight"]),
            "is_best_answer": option["is_best_answer"],
            "distractor_type": option["distractor_type"],
            "explanation": option["explanation"],
            "diagnosis": option["diagnosis"],
            "display_order": index,
        }
        for index, option in enumerate(chosen, start=1)
    ]
