import subprocess
import sys
from datetime import UTC, datetime, date
from unittest.mock import AsyncMock
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy.dialects import postgresql
from app.core.scheduling import scheduling_date
from app.repositories.coach_repository import CoachRepository
from app.services.workout_service import WorkoutService


def test_model_registry_is_complete_in_clean_process():
    subprocess.run([sys.executable,'-c', '''from app import models
from app.core.database import Base
expected = {'users','athlete_profiles','coach_profiles','coach_athletes','exercises','workouts','workout_exercises','workout_sets','workout_results','set_results','training_sessions','training_blocks','wods','wod_results'}
assert expected == set(Base.metadata.tables)
assert models.CoachAthlete.__tablename__ == 'coach_athletes'
assert models.TrainingSession.__tablename__ == 'training_sessions'
assert models.TrainingBlock.__tablename__ == 'training_blocks'
assert models.Wod.__tablename__ == 'wods'
assert models.WodResult.__tablename__ == 'wod_results'
'''],check=True)

@pytest.mark.parametrize('instant,zone,expected',[
    ('2026-10-19T20:29:59+00:00','Asia/Tehran',date(2026,10,19)),
    ('2026-10-19T20:30:00+00:00','Asia/Tehran',date(2026,10,20)),
    ('2026-10-20T03:59:59+00:00','America/New_York',date(2026,10,19)),
    ('2026-10-20T04:00:00+00:00','America/New_York',date(2026,10,20)),
    ('2026-03-08T06:59:59+00:00','America/New_York',date(2026,3,8)),
    ('2026-03-08T07:00:00+00:00','America/New_York',date(2026,3,8)),
])
def test_scheduling_midnight_boundaries(instant,zone,expected):
    assert scheduling_date(datetime.fromisoformat(instant),timezone=zone)==expected

def test_scheduling_rejects_naive_instant():
    with pytest.raises(ValueError,match='aware'):
        scheduling_date(datetime(2026,10,20))

@pytest.mark.asyncio
async def test_coach_lookup_only_locks_on_request():
    statements=[]
    async def execute(statement):
        statements.append(str(statement.compile(dialect=postgresql.dialect())))
        return SimpleNamespace(all=lambda:[])
    repo=CoachRepository(SimpleNamespace(execute=execute))
    await repo.athletes(uuid4(),uuid4())
    await repo.athletes(uuid4(),uuid4(),for_update=True)
    assert 'FOR UPDATE' not in statements[0]
    assert 'FOR UPDATE OF coach_athletes' in statements[1]

@pytest.mark.asyncio
async def test_progress_summary_uses_aggregates_and_bounded_activity():
    repo=SimpleNamespace(progress_totals=AsyncMock(return_value=(200,1000,2000)),get_history=AsyncMock(return_value=[]))
    athlete=uuid4()
    summary=await WorkoutService(repo).get_progress_summary(athlete)
    assert summary.total_completed_workouts==200
    assert summary.completion_percentage==50
    assert summary.completion_grade=='C'
    repo.get_history.assert_awaited_once_with(athlete,1,10)
