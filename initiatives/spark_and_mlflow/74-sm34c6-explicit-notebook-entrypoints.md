# SM-34C6: explicit score entrypoint with notebook API compatibility

Date: 2026-09-27. Baseline/HEAD: `d8e4949f`, the user-requested C4/C5 commit.
That commit has DCO sign-off; applicable hooks and 241 pre-commit tests passed.
C6 is locally complete and uncommitted. Next: SM-35.
No cloud run, deployment, push or scheduled automation.

## Caller audit and compatibility decision

Searched `skyulf-core`, `docs` and root `tests` for `run_notebook`,
`run_bundle_action`, `run_lifecycle_notebook`, `run_action` and
`train_local_candidate`:

- Generated `src/score.py` was the only template caller of `run_notebook`.
- Five generated lifecycle notebooks already use `run_lifecycle_notebook` with
  their fixed phase. Those calls and the graph remain unchanged.
- Notebook, output and project-code tests exercise the direct role-based API,
  including sequential training and approve/reject/rollback callers.
- Runtime, approval and lifecycle integration tests call `run_bundle_action`.
- The central guide documents direct `run_action`; the SM-28a SDK example uses
  `train_local_candidate`. These public paths remain unchanged.

Repository search cannot prove external callers absent. Therefore the old
role-based API is retained as a compatibility dispatcher, not removed or silently
changed to durable phased execution. Sequential lifecycle behavior lives in one
private helper; no new warning or deprecation deadline is imposed. This slice
clarifies responsibility rather than claiming a net source-line reduction.

## Implementation

- Added `run_score_notebook`: fixed score role, shared config/deployed-contract
  validation, inherited lifecycle-field removal, existing action/role/pin guards,
  and the same readable/JSON output path. It neither loads editable project code
  nor creates a training artifact directory or writes lifecycle task values.
- Generated `src/score.py` calls it directly, retaining separate report/exit cells.
- `run_notebook(task_role="score")` delegates to the same score implementation.
  Lifecycle delegates to the retained sequential implementation, including
  training-only source loading, artifact path, result conversion and task output.
  An invalid role now fails immediately at the dispatcher before reading widgets.
- `run_bundle_action`, `run_action`, `train_local_candidate` and fixed lifecycle
  phase execution are unchanged. No package-root exports were removed.
- The central guide explains both notebook paths and the compatibility boundary.
  New generated entrypoints need the matching wheel; old score entrypoints
  continue to work with it. Graph contract stays 2; config schema stays 1.

## Verification

Python 3.12.10; installed Databricks CLI 1.17.0. Local checks only.

```powershell
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_notebook.py -k 'delegates and score' -x -q --tb=short -p no:cacheprovider
$env:SKYULF_BUNDLE_CLI_TEST_PROFILE='skyulf'
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_notebook.py skyulf-core/tests/integrations/test_databricks_job_runtime.py skyulf-core/tests/integrations/test_databricks_job_output.py skyulf-core/tests/integrations/test_databricks_project_preprocessing.py skyulf-core/tests/integrations/test_databricks_lifecycle_notebook.py skyulf-core/tests/integrations/test_databricks_bundle_lifecycle.py skyulf-core/tests/integrations/test_databricks_local_approval.py skyulf-core/tests/integrations/test_databricks_bundle_generation.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_job_output.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check skyulf-core/skyulf/integrations/databricks/job_runtime.py skyulf-core/tests/integrations/test_databricks_bundle_notebook.py skyulf-core/tests/integrations/test_databricks_job_output.py 'skyulf-core/templates/databricks/template/{{.project_name}}/src/score.py'
.venv/Scripts/python.exe -m ruff format --check skyulf-core/skyulf/integrations/databricks/job_runtime.py skyulf-core/tests/integrations/test_databricks_bundle_notebook.py skyulf-core/tests/integrations/test_databricks_job_output.py 'skyulf-core/templates/databricks/template/{{.project_name}}/src/score.py'
.venv/Scripts/python.exe -m ty check backend skyulf-core/skyulf skyulf-core/tests run_skyulf.py celery_worker.py
git diff --check
```

- Red/green: generated-score test failed on the old temporary artifact-directory
  allocation; both engines and inherited approve/rollback parameters pass after
  switching the entrypoint. Config/contract and role/action rejection tests now
  exercise both the explicit score API and compatibility wrapper.
- Initial focused notebook/runtime/output/project/lifecycle suites: **121 passed**.
- Combined eight suites: **204 passed**, including **68 real CLI generation tests**
  and local MLflow lifecycle integrations.
- Independent review found a legacy ordering regression: result conversion had
  moved after publishing `score_requested`. A new deepcopy-failure test reproduced
  the early task write. Restored the original conversion-before-publication order;
  the final output suite passed **10 tests**, including this added regression.
  Thus 205 distinct cases were verified across the combined and focused runs;
  there was no single 205-test run. The reviewer confirmed the fix.
- Final scoped Ruff, format and full ty passed. C4/C5's strict documentation build
  passed before their commit; C6's small guide addition was inspected locally.

Manual/automatic lifecycle, operator evidence, saved-code replay, malformed score
pins, unresolved invocation/reference guards, report fallback and machine exit
behavior retain coverage. Local success does not establish live deployment or
permissions. The two persistent jobs were not updated; prior cloud limits remain.
