"""Run SQL on a Databricks SQL warehouse through the Statement Execution API.

Uses the Databricks CLI for auth so this file never handles a token.
"""
from __future__ import annotations

import json
import subprocess
import time


class SqlError(RuntimeError):
    """A statement reached the warehouse and the warehouse refused it."""


class Warehouse:
    def __init__(self, profile: str, warehouse_id: str) -> None:
        self.profile = profile
        self.warehouse_id = warehouse_id

    def _cli(self, *args: str) -> dict:
        proc = subprocess.run(
            ["databricks", *args, "-p", self.profile],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "databricks CLI failed")
        return json.loads(proc.stdout) if proc.stdout.strip() else {}

    def sql(self, statement: str, timeout: int = 240) -> list[list]:
        body = {
            "warehouse_id": self.warehouse_id,
            "statement": statement,
            "wait_timeout": "30s",
            "on_wait_timeout": "CONTINUE",
        }
        res = self._cli("api", "post", "/api/2.0/sql/statements", "--json", json.dumps(body))
        statement_id = res["statement_id"]
        started = time.time()
        while res.get("status", {}).get("state") in ("PENDING", "RUNNING"):
            if time.time() - started > timeout:
                raise TimeoutError(f"statement {statement_id} still running after {timeout}s")
            time.sleep(2)
            res = self._cli("api", "get", f"/api/2.0/sql/statements/{statement_id}")

        state = res.get("status", {}).get("state")
        if state != "SUCCEEDED":
            message = res.get("status", {}).get("error", {}).get("message") or state
            raise SqlError(" ".join(str(message).split()))
        return res.get("result", {}).get("data_array") or []

    def script(self, sql_text: str) -> None:
        """Run a file of statements separated by a line containing only `;`."""
        for statement in split_statements(sql_text):
            self.sql(statement)


def split_statements(sql_text: str) -> list[str]:
    out, buf = [], []
    for line in sql_text.splitlines():
        if line.strip() == ";":
            statement = "\n".join(buf).strip()
            if statement:
                out.append(statement)
            buf = []
        else:
            buf.append(line)
    tail = "\n".join(buf).strip()
    if tail:
        out.append(tail)
    return out
