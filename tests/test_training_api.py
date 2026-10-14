from uuid import uuid4

import pytest

from tests.conftest import FOREIGN_SET_ID, FOREIGN_WORKOUT_ID, UNKNOWN_WORKOUT_ID, WORKOUT_ID, FakeRepository
from app.api.v1.workouts import get_workout_service
from app.main import app
from app.services.workout_service import WorkoutService


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


def test_completed_sets_counts_only_completed_set_results(client, valid_result_payload):
    valid_result_payload["sets"][0]["completed"] = False
    client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)

    response = client.get("/v1/athletes/me/workout-history")

    assert response.json()["data"][0]["completed_sets"] == 9


def test_failed_submission_leaves_no_partial_writes(valid_result_payload):
    from fastapi.testclient import TestClient

    repository = FakeRepository(fail_set_insert=True)
    app.dependency_overrides[get_workout_service] = lambda: WorkoutService(repository)
    try:
        with TestClient(app) as test_client:
            with pytest.raises(RuntimeError):
                test_client.post(f"/v1/workouts/{WORKOUT_ID}/results", json=valid_result_payload)
    finally:
        app.dependency_overrides.clear()

    assert repository.session.rollbacks == 1
    assert repository.results == []
    assert repository.set_results == []
