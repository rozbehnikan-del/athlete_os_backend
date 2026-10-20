"""Isolated PostgreSQL integration coverage. Opt in with RUN_POSTGRES_INTEGRATION=1.

Creates only UUID-named databases owned by this run. Never migrates the configured
application database. Cleanup drops only databases successfully created here.
"""
import asyncio
from contextlib import contextmanager
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.scheduling import scheduling_date
from app.api.errors import ApiError
from app.models import User, Exercise, CoachAthlete, WorkoutResult, SetResult
from app.repositories.coach_repository import CoachRepository
from app.repositories.workout_repository import WorkoutRepository
from app.services.coach_service import CoachService
from app.services.workout_service import WorkoutService
from app.schemas.coach import WorkoutCreate
from app.schemas.workout_result import WorkoutResultCreate

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_INTEGRATION') != '1', reason='Requires opt-in disposable PostgreSQL databases')
ROOT = Path(__file__).resolve().parents[1]


def migrate(database, revision='head', stamp=False):
    with patch.dict(os.environ, {'DATABASE_NAME': database}):
        get_settings.cache_clear()
        config = Config(str(ROOT / 'alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'alembic'))
        try:
            (command.stamp if stamp else command.upgrade)(config, revision)
        finally:
            get_settings.cache_clear()


@contextmanager
def disposable_database(revision='head'):
    url = get_settings().database_url
    admin = create_engine(url, isolation_level='AUTOCOMMIT', poolclass=NullPool, connect_args={'connect_timeout': 10})
    name = 'athleteos_test_' + uuid4().hex
    created = False
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
            print('Created disposable database:', name)
        migrate(name, revision)
        yield name, url.set(database=name)
    finally:
        if created:
            assert name.startswith('athleteos_test_') and len(name) == len('athleteos_test_') + 32
            with admin.connect() as c:
                assert c.execute(text('select current_database()')).scalar() != name
                c.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


@pytest.fixture(scope='module')
def database():
    with disposable_database() as database:
        yield database


async def seed(url, *, sets=2):
    engine = create_async_engine(url, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    coach, athlete, exercise = uuid4(), uuid4(), uuid4()
    async with sessions() as session:
        session.add_all([User(id=coach, full_name='Test Coach', role='coach', is_active=True, created_at=now, updated_at=now),
                         User(id=athlete, full_name='Test Athlete', role='athlete', is_active=True, created_at=now, updated_at=now),
                         Exercise(id=exercise, slug=str(exercise), name='Integration exercise', is_active=True, created_at=now, updated_at=now)])
        await session.flush()
        session.add(CoachAthlete(id=uuid4(), coach_id=coach, athlete_id=athlete, status='active', started_at=now))
        await session.commit()
    payload = WorkoutCreate.model_validate({'title':'Isolated integration workout','scheduled_for':scheduling_date(),
        'exercises':[{'exercise_id':exercise,'order':1,'sets':[
            {'set_number':i,'target_reps':5,'target_weight':0,'weight_unit':'kg'} for i in range(1, sets+1)]}]})
    async with sessions() as session:
        workout = await CoachService(CoachRepository(session)).create(coach, athlete, payload)
    return engine, sessions, coach, athlete, payload, workout


def test_fresh_bootstrap_tables_and_constraints(database):
    _, url = database
    engine = create_engine(url)
    try:
        i = inspect(engine)
        from app.core.database import Base
        assert set(Base.metadata.tables).issubset(i.get_table_names())
        assert 'password_hash' in {c['name'] for c in i.get_columns('users')}
        constraints = i.get_unique_constraints('workout_results')
        assert len([c for c in constraints if set(c['column_names']) == {'workout_id','athlete_id'}]) == 1
        assert any(c['name'] == 'uq_workout_results_workout_athlete' for c in constraints)
        assert any(i['name']=='uq_workouts_athlete_scheduled_open' and i['unique'] for i in i.get_indexes('workouts'))
    finally:
        engine.dispose()


def test_concurrent_results_and_rollback(database):
    async def run():
        engine,sessions,coach,athlete,payload,workout=await seed(database[1])
        barrier=asyncio.Barrier(2)
        class RacingRepository(WorkoutRepository):
            async def result_exists(self, workout_id, athlete_id):
                exists=await super().result_exists(workout_id,athlete_id)
                await barrier.wait()
                return exists
        result=WorkoutResultCreate.model_validate({'completed_at':datetime.now(UTC), 'sets':[
            {'set_id':workout.exercises[0].sets[0].id,'actual_reps':6,'actual_weight':2.5,'weight_unit':'kg','rpe':7,'completed':True}]})
        async def submit():
            async with sessions() as session:
                try:
                    await WorkoutService(RacingRepository(session)).submit_result(workout.id,athlete,result)
                    return 'success'
                except ApiError as e:
                    assert e.status_code==409 and e.code=='WORKOUT_ALREADY_COMPLETED'
                    return 'conflict'
        outcomes=await asyncio.gather(submit(),submit())
        assert sorted(outcomes)==['conflict','success']
        async with sessions() as session:
            assert await session.scalar(select(func.count()).select_from(WorkoutResult).where(WorkoutResult.workout_id==workout.id))==1
            assert await session.scalar(select(func.count()).select_from(SetResult).join(WorkoutResult).where(WorkoutResult.workout_id==workout.id))==1
            with pytest.raises(ApiError) as duplicate:
                await WorkoutService(WorkoutRepository(session)).submit_result(workout.id,athlete,result)
            assert duplicate.value.status_code==409
        await engine.dispose()
    asyncio.run(run())


def test_schedule_constraint_lifecycle(database):
    async def run():
        engine,sessions,coach,athlete,payload,workout=await seed(database[1])
        async with sessions() as session:
            with pytest.raises(ApiError) as duplicate:
                await CoachService(CoachRepository(session)).create(coach,athlete,payload)
            assert duplicate.value.status_code==409
            assert duplicate.value.code=='WORKOUT_SCHEDULE_CONFLICT'
        from datetime import timedelta
        tomorrow=payload.model_copy(update={'scheduled_for':payload.scheduled_for+timedelta(days=1)})
        async with sessions() as session:
            await CoachService(CoachRepository(session)).create(coach,athlete,tomorrow)
        async with sessions() as session:
            await session.execute(text("update workouts set status='completed' where id=:id"),{'id':workout.id})
            await session.commit()
            await CoachService(CoachRepository(session)).create(coach,athlete,payload)
        await engine.dispose()
    asyncio.run(run())


def test_adoption_and_duplicate_guard():
    # An existing pre-hardening database retains rows and reuses its unique index.
    with disposable_database('0001_add_user_password_hash') as (name,url):
        engine=create_engine(url)
        with engine.begin() as c:
            coach,athlete=uuid4(),uuid4()
            c.execute(text("insert into users(id,full_name,role) values (:c,'Coach','coach'),(:a,'Athlete','athlete')"),{'c':coach,'a':athlete})
            c.execute(text("insert into workouts(athlete_id,coach_id,title,scheduled_for) values (:a,:c,'One',CURRENT_DATE),(:a,:c,'Two',CURRENT_DATE)"),{'a':athlete,'c':coach})
        with pytest.raises(RuntimeError,match='multiple open workouts'):
            migrate(name)
        with engine.connect() as c:
            assert c.scalar(text('select count(*) from workouts'))==2
            assert c.scalar(text('select version_num from alembic_version'))=='0001_add_user_password_hash'
        # Operator resolves the schedule explicitly; the migration never edits rows.
        with engine.begin() as c:
            c.execute(text("update workouts set status='cancelled' where title='Two'"))
        migrate(name)
        assert len(inspect(engine).get_unique_constraints('workout_results'))==1
        # An unversioned populated schema must be refused, then audited/stamped.
        migrate(name,'base',stamp=True)
        with pytest.raises(RuntimeError,match='empty application schema'):
            migrate(name)
        from scripts.audit_schema import audit
        with engine.connect() as connection:
            assert audit(connection)==[]
            assert connection.scalar(text('select count(*) from workouts'))==2
        # Stamp adoption of an already-existing baseline, then upgrade, is safe.
        migrate(name,'0001_add_user_password_hash',stamp=True)
        migrate(name)
        # Reuse an equivalent standalone unique index instead of duplicating it.
        migrate(name,'0001_add_user_password_hash',stamp=True)
        with engine.begin() as c:
            c.execute(text('alter table workout_results drop constraint uq_workout_results_workout_athlete'))
            c.execute(text('create unique index legacy_result_identity on workout_results(workout_id,athlete_id)'))
        migrate(name)
        assert len(inspect(engine).get_unique_constraints('workout_results'))==1
        # Existing duplicate result data must stop the migration without deletion.
        migrate(name,'0001_add_user_password_hash',stamp=True)
        with engine.begin() as c:
            c.execute(text('alter table workout_results drop constraint uq_workout_results_workout_athlete'))
            c.execute(text("insert into workout_results(workout_id,athlete_id) select id,athlete_id from workouts where title='One'"))
            c.execute(text("insert into workout_results(workout_id,athlete_id) select id,athlete_id from workouts where title='One'"))
        with pytest.raises(RuntimeError,match='duplicate workout results'):
            migrate(name)
        with engine.connect() as c:
            assert c.scalar(text('select count(*) from workout_results'))==2
        engine.dispose()


def test_result_failure_rolls_back_parent_and_sets(database):
    async def run():
        engine,sessions,coach,athlete,payload,workout=await seed(database[1])
        class FailingRepository(WorkoutRepository):
            async def add_set_results(self, results):
                await super().add_set_results(results)
                raise RuntimeError('Injected failure after set flush')
        result=WorkoutResultCreate.model_validate({'completed_at':datetime.now(UTC),'sets':[
            {'set_id':workout.exercises[0].sets[0].id,'actual_reps':5,'actual_weight':0,'weight_unit':'kg','completed':True}]})
        async with sessions() as session:
            with pytest.raises(RuntimeError,match='Injected failure'):
                await WorkoutService(FailingRepository(session)).submit_result(workout.id,athlete,result)
            assert await session.scalar(select(func.count()).select_from(WorkoutResult).where(WorkoutResult.workout_id==workout.id))==0
            assert await session.scalar(select(func.count()).select_from(SetResult).where(SetResult.workout_set_id==workout.exercises[0].sets[0].id))==0
            assert await session.scalar(text('select status from workouts where id=:id'),{'id':workout.id})=='active'
        await engine.dispose()
    asyncio.run(run())


def test_progress_aggregate_totals_and_bounded_activity(database):
    async def run():
        from app.models import Workout
        engine,sessions,coach,athlete,payload,workout=await seed(database[1])
        result=WorkoutResultCreate.model_validate({'completed_at':datetime.now(UTC),'sets':[
            {'set_id':workout.exercises[0].sets[0].id,'actual_reps':5,'actual_weight':0,'weight_unit':'kg','completed':True}]})
        async with sessions() as session:
            await WorkoutService(WorkoutRepository(session)).submit_result(workout.id,athlete,result)
            for _ in range(10):
                w=Workout(id=uuid4(),athlete_id=athlete,coach_id=coach,title='Empty historical session',scheduled_for=scheduling_date(),status='completed',created_at=datetime.now(UTC),updated_at=datetime.now(UTC))
                session.add(w)
                await session.flush()
                session.add(WorkoutResult(id=uuid4(),workout_id=w.id,athlete_id=athlete,completed_at=datetime.now(UTC)))
            await session.commit()
            summary=await WorkoutService(WorkoutRepository(session)).get_progress_summary(athlete)
            assert summary.total_completed_workouts==11
            assert summary.total_completed_sets==1
            assert summary.total_prescribed_sets==2
            assert summary.completion_percentage==50
            assert len(summary.recent_activity)==10
            other=await WorkoutService(WorkoutRepository(session)).get_progress_summary(uuid4())
            assert other.total_completed_workouts==0 and other.completion_percentage is None
        await engine.dispose()
    asyncio.run(run())


def test_real_api_coach_athlete_vertical_slice(database):
    from fastapi.testclient import TestClient
    from app.api.deps import get_session
    from app.core.security import hash_password
    from app.main import app
    from datetime import timedelta
    engine,sessions,coach,athlete,payload,workout=asyncio.run(seed(database[1]))
    password='isolated-test-password'
    async def credentials():
        async with sessions() as session:
            for user_id in (coach,athlete):
                await session.execute(text('update users set email=:email,password_hash=:password where id=:id'),
                    {'id':user_id,'email':f'{user_id}@test.local','password':hash_password(password)})
            await session.commit()
    asyncio.run(credentials())
    async def isolated_session():
        async with sessions() as session:
            yield session
    app.dependency_overrides[get_session]=isolated_session
    try:
        with TestClient(app) as client:
            def login(user_id):
                response=client.post('/v1/auth/login',json={'email':f'{user_id}@test.local','password':password})
                assert response.status_code==200
                return {'Authorization':'Bearer '+response.json()['data']['access_token']}
            coach_headers=login(coach); athlete_headers=login(athlete)
            assert client.get('/v1/coaches/me/athletes',headers=coach_headers).json()['data'][0]['id']==str(athlete)
            assert client.get(f'/v1/coaches/me/athletes/{athlete}',headers=coach_headers).status_code==200
            assert client.get('/v1/coaches/me/athletes',headers=athlete_headers).status_code==403
            assert client.get(f'/v1/coaches/me/athletes/{uuid4()}',headers=coach_headers).status_code==404
            assignment=payload.model_copy(update={'scheduled_for':payload.scheduled_for+timedelta(days=1)}).model_dump(mode='json')
            assert client.post(f'/v1/coaches/me/athletes/{athlete}/workouts',headers=coach_headers,json=assignment).status_code==201
            conflict=client.post(f'/v1/coaches/me/athletes/{athlete}/workouts',headers=coach_headers,json=assignment)
            assert conflict.status_code==409 and conflict.json()['error']['code']=='WORKOUT_SCHEDULE_CONFLICT'
            today=client.get('/v1/athletes/me/workouts/today',headers=athlete_headers)
            assert today.status_code==200 and today.json()['data']['id']==str(workout.id)
            result={'completed_at':datetime.now(UTC).isoformat(),'sets':[{
                'set_id':str(workout.exercises[0].sets[0].id),'actual_reps':6,'actual_weight':2.5,'weight_unit':'kg','rpe':7,'completed':True}]}
            assert client.post(f'/v1/workouts/{workout.id}/results',headers=athlete_headers,json=result).status_code==201
            assert client.post(f'/v1/workouts/{workout.id}/results',headers=athlete_headers,json=result).status_code==409
            summary=client.get('/v1/athletes/me/progress-summary',headers=athlete_headers)
            assert summary.status_code==200
            assert summary.json()['data']['total_completed_workouts']==1
            assert summary.json()['data']['completion_percentage']==50
            assert client.get('/v1/athletes/me/progress-summary').status_code==401
            assert client.get('/v1/athletes/me/progress-summary',headers=coach_headers).status_code==403
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
