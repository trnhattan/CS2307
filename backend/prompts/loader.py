from functools import lru_cache
from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parent / "templates"


@lru_cache
def load_prompt(name: str) -> str:
    if not name or Path(name).name != name:
        raise ValueError("Prompt name must be a plain file name")
    path = PROMPT_ROOT / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template '{name}' was not found")
    return path.read_text(encoding="utf-8").strip()
