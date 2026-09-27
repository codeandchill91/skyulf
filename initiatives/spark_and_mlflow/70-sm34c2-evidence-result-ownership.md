# SM-34C2: shared evidence and result ownership

Date: 2026-09-27. Baseline: `454d2dad` plus the existing C1 changes.
Status: locally complete; committed with C1 and the Sourcery follow-up as
`e16b27e8` on 2026-09-27. Applicable commit hooks passed with DCO sign-off.
The verification details below describe the pre-commit checkpoints. Next: SM-34C3.

## Ownership map

| Operation | Owner | Callers / compatibility |
| --- | --- | --- |
| Restore persisted training JSON to validated settings | `LocalTrainingSpec.from_payload` in `local_retraining` | Lifecycle `_spec` and the candidate evidence loader |
| Download and verify a named candidate's saved comparison, model/source and filter evidence | `local_training_evidence.load_candidate_evidence` | Approval, rejection and automatic comparison; old `_load_evidence` imports retained |
| Produce typed Bundle output, operator inputs and score-handoff decision | `local_workflow.build_bundle_result` and `BundleActionResult` | Notebook runtime and durable lifecycle result phase |
| Load verified custom-step identities before spec validation | Existing task/evidence adapters | Ordering retained; spec construction requires registered custom steps |
| Parse notebook parameters and publish readable/task output | `job_runtime` | Existing notebook entrypoints |
| Enforce durable phase/finalization and task-state guards | `lifecycle_tasks` / `_lifecycle_state` | Existing lifecycle entrypoints |

The task result phase no longer imports `job_runtime`. The old
`job_runtime.BundleActionResult`, `_bundle_result` and `_next_actions` paths are
aliases to the same objects, preserving existing callers without duplicate logic.
Approval and automatic workflow import the evidence owner directly, retaining
their existing `_load_evidence` names for compatibility and caller instrumentation.

No new production module was needed. `local_training_evidence` imports the spec
class inside its loader because `local_retraining` already uses its filter
receipt builders. The type annotation uses a type-checking import. This avoids
an import-time cycle without moving the entire training model into another file.

`workflow_config` still calls the existing training-policy/settings helpers:
those interpret user configuration, whereas `from_payload` restores saved
training evidence. This slice does not merge those different contracts.

## Preserved checks and deliberate normalization

The evidence loader retains its validation order: comparison digest, requested
model/version, supported engine, fitted engine, saved project source, spec,
holdout membership, dataset identity, filter digest/populations and saved recipe.
Verified custom Python is loaded before constructing the spec, so registered
custom pre-split steps remain available to its validation.

`from_payload` copies the top-level JSON before restoring ISO dates, date parsing
settings and tuple fields; engine validation stays with the evidence loader.
Absent `pre_split_steps` means an empty recipe, matching legacy approval evidence.
The task conversion now also accepts that absent empty recipe; its immutable
request/phase digest checks still run before conversion. Other required saved
fields retain their existing requirements and validation.

Result construction retains first-candidate null champion metrics, manual
approve/reject parameters, exact rollback receipts and the configured scoring
handoff. The task adapter checks successful finalization before constructing the
shared result. No source reads, evidence checks or mutation checks were removed.

## Verification

- Before production edits, runtime/output/approval/lifecycle suites: **156 passed**.
- New shared-contract tests before implementation: **16 failed** for missing
  shared entrypoints; the same tests then **16 passed**.
- Added a first-candidate result/import compatibility test and strengthened the
  existing real lifecycle roundtrip to block notebook-module loading at result
  publication for both engines.
- Final affected suites: **496 passed**, six expected legacy-policy deprecation
  warnings, in 250.93 seconds. No skips or failures; `final.log`.
- Scoped Ruff and format checks, full Python type check and `git diff --check`
  passed. Independent read-only diff review reported no findings.

Counts overlap: the final 496 includes the 17 new contract tests and baseline
test groups. This is not 496 plus the earlier baseline/focused counts.

Local logs are under `rehearsals/sm34c2_local/` (ignored local artifacts).
The final suite covers these files in `skyulf-core/tests/integrations/`:

```text
test_databricks_evidence_contracts.py
test_databricks_local_workflow.py
test_databricks_local_retraining.py
test_databricks_local_approval.py
test_databricks_lifecycle_tasks.py
test_databricks_date_free_training.py
test_databricks_custom_eligibility.py
test_databricks_pre_split_filters.py
test_databricks_job_runtime.py
test_databricks_job_output.py
test_databricks_lifecycle_notebook.py
test_databricks_workflow_config.py
```

Command: `python -m pytest <files above> -q --tb=short -p no:cacheprovider
--basetemp=initiatives/spark_and_mlflow/rehearsals/sm34c2_local/final`.
Ruff/format checks cover the six changed production files and two changed test
files; type check is `ty check backend skyulf-core/skyulf skyulf-core/tests
run_skyulf.py celery_worker.py`. Final whitespace check: `git diff --check`.

## Scope and continuation

C1 was staged during this session; its staged content was preserved. C2 remains
uncommitted. No cloud test, deployment, commit or push was performed. Existing
persistent Databricks jobs were not updated. Templates and the visible graph
are unchanged; these are local checks, not live acceptance.

Next is SM-34C3: measure repeated reads/replay and reuse verified state within
one invocation while preserving fresh mutation checks. See
[the six-task plan](68-integration-template-simplification-plan.md).

## Sourcery review follow-up (2026-09-27)

The user requested six readability fixes before C3. Three production files were
changed, preserving the earlier ownership boundaries and import compatibility:

- Candidate evidence loading now delegates artifact reads, comparison identity
  checks and saved project recipe loading to named helpers.
- Training evidence validation delegates identity/membership and population
  counts. Structural `KeyError`/`TypeError` still become the same malformed-evidence
  error; existing `ValueError` diagnostics propagate unchanged.
- `LocalTrainingSpec.__post_init__` sequences explicit random/temporal split,
  result-filter, column, budget/sampling and digest validation methods in the
  original order.
- Lifecycle orchestration delegates completion, active-branch checks, durable
  execution and failure recording. `begin` remains outside the execution try;
  receipts precede termination, and cleanup preserves the original exception.
- Both suggested `_prepare` dictionary comprehensions now use `output |= ...`.

Physical lines, including signatures/docstrings, measured with Python AST:

| Function | Before | After |
| --- | --- | --- |
| `load_candidate_evidence` | 69 | 26 |
| `validate_training_evidence` | 63 | 23 |
| `LocalTrainingSpec.__post_init__` | 111 | 20 |
| `run_lifecycle_phase` | 135 | 69 |

These are function lengths, not repository line savings or Sourcery quality
scores. Sourcery's proprietary score was not rerun. Helpers follow complete
responsibilities rather than an arbitrary ten-line limit.

Seven added characterization cases pin validation-error precedence and malformed
or foreign filter receipts. All 24 shared-contract tests passed before extraction;
the focused evidence/date-free suites passed 51 tests after extraction. Independent
review against exact pre-follow-up snapshots reported no findings. Final affected
suite: **503 passed**, six existing legacy-policy deprecation warnings, in 246.05
seconds; no failures/skips. Ruff/format, full Python type checks and
`git diff --check` passed. The 503 includes the earlier 496 plus seven new cases.

Snapshots and logs: `rehearsals/sm34c2_review/`. The final command uses the same
12 test files listed above, with its isolated `final` basetemp. No cloud action,
commit or push; C3 replay measurement remains the next task.
