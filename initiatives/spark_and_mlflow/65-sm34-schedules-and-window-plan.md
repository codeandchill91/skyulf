# SM-34 independent schedules and pinned training windows

> For agentic workers: use subagent-driven-development for implementation and
> scoped review. Complete the preceding integration quality corrections first.

**Goal:** Let operators independently schedule training and scoring, configure
the training window, and inspect the concrete data selection even if fitting
fails.

**Status:** LOCAL DONE on 2026-09-26. Implementation, independent review and
local/CLI gates passed. Live schedule triggers and contention were not run.

**Architecture:** Keep the existing two-job Bundle and Core training services.
Scheduling belongs to Bundle variables; data-selection policy belongs to
workflow JSON. The existing MLflow training run records its source/window before
read, split, CV and fit, then records enriched candidate evidence on success.

**Tech stack:** Python, pandas/Polars, MLflow, Delta source selection, Databricks
CLI 1.17.0, Go templates and Quartz job schedules.

**Spec:** SM-34 in [the approved local Bundle program](37-local-bundle-improvement-program.md).
User refinements: selected schedules enabled by default, editable cron, no
forced monthly cadence, score-only operation, no extra control tables or jobs.

## Global constraints and decisions

- Work on the existing user-selected branch `090`. No push or deployment.
- Finish report64 corrections and review before implementation starts here.
- Keep exactly `train` and `score`, concurrency one, queue enabled, zero mutation
  retries; lifecycle handoff uses the same score job as independent scheduling.
- Manual mode omits a schedule. Scheduled mode defaults to `UNPAUSED`; explicit
  `PAUSED` remains available. Verify resolved development target values, not just
  raw YAML. Resource pause settings override mode/preset defaults per the
  [official deployment-mode documentation](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes).
- Preserve existing `train_monthly` action for this slice; explain that it pins
  the latest source at invocation and does not mandate monthly cron. Do not add
  compatibility aliases or a new action-routing layer.
- Date-free full snapshots remain supported. Cron timezone, source parsing
  timezone and data-window timezone remain distinct.
- No new group split, serving, native Spark FE, quality gates or model tuning.
- English files/examples, existing Core test locations, one-line test docstrings.
- No new live run is implied; local/CLI verification and cloud proof stay distinct.

## Task 1: independent schedules and configurable calendar selection

Files: `skyulf-core/templates/databricks/databricks_template_schema.json`, existing
`template/{{.project_name}}/databricks.yml.tmpl`, job resources, workflow JSON,
README; `local_workflow.py`, `workflow_config.py`; existing Bundle generation,
template, window and config tests. Update the user-guide walkthrough.

Fields:

| Field | Default | Contract |
|---|---|---|
| retraining_mode | manual | Existing manual/scheduled choice |
| retraining_cron_expression | 0 0 3 3 * ? | Existing editable Quartz cron |
| retraining_timezone_id | UTC | Existing train clock |
| retraining_pause_status | UNPAUSED | PAUSED/UNPAUSED variable when scheduled |
| scoring_mode | manual | Independent manual/scheduled choice |
| scoring_cron_expression | 0 0 * * * ? | Hourly example, editable |
| scoring_timezone_id | UTC | Independent score clock |
| scoring_pause_status | UNPAUSED | Independent PAUSED/UNPAUSED variable |
| holdout_months | 1 | Rolling temporal only; null otherwise |
| result_availability_lag_hours | 0 | Availability filtering active; null otherwise |

- [x] First add failing tests for all four train/score scheduling combinations,
  independent pause/clock values and unchanged two-job/handoff structure.
- [x] Add conditional initializer questions with clear examples. Manual mode
  hides its schedule details. Emit schedule fields as target-overridable Bundle
  variables, never insert them into model/data workflow config.
- [x] Add temporal rolling holdout tests; require an integer from 1 through
  lookback-1. Existing total lookback includes holdout. Random rolling uses
  test_size and null holdout_months; fixed temporal retains explicit boundaries.
- [x] Add result lag tests; nonnegative integer up to 87600 elapsed UTC hours.
  Scheduled cutoff is invocation UTC minus lag; manual train retains explicit
  result_cutoff. Active filtering without an event column must continue working.
  Preserve inclusive result cutoff and half-open observation window.
- [x] Cover year/leap-month boundaries, spring/fall DST, local-vs-UTC month
  rollover and validation before source I/O. Do not infer any data window from
  cron frequency. Keep default four completed months/one heldout month/UTC.
- [x] Update preview, README and guide with score-only scheduling and an example
  using two-month holdout and delayed results. Explain pause vs no-op vs queue.
- [x] Run focused suites, actual installed-CLI generation, resolved strict dev
  validation, Ruff/format and full ty; obtain scoped review before Task2.

## Task 2: persist a concrete training pin before fitting can fail

Files: `local_retraining.py`, relevant existing tracking integration as needed,
local retraining/workflow tests, README and walkthrough. Reuse existing tracking
context rather than introducing nested runs or another orchestration module.

- [x] Reproduce a read/CV/fit failure and assert that an MLflow run records the
  resolved Delta version, input/target/keys, event/result boundaries and engine
  before that operation. Existing code opens the run only after fitting.
- [x] Open the existing run earlier after argument validation; log the pipeline
  configuration/source and a clearly named `training_snapshot.json` containing
  the concrete selection. Keep success-only `candidate_training_spec.json`
  and comparison/membership evidence semantics unchanged.
- [x] A runtime failure must leave the run FAILED, without model publication,
  alias mutation or score handoff. Do not start tracking for invalid arguments.
- [x] Pin Delta history once and preserve resolved boundaries through the run.
  Document explicit replay using the saved source version and boundaries with
  manual `train`; a new `train_monthly` invocation deliberately selects fresh
  data and is not replay. Saved pipeline/source/settings must accompany replay.
  No automatic retry, extra control table or new generic replay service.
- [x] Test failures and successful evidence on pandas/Polars, changed current
  source/time, manual/automatic lifecycle and existing heldout approval replay.
- [x] Run affected local suites, scoped lint/full ty, docs and final whole-change
  review. Record actual results and limitations in report65 and the open queue.

Live contention and scheduled execution need separately scoped acceptance; CLI
validation proves rendered/resolved configuration, not an executed clock trigger.

## Verification log

Task1 local checks: 231 focused tests and 63 installed-CLI generation tests
passed; full ty, scoped Ruff/format and whitespace checks passed. Independent
review approved and independently ran 36 window tests. The parent built a
current wheel and strictly validated the
generated `dev` target using profile `skyulf`, with no deployment or job run:

| Setting | First resolution | Variable override resolution |
| --- | --- | --- |
| Train pause | PAUSED | UNPAUSED |
| Train clock | `0 0 3 1 1,7 ?`, Europe/Vilnius | Unchanged |
| Score pause | UNPAUSED | PAUSED |
| Score clock | `0 15 * * * ?`, America/New_York | Unchanged |
| Both jobs | Concurrency 1, queue enabled | Unchanged |

Generated project (archived after checking):
`.cache/sm34-artifacts/.tmp-sm34-cli-all/test_cli_independent_schedules3/output/`
`sm33_generated`. Local `resolved-sm34.json` and `resolved-sm34-overrides.json`
record these results. This Task1 wheel predates the subsequent Task2 changes.
An additional project omitted both pause answers during initialization;
`.cache/sm34-defaults/output/sm33_generated/resolved-sm34-defaults.json` confirms
both schedules resolve to `UNPAUSED` in dev. All five temporary Task1 test
directories were moved under `.cache/sm34-artifacts`; pre-existing temporary
directories and MLflow data were left untouched.

Task2 opens the existing MLflow run before source read, split, CV, fitting and
heldout evaluation. Early artifacts are `training_snapshot.json` (resolved
selection) and `training_pipeline_config.json` (original pipeline input).
The existing `skyulf_pipeline_config.json` retains the effective pipeline;
using it as original input would prepend fixed cleanup twice. Successful
membership/comparison evidence and publication ordering remain unchanged.

The final combined 21-module suite passed **647 tests**, with one optional Spark
skip because pyspark is absent, and seven existing deprecation warnings.
Initial broad verification found six obsolete test fixtures using an `unused`
tracking URI. They now use isolated SQLite/artifact stores; all original FE
assertions remain. Their full module passed 66 tests. A final optional-dependency
fixture adjustment passed its six affected cases. These counts overlap.

Independent whole-change review and fixture re-review approved the changes;
25 independent failure/pin/replay tests passed. Full ty, integration Ruff/format,
strict documentation and whitespace checks passed. No code was deployed or
uploaded, and no job was run for SM-34. Local MLflow failure/approval/replay tests
use real stores but inject source failures and simulated clocks/history.

Final wheel: `.cache/sm34-defaults/output/sm33_generated/dist/`
`skyulf_core-0.9.0-py3-none-any.whl`. All 248 Core Python files match current source.
SHA-256: `28407a06663f0d3cdf40a757cc96329f775b31752a5441ec5ea7b2e1b477004a`.
This local wheel has not replaced any earlier live rehearsal wheel.
