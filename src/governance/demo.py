"""The whole narrative, in order. Run it, record it, or read the transcript.

Roughly seven minutes, most of it waiting for group membership to reach the
query engine - which is itself one of the things worth showing.
"""
from __future__ import annotations

import sys

from . import apply, config, roles, validate


def heading(number: str, title: str, point: str) -> None:
    print(f"\n{'=' * 78}\n{number}  {title}\n{'-' * 78}\n{point}\n")


def main() -> int:
    matrix = config.matrix()

    heading("1.", "The contract gate",
            "Every column declares a sensitivity. A column that can be masked also\n"
            "says what the mask looks like. This runs in CI, before the workspace.")
    if validate.main() != 0:
        return 1

    heading("2.", "The rules, in one file",
            "role x sensitivity -> level. Nothing else decides who sees what.")
    for role, spec in matrix["roles"].items():
        levels = ", ".join(f"{k}={v}" for k, v in spec.items() if k != "group")
        print(f"  {role:12} ({spec['group']:16}) {levels}")
    print(f"  {'default':12} {'':18} " + ", ".join(f"{k}={v}" for k, v in matrix["default"].items()))
    print("\n  public and internal carry no policy: a read grant is enough.")

    heading("3.", "Before",
            "Two rows, five columns, no policy over them. Policies live on the schema\n"
            "and outlive the table, so this drops them first - otherwise 'before'\n"
            "would quietly still be 'after'.")
    apply.drop_policies()
    apply.seed()
    apply.show()

    heading("4.", "Deploy the mechanism",
            "Functions, then column tags, then policies. That order matters: the\n"
            "other one leaves a window where a policy is live and its columns are\n"
            "still untagged, which reads as clear data.")
    if apply.deploy() != 0:
        return 1

    heading("5.", "The same table, read by three different people",
            "Nothing about the data changes between these reads. Only who is asking.")
    for role in ("full_access", "analyst", "consumer", "none"):
        label = role if role != "none" else "no role at all"
        print(f"\n  --- as {label} ---")
        roles.use(role)
        apply.show()

    heading("6.", "A table nobody has reviewed",
            "Classification is a tag like any other. Unverified means zero rows,\n"
            "not raw values, so an unreviewed table is dark rather than open.")
    apply.gate_on()
    apply.show()
    print()
    apply.gate_off()
    apply.show()

    heading("7.", "The failure mode worth knowing",
            "Two policies resolving to different masks on one column. Both deploy\n"
            "cleanly. The error arrives when somebody reads - which is why reading\n"
            "as real identities is not an optional test step.")
    apply.conflict()

    print(f"\n{'=' * 78}\nDone. `make teardown` removes the demo schemas.")
    print("Governed tags are account objects and stay where they are.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
