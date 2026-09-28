# Integrations code-quality review (2026-09-28)

Scope: `skyulf-core/skyulf/integrations/` (38 modules). Baseline `76597ee2`.
Tool-based review plus targeted reading; not a line-by-line audit. No code change.

## Gate results

| Check | Result |
| --- | --- |
| `ruff check`, `ruff format --check` | Clean, 38 files |
| `ty check` at the locked CI version 0.0.75 | 0 diagnostics in integrations |
| `lizard --CCN 10 -w` | Passes |
| Lizard duplicates | 0.4%, one small block in `mlflow/registry.py` |
| Docstrings (AST scan, private modules included) | None missing |
| TODO/FIXME | None |

SQL identifiers pass `table_name`/`column_name` validation and quoting.
`except BaseException` blocks record failure state and re-raise. All `noqa`
waivers carry reasons.

## Local test run

`python -m pytest skyulf-core/tests/integrations -q -p no:cacheprovider`:
1276 passed, 146 skipped, 15 failed. All 15 failures are subprocess tests that
need an installed `skyulf`: the local `.venv` lacked the editable install that
CI gets from `requirements-ci.txt` (`-e ./skyulf-core`). With `PYTHONPATH`,
11 passed; the remaining 4 use `python -I`, which ignores `PYTHONPATH` by design.
The local `ty` was 0.0.55 while `uv.lock` pins 0.0.75; the older version
reports false diagnostics. Fix: `uv pip install -r requirements-ci.txt`.

Skips: 58 optional Delta, 20 opt-in CLI generation, 1 wheel-install, 1 pyspark.
The Delta and CLI skips are also absent from CI (tracked in SM-40).

## Maintenance findings (not defects)

1. About 20 cross-module imports of underscore helpers, for example
   `_make_client`/`_require_mlflow` (registry → challenger, rejection,
   `_lifecycle_state`), `_frame_bytes` (local_batch → retraining, incremental),
   `_training_settings`/`_training_spec`/`_training_window_mode`
   (local_workflow → workflow_config), `_check_target`/`_scalar`
   (local_publish → local_incremental), `_manifest` (batch → local_publish),
   `_bounded_space` (local_search → project), `_next_actions` re-exported by
   job_runtime, `_mlflow_dtype`/`_scrub_local_artifact_uri` (model → local_model),
   `_get_or_create_experiment` (tracking → lifecycle_tasks),
   `_validate_fold_membership` (local_cv → local_search_results), plus Core
   privates `_build_splitter` and `_validate_bundle`. These are an undeclared
   internal API. Task SM-52.
2. Large modules: `local_retraining.py` 1525 lines, `mlflow/promotion.py` 1035,
   `lifecycle_tasks.py` 720, `local_workflow.py` 715. Report64 deliberately
   deferred broad restructuring; `promotion.py` stays coupled by design.
   `local_retraining.py` is the one split candidate. Task SM-53.
3. 88 functions sit at CCN 9–10, just under the gate. Any growth there needs a
   planned helper extraction; budget it inside the feature task that touches it.
4. 22 lines exceed 100 characters, all strings/docstrings. E501 is not
   selected, so no gate reports them. Fix opportunistically when editing.
