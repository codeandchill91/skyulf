# SM-35: multiple absolute quality gates

Date: 2026-09-27. Baseline `5c9798b9`; implementation currently uncommitted.
The user requested continuation after committing C6 and testing Databricks.
That cloud acceptance is recorded separately in [report75](75-sm34c-live-acceptance.md).
Scope/design: [program SM-35](37-local-bundle-improvement-program.md) and
[execution map](76-sm35-quality-gates-plan.md).

Status: locally DONE. Final integration suite, static checks, docs and review passed.

## Delivered behavior

- Optional `quality_gates` maps additional heldout metrics to absolute bounds.
  One selection metric still decides improvement. All quality bounds must pass;
  the primary threshold cannot be repeated/overridden in secondary gates.
- Workflow and SDK preflight share metric/task/domain/finite-bound validation.
  Error/loss bounds are nonnegative; classification bounds are [0,1], except
  MCC [-1,1]; R2/explained variance allow negatives but not values above 1.
- Existing heldout evaluation supplies every observed metric and its existing
  probability/class availability semantics. Missing or non-finite secondary
  metrics produce explicit failed gate outcomes. No second evaluator was added.
- SDK and durable tasks persist identical policy; first champion, re-staging,
  automatic promotion and manual approval re-evaluate every gate. Manual approval
  rejects policy changes. Ties never qualify; minimum improvement is absolute.
- `candidate_comparison.json` pins the policy and metrics. `quality_gates.json`
  records all outcomes. Version tags and notebook tables explain every bound,
  observed value and failure. Each version tag carries its event ID and
  `quality_gate_event` identifies current results after a supported SDK re-stage.
- Config/graph versions and initializer questions remain unchanged. Users add
  optional gates to workflow JSON. The guide includes regression/classification
  examples and distinguishes probability decisions from quality thresholds.
  There is no new generic RMSE threshold default.

## Historical evidence compatibility

`ModelComparisonReport` has an optional gate mapping. `comparison_payload` omits
an empty mapping so historical single-gate JSON/digests still match. Training,
promotion, rejection and the saved-evidence loader share `comparison_digest`.
SDK callers should use the existing returned `comparison_sha256`, or the new
canonical helpers when intentionally serializing evidence. Raw `asdict(report)`
includes the new optional field and is not the canonical receipt representation.
Existing tests that manually reconstructed hashes now use the canonical payload;
legacy JSON with no gate field still loads and is explicitly covered.

## Sourcery follow-up

The user flagged `compare_registered_local_models` and `_validate_request`.
Separated concrete model identity, holdout identity/budget, artifact contract,
paired evaluation, selected-value availability, absolute improvement and decision
helpers. The public comparison signature remains unchanged apart from the
SM-35 optional argument. Comparison body lines including docstring decreased
from 110 to 62 versus baseline; request validation from 55 to 11. These are
AST-derived body-line counts, not Sourcery scores. Sourcery was not rerun.

No arbitrary ten-line wrapper requirement was imposed on the explicit report
constructor. Helper names describe independent checks rather than numbered
extractions. All new functions/tests carry docstrings and behavioral assertions.

## Verification and review

New failing tests preceded implementation for extra gates, first champion,
offline config and visible report outcomes. Real classification tests exercise
one-class holdout/AUC unavailability; regression tests cover conflicting
secondary gates and ties. Durable MLflow tests cover both promotion policies,
saved run/version evidence, changed-policy approval rejection, and no scoring
handoff after a secondary failure. Existing SDK saved-code evidence tests now
also exercise additional gates on both engines.

The first broader run identified test fixtures using impossible negative error
bounds and raw dataclass hashes. Fixtures now use valid failing bounds/noisy
labels and canonical evidence. A mock report gained the new optional field.
A later run had 453 passed and one old error-message expectation: invalid
metrics now fail before reading/fitting instead of after evaluation. The test
now explicitly forbids a source read and expects preflight rejection.

Independent review found no promotion bypass or historical digest regression.
It identified stale per-gate version tags after SDK re-staging; event association
and a real registry re-stage regression fixed that finding. Follow-up review
found no remaining substantive issues, including the Sourcery extraction.

Scoped Ruff/format, full repository ty, `git diff --check`, and
`mkdocs build --strict` passed. The Windows docs wrapper initially misdecoded
stderr, then could not print Unicode to a legacy console encoding; the final
UTF-8 wrapper recorded the actual successful exit code 0.

Final command: `.venv/Scripts/python.exe -m pytest` with these integration files:
`test_mlflow_validation.py`, `test_mlflow_promotion.py`,
`test_databricks_workflow_config.py`, `test_databricks_local_approval.py`,
`test_databricks_evidence_contracts.py`, `test_databricks_local_workflow.py`,
`test_databricks_training_preparation.py`, `test_databricks_local_retraining.py`,
`test_databricks_date_free_training.py`, `test_databricks_lifecycle_tasks.py`,
`test_databricks_job_output.py`, `test_databricks_workflow_preview.py`,
`test_databricks_bundle_lifecycle.py`, followed by
`-q --tb=short --show-capture=no -p no:cacheprovider`.
All paths are under `skyulf-core/tests/integrations/`.

**459 passed**, 10 expected one-class/deprecated-policy warnings, 402.54 seconds.
Exact command/log retained in `rehearsals/sm35/final-command.txt` and
`rehearsals/sm35/final.log`. No SM-35 cloud run, deployment or commit yet.
The prior live C6 run does not verify these later multi-gate changes.

## Report placement discussion

The user asked whether split strategy belongs in `train_and_register` output.
Explained that preparation should still validate/pin the source and split policy,
while the training report is the more useful place for split/engine/CV/model
details. No graph or report-placement change was implemented from that question.

## Additional Sourcery cleanup (2026-09-27)

The subsequent user review also flagged alias commits, offline configuration,
preview rendering, action dispatch and pre-split validation. This follow-up is
a behavior-preserving extraction within the existing four modules:

- `_commit_change` now orchestrates preparation, verified alias updates and
  finalization. Each original exception boundary and pending-event rule remains.
- Workflow checks are grouped by supported fields, sources, model selection,
  quality policy and pipeline compatibility, in their original order.
- Preview rendering shares ordered step formatting and separates time windows,
  source selection and model/scoring details; its text remains unchanged.
- `run_action` delegates training and scoring to dedicated helpers. Training
  retains failure evidence and legacy champion-pin compatibility; full rebuild
  activates its output only after scoring succeeds.
- Pre-split admission separates fixed edits, missing-row filters and manual
  bounds. Learned-step rejection, protected keys/times, custom filter contracts
  and final source-column validation retain their original order.

AST body-line counts (including docstrings, excluding signatures), compared
with the uncommitted SM-35 state immediately before this follow-up:

| Function | Before | After |
| --- | ---: | ---: |
| `_commit_change` | 93 | 12 |
| `validate_workflow_config` | 92 | 24 |
| `preview_workflow_config` | 108 | 27 |
| `run_action` | 122 | 58 |
| `_pre_split_columns` | 101 | 9 |

The comparison function was already refactored as described above, so the
repeated warning did not trigger another extraction. Sourcery scores have not
been rerun; these line counts do not claim a new quality score.

An offline before/after check found identical values or exact exception types
and messages for **3,324 workflow validation/preview cases** and **188 pre-split
admission cases**. This includes malformed settings, missing fields, explicit
and runtime date boundaries, ordered recipes, protected columns and invalid
filter bounds. Script and before snapshots are in
`rehearsals/sourcery_sm35/`; they are local verification artifacts.

Independent static review of those snapshots against the current four modules
found no substantive differences in the protected behavior. Scoped Ruff/format,
full repository ty and `git diff --check` passed. The combined regression suite
passed: **578 tests**, 10 expected warnings, 410.32 seconds, exit 0. It uses the
13-file command above plus `test_databricks_pre_split_filters.py` and
`test_databricks_custom_eligibility.py`, with the same pytest flags. No additional
cloud test or commit was performed for this refactor.
