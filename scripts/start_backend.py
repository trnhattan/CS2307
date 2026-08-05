import asyncio

import uvicorn

from backend.core.config import get_settings
from backend.db.migrations import apply_migrations


def main() -> None:
    settings = get_settings()
    asyncio.run(apply_migrations())
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
    )


if __name__ == "__main__":
    main()
