"""Enforce result identity and the MVP single open workout per scheduled day.

Checks duplicates without deleting data; reuses/renames equivalent result uniqueness.
"""
import re
from alembic import op
import sqlalchemy as sa

revision = '0002_training_invariants'
down_revision = '0001_add_user_password_hash'
branch_labels = None
depends_on = None
RESULT_NAME = 'uq_workout_results_workout_athlete'
SCHEDULE_NAME = 'uq_workouts_athlete_scheduled_open'


def _open_predicate(value):
    value = re.sub(r'::(?:character varying|text)(?:\[\])?', '', value or '', flags=re.I)
    value = re.sub(r'[\s()]', '', value).lower()
    return value in ("status=anyarray['planned','active']", "status=anyarray['active','planned']", "statusin'planned','active'", "statusin'active','planned'")


def upgrade():
    bind = op.get_bind()
    # Block concurrent mutations while auditing and installing the invariants.
    bind.execute(sa.text('LOCK TABLE workout_results, workouts IN SHARE ROW EXCLUSIVE MODE'))
    for query, label in [
        ('SELECT 1 FROM workout_results GROUP BY workout_id, athlete_id HAVING count(*) > 1 LIMIT 1', 'duplicate workout results'),
        ("SELECT 1 FROM workouts WHERE status IN ('planned','active') AND scheduled_for IS NOT NULL GROUP BY athlete_id, scheduled_for HAVING count(*) > 1 LIMIT 1", 'multiple open workouts per day'),
    ]:
        if bind.execute(sa.text(query)).first():
            raise RuntimeError(f'Migration stopped: {label}. Review existing rows manually; no data was deleted.')
    inspector = sa.inspect(bind)
    quote = bind.dialect.identifier_preparer.quote
    equivalents = [c for c in inspector.get_unique_constraints('workout_results')
                   if set(c['column_names']) == {'workout_id', 'athlete_id'}]
    if equivalents:
        existing = next((c for c in equivalents if c['name'] == RESULT_NAME), equivalents[0])
        if existing['name'] != RESULT_NAME:
            op.execute(sa.text(f"ALTER TABLE workout_results RENAME CONSTRAINT {quote(existing['name'])} TO {quote(RESULT_NAME)}"))
    else:
        equivalent_index = next((i for i in inspector.get_indexes('workout_results')
            if i['unique'] and set(i['column_names']) == {'workout_id', 'athlete_id'}
            and not i.get('dialect_options', {}).get('postgresql_where')), None)
        if equivalent_index:
            op.execute(sa.text(f"ALTER TABLE workout_results ADD CONSTRAINT {quote(RESULT_NAME)} UNIQUE USING INDEX {quote(equivalent_index['name'])}"))
        else:
            op.create_unique_constraint(RESULT_NAME, 'workout_results', ['workout_id', 'athlete_id'])
    equivalent_schedule = next((i for i in inspector.get_indexes('workouts')
        if i['unique'] and set(i['column_names']) == {'athlete_id', 'scheduled_for'}
        and _open_predicate(i.get('dialect_options', {}).get('postgresql_where'))), None)
    if equivalent_schedule:
        if equivalent_schedule['name'] != SCHEDULE_NAME:
            op.execute(sa.text(f"ALTER INDEX {quote(equivalent_schedule['name'])} RENAME TO {quote(SCHEDULE_NAME)}"))
    else:
        op.create_index(SCHEDULE_NAME, 'workouts', ['athlete_id', 'scheduled_for'], unique=True,
                        postgresql_where=sa.text("status IN ('planned', 'active')"))


def downgrade():
    raise RuntimeError('Invariant downgrade requires a reviewed data and concurrency plan; automatic removal is disabled.')
