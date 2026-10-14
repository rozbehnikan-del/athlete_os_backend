import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete, func, select, update

from app.core.asyncio_compat import configure_event_loop_policy

configure_event_loop_policy()

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.workout import Workout
from app.models.workout_result import SetResult, WorkoutResult

DEMO_ATHLETE_ID = UUID("22222222-2222-4222-8222-222222222222")
DEMO_WORKOUT_ID = UUID("77777777-7777-4777-8777-777777777777")
EXPECTED_DATABASE_NAME = "athlete_os"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset only the seeded AthleteOS demo workout.")
    parser.add_argument("--confirm-demo-reset", action="store_true")
    return parser.parse_args()


async def reset_demo_workout() -> int:
    settings = get_settings()
    if settings.database_name != EXPECTED_DATABASE_NAME:
        print(f"Refusing to reset demo data for database '{settings.database_name}'.")
        print(f"Expected database: {EXPECTED_DATABASE_NAME}")
        return 1

    scheduled_for = date.today()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            workout_result_id = await session.scalar(
                select(WorkoutResult.id).where(
                    WorkoutResult.workout_id == DEMO_WORKOUT_ID,
                    WorkoutResult.athlete_id == DEMO_ATHLETE_ID,
                )
            )
            if workout_result_id is not None:
                await session.execute(delete(SetResult).where(SetResult.workout_result_id == workout_result_id))
                await session.execute(delete(WorkoutResult).where(WorkoutResult.id == workout_result_id))

            await session.execute(
                update(Workout)
                .where(
                    Workout.id == DEMO_WORKOUT_ID,
                    Workout.athlete_id == DEMO_ATHLETE_ID,
                )
                .values(
                    scheduled_for=scheduled_for,
                    status="active",
                    updated_at=func.now(),
                )
            )

    print("Demo workout reset: OK")
    print(f"Workout: {DEMO_WORKOUT_ID}")
    print(f"Athlete: {DEMO_ATHLETE_ID}")
    print(f"Scheduled for: {scheduled_for.isoformat()}")
    print("Status: active")
    return 0


def main() -> int:
    args = parse_args()
    if not args.confirm_demo_reset:
        print("Refusing to reset demo data without --confirm-demo-reset")
        return 1
    return asyncio.run(reset_demo_workout())


if __name__ == "__main__":
    raise SystemExit(main())
