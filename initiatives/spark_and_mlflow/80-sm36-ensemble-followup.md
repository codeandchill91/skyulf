# SM-36 ensemble configuration and compatibility follow-up

2026-09-27; branch `090`, HEAD `b67594b7`. SM-36 remains uncommitted.

## User request and source audit

The user requested a separate Databricks ensemble module, frontend/Core option
alignment and real verification of models, spaces, tuning and CV. The supplied
Sourcery report described an older monolithic `prepare_search_pipeline`. Current
source has 27 lines and four `if` statements, delegating model/CV preparation,
strategy validation and space admission. No fresh Sourcery score was measured.

Reviewed `EnsembleSettings.tsx`, `ensembleSettings/EnsembleFormSections.tsx`,
`AdvancedTuningOptions.tsx`, `CrossValidationSection.tsx`, `modelOptions.ts`,
Core `modeling/ensemble.py` and its hyperparameter registry. Frontend source was
read but not changed. Basic/Advanced mode remains absent from Bundle setup.

## Changes

- `databricks/local_ensemble.py` owns member selection, named/ordered weights,
  calibration, stacking/final estimator settings and nested fixed parameter
  handling. It rejects wrong-task members, duplicates, unused member maps,
  invalid weights/folds/parameter names and contradictory fixed search axes.
- Generated `src/ensemble.py` contains four disabled editable recipes for the
  classification/regression voting/stacking families. Set `USE_EXAMPLES=True`
  or edit `build_ensemble_params`. Returned keys overlay JSON parameters before
  `src/tuning.py`; source and SHA256 are pinned. Missing/None hooks preserve old
  projects. Scoring never reruns either builder.
- Shared tuning strategy, automatic spaces and shared CV still use Core.
  Stacking `cv` and calibration `calibration_cv` remain separate internal loops.
  Fixed base/final parameters remain fixed during automatic component search.
  Ordinary SDK ensembles use the same admission checks; requesting base tuning
  without a tuner wrapper is rejected.
- Hard voting artifacts record `classification_probabilities=False` and return
  prediction only. Local evaluation, MLflow signatures and SDK schemas follow
  the capability. No invented probabilities; old artifact manifests still load.
  Probability-based thresholds require a probability-capable classifier.
- Core now includes the frontend's SGD ensemble member, metadata and automatic
  search-space mapping; its default loss supports probabilities.

Reproduced before fixes: named weights were ignored; fixed nested estimator
values could be overwritten by automatic axes; malformed ensembles silently
fell back; hard voting could not be saved; ordinary configurations bypassed
admission; SGD was selectable in Canvas but absent from Core's ensemble map.

## Verification

All pytest invocations used `.venv/Scripts/python.exe -m pytest`, `-q`,
`--tb=short --show-capture=no`, with isolated `--basetemp` under
`tmp_repro_artifacts/sm36/`.

- **287 passed**, 509 warnings, 36.31s: `test_databricks_local_ensemble`,
  `test_databricks_ensemble_training`, `test_databricks_local_search`,
  `test_databricks_local_cv`, `test_databricks_search_training`,
  `test_databricks_project_ensemble`, `test_databricks_project_preprocessing`,
  `test_databricks_tuning_template`, `test_databricks_bundle_template`,
  `test_local_hard_voting`, `test_local_pipeline_artifact`,
  `test_databricks_local_sdk` under `skyulf-core/tests/integrations/`.
- **77 passed**, 6.36s: local ensemble admission plus
  `tests/integration/test_ensemble_calibrated_tuning_refit.py`,
  `tests/unit/test_ensemble_nodes.py`, `tests/unit/test_modeling_ensemble_gaps.py`
  under `skyulf-core`.
- **1 passed**, 5.95s: real SQLite MLflow registration, artifact replay and
  heldout comparison in `test_databricks_lifecycle_tasks.py -k hard_voting_search`.
- The real-fit matrix covers four families x five strategies, with additional
  Polars replay, calibration, hard voting, selected meta-learner/OOF settings,
  fixed automatic-search parameters and SGD scenarios. These are bounded tests,
  not exhaustive parameter-combination claims.
- Scoped Ruff/format (37 Python files), full repository ty scope and
  `git diff --check` passed. Behavioral review findings were resolved and covered
  by tests. Unknown keys inside ensemble `params` are rejected; model-level
  metadata remains permissive, matching Core's existing configuration contract.

Warnings were existing sklearn worker/deprecation notices, Polars interchange
deprecations, small-fixture R2 warnings and the deprecated Split alias. No test
failure was left unresolved. Counts overlap and must not be summed as unique tests.

No Databricks cloud job, deployment, commit or push in this follow-up. No frontend
build was needed because frontend files were unchanged. No new Sourcery score or
strict docs build was run. Hard voting supports label metrics, not probability
metrics. Optional model dependencies and estimator-specific parameter domains
still need to be available/valid in the runtime.

## Automatic component search default follow-up

The user requested automatic component tuning for every ensemble. Bundle tuner
admission now defaults an omitted `tune_base_models` to true for all four families;
explicit false stays false. This applies with examples disabled as well. All four
editable examples also state true. Ordinary fixed-model SDK training is unchanged,
and explicit search spaces still define their own axes. Candidate limits remain
enforced for the expanded grid product.

Red: four missing nested-axis failures and one missing example flag.
Green: **167 passed**, 493 warnings, 14.75s across local ensemble, project ensemble,
local search, real ensemble training, tuning template, local CV and search training
tests. Existing fixed-voting structure coverage now uses one selected learner so
its grid stays bounded; separate grid-budget coverage still passes. Scoped Ruff,
format and full ty passed. No commit or cloud run.

Segmentation was separately queued as [SM-36d](81-sm36d-segmentation-task.md).

## SHAP readability and usage follow-up

Applied the dictionary union suggestion in `merge_ensemble_fixed_space`.
`explain_training_artifact` now has 25 source lines and delegates bounded sampling,
input/transformed-schema checks, fitted-model explanation and JSON result admission.
No fresh Sourcery quality score was measured. Existing reason codes, deterministic
sampling, fitted-engine conversion and inference-only preprocessing were preserved.

Added cross-engine input coverage and failure-path assertions before refactoring
(23 passed), then a real optional-SHAP saved-artifact explanation test. Final
SHAP/ensemble checks: **51 passed**, 16 fixture warnings, 3.02s. Local MLflow
search/registration/comparison checks for pandas and Polars: **2 passed**, 8 warnings,
8.89s. Scoped Ruff/format and full ty passed. No cloud run or commit this turn.

The Bundle guide now documents `pipeline.explainability` configuration, the optional
SHAP runtime dependency, `train_and_register` status and MLflow `explanations.json`.
The feature cap skips oversized transformed feature sets; it does not select top
features. Current Bundle output is JSON evidence and a summary, not charts.
Search metric selection already exists; diagnostic CV reports multiple metrics
without a separate `cv_metric` setting.
