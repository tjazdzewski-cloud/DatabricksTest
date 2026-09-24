"""Compare the column contracts against the tags actually in the catalogue.

Two different jobs. Tags the contract declares are applied. Columns that exist
in the catalogue but appear in no contract are drift: the run fails rather than
guessing, because an unclassified column is readable.
"""
from __future__ import annotations

import sys

from . import config
from .dbx import Warehouse

GOVERNED = ("sensitivity", "mask_shape")


def desired() -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for _, contract in config.contracts():
        table = contract["table"]
        for column, spec in contract["columns"].items():
            wanted = {tag: spec[tag] for tag in GOVERNED if tag in spec}
            out[(table, column)] = wanted
    return out


def live(warehouse: Warehouse, settings: dict) -> tuple[dict, set]:
    catalog, schema = settings["catalog"], settings["schema"]
    tags: dict[tuple[str, str], dict[str, str]] = {}
    rows = warehouse.sql(
        f"SELECT table_name, column_name, tag_name, tag_value "
        f"FROM {catalog}.information_schema.column_tags WHERE schema_name = '{schema}'"
    )
    for table, column, tag, value in rows:
        tags.setdefault((table, column), {})[tag] = value

    columns = {
        (table, column)
        for table, column in warehouse.sql(
            f"SELECT table_name, column_name FROM {catalog}.information_schema.columns "
            f"WHERE table_schema = '{schema}'"
        )
    }
    return tags, columns


def main(argv: list[str]) -> int:
    apply_changes = "--apply" in argv
    settings = config.settings()
    warehouse = Warehouse(settings["profile"], settings["warehouse_id"])
    catalog, schema = settings["catalog"], settings["schema"]

    want = desired()
    have, live_columns = live(warehouse, settings)

    drift = sorted(live_columns - set(want))
    plan: list[str] = []

    for (table, column), wanted in sorted(want.items()):
        if (table, column) not in live_columns:
            continue
        current = have.get((table, column), {})
        changes = {tag: value for tag, value in wanted.items() if current.get(tag) != value}
        if changes:
            pairs = ", ".join(f"'{tag}' = '{value}'" for tag, value in changes.items())
            plan.append(
                f"ALTER TABLE {catalog}.{schema}.{table} ALTER COLUMN {column} SET TAGS ({pairs})"
            )

    if plan:
        print(f"{len(plan)} tag change(s):")
        for statement in plan:
            print(f"  {statement}")
    else:
        print("column tags already match the contracts")

    if drift:
        print("\ncolumns in the catalogue that no contract classifies:")
        for table, column in drift:
            print(f"  {table}.{column}")
        print("\nThese read clear. Classify them or drop them; the deploy stops here.")
        return 1

    if apply_changes:
        for statement in plan:
            warehouse.sql(statement)
        if plan:
            print("\napplied")
    elif plan:
        print("\ndry run. Pass --apply to write these.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
