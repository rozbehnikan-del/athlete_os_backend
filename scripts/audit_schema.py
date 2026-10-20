"""Read-only adoption preflight; never stamps or modifies the configured database."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, text
from app.core.config import get_settings


def audit(connection):
    expected=json.loads((Path(__file__).resolve().parents[1]/'docs/schema_contract.json').read_text(encoding='utf-8'))
    inspector=inspect(connection)
    problems=[]
    for table,contract in expected.items():
        if not inspector.has_table(table):
            problems.append(f'{table}: missing table'); continue
        actual={c['name']:c for c in inspector.get_columns(table)}
        for column in contract['columns']:
            c=actual.get(column['name'])
            if not c:
                problems.append(f"{table}.{column['name']}: missing column"); continue
            if (str(c['type']),c['nullable'],getattr(c['type'],'timezone',False),c['default']) != (column['type'],column['nullable'],column['timezone'],column['default']):
                problems.append(f"{table}.{column['name']}: type/nullability/timezone/default differs")
        uniques={frozenset(c['column_names']) for c in inspector.get_unique_constraints(table)}
        uniques.update(frozenset(i['column_names']) for i in inspector.get_indexes(table)
            if i['unique'] and not i.get('dialect_options',{}).get('postgresql_where'))
        for columns in contract['unique_columns']:
            if frozenset(columns) not in uniques: problems.append(f'{table}: missing uniqueness on {columns}')
        fks=inspector.get_foreign_keys(table)
        for fk in contract['foreign_keys']:
            if not any(all(actual[k]==fk[k] for k in fk) for actual in fks): problems.append(f'{table}: foreign key differs on {fk["constrained_columns"]}')
        checks={c['sqltext'] for c in inspector.get_check_constraints(table)}
        if not set(contract['checks']).issubset(checks): problems.append(f'{table}: check constraints differ')
        indexes={i['name']:i for i in inspector.get_indexes(table)}
        for index in contract['indexes']:
            actual_index=indexes.get(index['name'])
            if not actual_index or any(actual_index[k]!=index[k] for k in ('column_names','unique','dialect_options')):
                problems.append(f'{table}: index differs: {index["name"]}')
    for query,label in [
        ('select 1 from workout_results group by workout_id,athlete_id having count(*)>1 limit 1','duplicate results'),
        ("select 1 from workouts where status in ('planned','active') and scheduled_for is not null group by athlete_id,scheduled_for having count(*)>1 limit 1",'duplicate open workout dates')]:
        if not problems and connection.execute(text(query)).first(): problems.append(label)
    return problems


if __name__=='__main__':
    engine=create_engine(get_settings().database_url,connect_args={'connect_timeout':10})
    try:
        with engine.connect() as connection:
            problems=audit(connection)
        for problem in problems: print(problem)
        print('Schema adoption preflight: '+('FAILED; do not stamp.' if problems else 'PASS. Review backup and database identity before stamping.'))
        raise SystemExit(1 if problems else 0)
    except SystemExit:
        raise
    except Exception:
        raise SystemExit('Schema adoption preflight could not connect/inspect; diagnostics withheld to protect credentials.') from None
    finally:
        engine.dispose()
