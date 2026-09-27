# SM-36 local search integration evidence

Date: 2026-09-27. Baseline/current HEAD: `b67594b7` on branch `090`.
SM-35 was committed with DCO and passing hooks. SM-36 changes are uncommitted.

## Delivered behavior

- Generated projects directly select a tuning strategy; no Basic/Advanced mode
  or `search_mode` field. Task filters classification/regression model choices,
  including voting and stacking ensembles. Strategy controls offer default/custom
  settings; enabled CV exposes method, folds, shuffle and seed.
- Reuse Core grid, random, halving_grid, halving_random and Optuna. Automatic
  model/strategy spaces come from the existing catalog and ensemble builder.
  `src/tuning.py` optionally overrides the space; exact source and resolved
  configuration are pinned. Scoring never reruns that hook.
- Shared CV drives search once. All fold preprocessing and final refits use
  training rows only. CV-off uses one training-only 80/20 validation split.
  Nested selection is followed by a clearly labeled fixed-model diagnostic;
  this is not independently retuned nested CV.
- Bounded trials/full-grid combinations, explicit halving resources, Optuna's
  soft timeout and sequential estimator/search workers. Invalid/unknown fields
  and conflicting fixed parameters fail before source access.
- MLflow stores effective config, trial results, selected parameters and scorer;
  `train_and_register` renders a compact summary. Saved tuned artifacts preserve
  prediction parity, including Polars and temporal metadata handling.
- Optional SHAP uses bounded training samples and fitted preprocessing. Results
  or an explicit unavailable reason are saved in `explanations.json` and surfaced
  in the training report. A real local run completed for both engines, four
  sampled rows each.

## Verification

Commands use `.venv/Scripts/python.exe -m pytest`, `-q --tb=short` and isolated
workspace `--basetemp` directories. The broad and focused suites overlap; counts
below must not be summed as unique tests.

| Scope | Result |
| --- | --- |
| local_retraining, local_workflow, workflow_config, lifecycle_tasks, job_output, Core pipeline tuning leakage/time-series holdout, local artifact | 323 passed, 88 warnings, 252.80s |
| search_training, search_results, local_explanations, project_preprocessing, search_strategies, local_cv | 94 passed, 38 warnings, 40.58s |
| Core tuning engine + halving resource contract | 144 passed, 2 warnings, 5.65s |
| template/tuning template | 69 passed, 2 warnings |
| Actual CLI generation (`SKYULF_BUNDLE_CLI_TEST_PROFILE=skyulf`) | 68 passed, 25 warnings; no deployment |
| Durable tuned registration/comparison plus real bounded SHAP, both engines | 2 passed, 8 warnings, 11.27s |

Relevant test paths are under `skyulf-core/tests/integrations/`;
Core checks are `tests/unit/test_tuning_engine.py`,
`tests/integration/test_core_pipeline_tuning_leakage.py` and
`tests/integration/test_tuning_time_series_holdout.py` within `skyulf-core`.
Five real strategy fits include installed Optuna. The catalog sweep admitted
all 34 registered supervised models across all five strategies with an audit
grid cap of 10,000; this is preflight evidence, not 170 model-fit claims.

Focused failures were reproduced before fixes: ensemble constructor preparation,
temporal ordering metadata in the inference schema, halving resource forwarding,
nested class membership, missing notebook tuning summary, ensemble tuning control
misclassification, ignored wrapper typos and temporal column mismatch. Review
also pinned nested estimator worker defaults and default ensemble members.

## Limits

No SM-36 Databricks training/deploy/run or push occurred. CLI generation is offline.
No exhaustive fit claim for every model/strategy/parameter combination. Estimator
domain compatibility is checked at fit time. Optuna timeout does not interrupt
an active fit. SHAP bounds rows/features, not wall-clock execution. Decision-
threshold tuning and parallel model branches remain outside this adapter.
The later SM-36a/b/c program remains separate.

Final search-helper extraction keeps model/CV preparation, strategy validation and
space admission in focused helpers. The final combined search gate passed **83
tests, 32 warnings, 5.72s**: `test_databricks_local_search.py`,
`test_databricks_search_preview.py`, `test_databricks_search_results.py`,
`test_databricks_search_strategies.py`, `test_databricks_search_training.py`.
Changed Python Ruff check/format (25 files), full repository ty scope
(`backend skyulf-core/skyulf skyulf-core/tests run_skyulf.py celery_worker.py`)
and `git diff --check` passed. Independent review findings were fixed and
regression-tested. The docs strict build was not repeated in SM-36.

Owned local test directories were archived under ignored
`tmp_repro_artifacts/sm36/`; unrelated temporary directories were preserved.
SM-36 is locally complete, uncommitted, with cloud acceptance still unverified.
