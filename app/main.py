from sqlalchemy import text

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.v1.router import router as v1_router
from app.core.database import engine


app = FastAPI(title="AthleteOS Backend", version="0.1.0")
register_error_handlers(app)
app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        pass
    return {"status": "ok"}
