# Narration

Roughly two and a half minutes at a normal speaking pace. Structure and several
lines are Codex's; the cuts and the measured numbers are from the recorded run.

## 1. The contract gate

Before anything reaches the workspace, the contracts are checked. Every column must declare how sensitive it is, and anything that can be masked must say what the mask looks like. This runs in continuous integration. It proves the paperwork is complete. It does not yet prove that access control works.

## 2. The rules

One file decides who sees what. It maps a role against a sensitivity and gives a level: clear, partial, or masked. Anyone with no role listed falls through to masked. Public and internal columns carry no policy at all; for those, a read grant is enough.

## 3. Before

This is the table with nothing over it. Two investors, their email addresses, their commitments. Policies attach to the schema rather than the table, so they outlive a table being rebuilt. The demo drops them first, otherwise this shot would quietly still be the after.

## 4. Deploying the mechanism

Functions first, then the column tags, then the policies. That order is not cosmetic. A policy finds its columns by tag, so if it goes on before the tags are reconciled, there is a window where it is live and protecting nothing.

## 5. Four readers, one query

Now the same query, on the same table, read by four different people. Full access sees the address. An analyst sees the domain but not the person. A consumer sees an initial, a null, and a commitment rounded to the nearest thousand. With no role, almost nothing. Watch the waits. Every group change took about five minutes to reach the query engine, because it refreshes on a schedule rather than on demand. An elevation expiring is no prompter than one being granted.

## 6. Data nobody has reviewed

A table nobody has reviewed returns no rows at all. It is blocked, not empty. Once a steward marks it verified, the rows come back and masking takes over. Review decides whether you get rows. The role decides what is in them.

## 7. A deployment that passes and still fails

Here two policies resolve to different masks on the same column. Both deploy without an error. The failure appears only when somebody reads the table. A green deployment is not evidence that access control works, which is why reading as a real identity is not an optional step.

## 8. What never moved

Nothing in the stored data changed across any of this. The values were never rewritten. Only the rule above them changed, and that rule lives in a pull request where somebody reviews it, rather than in a console session nobody can see.
