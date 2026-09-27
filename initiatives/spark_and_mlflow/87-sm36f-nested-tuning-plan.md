# SM-36f: true nested tuning implementation plan

Date: 2026-09-27. Status: DONE, uncommitted.

Goal: evaluate the complete parameter-selection procedure using independent outer
folds, then search/refit a final deployable model on the full training partition.
Architecture: one Core coordinator reuses all five existing search strategies.
Backend and Databricks consume its stored result instead of running diagnostic
post-selection CV. Existing preprocessing adapters own fold-local fitting.
Tech stack: Python/sklearn/Core, FastAPI result transport, React/TypeScript,
Databricks local-engine bundles.

## Approved design and constraints

The user approved fresh tuning within every outer training fold, preprocessing
isolation, and untouched outer evaluation. Keep `nested_cv` as the existing
selection. `cv_folds` selects outer folds; optional `cv_inner_folds` selects inner
folds, with the existing min(3, outer-1)/2 default when omitted. Classification
uses stratified folds and regression KFold. Ordinary CV strategies retain their
semantics. This does not add temporal/group nested splitters.

Each outer search uses the same configured strategy/space/budget independently.
`n_trials` and Optuna timeout remain per-search budgets; expose total work.
Do not select the final configuration from the outer test scores. Run a separate
full-training inner-CV search and final refit. External holdout/validation rows
must never enter nested selection or outer scoring. Threshold tuning combined
with nested evaluation must fail explicitly until threshold selection itself
can be included inside outer folds.

Results retain final-search `best_params`, `best_score`, `trials`; add an optional
`nested_cv` report with fold-level selected params, inner best score, outer score,
row counts, trial counts, outer mean/std, metric and effective fold settings.
Old saved artifacts lacking this field remain readable and explicitly diagnostic.
No alias/registry changes, automatic commits, or rewrites of old artifacts.
Preserve existing staged SM-36 work.

## Task 1: Core coordinator and independent reference tests

Files: create `skyulf-core/skyulf/modeling/_tuning/nested.py` and
`skyulf-core/tests/integration/test_nested_tuning.py`; update `engine.py`,
`schemas.py`, `splitters.py` in the same tuning package.

- [x] RED: compare outer scores and per-fold winners with independent sklearn
  `GridSearchCV` inside a manual outer KFold/StratifiedKFold loop.
- [x] Add `TuningConfig.cv_inner_folds: int | None = None` and
  `TuningResult.nested_cv: dict[str, Any] | None = None`.
- [x] Implement `run_nested_search(tuner, X, y, config, *, preprocessing,
  progress_callback, log_callback) -> TuningResult`; its inner configs replace
  `nested_cv` with KFold/stratified and call `tuner.tune` without external validation.
- [x] Score each selected outer model through the existing fold-local fitting
  helper; reject nonfinite outer scores and insufficient complete folds.
- [x] Run final search on training rows only; retain final-model refit in `fit`.
- [x] Verify all five strategies, both tasks, preprocessing membership isolation,
  independent winners, external validation exclusion, invalid folds and failures.

## Task 2: result propagation and settings

Files: `local_cv.py`, `local_search.py`, `local_search_results.py`,
`workflow_config.py`, `job_output.py`, backend `_node_runners.py`,
frontend training/ensemble CV sections and pipeline conversion, template schema
and workflow JSON. Associated integration/frontend tests.

- [x] Forward optional inner folds without changing old default configs.
- [x] Return stored nested evidence from backend/Databricks; remove duplicate
  post-selection evaluation for new nested artifacts.
- [x] Keep legacy saved-result diagnostics clearly identified.
- [x] Expose outer/inner fold controls and nested evaluation results with metric,
  folds, mean/std and selected parameters; keep final model search score separate.
- [x] Verify template/API/Canvas mappings and saved-artifact replay.

## Task 3: verification and handoff

- [x] Run focused Core/backend/Databricks tests and Ruff/ty.
- [x] Run frontend tests/lint/build if frontend changed.
- [x] Build a fresh wheel and run bounded regression/classification/ensemble nested
  training for all five strategies in Databricks, checking persisted outer reports
  and prediction replay. Do not rerun unrelated 170 model matrix without a reason.
- [x] Record exact evidence, limits and commands in a new report; update queue,
  handoff and changelog. Commit only on explicit request.

All planned gates completed. User-approved cloud runs and additional backend
Basic/Advanced checks passed; see reports 88/89. Changes remain uncommitted.
