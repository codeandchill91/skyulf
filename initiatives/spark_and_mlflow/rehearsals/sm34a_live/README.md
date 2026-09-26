# SM-34A live task-graph rehearsal

The user authorized this final Databricks workflow rehearsal on 2026-09-26.
Profile: `skyulf`; personal workspace; existing schema
`workspace.skyulf_lifecycle_test`. The existing Bundle's two jobs are reused:
train `155738051514173` and score `684955889505992`.

## Scope

- Back up the local deployment and generate the current template for both engines.
- Deploy the real 11-task lifecycle graph with the current matching wheel.
- Keep independent training/scoring cron schedules **PAUSED** throughout testing.
  Train cron is January/July 1 at 03:00; score cron is daily at 03:00.
  Invoke the same `train` action manually; do not wait for or claim a clock firing.
- One new synthetic source `sm34a_20260926_r1_source`: 240 rows then three appended.
- Two models `sm34a_20260926_r1_{pandas,polars}_model` and two corresponding
  `sm34a_20260926_r1_{pandas,polars}_predictions` outputs.
- Pandas classification uses date-free stratified random splitting and automatic
  first-model promotion. Polars regression uses a four-month rolling calendar,
  one-month holdout, source date parsing, availability filtering and manual approval.
- Both use Core imputation/scaling, random forest models and three-fold evaluation CV.
- `training_version=null` selects and persists the current Delta version once.
- Training, registration, comparison, decision, finalization, result publication
  and conditional child scoring run as the actual generated separate tasks.
- Append three source records; run each engine's score and then an unchanged
  rerun. Audit persisted MLflow evidence, aliases, metrics and Delta outputs.

All runs have 900-second timeouts and no task retries/automatic optimization.
The fixture/audit helpers use one-time submissions, not additional persistent
jobs. No schema creation, resource deletion or production-resource modification.
Test tables/models and paused Bundle jobs remain inspectable afterwards.

## Evidence

`control.py` records requests, parent/task/child states and exact notebook exits.
`audit.py` verifies artifacts, aliases, row identities, predictions and output
history remotely. `verify_results.py` validates the collected local evidence.
Generated projects and the previous local deployment are kept in this directory.

## Live finding and correction

The source fixture run `20418446102265` succeeded with 240 rows.
Initial pandas train `1006534187913752` reported job SUCCESS and committed
champion v1, but `publish_result` was EXCLUDED with the message
"dependency type condition was not met"; the child score never ran. This was
an incomplete workflow despite the overall job status.

The branch join now explicitly uses `run_if: NONE_FAILED`, retaining all three
dependencies and the result phase's saved-evidence/status checks. An excluded
inactive branch may join a successful active branch; a failed active dependency
still blocks publication. The corresponding CLI graph regression failed in all
16 policy/compute combinations before the fix; all 63 CLI generation tests passed
afterwards. See [Databricks dependency conditions](https://docs.databricks.com/aws/en/jobs/run-if).

Corrected pandas train `175855943706739` uses a fresh model
`sm34a_20260926_r1_pandas_model_r2`, preserving the original model and failed
workflow evidence. Its data, preprocessing and model settings are unchanged.
No holdout-driven parameter search or gate weakening was used to force a new
promotion. The prediction table name remains the one listed above.

Runtime wheel SHA-256:
`1e2d8f2c7fdbb835b1d66e74587ef698786d247266f46693109ef517b8d7a138`.
All 250 Core Python files match source. The join fix is in the separately
generated Bundle YAML; the runtime wheel did not change.

## Final acceptance: PASS (2026-09-26)

The independent read-only audit `794212622317843` succeeded. The local
`verify_results.py` cross-check of parent tasks, child runs, exact notebook
results, MLflow evidence and Delta history also passed.

| Scenario | Run ID | Observed result |
|---|---|---|
| Corrected pandas training | `175855943706739` | All selected phases including `publish_result` succeeded; automatic champion v1; child score `132275940598247` wrote 240 predictions |
| Polars training | `921386114120286` | Candidate v1; manual review inputs published; no score before approval |
| Polars approval | `519028138418463` | Training tasks excluded; approve and `publish_result` succeeded; child score wrote 240 predictions |
| Polars increment | `541478313431488` | Three new predictions; target Delta version 2 |
| Polars no-op | `1108433218359541` | Initially observed QUEUED; then zero rows and unchanged target version 2 |
| Pandas increment | `468935408925687` | Three new predictions; target Delta version 2 |
| Pandas no-op | `178748492313637` | Zero rows and unchanged target version 2 |
| Final audit | `794212622317843` | Both tables have 243 distinct identities; original 240 full rows unchanged; saved model/metric/split evidence verified |

Pandas: 192 training / 48 heldout rows, heldout accuracy `0.9375`, F1
`0.9361702127659575`, three-fold stratified CV accuracy `0.9635416666666666`.
Polars: 184 window-selected rows, 17 unavailable results excluded, 110 training /
57 heldout rows; heldout RMSE `2.7785388471704864`, R² `0.9011087050003543`,
three-fold temporal CV RMSE `2.1665574768020393`.

Each output has Delta history populations `0 -> 240 -> 243`. Exact row comparison
including prediction/provenance fields confirmed no initial-row replacement.
Both models retain champion v1, source version 0 and FINISHED training runs.
The prefix contains only the source and two prediction tables: no control table.

The existing two jobs are idle; both clocks remain PAUSED. The final deployed
configuration is the pandas automatic-promotion case. Both generated cases are
retained locally for inspection. Existing resources were not deleted; the first
pandas model remains as evidence of the incomplete original graph.

Scope boundaries: this proves the selected automatic bootstrap, manual approve,
incremental/no-op and queued score paths on personal serverless. It does not
prove a wall-clock cron firing, rollback/reject paths of the new graph, competing
train writers, company production permissions or every preprocessing/model.
The subsequently requested graph simplification is recorded separately in
[SM-34B](../../67-sm34b-simplified-lifecycle-graph.md). This report retains the
original eleven-task acceptance evidence and does not validate the replacement.
