"""Move the current user between the demo roles, and wait until it takes effect.

The waiting is not an accident of the demo. Group membership reaches the query
engine on a refresh schedule, so granting a role and expiring one are both
delayed. This is the same delay that makes a time-bound elevation imperfect.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

from . import config
from .dbx import Warehouse


def _cli(profile: str, *args: str) -> dict:
    proc = subprocess.run(["databricks", *args, "-p", profile, "-o", "json"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def _me(profile: str) -> str:
    return _cli(profile, "current-user", "me")["id"]


def _groups(profile: str) -> dict[str, str]:
    payload = _cli(profile, "groups", "list")
    found = payload if isinstance(payload, list) else payload.get("Resources", [])
    return {g["displayName"]: g["id"] for g in found}


def _set_member(profile: str, group_id: str, user_id: str, member: bool) -> None:
    operation = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
        "Operations": [
            {"op": "add", "path": "members", "value": [{"value": user_id}]}
            if member
            else {"op": "remove", "path": f'members[value eq "{user_id}"]'}
        ],
    }
    subprocess.run(
        ["databricks", "api", "patch", f"/api/2.0/preview/scim/v2/Groups/{group_id}",
         "-p", profile, "--json", json.dumps(operation)],
        capture_output=True, text=True,
    )


def use(role: str) -> int:
    settings = config.settings()
    matrix = config.matrix()
    wanted_group = None
    if role != "none":
        if role not in matrix["roles"]:
            print(f"unknown role '{role}'. Roles: {', '.join(matrix['roles'])}, none")
            return 2
        wanted_group = matrix["roles"][role]["group"]

    profile = settings["profile"]
    user_id = _me(profile)
    groups = _groups(profile)
    demo_groups = [r["group"] for r in matrix["roles"].values()]

    for name in demo_groups:
        if name in groups:
            _set_member(profile, groups[name], user_id, member=(name == wanted_group))

    label = wanted_group or "no role at all"
    print(f"  membership set to: {label}")

    warehouse = Warehouse(profile, settings["warehouse_id"])
    checks = ", ".join(f"{settings['member_fn']}('{g}')" for g in demo_groups)
    started = time.time()
    while time.time() - started < 300:
        row = warehouse.sql(f"SELECT {checks}")[0]
        live = {g: v for g, v in zip(demo_groups, row)}
        if all((value == "true") == (name == wanted_group) for name, value in live.items()):
            print(f"  visible to the query engine after {int(time.time() - started)}s")
            return 0
        time.sleep(15)

    print("  still not visible after 300s - membership reaches the engine on a refresh schedule")
    return 1


if __name__ == "__main__":
    sys.exit(use(sys.argv[1] if len(sys.argv) > 1 else "none"))
