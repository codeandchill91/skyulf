# SM-34C4: shorter basic initialization, preserved advanced inputs

Date: 2026-09-27. Baseline/current HEAD: `f4d654cf` (C3 committed with DCO
sign-off and applicable hooks passing). C4 is locally complete, uncommitted.
Next: SM-34C5. No cloud run, deployment, push or runtime change.

## Change and compatibility decision

The schema retains all 72 input fields, their types, defaults, validation and
order. Thirteen advanced fields now use unconditional `skip_prompt_if: {}`:
snapshot version, window mode, random test fraction/seed/stratification,
sampling size/seed, four CV details, minimum improvement and risk category.
They remain configurable through existing init files and generated workflow JSON.
Basic date/availability, split, model, CV enable, budgets, lifecycle, schedule
and compute questions retain their existing conditional behavior.

| Measure | Before | After |
| --- | ---: | ---: |
| Visible prompts with all default answers | 33 | 26 |
| Schema source lines | 1,417 | 1,363 |
| Input fields | 72 | 72 |

This is an intentional interactive UX change: advanced values are no longer
individual questions. No new setup-mode switch or schema-generation framework.
The welcome text, CV/split prompts, central guide and generated README explain
the defaults and override paths. Init strings and native workflow values remain
distinct; `min_improvement` is a JSON number even in an init file. `auto` window
selection is resolved by initialization, not a generated runtime mode.

Changed files: template schema, narrow setup paragraphs in the generated README
and central Bundle guide, generation/prompt tests, changelog and queue/handoff.
No change to `workflow.json.tmpl`, Core normalization or examples was necessary.
The larger README/recipe cleanup remains C5.

## Verification

Runtime: installed Databricks CLI `v1.17.0`, repository `.venv` Python/pytest.
Profile `skyulf` was used only for local CLI initialization. No workspace data
read or remote writes were needed.

```powershell
databricks --version
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_template.py -k advanced_settings -q --tb=short
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_template.py skyulf-core/tests/integrations/test_databricks_workflow_config.py skyulf-core/tests/integrations/test_databricks_workflow_preview.py -q --tb=short
$env:SKYULF_BUNDLE_CLI_TEST_PROFILE='skyulf'
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_generation.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_generation.py -q --tb=short -k hidden_advanced -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check skyulf-core/tests/integrations/test_databricks_bundle_generation.py skyulf-core/tests/integrations/test_databricks_bundle_template.py
.venv/Scripts/python.exe -m ruff format --check skyulf-core/tests/integrations/test_databricks_bundle_generation.py skyulf-core/tests/integrations/test_databricks_bundle_template.py
.venv/Scripts/python.exe -m ty check backend skyulf-core/skyulf skyulf-core/tests run_skyulf.py celery_worker.py
git diff --check
```

- Red/green: both new prompt tests failed before the schema edit; affected
  local suites then passed **127 tests**, with two existing registry warnings.
- First CLI suite: **64 passed**. Expanded suite: **67 passed, 1 failed** because
  the new test supplied `min_improvement` as a string. CLI correctly rejected it.
  The test and guide now retain its numeric type. The final focused rerun passed
  **1 test, 67 deselected**: all **68 CLI cases** verified across these runs.
- Full ty initially found the new test dictionary inferred as string-only;
  preserving the numeric value within its comprehension fixed that diagnostic.
  Final full ty, scoped Ruff and format checks passed.
- Initial CLI version execution required sandbox escalation; a redirected CLI
  test log failed on cache-directory permissions before running any tests.
  Subsequent CLI tests used direct output and disabled pytest cache writing.
- A tiny real CLI probe verified both omitted advanced defaults and explicit
  supplied values with `skip_prompt_if: {}`. Its first draft lacked a required
  description; adding the description allowed both cases to pass.
- Independent review identified the numeric-type wording and two incomplete
  example-directory paths. Both were fixed and the reviewer confirmed them.

## Real CLI baseline comparison

A temporary template copy used the schema from
`git show f4d654cf:skyulf-core/templates/databricks/databricks_template_schema.json`.
For each case, schema defaults were merged with its existing example/overrides
and the same project name. Both templates were rendered with:

```powershell
databricks bundle init <template> --config-file <case.json> --output-dir <temporary-output> --profile skyulf
.venv/Scripts/python.exe <generated-project>/src/preview.py --action train
```

All eight existing example files passed, plus these four combinations:

| Engine | Split | Promotion | Compute |
| --- | --- | --- | --- |
| pandas | random | automatic | serverless |
| polars | temporal | automatic | policy_cluster |
| polars | random | manual_approval | policy_cluster |
| pandas | temporal | manual_approval | serverless |

Temporal matrix cases supplied `event_column=observed_at`; all four supplied
`quality_threshold=100.0`. Every case matched byte-for-byte for
`config/workflow.json`, `databricks.yml` and `resources/workflow.jobs.yml`.
Before/after offline training preview output also matched after normalizing
the temporary project path. Schema comparison confirmed unchanged names,
defaults, types, validators and ordering. Total: **12 comparisons passed**.

The CLI suite separately verifies omitted advanced defaults, all 13 nondefault
overrides, invalid limits/columns, conflicting policies, independent schedules,
serialized lifecycle definitions, and eight example previews. These are local
generation/preflight checks, not cloud acceptance. No claim is made about
workspace permissions, actual clusters, schedule firing or deployed wheel state.
