"""Load the governance contracts and the handful of environment settings."""
from __future__ import annotations

import os
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def settings() -> dict:
    warehouse = os.environ.get("DATABRICKS_WAREHOUSE_ID")
    if not warehouse:
        raise SystemExit("DATABRICKS_WAREHOUSE_ID is not set. Copy .env.example to .env and source it.")
    return {
        "profile": os.environ.get("DATABRICKS_PROFILE", "dbx-test"),
        "warehouse_id": warehouse,
        "catalog": os.environ.get("DEMO_CATALOG", "workspace"),
        "schema": os.environ.get("DEMO_SCHEMA", "governance_demo"),
        "gov_schema": os.environ.get("GOV_SCHEMA", "governance"),
        # is_account_group_member is correct for account groups. On a trial
        # workspace with workspace-local groups, is_member is the one that
        # resolves. `make whoami` tells you which.
        "member_fn": os.environ.get("MEMBER_FN", "is_account_group_member"),
        # How a role that reads `clear` is let through.
        #   except   - the group is listed in the policy's EXCEPT clause. Correct,
        #              and what production should use. Needs ACCOUNT-level groups:
        #              a workspace-local group is not a principal Unity Catalog
        #              can see, and policy creation fails with PRINCIPAL_DOES_NOT_EXIST.
        #   function - the group becomes a branch in the masking function that
        #              returns the value untouched. Works with workspace-local
        #              groups, which is all a trial workspace has.
        "clear_via": os.environ.get("CLEAR_VIA", "except"),
    }


def _load(relative: str) -> dict:
    return yaml.safe_load((ROOT / relative).read_text())


def tags() -> dict:
    return _load("governance/account/tags.yml")["tags"]


def matrix() -> dict:
    return _load("governance/catalog/access_matrix.yml")


def masks() -> dict:
    return _load("governance/catalog/masks.yml")


def contracts() -> list[tuple[str, dict]]:
    found = []
    for path in sorted((ROOT / "models").rglob("*.yml")):
        found.append((str(path.relative_to(ROOT)), yaml.safe_load(path.read_text())))
    return found
