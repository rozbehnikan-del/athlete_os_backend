# AthleteOS Backend

FastAPI backend skeleton for the AthleteOS Training API V1. It uses SQLAlchemy 2 async, PostgreSQL, Pydantic v2, Alembic, and pytest.

## Setup

Use Python 3.12+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in database credentials. Do not commit `.env`.

## Run Locally

```bash
uvicorn app.main:app --reload
```

API paths:

- `GET /health`
- `GET /v1/athletes/me/workouts/today`
- `GET /v1/workouts/{workout_id}`
- `POST /v1/workouts/{workout_id}/results`
- `GET /v1/athletes/me/workout-history`

## Tests

```bash
pytest
```

The included tests use dependency overrides/fakes and do not run destructive operations against the live `athlete_os` database.

## Database Notes

The app maps the existing PostgreSQL schema. It does not create tables on startup. The temporary auth dependency resolves the current athlete from `DEMO_ATHLETE_ID`; clients never send `athlete_id` for `me` routes.

## Alembic

Alembic is configured for future migrations only. Do not generate or apply destructive migrations against production without review.

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Docker

```bash
docker compose up --build
```

The container exposes port `8000` and runs:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Example Curl

```bash
curl http://localhost:8000/health
curl http://localhost:8000/v1/athletes/me/workouts/today
```
