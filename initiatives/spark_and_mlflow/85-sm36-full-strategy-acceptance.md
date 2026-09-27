# SM-36: complete model/strategy matrix and setting checks

Date: 2026-09-27. Baseline: `b67594b7` plus existing uncommitted SM-36 work.
Status: **PASS** for the bounded scope below; changes remain uncommitted.
No commit, push or persistent-job deployment in this follow-up.

## Nested CV: correction to the earlier explanation

This is existing Core behavior, not a missing Databricks transfer.

- `skyulf/modeling/cross_validation.py::_perform_nested_cv` explicitly runs the
  same fixed configuration in its inner and outer folds. Inner results measure
  stability; they do not select hyperparameters.
- `_tuning/splitters.py` maps `nested_cv` to an inner candidate-scoring splitter.
- The backend's post-tuning `_run_tuned_cv` evaluates the selected fixed
  model. Databricks `local_search_results.py::post_selection_cv` follows this
  contract and labels the result `post_selection_diagnostic`.
- Full nested tuning would run a fresh search inside each outer training fold,
  fit preprocessing only within the corresponding training boundaries, score
  each selected model on its untouched outer fold, and aggregate those outer
  scores. Final full-training selection/refit would be separate. That is a Core
  feature, with backend/template/report changes afterward; it is not implemented
  or claimed by this acceptance.

The post-selection diagnostic must not be presented as an unbiased evaluation
of the full model-selection procedure. The separate lifecycle holdout remains
separate from candidate-search CV. No CV semantics changed in this follow-up.

## Reproduced defect and fix

The installed Databricks runtime uses scikit-learn 1.6.1; the local environment
uses 1.8.0. Core unconditionally translated public Logistic Regression
`penalty` into the new `l1_ratio`/`C` representation. In 1.6.1, this drops an
explicit L1 choice and leaves the estimator's default L2 penalty. Successful
training and artifact replay alone did not catch the semantic error.

Two independent direct-L1 coefficient comparisons failed on the old wheel;
the two L2 controls passed. The reproduction run intentionally succeeds only
when those two pytest failures are observed:
[old-wheel reproduction](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/396968846973805/run/27771538645771).

`_sklearn_compat.py` now detects the installed estimator's penalty API. Legacy
versions retain explicit penalties and use the ratio only for Elastic Net;
new versions retain the existing translation. Direct training, tuning refits,
ensemble bases and stacking meta-learners share this helper.

Regression expectations use independent native sklearn models, comparing
coefficients, probabilities and candidate CV scores. They cover L1/L2,
Elastic Net, no penalty, fixed/searched settings, fold preprocessing and all
five tuning strategies. Local 1.8.0: **143 passed**. Cloud scikit-learn 1.6.1: **143 passed, 0 skipped** as well.

API references: [sklearn 1.6 LogisticRegression](https://scikit-learn.org/1.6/modules/generated/sklearn.linear_model.LogisticRegression.html),
[sklearn 1.8 LogisticRegression](https://scikit-learn.org/1.8/modules/generated/sklearn.linear_model.LogisticRegression.html).
Existing saved model versions were not rewritten or promoted by these tests;
retraining with the corrected wheel is required to apply the fix to old models.

## Final-wheel cloud scope

Wheel SHA256: `4cdab08d03d1a36d1798739eda29f7687566a87daa7ad4685ec6635df03e4a97`.
The matrix and settings notebooks verify all 254 installed Python module hashes.
Remote root: `/Workspace/Users/edwardwolfe99@gmail.com/skyulf_lifecycle_test/sm36_20260927_fullmatrix_r2`.
Raw receipts, notebooks and commands: `rehearsals/sm36_full_matrix_r2/`.

### Model matrix

34 template models (16 regression, 18 classification, including the four
ensemble families) crossed with grid, random, Optuna, halving grid and halving
random: **170 distinct combinations**. Each performs actual fitting, artifact
save/load and 16-row prediction parity. Logistic Regression additionally checks
that the winning penalty remains on the fitted model.

Full automatic spaces are used after explicit compute caps: supported fixed
parameters `n_estimators=8`, `max_depth=3`, `max_iter=100`, `n_jobs=1`.
Training uses 80 rows and 2 CV folds. Grid budget is 10,000; random/Optuna use
three trials (smaller finite spaces can have fewer distinct candidates).
Ensembles use two selected members and automatic component search spaces.
Both pandas and Polars are exercised across models.

Halving matrix cases use 48..80 sample bounds and can finish in one resource
round; separate halving setting cases below exercise successive resource rounds.
These are bounded compatibility checks, not convergence or predictive-quality
benchmarks on production data.

### Setting scenarios

| Group | Scenarios | Choices exercised |
| --- | ---: | --- |
| Optuna | 30 | TPE/random/CMA-ES; median/hyperband/none; pruning on/off; native SGD/XGBoost/LightGBM paths; timeout and defaults |
| Halving | 30 | Both strategies; factors 2/3/10; smallest/exhaust/integer/numeric-string minima; automatic/explicit maxima; sample/tree resources |
| CV and metrics | 84 | Five CV methods with every strategy where valid; enabled/disabled; shuffle; folds 2/3/5/20; seeds; all four regression and seven classification metrics; budget/rejection gates |
| Ensemble | 110 | Every selectable base learner in all four families; every stacking final learner; weights; calibration methods/folds; soft/hard voting; passthrough; internal CV; component tuning on/off |

Total: **254 scenarios**, including five expected rejection cases; 249 perform
actual fits and 24-row save/load prediction parity. Instrumentation verifies
actual sampler/pruner classes, halving resources and fitted ensemble settings.
The numeric domain is represented by defaults/boundaries, not every possible
number or the Cartesian product of every setting with every model. The expanded
classification data is binary; multiclass is not claimed by this matrix.

Real pruning behavior has a separate **90-test** Core suite: native callbacks,
fold and incremental pruning, public options, partial results and failure
handling. This is stronger evidence than merely accepting a pruning flag.

### Template generation

**45 actual CLI-generated projects** check strategy defaults/custom settings,
all sampler/pruner/pruning choices, halving resource/minimum choices and CV
methods. Each resulting modeling configuration passes Core preparation.
Evidence: `rehearsals/sm36_full_matrix/generation-results.json`.
These generation checks ran locally through the Databricks CLI and are not
counted as cloud training cases.

## Final results

All final corrected-wheel runs and their child tasks completed successfully.
[Compact verified receipt](86-sm36-full-strategy-receipt.json).

- [Model matrix](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/485413012821178/run/970243762859545): **170/170 passed**, **3,756 completed trials**, no failing candidates.
- [Settings](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/271842761630702/run/185266366095064): **254 passed**.
- [Penalty regression](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/448769376738758/run/417752247612270): **143 passed, 0 failed, 0 skipped**.
- [Pruning](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/958877517025017/run/342962382508327): **90 passed, 0 failed, 0 skipped**.

The first corrected-wheel matrix (`937366991507359`) hit a new harness error:
its fitted-penalty assertion accessed the tuning `(model, result)` tuple as an
estimator. The harness now uses the existing `_unwrap_tuned_model()` accessor.
This was not a product fit failure; that run is nevertheless not accepted as a
successful matrix. The final run has a separate notebook/output prefix and run ID.

All 254 wheel module hashes also match the current working source. Scoped Ruff,
format, ty and `git diff --check` passed. Remaining recorded warnings concern
upstream deprecations, smaller finite random spaces and one undefined precision
score on a degenerate synthetic-data candidate. The ignored Logistic Regression
penalty warning seen before the fix is absent from the final matrix/settings.

The earlier full-matrix attempt passed fit/replay checks but its warning audit
revealed the penalty bug above; it does not prove penalty correctness. Keep its
raw evidence in `rehearsals/sm36_full_matrix/` as the pre-fix record.

## Reproduction commands

```powershell
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integration/test_logistic_penalty_consistency.py skyulf-core/tests/integration/test_logistic_elasticnet_defaults.py -q --tb=short --disable-warnings --basetemp .tmp-sm36-penalty-final
.venv/Scripts/ruff.exe check skyulf-core/skyulf/modeling/_sklearn_compat.py skyulf-core/skyulf/modeling/classification.py skyulf-core/tests/integration/test_logistic_penalty_consistency.py
.venv/Scripts/ty.exe check skyulf-core/skyulf/modeling/_sklearn_compat.py skyulf-core/skyulf/modeling/classification.py skyulf-core/tests/integration/test_logistic_penalty_consistency.py
.venv/Scripts/python.exe initiatives/spark_and_mlflow/rehearsals/sm36_full_matrix_r2/launch.py status penalty matrix_final settings pruning
.venv/Scripts/python.exe initiatives/spark_and_mlflow/rehearsals/sm36_full_matrix_r2/collect.py
```

New rehearsal/report files are ignored by the repository and require explicit
selection at a later commit. Existing staged changes were preserved.
