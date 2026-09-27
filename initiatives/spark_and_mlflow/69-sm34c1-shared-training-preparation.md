# SM-34C1: shared training preparation and registration

Date: 2026-09-27. Baseline: `454d2dad`, branch `090`.
Status: locally complete, uncommitted. Next: SM-34C2.

## Changes and ownership

- `local_workflow._prepare_training` owns automatic quality-gate validation,
  CV configuration/validation, source snapshot selection and champion resolution.
  Both `run_action(train)` and lifecycle `_prepare` call it. Score model selection
  stays independent; caller configuration is not mutated.
- `local_retraining._register_candidate` owns registration and the existing
  256-byte UTF-8 tag limit/fallback. Both execution adapters call it.
- SDK run ownership, callback placement and finalization remain in the SDK path.
  The task adapter retains durable run creation, mutation intent, registration
  receipts, candidate resolution, phase receipts and finalization.
- Task registration still records intent before the registry call and saves its
  registration receipt before resolving the registered candidate. A resolution
  failure therefore retains evidence of the already-created model version.

Two explicit helpers replace duplicated decisions; no new production module,
framework, dependency or public API was introduced. This is an ownership change,
not a claim of fewer total source lines or faster cloud execution.

## Compatibility details

Legacy SDK `auto_champion` ignores an explicit expected champion pin, as before.
Current SDK policy configuration and all durable training tasks reject stale
expected champions. Regression tests preserve that intentional difference.

The task path now validates the raw pipeline's CV configuration before reading
the source or registry. Its later `_candidate_config` validation of the effective
pipeline after pre-split preparation is retained. Invalid requests fail earlier;
run creation and publication still follow validation.

## Verification

All commands ran locally using the existing Python environment. Logs and isolated
test data are under `rehearsals/sm34c1_local/` (local, ignored artifacts).

| Check | Result |
| --- | --- |
| Original workflow, retraining and lifecycle-task suites before editing | 178 passed; `baseline.log` |
| New preparation cases before extraction | 18 failed because the helper did not exist; `red.log` |
| Initial preparation + workflow checks | 79 passed |
| Combined preparation/workflow/retraining/lifecycle suites | 199 passed, one new test-fixture failure; `final.log` |
| Corrected preparation suite | 19 passed; `focused-final.log` |
| Notebook lifecycle, runtime and readable output suites | 83 passed; `adapters.log` |
| Scoped Ruff and format checks; repository Python type check | Passed |
| Independent production diff review | No production findings; missing test inputs corrected |

The failed test omitted `metric` and `min_improvement`, so it stopped before its
mocked fit boundary. Only those fixture inputs changed after the combined run;
all 19 tests in that file were rerun successfully. Counts above overlap and must
not be summed. The combined suite contains 200 distinct cases; the separate
adapter suite contains 83. A second full combined run was not performed.

New coverage checks both engines, automatic/manual policy, absent/existing
champion, latest/explicit snapshot, score-pin preservation, invalid preparation,
legacy SDK compatibility, strict task champion checks before run creation, and
registration evidence surviving a post-registration resolution failure.

Commands (pytest also used `-q --tb=short -p no:cacheprovider` and isolated
`--basetemp` directories):

```text
python -m pytest skyulf-core/tests/integrations/test_databricks_training_preparation.py skyulf-core/tests/integrations/test_databricks_local_workflow.py skyulf-core/tests/integrations/test_databricks_local_retraining.py skyulf-core/tests/integrations/test_databricks_lifecycle_tasks.py
python -m pytest skyulf-core/tests/integrations/test_databricks_training_preparation.py
python -m pytest skyulf-core/tests/integrations/test_databricks_lifecycle_notebook.py skyulf-core/tests/integrations/test_databricks_job_runtime.py skyulf-core/tests/integrations/test_databricks_job_output.py
ruff check skyulf-core/skyulf/integrations/databricks/local_workflow.py skyulf-core/skyulf/integrations/databricks/local_retraining.py skyulf-core/skyulf/integrations/databricks/lifecycle_tasks.py skyulf-core/tests/integrations/test_databricks_training_preparation.py skyulf-core/tests/integrations/test_databricks_lifecycle_tasks.py
ruff format --check skyulf-core/skyulf/integrations/databricks/local_workflow.py skyulf-core/skyulf/integrations/databricks/local_retraining.py skyulf-core/skyulf/integrations/databricks/lifecycle_tasks.py skyulf-core/tests/integrations/test_databricks_training_preparation.py skyulf-core/tests/integrations/test_databricks_lifecycle_tasks.py
ty check backend skyulf-core/skyulf skyulf-core/tests run_skyulf.py celery_worker.py
git diff --check
```

## Boundaries and next step

No template, graph, frontend, deployment or cloud execution changed. No commit
or push was made. The two persistent Databricks jobs still use the earlier wheel;
even the preceding `daa1e1c7` readable-output fix has only its isolated live test.
These local checks are not live acceptance of C1.

Continue with C2's spec/evidence/result ownership map in
[the simplification plan](68-integration-template-simplification-plan.md).
Replay optimization, setup reduction, template documentation and retirement of
legacy routing remain C3-C6 tasks.
