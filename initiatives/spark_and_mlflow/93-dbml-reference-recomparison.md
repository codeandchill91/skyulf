# dbml reference re-comparison (2026-09-28)

Date: 2026-09-28. Skyulf baseline: `76597ee2` (branch state after PR #179).
Reference: `/Users/BH7043/repositories/dbml-mlops-template` (static read, not
deployed). Earlier comparison: [report36](36-bundle-reference-comparison-and-readiness.md).
Status: planning input only. No code, resource or deployment change.

## Scope

Compared `skyulf-core/templates/databricks/`, `skyulf/integrations/databricks/`
and `skyulf/integrations/mlflow/` with the reference classification/regression
bundles, jobs, configs, services, tests, workflows and schema. The reference
`docs/*` folders are empty, so intent was taken from README/config comments.
Reference behavior was not executed; file presence is not proof it works.

## What changed since report36

SM-30 through SM-36f closed most report36 findings (manual approval, runtime
parameters, independent score clock, simplified graph, multi-metric gates,
Core search/ensembles/nested CV, smaller generated project). Skyulf now leads
the reference on pinning/replay, receipts, promotion/rollback, incremental
scoring, search and serverless compute. Remaining gaps are operational and
peripheral MLOps layers.

## Gap mapping

"Existing" means an open queue task already owns the gap; the listed items are
acceptance additions, not new scope.

| Gap vs reference | Owner | Acceptance additions from this review |
| --- | --- | --- |
| No `run_as`, job/model/experiment permissions, placeholder hosts, home-folder production roots | SM-37 | Optional DAB `registered_models`/`schemas` grants; experiment permissions; operator group `CAN_MANAGE_RUN` for approve/reject/rollback; optional per-target host/catalog prompts (blank keeps `REPLACE_*`); shared non-home `root_path` for syst/prod (today `~/<project>/<target>`, so the experiment under `${workspace.root_path}` lands in the deployer's home) |
| No notifications, health rules, timeouts | SM-38 | `email_notifications`/`webhook_notifications` incl. duration warning; `health.rules` `RUN_DURATION_SECONDS`; task `timeout_seconds`; blank-default variables |
| Hardcoded wheel/MLflow pins, manual wheel build, serverless cost tags | SM-39 | DAB `artifacts:` build instead of manual `uv build --out-dir`; one Skyulf/MLflow version variable (today `0.9.0` appears in four resource places); add `optuna`/`optuna-integration` automatically when `search_strategy=optuna`; serverless `budget_policy_id` and job-level `tags` because `custom_tags` only apply to policy clusters |
| No generated tests, CI/CD, quality tooling; no `ci` target | SM-40 | Add a `ci` target (reference has one) with small sampling; generated `tests/` calling recipe builders plus `preflight_local`; `pyproject.toml`/ruff/pre-commit/`.gitignore`; repository CI: the CLI generation suite is opt-in via `SKYULF_BUNDLE_CLI_TEST_PROFILE`, so add a credential-free render of every `examples/*-init.example.json` checked against `databricks bundle schema`; per-project working directory when one repository holds several generated projects (reference uses `working_directory`) |
| Generation retention | SM-41 | Unchanged |
| No runnable examples | SM-42 | Optional demo-data setup that creates a CDF-enabled sample source so a first deploy runs end to end (reference ships three example projects); generated README links pinned to the docs version matching the wheel |
| No drift/data-quality/performance monitoring or dashboards | SM-23a | Reuse `skyulf/profiling/drift.py` `DriftCalculator` (Polars; PSI/KS/Wasserstein/KL): reference = pinned training snapshot, current = scored window; delayed-label performance by joining matured results on `record_key_columns` with `result_available_at`; outputs to MLflow and one Delta table; optional `quality_monitors` InferenceLog profile on the prediction table; optional `.lvdash.json` with warehouse lookup |
| Serving, A/B, ai_query | SM-19a/b/d | Unchanged (report39) |
| Feature Store / Lakebase online | SM-21a/b | Unchanged (report39) |
| Endpoint inference tables | SM-23b | Unchanged |
| Suffix-scoped dev/CI cleanup | **SM-45 (new)** | See below |
| Event-driven scoring | **SM-46 (new)** | See below |
| MLflow/UC lineage and model documentation | **SM-47 (new)** | See below |
| Drift/performance-triggered retraining | **SM-23c (new)** | See below |
| Resource file layout and display names | **SM-48 (new)** | See below |
| Upgrading an already generated project | **SM-49 (new)** | See below |
| Explicit period backfill (reference `back_fill` + dates) | **SM-50 (new)** | See below |
| Production model-version/run retention | **SM-51 (new)** | See below |

## New tasks

### SM-45 — Suffix-scoped development resource cleanup

Dependencies: SM-37, SM-40. Reference: `cleanup_workflow_resource.yml.tmpl`, `CLEANUP.md.tmpl`.

- Optional cleanup job for `test`/`ci` targets: suffixed model versions and
  aliases, experiment, prediction tables/views/generations.
- `dry_run=true` default, explicit confirmation, refuse production-mode
  targets; report the preview before deletion.
- Separate from SM-41 generation retention; never touches active production outputs.
- Acceptance: dry-run inventory equals deleted set; production target rejected;
  a second developer's suffix untouched.

### SM-46 — Optional table-update scoring trigger

Dependencies: SM-34, SM-38.

- Add `scoring_mode: on_table_update` using the Jobs `trigger.table_update`
  on the score source. Reuse CDF progress, queueing and no-op semantics.
- Acceptance: bursts of source commits queue/coalesce without duplicate rows;
  no-op on unchanged source; trigger paused in development targets; strict validation.

### SM-47 — MLflow/UC lineage and model-version documentation

Dependencies: SM-38.

- Log the pinned training source as an MLflow dataset input (verify the
  MLflow 3.16.1 Delta/UC dataset API first) so UC lineage links table and model.
- Write a model-version description/model card: data window, snapshot
  version, metrics, gate results, recipe digest, `risk_category`.
- Optional DAB `experiments` resource with permissions instead of an implicit
  workspace path.
- Investigate MLflow 3 deployment jobs against the approve flow. Report only;
  must not introduce a second alias writer.
- Acceptance: lineage visible for a live run; description matches saved evidence.

### SM-23c — Drift or performance-triggered retraining

Dependencies: SM-23a, SM-37.

- Optional `retraining_mode: on_drift`: monitor result feeds a condition task
  that runs the existing `train` job.
- Promotion policy and gates stay unchanged; the trigger never approves.
- Acceptance: critical drift starts one queued train run; moderate/none does
  not; repeated signals do not stack runs.

### SM-48 — Split Bundle job resources and clearer display names

Dependencies: none. User-requested after this review.

- Split `resources/workflow.jobs.yml` into `resources/train.job.yml` and
  `resources/score.job.yml`; `include: resources/*.yml` already covers both.
  The `&lifecycle_task` anchors stay inside the train file.
- Optionally clarify job display names (for example `${bundle.name}_training`);
  display names do not change job IDs.
- Keep job keys `train` and `score`. Renaming a key makes DAB delete and
  recreate the job, losing its ID and run history, and breaks
  `bundle run train` commands and recorded live evidence.
- Keep the `src/` layout; notebooks are thin entrypoints and the library does
  not depend on the resource file name.
- Acceptance: redeploy updates the same two job IDs; cross-file
  `${resources.jobs.score.id}` resolves; template/generation tests, bundle
  guide and generated README (`deployed_score_handoff` note) updated; strict
  validation passes for serverless and policy-cluster generation.

### SM-49 — Generated-project upgrade path

Dependencies: SM-39, SM-48.

- `migrate_workflow_config` upgrades JSON only; resources, notebooks and wheel
  references have no upgrade procedure. SM-48/SM-39 make this concrete.
- Regenerate from saved init answers into a temporary directory, show a
  reviewed diff, keep user-edited recipe files, run config migration and
  deployed-contract validation before deploy.
- Acceptance: an SM-48-era project upgrades with the same job IDs, preserved
  recipes and strict validation; guide section added.

### SM-50 — Explicit period backfill action

Dependencies: SM-41.

- Library `publish_replace_period` (SM-15L) is not exposed in the Bundle; the
  score job offers only incremental append and full rebuild.
- Optional score-job operator action with explicit period and pinned model
  version; rows outside the period preserved; receipt written; replay no-op.
- Acceptance: period rows replaced once, other rows unchanged, CDF progress
  unaffected, concurrent score requests queue.

### SM-51 — Production model-version and run retention

Dependencies: SM-37, SM-41.

- Every scheduled training registers a version; nothing retires old versions
  or MLflow runs. SM-41 covers prediction generations; SM-45 covers dev only.
- Preview then scoped operator deletion. Champion, previous_champion,
  challenger and receipt-referenced versions and their runs are protected.
- Acceptance: preview equals deleted set; rollback still succeeds; approval
  evidence of protected versions still verifies.

## Do not copy from the reference

Committed `YOUR_*` placeholders, commented-out schedules, duplicated
classification/regression trees, the duplicated `feature_store_model_enabled`
job parameter, cluster-only compute and unguarded `mlflow.evaluate`
promotion. Skyulf's validated config, receipts and serverless option stay.

## Corrections to the chat report of 2026-09-28

- The schema has 91 properties, but the default setup asks 26 prompts
  (SM-34C4); a new quick/advanced profile is not needed.
- Strict `bundle validate` is exercised by the opt-in CLI suite and live
  reports; the gap is that repository CI does not run it automatically.
