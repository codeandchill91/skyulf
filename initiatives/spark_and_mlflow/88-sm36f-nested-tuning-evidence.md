# SM-36f true nested tuning: local and cloud acceptance

Date: 2026-09-27. Baseline: `b67594b7`, branch `090` with preceding staged
SM-36 work preserved. Changes uncommitted. Status: local and approved cloud acceptance passed.

## Delivered behavior

- Core coordinator `modeling/_tuning/nested.py` reuses grid, random, Optuna,
  halving grid and halving random within each independent outer training fold.
- Regression uses KFold; classification uses StratifiedKFold. `cv_folds` is the
  outer count; optional `cv_inner_folds` is the inner count. Omission preserves
  the earlier inner-count formula (2 for two outer folds, otherwise min(3, outer-1)).
- Preprocessing is learned within inner training folds and refit on outer training
  rows before outer scoring. External validation/holdout is excluded from search.
- A separate full-training search selects final saved parameters. Outer scores
  never select them. Budgets apply independently to each of outer+1 searches.
- `TuningResult.nested_cv` persists outer winners, inner best scores, outer scores,
  row/trial counts, scorer, mean/std and effective fold settings. Existing result
  fields continue to describe the final search.
- Backend and Databricks reuse this evidence without repeating post-selection CV.
  Canvas exposes outer/inner controls and displays outer evaluation separately
  from the final search score. Generated bundles preserve explicit inner folds.
- Legacy saved results remain readable and explicitly diagnostic. No old artifacts
  or model versions were changed. Ordinary standalone fixed-model CV retains its
  diagnostic semantics; explicit Databricks inner-fold settings require tuning.

## Negative and independent evidence

Independent sklearn GridSearchCV inside a manual outer loop matches Core winners,
inner scores and outer scores, including StandardScaler preprocessing. Membership
audits cover all five strategies: each preprocessing fit uses only the relevant
outer training rows, and inner fits use smaller subsets. Changing external
validation labels does not alter nested results or final selection.

Invalid inner folds, insufficient membership, nonfinite outer evaluation and
`tune_threshold=True` fail explicitly. Backend rejects nested preprocessing
fallbacks even when legacy warning/ignore behavior permits ordinary training.
Saved artifact reload retains nested evidence without rerunning evaluation.

## Executed checks

All Python commands use `.venv/Scripts/python.exe -m pytest` from the repository.

| Check | Result |
| --- | --- |
| New `skyulf-core/tests/integration/test_nested_tuning.py` | 24 passed |
| Relevant Core/backend/Databricks regression selection below | 499 passed, 0 failed |
| `skyulf-core/tests/integrations/test_databricks_job_output.py` | 12 passed |
| Real CLI bundle generation `-k 'nested_search_preserves or default'`, profile `skyulf` | 3 passed, 66 deselected |
| Earlier frontend selection including pipelineConverter | 164 passed |
| Final frontend selection below, including new payload tests | 113 passed |
| Scoped Ruff including new modules/tests | Passed |
| `ty check backend skyulf-core/skyulf skyulf-core/tests run_skyulf.py celery_worker.py` | Passed |
| `npm run lint`, `npm run build` in frontend/ml-canvas | Passed; generated assets rebuilt |
| `git diff --check` | Passed |

The 499-test selection (counts overlap the individual checks above):

```text
skyulf-core/tests/integration/test_nested_tuning.py
skyulf-core/tests/unit/test_tuning_engine.py
skyulf-core/tests/unit/test_tuning_refactor_branches.py
skyulf-core/tests/unit/test_tuning_engine_failure_branches.py
skyulf-core/tests/unit/test_tuning_failed_fold_semantics.py
skyulf-core/tests/integration/test_tuning_per_fold_refit.py
skyulf-core/tests/integration/test_core_pipeline_tuning_leakage.py
skyulf-core/tests/integration/test_tuning_positive_class.py
skyulf-core/tests/integration/test_tuning_class_weights.py
skyulf-core/tests/integration/test_ensemble_calibrated_tuning_refit.py
skyulf-core/tests/integrations/test_databricks_local_cv.py
skyulf-core/tests/integrations/test_databricks_local_search.py
skyulf-core/tests/integrations/test_databricks_search_preview.py
skyulf-core/tests/integrations/test_databricks_tuning_template.py
skyulf-core/tests/integrations/test_databricks_search_results.py
skyulf-core/tests/integrations/test_databricks_ensemble_training.py
tests/integration/test_node_runners_extra.py
-q --tb=short --disable-warnings --basetemp .tmp-sm36f-regression
```

Final frontend command:

```text
npx vitest run src/core/utils/pipelineConversion/training.test.ts src/modules/nodes/modeling/TrainingSettings.test.tsx src/modules/nodes/modeling/EnsembleSettings.test.tsx src/components/panels/jobs/JobDetailsView.test.tsx
```

Existing jsdom XHR error output did not fail component assertions. Vite reported
its existing circular vendor chunks and empty vendor-react chunk; build exited 0.

## Cloud acceptance completed after explicit approval

The initial automatic upload rejection was resolved by explicit user approval of
this payload and the workspace/directory. The initial upload then found a name
collision between the `tests` directory and notebook. The harness now uses
`check_tests`; no job had been submitted before that correction.

- [Nested matrix run 199364385609013](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/385813254266137/run/199364385609013): all six tasks SUCCESS.
- [Fixed-model run 997025503004339](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/785014317752504/run/997025503004339): SUCCESS.

| Cloud coverage | Passed |
| --- | --- |
| Grid nested: 6 families x pandas/Polars | 12/12 |
| Random nested: same 12 plus 6 automatic spaces | 18/18 |
| Optuna nested | 12/12 |
| Halving grid nested | 12/12 |
| Halving random nested | 12/12 |
| Independent reference/leakage/failure tests | 24/24, no skips |
| Basic/fixed: 6 families x pandas/Polars, ordinary 2-fold CV | 12/12 |

Families: logistic regression, ridge regression, voting classifier/regressor,
stacking classifier/regressor. Ensemble cases retain configured weights, voting
mode, stacking CV and passthrough; automatic voting-classifier search also uses
calibration. Across nested cases: 198 outer evaluations and 552 trials across
inner/final searches. Saved-artifact reload prediction checks cover 1,872 rows
across all 78 training cases. Every case's MLflow cross-validation JSON was logged,
downloaded and checked for equality. These jobs exercise the real Core/Databricks
adapters on serverless workers, not a new deployment of production lifecycle jobs.

The final wheel was built using `uv build --wheel --no-build-isolation --cache-dir
.tmp-sm36-uv-cache skyulf-core --out-dir
initiatives/spark_and_mlflow/rehearsals/sm36f_nested/dist`.
SHA256: `df533394fd76eaef511e78a876573f8c04af8f68e43c78127ff828ee9d9d670b`.
All 255 packaged modules matched local source bytes and installed worker bytes.
Cloud versions: sklearn 1.6.1, MLflow 3.16.1, Optuna 5.0.0, pandas 2.2.3,
Polars 1.44.2. Product source did not change after wheel build.

Reproducible orchestration: `rehearsals/sm36f_nested/control.py` with `setup`,
`status`, `collect`, `fixed`, `status fixed`. The reused helper submits idempotent
isolated serverless runs with no retries or schedules. Detailed case files,
MLflow run IDs, runtime receipts and source hashes are in the rehearsal folder;
[verified aggregate receipt](89-sm36f-nested-tuning-receipt.json).

## User follow-up: backend Basic and Advanced

Added `tests/integration/test_nested_training_modes.py`: six families x two run
modes (`fixed`, `tuned`) x two CV methods (ordinary, nested) = **24 passed**.
Each uses a real PipelineEngine with CSV loader, 80/20 splitter, StandardScaler,
training and saved model replay. Assertions cover 96 training/24 test rows,
preprocessing isolation, one fixed or two searched candidates, fixed C/alpha,
ensemble members/weights/voting or stacking CV/passthrough, retained nested fold
counts/scores and reloaded predictions. Nested outer and inner folds both equal 2;
ordinary CV uses StratifiedKFold for classification and KFold for regression.

The first test run incorrectly treated the stored `(X, y)` test tuple as a frame;
all training nodes had succeeded. Correcting the test to unpack the established
contract yielded 24/24; additional estimator-setting assertions also passed.
No production code changes were required by these follow-up checks.

Final exact command:

```text
.venv/Scripts/python.exe -m pytest tests/integration/test_nested_training_modes.py -q --tb=short --show-capture=no --disable-warnings --basetemp .tmp-sm36f-backend-modes-final --junitxml=initiatives/spark_and_mlflow/rehearsals/sm36f_nested/backend-modes.xml
```

Scoped Ruff lint/format and ty checks passed. This is backend execution-engine
coverage, not a browser-to-HTTP-to-Celery acceptance test. Existing frontend
conversion/component checks separately verify the UI payload and displayed result.

## Limits and handoff

No nested temporal/group splitters or nested threshold optimization were added.
Classification/regression and ensemble algorithmic coverage is bounded by the
tests above, not every model/strategy/settings Cartesian product. Historical
170-case cloud evidence predates this coordinator and remains separate.
SM-36d segmentation and SM-36e SHAP setup remain waiting. No commit or push.

## Commit closure and requested follow-ups

The user requested a local commit of the completed SM-36/SM-36f work and three
separate future tasks. SM-36g temporal, SM-36h group and SM-36i threshold nested
support are READY, not implemented; scopes and acceptance are in reports 90-92.
This report's earlier "uncommitted" statements describe the verification checkpoint.

Fresh pre-commit verification on 2026-09-27:

- 25 changed/new Python test modules: 773 passed, 14 failed, 69 skipped. Skips are
  opt-in real CLI generation cases; previous actual CLI evidence remains separate.
- Failures were 11 lightweight template-renderer expectations missing the optional
  inner-fold conditional, one historical diagnostic-only nested expectation, and
  two output tests assuming no globally configured stdout log handler.
- Updated the test renderer and nested result assertion; isolated and asserted the
  warning call while preserving strict printed/exit JSON assertions. No product
  behavior changed. The combined affected suite then passed **176 tests**:
  `test_databricks_bundle_template.py`, `test_databricks_ensemble_training.py`,
  `test_databricks_job_output.py`, `test_databricks_search_strategies.py`, and
  backend `test_node_runners_extra.py`. Raw JUnit receipts remain in the rehearsal.
- Final frontend selection (training payload conversion, pipelineConverter,
  TrainingSettings, EnsembleSettings, JobDetailsView): **166 passed**.
- `mkdocs build --strict` passed. Added the historical CV section anchor so older
  guide links still resolve. Existing segmentation page nav notice remains.
- All 255 Core module bytes still match cloud wheel `df533394`; no new cloud run
  was needed for test-helper/doc-only corrections.
- Local commit includes explicit reports/receipts/tasks and generated Canvas assets;
  temporary test directories and generated cloud environments remain local.
