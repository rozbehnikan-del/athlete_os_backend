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
python scripts/run_server.py
```

API paths:

- `GET /health`
- `GET /ready`
- `GET /v1/coaches/me/athletes`
- `GET /v1/coaches/me/athletes/{athlete_id}`
- `POST /v1/coaches/me/athletes/{athlete_id}/workouts`
- `GET /v1/exercises` (authenticated shared library)
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

## Local Auth Setup

Add local-only auth values to `.env`:

```dotenv
JWT_SECRET_KEY=<strong-local-secret>
DEMO_ATHLETE_PASSWORD=<local-dev-password>
DEMO_COACH_PASSWORD=<local-dev-password>
```

Run migrations:

```bash
alembic upgrade head
```

Set the seeded demo user passwords:

```powershell
.\scripts\set_demo_passwords.ps1
```

Login with email/password:

```bash
POST /v1/auth/login
```

Use the returned access token on protected endpoints:

```http
Authorization: Bearer <token>
```

Plain passwords are never stored; the setup script hashes local demo passwords before writing them.

## Database Notes

The app maps the existing PostgreSQL schema. It does not create tables on startup. Protected API routes require a bearer access token; clients never send `athlete_id` for `me` routes.

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

## Coach assignment MVP

Coach routes require a coach JWT and an active, non-ended coach_athletes relationship.
Unassigned athletes return 404. Creation commits workout, exercises and sets together,
or rolls them all back. Existing database constraints require explicit target_reps,
target_weight and kg/lb weight_unit for every prescribed set; no unit is invented.

History now includes derived completion_percentage and completion_grade. No migration
is needed. Grade measures completed sets / prescribed sets, not athletic ability.

On Windows use the run_server.py launcher above (or scripts/run_local.ps1) so the
selector event loop is chosen before Uvicorn starts; psycopg async rejects Proactor.
The launcher binds localhost and accepts --port (default 8000).

For the opt-in Flutter live UI test, run this server on port 8011, then execute
scripts/verify_live_mvp.ps1 in the sibling Flutter repository. This test writes only
clearly named workouts/results for the known local demo Ali account. It uses local
demo passwords from .env via a deleted temporary file; never put them in source.

Read-only persistence verification for a workout ID printed by that test:

```powershell
.\.venv\Scripts\python.exe scripts/verify_mvp_persistence.py <workout-id>
```

## MVP hardening

See [safe database bootstrap/adoption](docs/database_bootstrap.md) before upgrading.
Fresh databases now upgrade from a complete guarded baseline. Existing initialized
schemas must be audited and safely adopted; never run a fresh bootstrap on development.
The hardening migration reuses result uniqueness and adds a partial unique schedule
index (one active/planned workout per athlete/date). Duplicate rows stop migration
without automatic deletion. Apply the reviewed migration before deploying this code.

`GET /v1/athletes/me/progress-summary` returns real SQL aggregates plus at most ten
recent activities. Flutter Progress uses it independently of paginated History.
Scheduling uses explicit `SCHEDULING_TIMEZONE` (default `Asia/Tehran`). Athlete-specific
zones and multi-session schedules remain v0.2 work, with no Performance Grading added.

CI uses Python 3.12 and its own PostgreSQL service, never development data. Run the
opt-in PostgreSQL suite described in the bootstrap guide for fresh schema, adoption,
real concurrent submissions and full authenticated Coach-to-Athlete API verification.
