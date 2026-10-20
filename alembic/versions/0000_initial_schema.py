"""Complete pre-auth application schema, captured from inspected PostgreSQL catalog.

Fresh databases only. Initialized databases must be audited and stamped at 0001;
this revision refuses to run if ANY application table already exists.
"""
from alembic import op
import sqlalchemy as sa

revision = '0000_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

TABLES = ['exercises', 'users', 'athlete_profiles', 'coach_athletes', 'coach_profiles', 'workouts', 'workout_exercises', 'workout_results', 'workout_sets', 'set_results']
DDL = (
    """
CREATE TABLE exercises (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	slug VARCHAR(120) NOT NULL,
	name VARCHAR(150) NOT NULL,
	category VARCHAR(80),
	body_area VARCHAR(80),
	movement_pattern VARCHAR(80),
	equipment VARCHAR(80),
	difficulty VARCHAR(50),
	purpose VARCHAR(100),
	is_active BOOLEAN DEFAULT true NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT exercises_pkey PRIMARY KEY (id),
	CONSTRAINT exercises_slug_key UNIQUE (slug)
)
    """,
    """
CREATE TABLE users (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	email VARCHAR(255),
	phone VARCHAR(50),
	full_name VARCHAR(150) NOT NULL,
	role VARCHAR(30) NOT NULL,
	is_active BOOLEAN DEFAULT true NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT users_pkey PRIMARY KEY (id),
	CONSTRAINT users_email_key UNIQUE (email),
	CONSTRAINT users_phone_key UNIQUE (phone),
	CONSTRAINT users_role_check CHECK (role::text = ANY (ARRAY['athlete'::character varying, 'coach'::character varying, 'doctor'::character varying, 'nutritionist'::character varying, 'admin'::character varying]::text[]))
)
    """,
    """
CREATE TABLE athlete_profiles (
	user_id UUID NOT NULL,
	date_of_birth DATE,
	gender VARCHAR(20),
	height_cm NUMERIC(6, 2),
	weight_kg NUMERIC(6, 2),
	experience_level VARCHAR(30),
	goals TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT athlete_profiles_pkey PRIMARY KEY (user_id),
	CONSTRAINT athlete_profiles_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)
    """,
    """
CREATE TABLE coach_athletes (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	coach_id UUID NOT NULL,
	athlete_id UUID NOT NULL,
	status VARCHAR(20) DEFAULT 'active'::character varying NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	ended_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT coach_athletes_pkey PRIMARY KEY (id),
	CONSTRAINT coach_athletes_athlete_id_fkey FOREIGN KEY(athlete_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT coach_athletes_coach_id_fkey FOREIGN KEY(coach_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT coach_athletes_coach_id_athlete_id_key UNIQUE (coach_id, athlete_id),
	CONSTRAINT coach_athletes_check CHECK (coach_id <> athlete_id),
	CONSTRAINT coach_athletes_status_check CHECK (status::text = ANY (ARRAY['active'::character varying, 'paused'::character varying, 'ended'::character varying]::text[]))
)
    """,
    """
CREATE TABLE coach_profiles (
	user_id UUID NOT NULL,
	bio TEXT,
	specialty VARCHAR(150),
	years_experience INTEGER,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT coach_profiles_pkey PRIMARY KEY (user_id),
	CONSTRAINT coach_profiles_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT coach_profiles_years_experience_check CHECK (years_experience IS NULL OR years_experience >= 0)
)
    """,
    """
CREATE TABLE workouts (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	athlete_id UUID NOT NULL,
	coach_id UUID NOT NULL,
	title VARCHAR(180) NOT NULL,
	category VARCHAR(80),
	focus VARCHAR(120),
	scheduled_for DATE,
	status VARCHAR(20) DEFAULT 'planned'::character varying NOT NULL,
	coach_notes TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT workouts_pkey PRIMARY KEY (id),
	CONSTRAINT workouts_athlete_id_fkey FOREIGN KEY(athlete_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT workouts_coach_id_fkey FOREIGN KEY(coach_id) REFERENCES users (id) ON DELETE RESTRICT,
	CONSTRAINT workouts_status_check CHECK (status::text = ANY (ARRAY['planned'::character varying, 'active'::character varying, 'completed'::character varying, 'cancelled'::character varying]::text[]))
)
    """,
    """
CREATE TABLE workout_exercises (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	workout_id UUID NOT NULL,
	exercise_id UUID NOT NULL,
	exercise_order INTEGER NOT NULL,
	coaching_note TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT workout_exercises_pkey PRIMARY KEY (id),
	CONSTRAINT workout_exercises_exercise_id_fkey FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE RESTRICT,
	CONSTRAINT workout_exercises_workout_id_fkey FOREIGN KEY(workout_id) REFERENCES workouts (id) ON DELETE CASCADE,
	CONSTRAINT workout_exercises_workout_id_exercise_order_key UNIQUE (workout_id, exercise_order),
	CONSTRAINT workout_exercises_exercise_order_check CHECK (exercise_order >= 1)
)
    """,
    """
CREATE TABLE workout_results (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	workout_id UUID NOT NULL,
	athlete_id UUID NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	athlete_notes TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT workout_results_pkey PRIMARY KEY (id),
	CONSTRAINT workout_results_athlete_id_fkey FOREIGN KEY(athlete_id) REFERENCES users (id) ON DELETE CASCADE,
	CONSTRAINT workout_results_workout_id_fkey FOREIGN KEY(workout_id) REFERENCES workouts (id) ON DELETE CASCADE,
	CONSTRAINT workout_results_workout_id_athlete_id_key UNIQUE (workout_id, athlete_id)
)
    """,
    """
CREATE TABLE workout_sets (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	workout_exercise_id UUID NOT NULL,
	set_number INTEGER NOT NULL,
	target_reps INTEGER NOT NULL,
	target_weight NUMERIC(8, 2) DEFAULT 0 NOT NULL,
	weight_unit VARCHAR(10) DEFAULT 'kg'::character varying NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT workout_sets_pkey PRIMARY KEY (id),
	CONSTRAINT workout_sets_workout_exercise_id_fkey FOREIGN KEY(workout_exercise_id) REFERENCES workout_exercises (id) ON DELETE CASCADE,
	CONSTRAINT workout_sets_workout_exercise_id_set_number_key UNIQUE (workout_exercise_id, set_number),
	CONSTRAINT workout_sets_set_number_check CHECK (set_number >= 1),
	CONSTRAINT workout_sets_target_reps_check CHECK (target_reps >= 0),
	CONSTRAINT workout_sets_target_weight_check CHECK (target_weight >= 0::numeric),
	CONSTRAINT workout_sets_weight_unit_check CHECK (weight_unit::text = ANY (ARRAY['kg'::character varying, 'lb'::character varying]::text[]))
)
    """,
    """
CREATE TABLE set_results (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	workout_result_id UUID NOT NULL,
	workout_exercise_id UUID NOT NULL,
	workout_set_id UUID NOT NULL,
	actual_reps INTEGER NOT NULL,
	actual_weight NUMERIC(8, 2) DEFAULT 0 NOT NULL,
	weight_unit VARCHAR(10) NOT NULL,
	rpe NUMERIC(3, 1),
	completed BOOLEAN DEFAULT true NOT NULL,
	athlete_notes TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT set_results_pkey PRIMARY KEY (id),
	CONSTRAINT set_results_workout_exercise_id_fkey FOREIGN KEY(workout_exercise_id) REFERENCES workout_exercises (id) ON DELETE RESTRICT,
	CONSTRAINT set_results_workout_result_id_fkey FOREIGN KEY(workout_result_id) REFERENCES workout_results (id) ON DELETE CASCADE,
	CONSTRAINT set_results_workout_set_id_fkey FOREIGN KEY(workout_set_id) REFERENCES workout_sets (id) ON DELETE RESTRICT,
	CONSTRAINT set_results_workout_result_id_workout_set_id_key UNIQUE (workout_result_id, workout_set_id),
	CONSTRAINT set_results_actual_reps_check CHECK (actual_reps >= 0),
	CONSTRAINT set_results_actual_weight_check CHECK (actual_weight >= 0::numeric),
	CONSTRAINT set_results_rpe_check CHECK (rpe IS NULL OR rpe >= 1::numeric AND rpe <= 10::numeric),
	CONSTRAINT set_results_weight_unit_check CHECK (weight_unit::text = ANY (ARRAY['kg'::character varying, 'lb'::character varying]::text[]))
)
    """,
    """
CREATE INDEX idx_users_role ON users (role)
    """,
    """
CREATE INDEX idx_coach_athletes_athlete ON coach_athletes (athlete_id)
    """,
    """
CREATE INDEX idx_coach_athletes_coach ON coach_athletes (coach_id)
    """,
    """
CREATE INDEX idx_workouts_athlete ON workouts (athlete_id)
    """,
    """
CREATE INDEX idx_workouts_coach ON workouts (coach_id)
    """,
    """
CREATE INDEX idx_workouts_scheduled_for ON workouts (scheduled_for)
    """,
    """
CREATE INDEX idx_workout_exercises_workout ON workout_exercises (workout_id)
    """,
    """
CREATE INDEX idx_workout_results_athlete ON workout_results (athlete_id)
    """,
    """
CREATE INDEX idx_workout_results_completed_at ON workout_results (completed_at DESC)
    """,
    """
CREATE INDEX idx_workout_sets_exercise ON workout_sets (workout_exercise_id)
    """,
    """
CREATE INDEX idx_set_results_workout_exercise ON set_results (workout_exercise_id)
    """,
    """
CREATE INDEX idx_set_results_workout_result ON set_results (workout_result_id)
    """,
)

def upgrade():
    inspector = sa.inspect(op.get_bind())
    if any(inspector.has_table(name) for name in TABLES):
        raise RuntimeError('Baseline requires an empty application schema. Audit existing schema and stamp 0001_add_user_password_hash; see docs/database_bootstrap.md.')
    for statement in DDL:
        op.execute(statement)

def downgrade():
    raise RuntimeError('Baseline downgrade is intentionally disabled; restore a reviewed backup instead.')
