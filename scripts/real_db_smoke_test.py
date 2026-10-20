import asyncio
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from psycopg import Error as PsycopgError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.asyncio_compat import configure_event_loop_policy

configure_event_loop_policy()

from app.core.scheduling import scheduling_date
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.repositories.workout_repository import WorkoutRepository
from app.services.workout_service import WorkoutService


def _iter_exception_details(exc: BaseException) -> list[BaseException]:
    details: list[BaseException] = []
    seen: set[int] = set()
    stack: list[BaseException | None] = [exc]

    while stack:
        current = stack.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        details.append(current)

        orig = getattr(current, "orig", None)
        if isinstance(orig, BaseException):
            stack.append(orig)
        stack.append(current.__cause__)
        stack.append(current.__context__)

    return details


def _redact_secret_text(text: str, password: str) -> str:
    redacted = text
    if password:
        redacted = redacted.replace(password, "<redacted>")
    redacted = re.sub(r"://([^:/@\s]+):([^@\s]+)@", r"://\1:<redacted>@", redacted)
    redacted = re.sub(r"(?i)(password\s*[=:]\s*)\S+", r"\1<redacted>", redacted)
    return redacted


def _safe_exception_summary(exc: BaseException, password: str) -> str:
    messages: list[str] = []
    for detail in _iter_exception_details(exc):
        message = str(detail).strip()
        if message:
            messages.append(f"{detail.__class__.__name__}: {message}")

    if not messages:
        messages.append(exc.__class__.__name__)

    return _redact_secret_text(" | ".join(dict.fromkeys(messages)), password)


def _categorize_connection_failure(exc: BaseException) -> str:
    text = " ".join(
        f"{detail.__class__.__name__} {str(detail)}".lower()
        for detail in _iter_exception_details(exc)
    )

    if "password authentication failed" in text or "authentication failed" in text:
        return "authentication_failed"
    if "sslmode" in text and ("require" in text or "required" in text):
        return "ssl_required"
    if "ssl" in text and any(term in text for term in ("rejected", "not supported", "does not support")):
        return "ssl_rejected"
    if "connection refused" in text or "actively refused" in text:
        return "connection_refused"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    return "unknown"


async def main() -> int:
    settings = get_settings()

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            database_name = await connection.scalar(text("SELECT current_database()"))
    except (SQLAlchemyError, PsycopgError) as exc:
        print("Database connection: FAILED")
        print(f"Exception: {exc.__class__.__name__}")
        print(f"Cause: {_safe_exception_summary(exc, settings.database_password)}")
        print(f"Likely cause: {_categorize_connection_failure(exc)}")
        print(f"Host: {settings.database_host}")
        print(f"Port: {settings.database_port}")
        print(f"Database: {settings.database_name}")
        print(f"User: {settings.database_user}")
        return 1

    if database_name != settings.database_name:
        print(f"Database connection: OK")
        print(f"Database: {database_name}")
        print(f"Expected database: {settings.database_name}")
        return 1

    async with AsyncSessionLocal() as session:
        repository = WorkoutRepository(session)
        service = WorkoutService(repository)
        workout = await service.get_today_workout(settings.demo_athlete_id)

    if workout is None:
        print("Database connection: OK")
        print(f"Database: {database_name}")
        print(f"Athlete: {settings.demo_athlete_id}")
        print(f"No planned/active workout found for today ({scheduling_date().isoformat()}).")
        return 1

    total_sets = sum(len(exercise.sets) for exercise in workout.exercises)
    print("Database connection: OK")
    print(f"Database: {database_name}")
    print(f"Athlete: {settings.demo_athlete_id}")
    print(f"Workout: {workout.title}")
    print(f"Category: {workout.category}")
    print(f"Focus: {workout.focus}")
    print(f"Exercises: {len(workout.exercises)}")
    print(f"Sets: {total_sets}")
    print("")
    print("Exercises:")
    for index, exercise in enumerate(workout.exercises, start=1):
        print(f"{index}. {exercise.exercise.name} - {len(exercise.sets)} sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
