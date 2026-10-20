from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from app.api.deps import get_current_user
from app.api.v1.coaches import get_coach_service
from app.main import app
from app.services.coach_service import CoachService
from app.schemas.coach import WorkoutCreate
from tests.conftest import COACH_ID, ATHLETE_ID, FakeRepository

EXERCISE_ID = uuid4()
def payload():
    return {'title':'Coach assignment','scheduled_for':date.today().isoformat(),
        'exercises':[{'exercise_id':str(EXERCISE_ID),'order':1,'sets':[
            {'set_number':1,'target_reps':8,'target_weight':20,'weight_unit':'kg'}]}]}

class Repository:
    def __init__(self):
        self.session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        self.created = []
        self.fail = False
    async def athletes(self, coach_id, athlete_id=None, *, for_update=False):
        if coach_id != COACH_ID or athlete_id not in (None, ATHLETE_ID): return []
        return [(SimpleNamespace(id=ATHLETE_ID, full_name='Ali', email='ali@athleteos.local',
            phone=None, is_active=True, password_hash='never expose'), None)]
    async def exercises(self):
        return [SimpleNamespace(id=EXERCISE_ID,slug='back-squat',name='Back Squat')]
    async def exercise_ids(self, ids): return ids & {EXERCISE_ID}
    async def add_workout(self, workout):
        self.created.append(workout)
        if self.fail: raise RuntimeError('insertion failed')

@pytest.fixture()
def setup():
    repo = Repository()
    workouts = FakeRepository()
    original_detail = workouts.get_workout_detail
    async def detail(workout_id):
        if repo.created and repo.created[-1].id == workout_id:
            workout = repo.created[-1]
            workout.coach = None
            for e in workout.workout_exercises:
                e.exercise = SimpleNamespace(id=e.exercise_id,slug='back-squat',name='Back Squat')
            return workout
        return await original_detail(workout_id)
    workouts.get_workout_detail = detail
    service = CoachService(repo, workouts)
    app.dependency_overrides[get_coach_service] = lambda: service
    with TestClient(app) as client:
        yield client, repo, service
    app.dependency_overrides.clear()

def login(role='coach'):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=COACH_ID,role=role)

@pytest.mark.parametrize('path', ['/v1/coaches/me/athletes',f'/v1/coaches/me/athletes/{ATHLETE_ID}'])
def test_missing_auth(setup, path):
    assert setup[0].get(path).status_code == 401

def test_athlete_forbidden(setup):
    login('athlete')
    assert setup[0].get('/v1/coaches/me/athletes').status_code == 403

def test_roster_and_detail(setup):
    login()
    client = setup[0]
    response = client.get('/v1/coaches/me/athletes')
    assert response.status_code == 200
    assert len(response.json()['data']) == 1
    assert 'password_hash' not in response.text
    detail = client.get(f'/v1/coaches/me/athletes/{ATHLETE_ID}')
    assert detail.status_code == 200
    assert 'training' in detail.json()['data']
    assert client.get(f'/v1/coaches/me/athletes/{uuid4()}').status_code == 404

def test_creation_and_library(setup):
    login()
    client, repo, _ = setup
    assert client.get('/v1/exercises').json()['data'][0]['id'] == str(EXERCISE_ID)
    result = client.post(f'/v1/coaches/me/athletes/{ATHLETE_ID}/workouts',json=payload())
    assert result.status_code == 201, result.text
    repo.session.commit.assert_awaited_once()
    created = repo.created[0]
    assert created.coach_id == COACH_ID and created.athlete_id == ATHLETE_ID
    assert created.workout_exercises[0].workout_sets[0].target_reps == 8

def test_unassigned_and_unknown_exercise(setup):
    login()
    client, repo, _ = setup
    assert client.post(f'/v1/coaches/me/athletes/{uuid4()}/workouts',json=payload()).status_code == 404
    data = payload(); data['exercises'][0]['exercise_id'] = str(uuid4())
    assert client.post(f'/v1/coaches/me/athletes/{ATHLETE_ID}/workouts',json=data).status_code == 422
    assert not repo.created
    repo.session.commit.assert_not_awaited()

@pytest.mark.parametrize('case', ['order','sets','reps','weight','unit','title','date','coach_id','null_unit','set_number','negative_order','huge_weight','empty_exercises','empty_sets'])
def test_invalid_assignment(setup, case):
    login()
    data = payload(); exercise = data['exercises'][0]; s = exercise['sets'][0]
    if case == 'order': data['exercises'].append(deepcopy(exercise))
    if case == 'sets': exercise['sets'].append(deepcopy(s))
    if case == 'reps': s['target_reps'] = -1
    if case == 'weight': s['target_weight'] = -1
    if case == 'unit': s['weight_unit'] = 'stone'
    if case == 'null_unit': s['weight_unit'] = None
    if case == 'set_number': s['set_number'] = 0
    if case == 'negative_order': exercise['order'] = -1
    if case == 'huge_weight': s['target_weight'] = 1e20
    if case == 'empty_exercises': data['exercises'] = []
    if case == 'empty_sets': exercise['sets'] = []
    if case == 'title': data['title'] = '   '
    if case == 'date': data['scheduled_for'] = 'bad'
    if case == 'coach_id': data['coach_id'] = str(COACH_ID)
    response = setup[0].post(f'/v1/coaches/me/athletes/{ATHLETE_ID}/workouts',json=data)
    assert response.status_code == 422
    assert not setup[1].created

@pytest.mark.anyio
async def test_creation_failure_rolls_back(setup):
    _, repo, service = setup
    repo.fail = True
    with pytest.raises(RuntimeError):
        await service.create(COACH_ID,ATHLETE_ID,WorkoutCreate.model_validate(payload()))
    repo.session.rollback.assert_awaited_once()
    repo.session.commit.assert_not_awaited()

