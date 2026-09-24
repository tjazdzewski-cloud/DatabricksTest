"""CI gate. Fails the pull request before anything reaches the workspace.

Checks that every column declares a governed sensitivity, that a column which
can be masked also says what the mask should look like, and that every value
used anywhere exists in the account tag definitions.
"""
from __future__ import annotations

import sys

from . import config


def main() -> int:
    tags = config.tags()
    matrix = config.matrix()
    masks = config.masks()["shapes"]

    sensitivities = set(tags["sensitivity"]["values"])
    shapes = set(tags["mask_shape"]["values"])
    governed = set(matrix["default"])
    problems: list[str] = []

    for shape in shapes:
        if shape not in masks:
            problems.append(f"governance/catalog/masks.yml: no expression for mask_shape '{shape}'")

    for name, role in matrix["roles"].items():
        for sensitivity in governed:
            level = role.get(sensitivity)
            if level not in matrix["levels"]:
                problems.append(f"access_matrix.yml: role '{name}' has no valid level for '{sensitivity}'")

    for path, contract in config.contracts():
        for column, spec in contract["columns"].items():
            where = f"{path}:{column}"
            sensitivity = spec.get("sensitivity")
            if sensitivity is None:
                problems.append(f"{where}: no sensitivity. Every column declares one.")
                continue
            if sensitivity not in sensitivities:
                problems.append(f"{where}: sensitivity '{sensitivity}' is not a governed value")
            if sensitivity in governed:
                shape = spec.get("mask_shape")
                if shape is None:
                    problems.append(f"{where}: sensitivity '{sensitivity}' is masked for someone, so it needs a mask_shape")
                elif shape not in shapes:
                    problems.append(f"{where}: mask_shape '{shape}' is not a governed value")

    if problems:
        print("contracts rejected:\n")
        for problem in problems:
            print(f"  - {problem}")
        print()
        return 1

    columns = sum(len(c["columns"]) for _, c in config.contracts())
    print(f"contracts ok: {len(config.contracts())} table(s), {columns} columns, every one classified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
