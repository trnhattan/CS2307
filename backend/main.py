# python -m uvicorn backend.main:app --host 0.0.0.0 --port 8081 --reload
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.api.router import api_router
from backend.core.config import get_settings
from backend.db.session import async_session_factory, engine
from backend.learner_mcp.server import learner_mcp_app


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with learner_mcp_app.lifespan():
        yield
    await engine.dispose()


app = FastAPI(
    title=get_settings().app_name,
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL is unavailable",
        ) from error
    return {"status": "ready"}


app.mount("/", learner_mcp_app)
