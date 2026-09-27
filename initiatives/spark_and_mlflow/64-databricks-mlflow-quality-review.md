# Databricks and MLflow integration quality review

Date: 2026-09-26. Baseline: `d5d2398d`, branch `090`.
Status: DONE for the documented review/fix scope; independent review approved.

The requested H2/H3 delivery was committed first, with 289 affected tests,
strict documentation and all applicable hooks passing. Two independent
read-only reviews examined the Databricks and MLflow folders. Standard Ruff
and format checks pass across their 31 modules. A stricter diagnostic McCabe
threshold of 15 identifies 14 complex functions; that is a maintenance signal,
not evidence of 14 bugs or a new repository-wide quality gate.

## Confirmed fixes

1. `LocalSourceSpec` must compare UTC instants across DST folds. Its existing
   wall-clock comparison rejects a valid repeated-hour interval and accepts
   the reverse. Preserve the existing nonexistent-local-time checks.
2. Controlled champion selection must verify the referenced committed event,
   not only the registered-model marker. Initial, promotion and rollback
   receipts remain valid; challenger/rejection/history semantics stay separate.
3. Concurrent first use of an MLflow experiment must handle the specific
   already-exists race with one lookup. Other failures must still propagate.
4. Registry concrete versions must be positive integers or positive ASCII
   decimal strings; reject negative, nonnumeric, stage-like or bool selectors
   before MLflow imports and remote calls.
5. Registry URI type validation must precede Unity Catalog string operations,
   producing the intended actionable ValueError for malformed arguments.

## Readability scope

Extract ordered pre-split application and survivor-preservation checks from
`split_labeled_snapshot` into cohesive private helpers in the same module.
Keep raw feature recovery, final partitioning and evidence construction in the
orchestrator. Preserve validation order, exact evidence and once-only replay.
Do not introduce a second node executor, a new registry or broad class layers.

Do not reorganize all modules to meet an arbitrary ten-line rule. In particular,
alias pending-state/recovery and rollback are tightly coupled, and upcoming
SM-34 modifies the workflow/window contracts. Larger style-only changes need
separate justification. The already-completed fixed_columns extraction remains.

## Verification and boundaries

Each correctness fix needs a focused failing regression followed by the fix.
Cover valid and malformed champion receipts, deterministic experiment creation
races and unchanged permission/network failure propagation. Run affected local
MLflow, date/SDK, pre-split/custom, approval and training suites; then scoped
Ruff/format, full ty and a scoped independent review. No additional cloud run,
deployment or commit is implied by the quality review. Continue SM-34 after
the verified local fixes and review are complete.

## Local results

Five defects reproduced in focused tests: 27 failures before the changes,
followed by 46 passing cases. The affected integration suite passed 428 tests;
one optional Spark test skipped because pyspark is not installed. Five existing
policy deprecation warnings remain. Six focused experiment-creation tests also
passed, including two supplemental connection/timeout propagation cases.
Full ty, scoped Ruff/format and whitespace checks passed.

The pre-split extraction reduces diagnostic McCabe complexity of
`split_labeled_snapshot` from 47 to 25; its three helpers score 12, 7 and 6.
This is a readability improvement, not a claim about a new Sourcery score.
No cloud run or deployment was performed for these changes.

Independent review found no correctness, regression or scope issues. It ran
48 focused fix regressions and 22 pre-split/custom invariants successfully.
These overlap the integration suite and are not an additional coverage total.
SM-34 can proceed. Broader style-only module restructuring remains deferred.
