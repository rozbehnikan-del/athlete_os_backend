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
- `GET /ready`
- `GET /v1/athletes/me/workouts/today`
- `GET /v1/workouts/{workout_id}`
- `POST /v1/workouts/{workout_id}/results`
- `GET /v1/athletes/me/workout-history`

## First Real Database Verification

1. Prepare the local environment:

```powershell
.\scripts\setup_local.ps1
```

2. Edit `.env` locally and enter the real PostgreSQL connection details:

```dotenv
DATABASE_HOST=
DATABASE_USER=
DATABASE_PASSWORD=
```

Never commit `.env`.

3. Run the read-only database smoke test:

```powershell
.\scripts\verify_real_db.ps1
```

4. Start the backend:

```powershell
.\scripts\run_local.ps1
```

5. In another terminal, verify read endpoints:

```powershell
.\scripts\verify_api.ps1
```

This verification is read-only. Do not submit workout results against the real `athlete_os` database during the first connectivity pass.

## Demo End-to-End Reset

To repeat the demo Training flow after submitting a workout result, reset only the seeded demo athlete/workout:

```powershell
.\scripts\reset_demo_workout.ps1
```

Then verify the read-only smoke test:

```powershell
.\scripts\verify_real_db.ps1
```

Expected: the demo workout is active and scheduled for today. The reset script is scoped to the hardcoded demo athlete `22222222-2222-4222-8222-222222222222` and demo workout `77777777-7777-4777-8777-777777777777`.

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
curl http://localhost:8000/ready
curl http://localhost:8000/v1/athletes/me/workouts/today
```

Manual result submission writes to the configured database. Only run this against a disposable/local dataset after replacing the IDs with values from `GET /v1/athletes/me/workouts/today`.

```bash
curl -X POST http://localhost:8000/v1/workouts/<workout_id>/results \
  -H "Content-Type: application/json" \
  -d '{
    "completed_at": "2026-10-14T12:45:30Z",
    "notes": "Felt strong today.",
    "sets": [
      {
        "set_id": "<set_id>",
        "actual_reps": 8,
        "actual_weight": 82.5,
        "weight_unit": "kg",
        "rpe": 8,
        "completed": true,
        "notes": null
      }
    ]
  }'
```
