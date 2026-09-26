# SM-34B live graph acceptance

Status: ACCEPTED, 2026-09-26/27. The user authorized live Databricks testing
followed by a commit on 2026-09-26. Profile `skyulf`, existing personal test schema
`workspace.skyulf_lifecycle_test`, existing train job `155738051514173` and
score job `684955889505992`. Both jobs were confirmed idle with paused clocks.

## Approved execution scope

- Back up the existing local deployment, then generate the current eight-task
  graph for pandas automatic classification and Polars manual regression.
- Reuse the two existing jobs. Keep both schedules PAUSED and 900-second run
  limits; no automatic retry. Install the matching locally verified wheel.
- Create a new synthetic source with 240 records, then append exactly three.
  Use `sm34b_20260926_r1` names so previous acceptance evidence is preserved.
- Validate automatic promotion/child scoring and manual train/approve/child
  scoring. Confirm exact graph task states and real dynamic branch-state values.
- Run incremental and unchanged no-op scoring on both engines; audit retained
  rows, model identity, metrics, CV, pinned source and MLflow phase evidence.
- Exercise a failed training task and a notebook-output failure after a durable
  model decision. Verify cleanup and no score handoff, preserving any committed
  model mutation. Restore generated notebooks/config after fault injection.
- Run applicable local gates, record evidence, then DCO-sign the intended commit.

No production resources, resource deletion, extra persistent jobs or clock firing
are in this scope. Temporary helper submissions and new bounded test resources
belong to this explicitly requested rehearsal. Previous run artifacts remain.

## Evidence

All positive paths, both intentional failures, the read-only remote audit and
the local evidence verifier passed. See [the compact receipt](acceptance-summary.json).

| Case | Databricks run | Result |
| --- | --- | --- |
| Synthetic source creation | `1112886513834353` | SUCCESS, 240 rows |
| pandas automatic training | `1020745602367141` | SUCCESS, champion v1 |
| pandas initial child scoring | `220449259044084` | SUCCESS, 240 predictions |
| Polars manual training | `561244445968479` | SUCCESS, candidate v1; scoring excluded |
| Polars approval | `1012755962706750` | SUCCESS, champion v1 |
| Polars initial child scoring | `447480344397786` | SUCCESS, 240 predictions |
| Append three records | `59175300989205` | SUCCESS, source v1 has 243 rows |
| Polars incremental scoring | `1080728831182086` | SUCCESS, three predictions |
| Polars unchanged scoring | `943696298018372` | SUCCESS, zero predictions; observed QUEUED first |
| pandas incremental scoring | `123250001064806` | SUCCESS, three predictions |
| pandas unchanged scoring | `852397185521793` | SUCCESS, zero predictions |
| Invalid model fit | `967615355888372` | Expected FAILED; MLflow FAILED, finalized, no result or scoring |
| Notebook failure after promotion | `781333985699870` | Expected FAILED; promotion preserved, finalized, no result or scoring |
| Read-only MLflow/Delta audit | `683054016979330` | SUCCESS; both engines and failure evidence verified |

Run links use the workspace's run page, for example
[pandas training](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/155738051514173/run/1020745602367141),
[Polars approval](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/155738051514173/run/1012755962706750),
and [Polars queued no-op](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/684955889505992/run/943696298018372).
Training/approval use job `155738051514173`; all scoring uses job
`684955889505992`.

The final [read-only audit](https://dbc-45604623-c18b.cloud.databricks.com/?o=7474646244882000#job/90315752515920/run/683054016979330)
verified source v0 has 240 records and current v1 has 243. Both training runs
pinned v0, stored finite heldout/CV metrics and all seven durable phase receipts.
Prediction histories are exactly 0, 240, 243 rows; no-ops preserve Delta version 2,
model v1 and the initial 240 complete rows. Polars temporal/date parsing and
delayed-label eligibility agree with the frozen source and saved split counts.

The failed fit created no registration intent. The post-decision failure kept
its isolated champion v1 and FINISHED MLflow run; its Databricks parent and
completion task failed, no result receipt was published and no prediction table
was created. Both failures skipped the score condition and child score task.
This exercises actual Databricks branch outcomes through the ALL_DONE join.

### Final deployed state and limits

The normal pandas automatic-promotion configuration is restored. Read-only
`jobs get`/`list-runs --active-only` checks confirmed both persistent jobs idle,
both schedules PAUSED and `max_concurrent_runs=1`. The lifecycle has eight
tasks/eight edges; scoring has one task. Exporting the deployed comparison
notebook confirmed the deliberate failure was removed. No resources were deleted.

This acceptance covers the personal synthetic-data workspace. Clock firing,
company deployment, live reject/rollback and other unexercised failure types
are not claimed; local tests cover manual actions and additional phase failures.

### Initial infrastructure failure

The first wheel upload was blocked by the local build file's OWNER RIGHTS ACL.
The attempted fixture run `60875883898520` consequently failed before data work
because its notebook had not been uploaded. The wheel bytes were rewritten to
a normal file without changing the hash; upload succeeded, and the distinct
`fixture_create_r2` submission above succeeded. This failure is retained as
infrastructure evidence and is not counted as a successful acceptance case.

### Local verification and reproducibility

- Final broad Databricks suite: 735 passed, 16 optional Spark/Delta skips,
  16 warnings, 313.35 seconds.
- Separate real CLI generation suite: 63 passed, 42.14 seconds.
- Strict docs build passed; applicable pre-commit hooks are run before commit.
- Wheel: `skyulf_core-0.9.0-py3-none-any.whl`, SHA-256
  `709372f64349386fb7404861a055b66a958100997f54f8a8d3ff1ad02cc04ac7`.
- Local Python 3.12.10, MLflow 3.16.1, pandas 2.3.2, Polars 1.44.1,
  scikit-learn 1.8.0, pytest 9.1.1, Databricks CLI 1.17.0.
- Independent review approved the implementation and live acceptance helpers.

`control.py` saves exact CLI requests, run/task states and notebook outputs.
`fixture.py` creates/appends the bounded data; `prepare_faults.py` creates the
two isolated fault variants. `run_remaining.py` records the executed sequence
after initial training/approval. `audit.py` runs read-only remote assertions;
`verify_results.py` cross-checks saved task/output/audit evidence and produces
the compact committed `acceptance-summary.json`.
The separately saved `polars_noop-queued.json` records the live queued state;
`final-job-state.json` records the final read-only job/notebook checks. The local
verifier includes both in its acceptance receipt.

Scripts use this rehearsal's existing job IDs, dated resources and idempotency
tokens. Inspect current state and choose fresh resource/token names before any
future rerun. Generated projects, the previous deployment backup, complete raw
CLI evidence, logs and wheel remain local; the compact receipt and scripts are
selected explicitly for Git. No credentials are included.
