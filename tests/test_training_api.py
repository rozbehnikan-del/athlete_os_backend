import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import (
    ATHLETE_ID,
    COACH_ID,
    FOREIGN_SET_ID,
    FOREIGN_WORKOUT_ID,
    UNKNOWN_WORKOUT_ID,
    WORKOUT_ID,
    FakeRepository,
    build_result_payload,
)
from app.api.deps import get_current_athlete, get_user_repository
from app.api.v1.workouts import get_workout_service
from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import app
from app.main import add_cors_middleware
from app.services.workout_service import WorkoutService


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_local_cors_preflight_succeeds(client):
    response = client.options(
        "/v1/athletes/me/workouts/today",
        headers={
            "Origin": "http://localhost:54321",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type, Accept",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:54321"
    assert "Accept" in response.headers["access-control-allow-headers"]


def test_foreign_origin_is_not_allowed_in_production_style_config(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "not-change-me")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.athleteos.example")
    get_settings.cache_clear()
    production_app = FastAPI()
    add_cors_middleware(production_app)

    with TestClient(production_app) as test_client:
        response = test_client.options(
            "/anything",
            headers={
                "Origin": "http://localhost:54321",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


class RoleUserRepository:
    def __init__(self) -> None:
        self.users = {
            ATHLETE_ID: type(
                "User",
                (),
                {
                    "id": ATHLETE_ID,
                    "email": "ali@athleteos.local",
                    "phone": None,
                    "full_name": "Ali",
                    "role": "athlete",
                    "is_active": True,
                },
            )(),
            COACH_ID: type(
                "User",
                (),
                {
                    "id": COACH_ID,
                    "email": "coach@athleteos.local",
                    "phone": None,
                    "full_name": "Coach",
                    "role": "coach",
                    "is_active": True,
                },
            )(),
        }

    async def get_by_id(self, user_id):
        return self.users.get(user_id)


def test_athlete_jwt_can_access_training_endpoint(fake_repository):
    app.dependency_overrides[get_workout_service] = lambda: WorkoutService(fake_repository)
    app.dependency_overrides[get_user_repository] = lambda: RoleUserRepository()
    token, _ = create_access_token(ATHLETE_ID, "athlete")
    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                "/v1/athletes/me/workouts/today",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_coach_jwt_receives_403_from_athlete_training_endpoint(fake_repository):
    app.dependency_overrides[get_workout_service] = lambda: WorkoutService(fake_repository)
    app.dependency_overrides[get_user_repository] = lambda: RoleUserRepository()
    token, _ = create_access_token(COACH_ID, "coach")
    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                "/v1/athletes/me/workouts/today",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_today_workout_returns_expected_workout(client):
    response = client.get("/v1/athletes/me/workouts/today")

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Today's Workout"


def test_today_workout_returns_3_exercises(client):
    response = client.get("/v1/athletes/me/workouts/today")

    assert len(response.json()["data"]["exercises"]) == 3


def test_back_squat_returns_4_sets(client):
    response = client.get("/v1/athletes/me/workouts/today")

    back_squat = response.json()["data"]["exercises"][0]
    assert back_squat["exercise"]["slug"] == "back-squat"
    assert len(back_squat["sets"]) == 4


def test_get_workout_by_id_works(client):
    response = client.get(f"/v1/workouts/{WORKOUT_ID}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(WORKOUT_ID)


def test_unknown_workout_returns_404(client):
    response = client.get(f"/v1/workouts/{UNKNOWN_WORKOUT_ID}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKOUT_NOT_FOUND"


def test_foreign_owned_workout_returns_403(client):
    response = client.get(f"/v1/workouts/{FOREIGN_WORKOUT_ID}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_invalid_rpe_returns_422(client, valid_result_payload):
    valid_result_payload["sets"][0]["rpe"] = 11

    response = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_foreign_set_id_is_rejected(client, valid_result_payload):
    valid_result_payload["sets"][0]["set_id"] = str(FOREIGN_SET_ID)

    response = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_SET"


def test_duplicate_set_id_in_payload_is_rejected(client, valid_result_payload):
    valid_result_payload["sets"][1]["set_id"] = valid_result_payload["sets"][0]["set_id"]

    response = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_SET"


def test_valid_result_creates_workout_result(client, fake_repository, valid_result_payload):
    response = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert response.status_code == 201
    assert len(fake_repository.results) == 1
    assert response.json()["data"]["status"] == "completed"


def test_result_response_contains_completed_sets(client, valid_result_payload):
    response = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert response.status_code == 201
    assert response.json()["data"]["completed_sets"] == 10


def test_result_submission_marks_workout_completed(client, fake_repository, valid_result_payload):
    response = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert response.status_code == 201
    assert fake_repository.workout.status == "completed"


def test_valid_result_creates_set_results(client, fake_repository, valid_result_payload):
    response = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert response.status_code == 201
    assert len(fake_repository.set_results) == 10


def test_duplicate_result_returns_409(client, valid_result_payload):
    first = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)
    second = client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "WORKOUT_ALREADY_COMPLETED"


def test_history_returns_completed_workout(client, valid_result_payload):
    client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    response = client.get("/v1/athletes/me/workout-history")

    assert response.status_code == 200
    assert response.json()["data"][0]["workout_id"] == str(WORKOUT_ID)


def test_history_contains_sets(client, valid_result_payload):
    client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    response = client.get("/v1/athletes/me/workout-history")

    assert len(response.json()["data"][0]["sets"]) == 10


def test_history_set_contains_required_identity_fields(client, valid_result_payload):
    client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    response = client.get("/v1/athletes/me/workout-history")
    history_set = response.json()["data"][0]["sets"][0]

    assert history_set["set_id"]
    assert history_set["prescription_id"]
    assert history_set["exercise_id"]


def test_history_set_ordering_is_deterministic(client, valid_result_payload):
    client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    response = client.get("/v1/athletes/me/workout-history")
    sets = response.json()["data"][0]["sets"]

    assert [item["set_number"] for item in sets[:4]] == [1, 2, 3, 4]
    assert [item["set_number"] for item in sets[4:7]] == [1, 2, 3]
    assert [item["set_number"] for item in sets[7:]] == [1, 2, 3]


def test_incomplete_set_is_represented_correctly(client, valid_result_payload):
    valid_result_payload["sets"][0]["completed"] = False
    valid_result_payload["sets"][0]["notes"] = "Skipped for knee soreness."
    client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    response = client.get("/v1/athletes/me/workout-history")
    history_set = response.json()["data"][0]["sets"][0]

    assert history_set["completed"] is False
    assert history_set["notes"] == "Skipped for knee soreness."


def test_completed_sets_counts_only_completed_set_results(client, valid_result_payload):
    valid_result_payload["sets"][0]["completed"] = False
    client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    response = client.get("/v1/athletes/me/workout-history")

    assert response.json()["data"][0]["completed_sets"] == 9


def test_failed_submission_leaves_no_partial_writes(valid_result_payload):
    from fastapi.testclient import TestClient

    repository = FakeRepository(fail_set_insert=True)
    payload = build_result_payload(repository)
    app.dependency_overrides[get_workout_service] = lambda: WorkoutService(repository)
    app.dependency_overrides[get_current_athlete] = lambda: SimpleNamespace(
        id=ATHLETE_ID,
        email="ali@athleteos.local",
        phone=None,
        full_name="Ali",
        role="athlete",
        is_active=True,
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=payload)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert repository.session.rollbacks == 1
    assert repository.session.commits == 0
    assert repository.results == []
    assert repository.set_results == []
    assert repository.workout.status == "active"


def test_reset_script_requires_confirmation(capsys):
    from scripts import reset_demo_workout

    original_argv = sys.argv
    sys.argv = ["reset_demo_workout.py"]
    try:
        exit_code = reset_demo_workout.main()
    finally:
        sys.argv = original_argv

    assert exit_code == 1
    assert "Refusing to reset demo data without --confirm-demo-reset" in capsys.readouterr().out


def test_reset_script_scope_constants_are_demo_only():
    from scripts.reset_demo_workout import DEMO_ATHLETE_ID, DEMO_WORKOUT_ID

    assert str(DEMO_ATHLETE_ID) == "22222222-2222-4222-8222-222222222222"
    assert str(DEMO_WORKOUT_ID) == "77777777-7777-4777-8777-777777777777"
