import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import update

from app.core.asyncio_compat import configure_event_loop_policy

configure_event_loop_policy()

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User

DEMO_ATHLETE_ID = UUID("22222222-2222-4222-8222-222222222222")
DEMO_COACH_ID = UUID("11111111-1111-4111-8111-111111111111")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set local passwords for seeded AthleteOS demo users.")
    parser.add_argument("--confirm-demo-passwords", action="store_true")
    return parser.parse_args()


def _read_passwords() -> tuple[str, str]:
    settings = get_settings()
    athlete_password = settings.demo_athlete_password
    coach_password = settings.demo_coach_password
    if not athlete_password or not coach_password:
        print("DEMO_ATHLETE_PASSWORD and DEMO_COACH_PASSWORD must be set.")
        raise SystemExit(1)
    return athlete_password, coach_password


async def set_demo_passwords() -> int:
    athlete_password, coach_password = _read_passwords()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(
                update(User)
                .where(User.id == DEMO_ATHLETE_ID)
                .values(password_hash=hash_password(athlete_password))
            )
            await session.execute(
                update(User)
                .where(User.id == DEMO_COACH_ID)
                .values(password_hash=hash_password(coach_password))
            )

    print("Demo passwords set: OK")
    print(f"Athlete: {DEMO_ATHLETE_ID}")
    print(f"Coach: {DEMO_COACH_ID}")
    return 0


def main() -> int:
    args = parse_args()
    if not args.confirm_demo_passwords:
        print("Refusing to set demo passwords without --confirm-demo-passwords")
        return 1
    return asyncio.run(set_demo_passwords())


if __name__ == "__main__":
    raise SystemExit(main())
