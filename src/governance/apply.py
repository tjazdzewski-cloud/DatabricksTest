"""Everything that touches the workspace. One verb per command."""
from __future__ import annotations

import pathlib
import sys
import time

from . import config, generate
from .dbx import SqlError, Warehouse


def _wh() -> tuple[Warehouse, dict]:
    settings = config.settings()
    return Warehouse(settings["profile"], settings["warehouse_id"]), settings


def _literal(value, column_type: str) -> str:
    upper = column_type.upper()
    if upper.startswith("DATE"):
        return f"DATE'{value}'"
    if upper.startswith(("DECIMAL", "INT", "BIGINT", "DOUBLE", "FLOAT")):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def seed() -> int:
    warehouse, settings = _wh()
    catalog, schema, gov = settings["catalog"], settings["schema"], settings["gov_schema"]
    warehouse.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    warehouse.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{gov}")

    for path, contract in config.contracts():
        table = f"{catalog}.{schema}.{contract['table']}"
        columns = contract["columns"]
        ddl = ", ".join(f"{name} {spec['type']}" for name, spec in columns.items())
        warehouse.sql(f"CREATE OR REPLACE TABLE {table} ({ddl})")
        types = [spec["type"] for spec in columns.values()]
        rows = []
        for row in contract.get("sample_rows", []):
            rows.append("(" + ", ".join(_literal(v, t) for v, t in zip(row, types)) + ")")
        if rows:
            warehouse.sql(f"INSERT INTO {table} VALUES " + ", ".join(rows))
        warehouse.sql(f"ALTER TABLE {table} SET TAGS ('classification' = 'verified')")
        print(f"seeded {table}  ({len(rows)} rows)  from {path}")
    return 0


def _run_file(warehouse: Warehouse, name: str, retries: int = 6) -> None:
    text = (config.ROOT / "build" / name).read_text()
    for attempt in range(retries):
        try:
            warehouse.script(text)
            print(f"  applied build/{name}")
            return
        except SqlError as error:
            if "Unknown tag policy key" in str(error) and attempt < retries - 1:
                print(f"  build/{name}: tag not visible to the policy compiler yet, retrying")
                time.sleep(20)
                continue
            raise


def deploy() -> int:
    warehouse, _ = _wh()
    generate.main()
    print("\nfunctions")
    _run_file(warehouse, "010_functions.sql")
    print("\ncolumn tags")
    from . import reconcile_tags
    if reconcile_tags.main(["--apply"]) != 0:
        return 1
    print("\npolicies")
    _run_file(warehouse, "020_policies.sql")
    print("\nTags are reconciled before the policies go on. The other order leaves a")
    print("window where a policy is live and its columns are still untagged.")
    return 0


def show() -> int:
    warehouse, settings = _wh()
    catalog, schema = settings["catalog"], settings["schema"]
    for _, contract in config.contracts():
        table = contract["table"]
        columns = list(contract["columns"])
        rows = warehouse.sql(
            f"SELECT {', '.join(columns)} FROM {catalog}.{schema}.{table} ORDER BY 1"
        )
        widths = [
            max([len(str(name))] + [len(str(row[i])) for row in rows])
            for i, name in enumerate(columns)
        ]
        print("  " + "  ".join(c.ljust(w) for c, w in zip(columns, widths)))
        print("  " + "  ".join("-" * w for w in widths))
        for row in rows:
            print("  " + "  ".join(str(v).ljust(w) for v, w in zip(row, widths)))
        if not rows:
            print(f"  no rows. {table} is blocked, not empty.")
    return 0


def whoami() -> int:
    warehouse, settings = _wh()
    matrix = config.matrix()
    groups = [r["group"] for r in matrix["roles"].values()] + list(matrix.get("exempt", []))
    checks = ", ".join(
        f"is_member('{g}') AS ws_{g}, is_account_group_member('{g}') AS acct_{g}" for g in groups
    )
    rows = warehouse.sql(f"SELECT current_user() AS me, {checks}")
    names = ["me"] + [f"{kind}:{g}" for g in groups for kind in ("workspace", "account")]
    for name, value in zip(names, rows[0]):
        print(f"  {name:28} {value}")
    print(f"\n  policies are generated with {settings['member_fn']}()")
    return 0


def gate_on() -> int:
    warehouse, settings = _wh()
    _run_file(warehouse, "030_gate.sql")
    catalog, schema = settings["catalog"], settings["schema"]
    for _, contract in config.contracts():
        warehouse.sql(
            f"ALTER TABLE {catalog}.{schema}.{contract['table']} "
            "SET TAGS ('classification' = 'unverified')"
        )
    print("  every table marked unverified: a reader now gets zero rows")
    return 0


def gate_off() -> int:
    warehouse, settings = _wh()
    catalog, schema = settings["catalog"], settings["schema"]
    for _, contract in config.contracts():
        warehouse.sql(
            f"ALTER TABLE {catalog}.{schema}.{contract['table']} "
            "SET TAGS ('classification' = 'verified')"
        )
    print("  every table marked verified: blocking stops, masking takes over")
    return 0


def conflict() -> int:
    warehouse, settings = _wh()
    catalog, schema, gov = settings["catalog"], settings["schema"], settings["gov_schema"]
    warehouse.sql(
        f"CREATE OR REPLACE FUNCTION {catalog}.{gov}.mask_other(val VARIANT, shape STRING) "
        "RETURNS VARIANT RETURN '### conflict ###'::VARIANT"
    )
    warehouse.sql(
        f"CREATE OR REPLACE POLICY mask_conflict ON SCHEMA {catalog}.{schema} "
        f"COLUMN MASK {catalog}.{gov}.mask_other TO `account users` FOR TABLES "
        "MATCH COLUMNS has_tag_value('sensitivity', 'restricted') AS c ON COLUMN c "
        "USING COLUMNS (get_column_tag_value(c, 'mask_shape'))"
    )
    print("  second policy created. It deployed cleanly - that is the point.")
    try:
        show()
        print("  (no error - unexpected)")
    except SqlError as error:
        print(f"\n  read failed: {error}"[:400])
    warehouse.sql(f"DROP POLICY mask_conflict ON SCHEMA {catalog}.{schema}")
    print("\n  conflicting policy dropped")
    return 0


def teardown() -> int:
    warehouse, settings = _wh()
    catalog, schema, gov = settings["catalog"], settings["schema"], settings["gov_schema"]
    for sensitivity in config.matrix()["default"]:
        try:
            warehouse.sql(f"DROP POLICY mask_{sensitivity} ON SCHEMA {catalog}.{schema}")
        except SqlError:
            pass
    for name in ("block_unverified", "mask_conflict"):
        try:
            warehouse.sql(f"DROP POLICY {name} ON SCHEMA {catalog}.{schema}")
        except SqlError:
            pass
    warehouse.sql(f"DROP SCHEMA IF EXISTS {catalog}.{schema} CASCADE")
    warehouse.sql(f"DROP SCHEMA IF EXISTS {catalog}.{gov} CASCADE")
    print("  demo schemas and policies removed. Governed tags are account objects and stay.")
    return 0


COMMANDS = {
    "seed": seed, "deploy": deploy, "show": show, "whoami": whoami,
    "gate-on": gate_on, "gate-off": gate_off, "conflict": conflict, "teardown": teardown,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: python -m src.governance.apply {" + "|".join(COMMANDS) + "}")
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]]())
