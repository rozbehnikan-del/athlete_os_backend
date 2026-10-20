# Safe PostgreSQL bootstrap and adoption

Supported target: PostgreSQL 13+ (CI uses 16), Python 3.12.
Never use the development database for fresh-install testing.

## Revision chain

`0000_initial_schema -> 0001_add_user_password_hash -> 0002_training_invariants`

The new root is static, reviewed DDL for the ten current application tables,
including existing defaults, foreign keys, checks, unique constraints and indexes.
It deliberately excludes password_hash so the historical 0001 remains meaningful.
0001 now names the new root as its predecessor; its own upgrade is unchanged.
Databases already at 0001 do not execute the newly inserted ancestor.
Unrelated product tables in a development database are not part of this app baseline.

The baseline refuses to run if ANY application table exists. It never uses
CREATE TABLE IF NOT EXISTS to conceal a partial or mismatched installation.
All revisions use PostgreSQL transactional DDL. No autogenerate was run.
Baseline/invariant downgrades are disabled to prevent accidental destructive undo.

## Fresh database

Create a genuinely empty disposable database using your database administration
connection. Do not point the following commands at athlete_os or an existing database.
The connection host/user/password continue to come from the local, uncommitted .env;
only DATABASE_NAME is overridden here. Substitute the actual newly created name:

```powershell
$env:DATABASE_NAME = 'athleteos_scratch_NEW_UNIQUE_NAME'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe scripts/audit_schema.py
Remove-Item Env:DATABASE_NAME
```

A fully automatic disposable verification, using the configured server credentials
with CREATEDB privilege, is available without manually creating a database:

```powershell
$env:RUN_POSTGRES_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest tests/test_postgres_integration.py -q --tb=short
Remove-Item Env:RUN_POSTGRES_INTEGRATION
```

The tests create fresh `athleteos_test_<uuid>` databases, invoke Alembic upgrade head,
prove the ten tables, password_hash, FK-backed lifecycle, one result constraint and
partial schedule index, exercise real writes/concurrency, and drop only databases
successfully created by that test invocation. Never substitute a shared database.
No seeded credentials, exercise library or demo users are installed by migrations;
provision reviewed local/demo data separately using the existing scripts as appropriate.

## Existing initialized database

1. Confirm database identity and take a verified backup and schema-only snapshot.
2. Stop or pause application writers for the reviewed migration window.
3. Compare that schema with `0000_initial_schema.py`, 0001, and
   `docs/schema_contract.json`; run the read-only audit below. It checks all expected
   columns/types/nullability/defaults, FKs, checks, unique keys and existing indexes,
   plus duplicate results and open athlete/date collisions. Additional unrelated
   tables and the new hardening index are allowed. Schema differences require review.
4. If already at 0001, do not stamp it again. If it is unversioned but the full audit
   passes INCLUDING password_hash, stamp ONLY 0001, then apply the new invariant
   revision. A missing password_hash or partial schema requires a separate reviewed
   recovery; never falsely stamp it complete.

```powershell
.\.venv\Scripts\python.exe scripts/audit_schema.py
.\.venv\Scripts\python.exe -m alembic current
# ONLY for the audited, backed-up, fully initialized but unversioned schema:
.\.venv\Scripts\python.exe -m alembic stamp 0001_add_user_password_hash
# For either that adopted schema or an existing schema already at 0001:
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe scripts/audit_schema.py
```

Do not stamp head: that would skip installing invariants. Do not run autogenerate
against development as a bootstrap strategy. Existing versioned databases at 0001
only need the reviewed 0002 upgrade; no baseline table creation occurs.

## Invariants and data safety

0002 first locks workouts/workout_results against concurrent writes, then audits
both duplicate identities and open schedules. Any conflict raises an error and
rolls back without deleting or changing rows. Resolve conflicts manually under an
explicit data policy before retrying; there is no automatic deduplication.

The already-existing result unique constraint is renamed to
`uq_workout_results_workout_athlete`; an equivalent standalone unique index can be
attached instead. No redundant unique index is created. Missing uniqueness is added.

`uq_workouts_athlete_scheduled_open` is a PostgreSQL partial unique index on
(athlete_id, scheduled_for) WHERE status IN ('planned','active'). Completed/cancelled
history is unrestricted. Null legacy schedule dates are left untouched; the creation
API always requires a date. Equivalent existing open-schedule indexes are reused.

Creating/renaming these invariants can block writers and index creation scans existing
rows. Choose a maintenance window for large datasets; this is a transactional MVP
migration, not a concurrent zero-downtime index rollout.

## Date policy

Set `SCHEDULING_TIMEZONE=Asia/Tehran` (default) or another valid IANA zone in .env.
The scheduling abstraction derives calendar dates from aware UTC instants using
zoneinfo, independently of host locale. Coach status and Today's Workout share it.
No athlete timezone field exists, so athlete-specific zones remain an immediate
v0.2 follow-up. No UTC offset is persisted as timezone identity.

## Deployment order and diagnostics

Apply the audited 0002 migration before serving the hardened application: database
uniqueness is the concurrency guarantee. Application prechecks alone are insufficient.
The development database was inspected read-only and left at 0001 during this sprint.
All mutation and migration verification used disposable databases.

Integration tests redact configured database passwords from pytest failure reports.
Use --tb=short for manual database tests. Do not publish raw driver connection logs.
