# SM-34C3: remove discarded replay and reuse verified phase metadata

Date: 2026-09-27. Baseline: `e16b27e8` (C1/C2 and Sourcery follow-up, DCO signed;
all applicable commit hooks passed). C3 is locally complete and uncommitted.
No cloud run or deployment. Next: SM-34C4.

## Measured repetition

The bounded reproduction uses real isolated MLflow registries/artifacts, both
pandas and Polars, and automatic/manual approval policies. Only Spark transport
is replaced by a counted local frame read. Counters wrap real MLflow downloads
and real task evidence validation, rather than replacing their behavior.

| Group / operation | Before | After |
| --- | ---: | ---: |
| `train_register`: source reads | 2 | 2 |
| `train_register`: client artifact downloads | 12 | 12 |
| `compare_decide`: source reads | 3 | 2 |
| `compare_decide`: client artifact downloads | 27 | 25 |
| `compare_decide`: train receipt downloads | 6 | 5 |
| `compare_decide`: prepare receipt downloads | 6 | 5 |
| `compare_decide`: task filter-evidence validation calls | 4 | 3 |
| `compare_decide`: MLflow download API calls, automatic | 37 | 35 |
| `compare_decide`: MLflow download API calls, manual | 35 | 33 |

Counts match across both engines. MLflow API-call totals include calls delegated
by its client, so they overlap client downloads; do not add the two counts or
interpret them as network transfers. These are operation counts, not measured
cloud latency or memory savings. Raw local evidence is in
`rehearsals/sm34c3_local/{red.log,counts.log,operation-counts.json}`.

## Implementation and retained checks

Only `lifecycle_tasks.py` changes production behavior:

- `_load_training_evidence` retains the fresh train receipt chain, run URI,
  package digest, fitted engine/config/custom source, saved-spec equality,
  invocation pin and filter evidence checks, before reading source data.
- `_ReplayEvidence` carries those already-verified objects inside the current
  phase. It is a frozen container, not a deep-immutable cache. Its fields are
  not modified, and no instance crosses a phase or task boundary.
- `_replay` adds the source read/split and exact membership verification for
  evaluation and comparison. Comparison reuses its verified fitted metadata,
  removing the second train-receipt/prepare-chain download inside that phase.
- Decision verifies the invocation/package evidence, then calls the unchanged
  decision service. That service freshly loads registered evidence and performs
  the source replay and membership check before staging or promoting. The old
  decision-side source replay was discarded and is removed.

The evaluation phase deliberately still rereads the train receipt after model
evaluation, immediately before registration intent. This catches changes during
evaluation before a registry mutation. Thus `train_register` operation counts
stay unchanged. Training and evaluation also retain separate source reads: the
latter verifies the persisted package and population before registration.

Grouped phases still create/bind their own stores and verify the full predecessor
chain. No global or cross-task cache was added, and `_PhaseStore` is unchanged.
Repeated model/registry reads at durable phase and mutation boundaries remain
because they verify current evidence. Alias checks and final task-output gates
are unchanged.

One deliberate ordering difference: if both registered evidence and source data
are invalid during decision, registered-evidence validation can now fail first.
Both must still be valid before any alias mutation; exact failure precedence in
that doubly-invalid case is not claimed to be unchanged.

## Verification

- Four operation-count regressions failed before implementation (`3 != 2` source
  reads) and passed after it, for both engines and both promotion policies.
- Five additional guards cover a train receipt edited during evaluation and
  receipt/filter/membership/champion edits between comparison and decision in a
  grouped call. An initial test assertion was adjusted for MLflow returning an
  integer alias version; production behavior already rejected the changed alias.
- Independent review found no issues. Scoped Ruff/format, full Python type
  checks and `git diff --check` passed. Final affected suite: **327 passed**,
  six existing legacy-policy deprecation warnings, in 221.14 seconds. No skips
  or failures; counts include all nine new regressions.

Final suite: lifecycle tasks, local workflow, local approval, lifecycle notebook,
job runtime/output, evidence contracts and custom eligibility under
`skyulf-core/tests/integrations/`; `python -m pytest <files> -q --tb=short
-p no:cacheprovider --basetemp=initiatives/spark_and_mlflow/rehearsals/sm34c3_local/final`.
It includes existing corruption, custom-code replay, phase failure, rollback,
quality rejection and post-promotion output-failure guards. Log: `final.log`.

The subsequent Sourcery condition follow-up removes the unused `existing` local
in `_prepare` and tests `search_runs` directly. The focused existing lifecycle
test passed (1 passed), with Ruff and format checks passing; log:
`prepare-condition.log`. No workflow behavior changed.

Next task is SM-34C4 (initializer simplification), as scoped in
[the plan](68-integration-template-simplification-plan.md).
