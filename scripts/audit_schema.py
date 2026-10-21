"""Read-only adoption preflight; never stamps or modifies the configured database."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def normalize_check(expression):
    value = (expression or "").lower()

    # PostgreSQL may add redundant text/varchar casts and formatting.
    # Ignore formatting-only differences while preserving numeric casts
    # and the actual semantic meaning of the constraint.
    value = re.sub(
        r"::(?:character varying|text)(?:\[\])?",
        "",
        value,
    )
    value = re.sub(r"\s+", "", value)

    while value.startswith("(") and value.endswith(")"):
        value = value[1:-1]

    return value


def audit(connection):
    expected = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "docs"
            / "schema_contract.json"
        ).read_text(encoding="utf-8")
    )

    inspector = inspect(connection)
    problems = []

    for table, contract in expected.items():
        if not inspector.has_table(table):
            problems.append(f"{table}: missing table")
            continue

        actual = {
            column["name"]: column
            for column in inspector.get_columns(table)
        }

        for column in contract["columns"]:
            current = actual.get(column["name"])

            if not current:
                problems.append(
                    f"{table}.{column['name']}: missing column"
                )
                continue

            current_definition = (
                str(current["type"]),
                current["nullable"],
                getattr(current["type"], "timezone", False),
                current["default"],
            )

            expected_definition = (
                column["type"],
                column["nullable"],
                column["timezone"],
                column["default"],
            )

            if current_definition != expected_definition:
                problems.append(
                    f"{table}.{column['name']}: "
                    "type/nullability/timezone/default differs"
                )

        uniques = {
            frozenset(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table)
        }

        uniques.update(
            frozenset(index["column_names"])
            for index in inspector.get_indexes(table)
            if index["unique"]
            and not index.get(
                "dialect_options",
                {},
            ).get("postgresql_where")
        )

        for columns in contract["unique_columns"]:
            if frozenset(columns) not in uniques:
                problems.append(
                    f"{table}: missing uniqueness on {columns}"
                )

        foreign_keys = inspector.get_foreign_keys(table)

        for foreign_key in contract["foreign_keys"]:
            if not any(
                all(
                    actual_fk[key] == foreign_key[key]
                    for key in foreign_key
                )
                for actual_fk in foreign_keys
            ):
                problems.append(
                    f"{table}: foreign key differs on "
                    f"{foreign_key['constrained_columns']}"
                )

        checks = {
            normalize_check(check["sqltext"])
            for check in inspector.get_check_constraints(table)
        }

        expected_checks = {
            normalize_check(value)
            for value in contract["checks"]
        }

        if not expected_checks.issubset(checks):
            problems.append(
                f"{table}: check constraints differ"
            )

        indexes = {
            index["name"]: index
            for index in inspector.get_indexes(table)
        }

        for index in contract["indexes"]:
            actual_index = indexes.get(index["name"])

            if (
                not actual_index
                or any(
                    actual_index[key] != index[key]
                    for key in (
                        "column_names",
                        "unique",
                        "dialect_options",
                    )
                )
            ):
                problems.append(
                    f"{table}: index differs: {index['name']}"
                )

    duplicate_checks = [
        (
            """
            select 1
            from workout_results
            group by workout_id, athlete_id
            having count(*) > 1
            limit 1
            """,
            "duplicate results",
        ),
        (
            """
            select 1
            from workouts
            where status in ('planned', 'active')
              and scheduled_for is not null
            group by athlete_id, scheduled_for
            having count(*) > 1
            limit 1
            """,
            "duplicate open workout dates",
        ),
    ]

    for query, label in duplicate_checks:
        if (
            not problems
            and connection.execute(text(query)).first()
        ):
            problems.append(label)

    return problems


if __name__ == "__main__":
    engine = create_engine(
        get_settings().database_url,
        connect_args={"connect_timeout": 10},
    )

    try:
        with engine.connect() as connection:
            problems = audit(connection)

        for problem in problems:
            print(problem)

        print(
            "Schema adoption preflight: "
            + (
                "FAILED; do not stamp."
                if problems
                else (
                    "PASS. Review backup and database identity "
                    "before stamping."
                )
            )
        )

        raise SystemExit(
            1 if problems else 0
        )

    except SystemExit:
        raise

    except Exception:
        raise SystemExit(
            "Schema adoption preflight could not connect/inspect; "
            "diagnostics withheld to protect credentials."
        ) from None

    finally:
        engine.dispose()