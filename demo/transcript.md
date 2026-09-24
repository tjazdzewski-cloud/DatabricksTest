# Demo transcript

A real run against a Databricks workspace, captured with `asciinema rec` while
`make demo` executed. Nothing below is edited, and the same run is playable as
`demo/demo.cast`.

The waits between roles are real: group membership reaches the query engine on a
refresh schedule, which is the same delay that makes a time-bound elevation
imperfect.

```

==============================================================================
1.  The contract gate
------------------------------------------------------------------------------
Every column declares a sensitivity. A column that can be masked also
says what the mask looks like. This runs in CI, before the workspace.

contracts ok: 1 table(s), 5 columns, every one classified

==============================================================================
2.  The rules, in one file
------------------------------------------------------------------------------
role x sensitivity -> level. Nothing else decides who sees what.

  full_access  (poc_full_access ) confidential=clear, restricted=clear
  analyst      (poc_analyst     ) confidential=clear, restricted=partial
  consumer     (poc_consumer    ) confidential=partial, restricted=masked
  default                         confidential=masked, restricted=masked

  public and internal carry no policy: a read grant is enough.

==============================================================================
3.  Before
------------------------------------------------------------------------------
Two rows, five columns, nothing applied yet.

seeded workspace.governance_demo.investors  (2 rows)  from models/silver/investors.yml
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1

  investor_id  investor_name  investor_email   commitment_usd  snapshot_date
  -----------  -------------  ---------------  --------------  -------------
  I-1          Jane Doe       ***@yale.edu     1250000.00      2026-09-24   
  I-2          John Roe       ***@example.com  875500.50       2026-09-24   

==============================================================================
4.  Deploy the mechanism
------------------------------------------------------------------------------
Functions, then column tags, then policies. That order matters: the
other one leaves a window where a policy is live and its columns are
still untagged, which reads as clear data.

wrote build/010_functions.sql  (28 lines)
wrote build/020_policies.sql  (18 lines)
wrote build/030_gate.sql  (9 lines)

functions
  applied build/010_functions.sql

column tags
column tags already match the contracts

policies
  applied build/020_policies.sql

Tags are reconciled before the policies go on. The other order leaves a
window where a policy is live and its columns are still untagged.

==============================================================================
5.  The same table, read by three different people
------------------------------------------------------------------------------
Nothing about the data changes between these reads. Only who is asking.


  --- as full_access ---
  membership set to: poc_full_access
  visible to the query engine after 117s
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1

  investor_id  investor_name  investor_email        commitment_usd  snapshot_date
  -----------  -------------  --------------------  --------------  -------------
  I-1          Jane Doe       jane.doe@yale.edu     1250000.00      2026-09-24   
  I-2          John Roe       john.roe@example.com  875500.50       2026-09-24   

  --- as analyst ---
  membership set to: poc_analyst
  visible to the query engine after 300s
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1

  investor_id  investor_name  investor_email   commitment_usd  snapshot_date
  -----------  -------------  ---------------  --------------  -------------
  I-1          Jane Doe       ***@yale.edu     1250000.00      2026-09-24   
  I-2          John Roe       ***@example.com  875500.50       2026-09-24   

  --- as consumer ---
  membership set to: poc_consumer
  visible to the query engine after 300s
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1

  investor_id  investor_name  investor_email  commitment_usd  snapshot_date
  -----------  -------------  --------------  --------------  -------------
  I-1          J.             None            1250000.00      2026-09-24   
  I-2          J.             None            876000.00       2026-09-24   

  --- as no role at all ---
  membership set to: no role at all
  visible to the query engine after 301s
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1

  investor_id  investor_name  investor_email  commitment_usd  snapshot_date
  -----------  -------------  --------------  --------------  -------------
  I-1          None           None            None            2026-09-24   
  I-2          None           None            None            2026-09-24   

==============================================================================
6.  A table nobody has reviewed
------------------------------------------------------------------------------
Classification is a tag like any other. Unverified means zero rows,
not raw values, so an unreviewed table is dark rather than open.

  applied build/030_gate.sql
  every table marked unverified: a reader now gets zero rows
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1

  investor_id  investor_name  investor_email  commitment_usd  snapshot_date
  -----------  -------------  --------------  --------------  -------------
  no rows. investors is blocked, not empty.

  every table marked verified: blocking stops, masking takes over
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1

  investor_id  investor_name  investor_email  commitment_usd  snapshot_date
  -----------  -------------  --------------  --------------  -------------
  I-1          None           None            None            2026-09-24   
  I-2          None           None            None            2026-09-24   

==============================================================================
7.  The failure mode worth knowing
------------------------------------------------------------------------------
Two policies resolving to different masks on one column. Both deploy
cleanly. The error arrives when somebody reads - which is why reading
as real identities is not an optional test step.

  second policy created. It deployed cleanly - that is the point.
  $ SELECT investor_id, investor_name, investor_email, commitment_usd, snapshot_date FROM workspace.governance_demo.investors ORDER BY 1


  read failed: [COLUMN_MASKS_FEATURE_NOT_SUPPORTED.MULTIPLE_MASKS] Column mask policies for `workspace`.`governance_demo`.`investors` are not supported: Table `workspace`.`governance_demo`.`investors` has access control policies resulting in multiple column masks `ColumnMask(investor_email,List(workspace, governance, mask_restricted),Vector(PolicyFunctionArgument(unresolved,'email')),None)`, `Col

  conflicting policy dropped

==============================================================================
Done. `make teardown` removes the demo schemas.
Governed tags are account objects and stay where they are.
```
