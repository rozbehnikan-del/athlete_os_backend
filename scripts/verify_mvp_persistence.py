"""Read-only verification of a workout produced by Flutter's opt-in MVP test."""
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.repositories.workout_repository import WorkoutRepository
from app.services.workout_service import WorkoutService
from app.core.completion_grade import completion_grade
from sqlalchemy import text

async def verify(workout_id: UUID):
    settings = get_settings()
    assert settings.environment == 'local' and settings.database_name == 'athlete_os'
    athlete_id = UUID('22222222-2222-4222-8222-222222222222')
    coach_id = UUID('11111111-1111-4111-8111-111111111111')
    async with AsyncSessionLocal() as session:
        assert await session.scalar(text('select current_database()')) == 'athlete_os'
        repository = WorkoutRepository(session)
        workout = await repository.get_workout_detail(workout_id)
        assert workout and workout.athlete_id == athlete_id and workout.coach_id == coach_id
        assert workout.title.startswith('MVP Flutter E2E ')
        assert workout.status == 'completed'
        rows = (await session.execute(text('''select sr.actual_reps, sr.actual_weight, sr.rpe, sr.completed
            from set_results sr join workout_results wr on wr.id=sr.workout_result_id
            where wr.workout_id=:id and wr.athlete_id=:athlete'''),
            {'id': workout_id, 'athlete': athlete_id})).all()
        assert len(rows) == 1 and rows[0].actual_reps == 6 and float(rows[0].actual_weight) == 2.5
        assert float(rows[0].rpe) == 7 and rows[0].completed
        total_sets = sum(len(e.workout_sets) for e in workout.workout_exercises)
        assert total_sets == 2 and completion_grade(1, total_sets) == (50.0, 'C')
        print(f'PostgreSQL workout={workout_id}: completed; sets=1/2; reps=6; weight=2.5; RPE=7; grade=C (50%). PASS')
    await engine.dispose()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workout_id', type=UUID)
    asyncio.run(verify(parser.parse_args().workout_id))
