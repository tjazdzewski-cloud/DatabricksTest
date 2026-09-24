# Column-level data governance, as code

A working demo of the mechanism: **the organisation defines its own tags, the
tags decide what each person sees, and all of it is deployed from YAML in this
repository.** Nothing is clicked in the workspace.

Everything here runs against one Databricks workspace. Workspace-catalogue
bindings — the other half of the design, which separates environments — are not
demonstrated, because that needs more than one workspace.

## What is where

| Path | What it is |
| --- | --- |
| `governance/account/tags.yml` | The governed tags. Account scope, one definition for the whole estate. |
| `governance/catalog/access_matrix.yml` | role × sensitivity → level. The only place the rules are written. |
| `governance/catalog/masks.yml` | What each level looks like, per shape. |
| `models/silver/investors.yml` | A table contract. Two tag lines per column, and nothing else. |
| `src/governance/` | validate, bootstrap, generate, reconcile, apply. |
| `build/` | Generated SQL. Never edited, never committed. |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env && source .env
make whoami
```

## The demo, in order

Each step is one command and one idea.

**1. The contract gate.** `make validate`

Every column must declare a sensitivity, and anything that can be masked must
say what the mask looks like. Delete a `sensitivity:` line from
`models/silver/investors.yml` and run it again: the pull request fails before
anything reaches the workspace.

**2. Account setup.** `make bootstrap`

Creates the governed tags and the groups. This is the only step that needs an
account-level identity; environment deploys must never be able to create tags.
A new tag is usable for tagging immediately but takes a little longer to become
usable inside a policy, so `make deploy` retries.

**3. Some data.** `make seed` then `make show`

Two rows, five columns, clear. This is the "before".

**4. The mechanism.** `make deploy` then `make show`

Functions, then column tags, then policies — in that order, because the other
one leaves a window where a policy is live and its columns are still untagged.
The same rows now read differently, and the table was never modified. Only the
rule above it changed.

**5. Who you are changes what you see.** Edit the level in
`access_matrix.yml` — give `consumer` `clear` instead of `partial` — then
`make deploy && make show`. One line in one file, and the value changes.

**6. The classification gate.** `make gate-on` then `make show`

A table nobody has reviewed returns zero rows rather than raw values. Then
`make gate-off` and read again: blocking stops, masking takes over.

**7. The failure mode worth knowing.** `make conflict`

Two policies resolving to different masks on one column. Both deploy cleanly.
The error appears only when somebody reads the table — which is why the identity
tests in step 4 are not optional.

**8. Clean up.** `make teardown`

## Two things the demo proves that documentation does not

A table owner, even an account admin, is masked like everyone else. Ownership is
not an exemption, which is why a pipeline identity has to be listed in `EXCEPT`
or it reads masked values and writes them permanently into the layer below.

One masking function must take and return `VARIANT`. A `STRING`-returning
function over a `DECIMAL` column fails at read time with `CAST_INVALID_INPUT`,
in front of the user, not at deploy.
