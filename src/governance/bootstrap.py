"""Account-level setup. Runs once, under an identity that may create tags.

Governed tags are account objects: one definition serves every catalogue in the
account. Environment deploys consume them and must never be able to create them.
"""
from __future__ import annotations

import json
import subprocess
import sys

from . import config
from .dbx import SqlError, Warehouse


def _groups_needed(matrix: dict) -> list[str]:
    groups = [role["group"] for role in matrix["roles"].values()]
    return groups + list(matrix.get("exempt", []))


def _ensure_group(profile: str, name: str) -> str:
    existing = subprocess.run(
        ["databricks", "groups", "list", "-p", profile, "-o", "json"],
        capture_output=True, text=True,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        payload = json.loads(existing.stdout)
        found = payload if isinstance(payload, list) else payload.get("Resources", [])
        for group in found:
            if group.get("displayName") == name:
                return "exists"
    made = subprocess.run(
        ["databricks", "groups", "create", "--display-name", name, "-p", profile, "-o", "json"],
        capture_output=True, text=True,
    )
    return "created" if made.returncode == 0 else f"failed: {made.stderr.strip()[:80]}"


def main() -> int:
    settings = config.settings()
    warehouse = Warehouse(settings["profile"], settings["warehouse_id"])

    print("governed tags")
    for key, spec in config.tags().items():
        values = ", ".join(f"'{value}'" for value in spec["values"])
        try:
            warehouse.sql(f"CREATE GOVERNED TAG {key} VALUES ({values})")
            print(f"  created  {key}: {spec['values']}")
        except SqlError as error:
            if "already exists" in str(error).lower():
                print(f"  exists   {key}")
            else:
                print(f"  FAILED   {key}: {error}")
                return 1

    print("\ngroups")
    for group in _groups_needed(config.matrix()):
        print(f"  {_ensure_group(settings['profile'], group):8} {group}")

    print("\nA governed tag is usable for tagging immediately, but takes a little")
    print("longer to become usable inside a policy condition. `make deploy` retries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
