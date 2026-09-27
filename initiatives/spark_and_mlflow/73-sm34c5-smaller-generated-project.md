# SM-34C5: smaller generated README and preprocessing recipe

Date: 2026-09-27. HEAD: `f4d654cf`. C4 and C5 were committed as `d8e4949f` (DCO signed; all applicable hooks passed).
Baseline is the locally completed C4 tree, not the older committed README.
No cloud run, deployment, push or runtime adapter change. Next: SM-34C6.

## Delivered

| Generated source | C4 baseline | C5 |
| --- | ---: | ---: |
| `README.md.tmpl` | 660 lines | 154 lines |
| `src/preprocessing.py` | 113 lines | 24 lines |

README now follows configure/preview, build/deploy, train/inspect/operator and
score/recovery steps. It retains both jobs, all eight lifecycle task names,
approve/reject/rollback inputs, first-champion limits, scoring pin semantics,
schedule activation, transfer limits and recovery pointers. Eight central guide
links replace repeated date/CV, custom recipe, migration and replay explanations.

The stale `workflow_contract: "1"` is corrected to `"2"`; workflow JSON still
uses `config_version: 1`. Instructions cover all generated notebook entrypoints
and all occurrences of `deployed_score_handoff`, not an obsolete two-notebook
layout. The central guide's old risk-category question wording is also aligned
with C4's config-only advanced field.

The generated Python file keeps two empty recipe builders and minimal commented
Core examples. The prior self-contained tutorial is preserved at
`skyulf-core/templates/databricks/examples/preprocessing_custom.py`. Guides tell
users to copy its imports/classes/helpers into their project's single saved file;
they must not import a sibling example module. No new runtime import, framework
or dependency was added. Existing projects retain their current Python source.

`src/preview.py.tmpl` needed no modification. Its existing loading/validation
continues to operate on both the minimal recipe and enabled custom code.

## Verification

Python 3.12.10, Databricks CLI 1.17.0. Exact test/check commands:

```powershell
$env:SKYULF_BUNDLE_CLI_TEST_PROFILE='skyulf'
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_generation.py -k independent_schedules -x -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_template.py skyulf-core/tests/integrations/test_databricks_project_preprocessing.py skyulf-core/tests/integrations/test_databricks_node_phase_recipes.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m pytest skyulf-core/tests/integrations/test_databricks_bundle_generation.py -q --tb=short -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check skyulf-core/tests/integrations/test_databricks_bundle_generation.py skyulf-core/tests/integrations/test_databricks_project_preprocessing.py skyulf-core/tests/integrations/test_databricks_node_phase_recipes.py skyulf-core/templates/databricks/examples/preprocessing_custom.py 'skyulf-core/templates/databricks/template/{{.project_name}}/src/preprocessing.py'
.venv/Scripts/python.exe -m ruff format --check skyulf-core/tests/integrations/test_databricks_bundle_generation.py skyulf-core/tests/integrations/test_databricks_project_preprocessing.py skyulf-core/tests/integrations/test_databricks_node_phase_recipes.py skyulf-core/templates/databricks/examples/preprocessing_custom.py 'skyulf-core/templates/databricks/template/{{.project_name}}/src/preprocessing.py'
.venv/Scripts/python.exe -m ty check backend skyulf-core/skyulf skyulf-core/tests run_skyulf.py celery_worker.py
git diff --check
```

- The generated README regression failed before the edit: actual task contract
  `2` differed from documented `1`. It now compares every notebook's parameter
  with the documented contract and verifies every generated task is named.
- **109 local tests passed**, with two existing deprecated registry alias warnings.
  The first sandbox attempt had 71 passes and 38 fixture setup errors because
  it could not access the existing global pytest temp directory. The same suite
  completed with local filesystem permission escalation; no product fix required.
- **68 real CLI generation tests passed**, including four schedule combinations,
  both engines, compute/policy combinations and all eight example previews.
- The moved custom eligibility example passes on both engines. The artifact
  replay test now additionally copies and enables the published centering
  example, fits it, changes the source file to raise, then loads the saved model
  in a fresh process and verifies identical predictions for pandas and Polars.
  Existing fresh-process MLflow loading and fold-local CV checks also passed.
- Scoped Ruff, format and full ty passed. Eight README guide URLs were mapped
  to local Markdown files and their anchors checked against rendered heading IDs
  using Python Markdown with `toc`, `fenced_code`, and `tables` extensions.
  The example link uses the repository's default `master` branch; its file exists
  locally and will become available remotely when published.
- Independent read-only review found no remaining issues in the shorter README,
  central links, copied-source contract or regression tests.

These are local generation, saved-artifact and documentation checks. They do
not establish cloud deployment, cluster permissions or live job behavior.
Before the user-requested commit, `mkdocs build --strict` passed (exit 0). Prior persistent-job deployment
limits remain unchanged. Preserve unrelated local test artifacts.


## User-requested example follow-ups

The reference custom classes remain in `examples/preprocessing_custom.py`.
Runnable pandas/Polars demos are in `examples/run_preprocessing_examples.py`.
The reference file now includes explicit copy/import/class/builder instructions,
column requirements and the generated-project preview command. The starter file
also explains its role and empty defaults (26 lines after that clarification).
Both demos produced the expected means/eligible IDs; six focused saved-source
and eligibility tests passed after separating the files. No sibling import was
introduced into the captured project recipe; only the standalone demo imports
its adjacent reference file. The existing recipe helpers remain unchanged.

Final pre-commit verification: the six affected suites (template, workflow config,
preview, project preprocessing, node recipes and real CLI generation) passed
**241 tests**, with two existing registry deprecation warnings.
