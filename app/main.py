import logging

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.api.errors import register_error_handlers
from app.api.v1.router import router as v1_router
from app.core.asyncio_compat import configure_event_loop_policy

configure_event_loop_policy()

from app.core.database import engine

logger = logging.getLogger(__name__)

app = FastAPI(title="AthleteOS Backend", version="0.1.0")
register_error_handlers(app)
app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", response_model=None)
async def ready() -> Response:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database readiness check failed.")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "unavailable"},
        )
    return JSONResponse(content={"status": "ready", "database": "ok"})
