from datetime import UTC, datetime, timedelta
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_user_repository
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app

ATHLETE_ID = UUID("22222222-2222-4222-8222-222222222222")
COACH_ID = UUID("11111111-1111-4111-8111-111111111111")
ATHLETE_PASSWORD = "correct-local-password"


class FakeUserRepository:
    def __init__(self) -> None:
        self.users = {
            ATHLETE_ID: SimpleNamespace(
                id=ATHLETE_ID,
                email="ali@athleteos.local",
                phone=None,
                full_name="Ali",
                role="athlete",
                is_active=True,
                password_hash=hash_password(ATHLETE_PASSWORD),
            ),
            COACH_ID: SimpleNamespace(
                id=COACH_ID,
                email="coach@athleteos.local",
                phone=None,
                full_name="Coach",
                role="coach",
                is_active=True,
                password_hash=hash_password("coach-password"),
            ),
        }

    async def get_by_email(self, email: str):
        return next((user for user in self.users.values() if user.email == email), None)

    async def get_by_id(self, user_id):
        return self.users.get(user_id)


@pytest.fixture(autouse=True)
def auth_settings(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def user_repository():
    return FakeUserRepository()


@pytest.fixture()
def auth_client(user_repository):
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_password_hashing_and_verification_works():
    hashed = hash_password("secret")

    assert hashed != "secret"
    assert verify_password("secret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_correct_login_succeeds(auth_client):
    response = auth_client.post(
        "/v1/auth/login",
        json={"email": " ALI@athleteos.local ", "password": ATHLETE_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600


def test_login_rejects_malformed_email(auth_client):
    response = auth_client.post(
        "/v1/auth/login",
        json={"email": "not-an-email", "password": ATHLETE_PASSWORD},
    )

    assert response.status_code == 422


def test_wrong_password_returns_401(auth_client):
    response = auth_client.post(
        "/v1/auth/login",
        json={"email": "ali@athleteos.local", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_unknown_email_returns_401(auth_client):
    response = auth_client.post(
        "/v1/auth/login",
        json={"email": "missing@athleteos.local", "password": ATHLETE_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_login_does_not_disclose_which_credential_failed(auth_client):
    wrong_password = auth_client.post(
        "/v1/auth/login",
        json={"email": "ali@athleteos.local", "password": "wrong"},
    )
    unknown_email = auth_client.post(
        "/v1/auth/login",
        json={"email": "missing@athleteos.local", "password": "wrong"},
    )

    assert wrong_password.json() == unknown_email.json()


def test_inactive_user_login_returns_403(auth_client, user_repository):
    user_repository.users[ATHLETE_ID].is_active = False

    response = auth_client.post(
        "/v1/auth/login",
        json={"email": "ali@athleteos.local", "password": ATHLETE_PASSWORD},
    )

    assert response.status_code == 403


def test_auth_me_with_valid_token_succeeds(auth_client):
    token, _ = create_access_token(ATHLETE_ID, "athlete")

    response = auth_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(ATHLETE_ID)
    assert response.json()["data"]["role"] == "athlete"


def test_auth_me_missing_token_returns_401(auth_client):
    response = auth_client.get("/v1/auth/me")

    assert response.status_code == 401


def test_auth_me_malformed_token_returns_401(auth_client):
    response = auth_client.get("/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401


def test_auth_me_expired_token_returns_401(auth_client):
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(ATHLETE_ID),
            "role": "athlete",
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = auth_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_auth_me_wrong_token_type_returns_401(auth_client):
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(ATHLETE_ID),
            "role": "athlete",
            "type": "refresh",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = auth_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_auth_me_nonexistent_subject_returns_401(auth_client):
    token, _ = create_access_token(uuid4(), "athlete")

    response = auth_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_auth_me_inactive_user_returns_403(auth_client, user_repository):
    user_repository.users[ATHLETE_ID].is_active = False
    token, _ = create_access_token(ATHLETE_ID, "athlete")

    response = auth_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_auth_me_returns_role(auth_client):
    token, _ = create_access_token(COACH_ID, "coach")

    response = auth_client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "coach"


def test_set_demo_passwords_requires_confirmation(capsys):
    from scripts import set_demo_passwords

    original_argv = sys.argv
    sys.argv = ["set_demo_passwords.py"]
    try:
        exit_code = set_demo_passwords.main()
    finally:
        sys.argv = original_argv

    assert exit_code == 1
    assert "Refusing to set demo passwords without --confirm-demo-passwords" in capsys.readouterr().out
