# SM-35: optional absolute quality gates

Date: 2026-09-27. Implements the approved SM-35 scope in
[the local Bundle program](37-local-bundle-improvement-program.md).
Implemented after the SM-34C live acceptance/fix passed.
[Verification and Sourcery follow-up](77-sm35-quality-gates-evidence.md).

## Contract

- Keep `metric`, `min_improvement` and `quality_threshold`. Minimum improvement
  is an absolute difference in the selection metric; ties never qualify.
- Optional `quality_gates` is a mapping of additional held-out metric names to
  absolute thresholds. Reuse existing metric sets and directions. All gates
  must pass; do not let a secondary gate override the selection metric's gate.
- Validate finite numeric thresholds, domains and task compatibility before
  source access. Missing/non-finite secondary metrics fail closed with an
  explicit explanation. Existing classification evaluation owns probability
  and class availability; do not introduce a second metric implementation.
- First champion still requires an explicit selection-metric threshold and
  must pass every additional gate. Manual approval must preserve the exact
  saved policy; fresh re-evaluation precedes alias changes.
- Keep historical single-gate report hashes valid. A new optional dataclass
  field must not silently change serialized evidence used by old receipts.
- Show every gate's observed value, bound, direction and failure reason in
  MLflow evidence and notebook output. Quality bounds never alter probability
  decision thresholds. Default quality threshold remains null.

## File map and execution

- [x] `mlflow/validation.py`: shared threshold validation, optional report policy,
  gate outcomes, canonical backward-compatible comparison payload/digest.
  Pin regression/classification, tie, conflicting gates, missing metrics and
  malformed policies in `test_mlflow_validation.py` before implementation.
- [x] `mlflow/promotion.py` and `rejection.py`: propagate the policy through
  fresh comparison and digest checks, enforce all gates for first champion,
  report failed gates in version evidence. Test no alias mutation on failure.
- [x] `databricks/local_retraining.py`, `lifecycle_tasks.py`, `local_workflow.py`,
  `local_training_evidence.py`, `local_approval.py`: pass and save the same
  policy across SDK/task/approval boundaries, preserve historical evidence.
- [x] `databricks/workflow_config.py` and `job_output.py`: offline policy
  checks, preview and readable gate details. Add optional config example and
  central guide text without adding another interactive initializer question.
- [x] Run focused comparison, promotion, approval, workflow, notebook-output
  and durable lifecycle suites; Ruff/format/ty, independent review, exact queue
  evidence. No new Databricks run required for SM-35 unless a runtime issue
  makes one necessary; SM-34C cloud acceptance is a separate scope.

Repository paths above are relative to `skyulf-core/skyulf/integrations/`;
tests live in `skyulf-core/tests/integrations/`. Reuse
`skyulf/inference/local_evaluation.py` unchanged unless evidence shows a gap.
Backend and Canvas are outside this integration-only task.
