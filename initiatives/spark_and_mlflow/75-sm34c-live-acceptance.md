# SM-34C isolated Databricks acceptance

Date: 2026-09-27. C6 committed as `d9596763`; cloud-discovered custom
registration fix committed as `5c9798b9`. Both have DCO sign-off and passing
applicable pre-commit hooks. No push.

Status: corrected live run and every active task passed. Operator branch was
correctly excluded for a training request.

## Scope

Profile `skyulf`, personal test workspace `dbc-45604623-c18b.cloud.databricks.com`.
Generated the current template using CLI 1.17.0 and ran its notebooks using an
isolated ephemeral Jobs submission. Persistent train/score jobs and schedules
were not changed. The run-job score handoff was replaced only in the rehearsal
by the generated score notebook in the same run. This tests the score entrypoint
but does not revalidate the two-job queue/handoff boundary.

Existing synthetic source `workspace.skyulf_lifecycle_test.sm34b_20260926_r1_source`
is pinned at Delta version 1 for training. Polars, full snapshot/random split,
random forest regressor (16 trees, depth 5, seed 42), two-fold training-only CV.
Published custom centering recipe copied into the single project Python file,
after mean imputation. Maximum 500 rows/4 MiB. Automatic first champion, explicit
RMSE bound 20, champion scoring and a new prediction table. No schedules/retries.

## Failure retained and fixed

The initial Jobs submission was rejected before execution because the temporary
test preparer assigned a timeout to conditional tasks. Corrected the preparer
to set timeout only on notebook tasks; product YAML already had valid settings.

Run `274294158537457` then failed at `train_and_register`: the fresh task imported
custom class definitions but never called the saved builder containing
`custom_step`, so CV could not resolve `CenterCalculator` in the registry.
`finalize_and_report` correctly rejected failed task outcomes and scoring was
upstream-failed. No success or scoring handoff was published.

Fix: `_spec` restores registrations from both saved builders before validating
the pinned training specification. Builder output does not replace saved steps;
editable workspace source is not read by subsequent tasks. Existing trusted-code
execution and source digest checks remain.

Regression tests clear both project modules and node registrations between
prepare/train/compare, delete the editable project file, then exercise CV and
promotion on pandas and Polars, with and without custom pre-split eligibility.
All four pass. Independent reviewer found no concrete issues.

```powershell
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_lifecycle_tasks.py skyulf-core/tests/integrations/test_databricks_project_preprocessing.py skyulf-core/tests/integrations/test_databricks_local_cv.py -q --tb=short -p no:cacheprovider
```

143 passed, one expected legacy-policy deprecation warning, 204.49 seconds.
Scoped Ruff/format and ty passed; commit hooks passed. Initial sandbox pytest
attempt could not access the default temporary directory; authorized rerun used
normal temporary storage and reproduced the actual registration failure before
the fix.

## Corrected run

[Run 1021551603110584](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/319432320978553/run/1021551603110584)
uses a fresh `sm34c_20260927_r2` workspace directory/model/prediction prefix.
Wheel module hashes were verified locally against committed `5c9798b9` sources.
Training and registration passed: version 1, heldout RMSE 0.8301393169566954,
R2 0.99025579952991. Champion v1 and MLflow run
`d0e54be658f8473fa04c9441d2bfbaeb` are FINISHED. The verifier checked all seven
durable receipts, two CV folds, all finite CV/holdout metrics, saved custom
source, installed wheel hashes, five HTML reports, and exactly 243 non-null
predictions with keys 0..242 and the correct model/version provenance.
Score input/output counts are both 243; source end and Delta commit version
are both 1. [Compact acceptance receipt](75-sm34c-live-receipt.json).

This is one scenario with a diagnosed failed attempt and one corrected run.
Live reject/rollback, multiple champions, concurrency and production permissions
were not retested. The old two persistent jobs remain on their previous wheel.

Local raw evidence: ignored `rehearsals/sm34c_live/` and `sm34c_live_r2/` contain
request, build hashes, generated project, verifier and per-task API responses.
These do not contain authentication credentials.
