# Integration and template simplification plan

> Execute one task at a time using `executing-plans`; do not start implementation
> merely because this plan exists. The user resumed C1-C6 on 2026-09-27.

**Goal:** Reduce duplicated decisions, repeated work and setup/documentation bulk
without changing the supported training, approval, rollback and scoring contracts.

**Architecture:** Keep thin fixed notebook entrypoints and two serialized jobs.
Share ordinary training/evidence operations between the sequential SDK and durable
task adapter. Keep persistence and task-state handling in the task adapter.
Use small explicit helpers rather than a new workflow framework or generic base classes.

**Tech stack:** Python, pandas/Polars, MLflow, Databricks Bundle templates and pytest.

**Spec:** User-requested review of `skyulf-core/skyulf/integrations/` followed by
`skyulf-core/templates/`, and the six findings summarized below, 2026-09-27.

**State:** SM-34C1/C2 and the Sourcery follow-up are committed as `e16b27e8`.
**SM-34C3** is committed as `f4d654cf`; **SM-34C4/C5** are committed as
`d8e4949f`; **SM-34C6** is locally complete, uncommitted. **SM-35** is next.
Original baseline: `454d2dad`, following `daa1e1c7`
and graph commit `bd49f49e`. The unrelated gitignore commit is preserved.

## Findings and constraints

- Databricks integrations currently span 24 files / 7,192 lines; the MLflow
  package spans nine files / 2,479 lines, including comments and docstrings.
  These are orientation counts, not deletion targets.
- `_prepare` and `run_action(train)` overlap in policy, snapshot and champion
  preparation. Fit/comparison calculations already share helpers; retain that reuse.
- `_replay` is called by evaluation, comparison and decision; automatic decision
  then loads evidence/data again. Profile reads before claiming a performance gain.
- Private helpers cross module boundaries, including the task layer importing
  `_bundle_result` from the notebook runtime.
- The initializer has 72 fields, 43 conditional prompts and 1,417 source lines.
  The README template has 653 source lines; generated output varies by options.
- README currently says `workflow_contract: "1"` at its operator section, while
  deployed template/runtime require `"2"`. Track this concrete drift in SM-34C5.
- Current templates call `run_notebook` only for score; its lifecycle branch
  still exists. External callers are not proven absent.

Preserve pinned snapshots, heldout membership, saved custom Python, fold-local
preprocessing, pandas/Polars parity, manual approval without fitting, promotion
receipts, rollback preconditions, uncertain-outcome handling and guarded scoring.
Do not change eight-task graph semantics, two-job serialization or repair policy.
No new dependency, metaprogrammed configuration framework, global cache or broad
file reshuffle. Keep Spark and whole-frame local artifact contracts distinct.

The existing report fix passed one live rendering test (`6136609106178`) and is
committed in `daa1e1c7`. It was not deployed to the persistent jobs: automatic
approval rejected that extra mutation. Do not assume those jobs run the fixed wheel.
This plan does not authorize cloud runs, persistent deployment or a new commit.

## Delivery order

SM-34C1 -> SM-34C2 -> SM-34C3 -> SM-34C4 -> SM-34C5 -> SM-34C6 -> SM-35.
This is the requested delivery order; not every later task is technically blocked
by every earlier one. Complete and verify one slice before starting the next.

### SM-34C1 — Share training preparation and registration operations

**Status:** DONE, committed in `e16b27e8`. [Evidence](69-sm34c1-shared-training-preparation.md).

**Files:** `skyulf-core/skyulf/integrations/databricks/local_workflow.py`,
`lifecycle_tasks.py`, `local_retraining.py`.

**Tests:** `skyulf-core/tests/integrations/test_databricks_local_workflow.py`,
`test_databricks_local_retraining.py`, `test_databricks_lifecycle_tasks.py`,
`test_databricks_training_preparation.py`.

- [x] Map overlapping policy, snapshot/champion resolution and registration
  operations. Record any intentional SDK/task differences before extracting them.
- [x] Pin observable parity for automatic/manual policy, absent/stale champion,
  latest/explicit snapshot, invalid quality gate and registration failure.
- [x] Extract only shared operations. Keep run creation, durable mutation intent,
  phase receipts and finalization owned by their existing execution adapters.
- [x] Verify both SDK and task callers use the shared operations without changing
  saved evidence, public return types or failure/score-handoff semantics.

**Acceptance:** One owner for each extracted business decision, preserved public
entrypoints and passing relevant suites. Do not merge the two execution adapters
into a flag-heavy function merely to remove lines.

### SM-34C2 — Clarify evidence and result ownership

**Status:** DONE, committed in `e16b27e8`; 503 tests after the Sourcery readability follow-up,
lint/type checks and independent review passed. [Evidence](70-sm34c2-evidence-result-ownership.md).

**Files:** `lifecycle_tasks.py`, `local_approval.py`, `local_workflow.py`,
`local_training_evidence.py`, `local_retraining.py`, `job_runtime.py` under the
Databricks integration package; associated evidence/approval/runtime/config tests.
`workflow_config.py` was reviewed; its user-config conversion remains distinct.

- [x] Map private cross-module calls and choose explicit owners for the shared
  training-spec deserialization, verified evidence loading and result construction.
- [x] Reuse one spec conversion path for lifecycle `_spec` and approval evidence
  loading, preserving dates, tuple fields, optional fields and saved custom code.
- [x] Remove the task-to-notebook dependency for result construction. Use an
  existing suitable owner; add a small module only if it removes a real cycle.
- [x] Verify corrupted/foreign evidence, missing champion metrics, approval,
  rejection and rollback outputs against existing contracts.

**Acceptance:** Shared operations have clear ownership without changing importable
APIs accidentally. Naming changes alone do not count as completion.

### SM-34C3 — Avoid redundant replay within a task

**Status:** DONE, committed as `f4d654cf`. 327 tests, lint/type checks and independent
review passed. [Measured operation counts and guards](71-sm34c3-replay-reuse.md).

**Files:** `lifecycle_tasks.py`, `_lifecycle_state.py`, `local_workflow.py`,
`local_approval.py`; `test_databricks_lifecycle_tasks.py` and approval tests.

- [x] Record source reads, artifact downloads and evidence checks for grouped
  train/register and compare/decide paths using a bounded local reproduction.
- [x] Reuse verified state only within the same invocation/task where safe;
  avoid deserializing or reading the same immutable data solely to discard it.
- [x] Preserve fresh registry checks at model mutation boundaries and durable
  checks across tasks. No cross-run/global cache or removal of digest checks.
- [x] Compare operation counts before/after and verify tampered evidence,
  changed champion, phase failures and post-promotion output failure still fail safely.

**Acceptance:** Measured redundant work removed with unchanged outcomes. If a
repeat is necessary, document why and retain it; do not weaken checks for speed.

### SM-34C4 — Reduce initial setup complexity

**Status:** DONE, committed as `d8e4949f`. 127 local tests and 68 CLI cases verified;
12 before/after generated configurations and previews matched.
[Evidence](72-sm34c4-initializer-simplification.md).

**Files:** `skyulf-core/templates/databricks/databricks_template_schema.json`,
`template/{{.project_name}}/config/workflow.json.tmpl`, `examples/*.json`,
integration `workflow_config.py` only if normalization genuinely needs changing.

**Tests:** `test_databricks_bundle_generation.py`,
`test_databricks_bundle_template.py`, `test_databricks_workflow_config.py`,
`test_databricks_workflow_preview.py`.

- [x] Separate essential first-run inputs from advanced settings. Retain existing
  date, CV, sampling, schedule, compute and lifecycle capabilities.
- [x] Reduce repeated prompt conditions and explain advanced configuration through
  existing example files/config editing; preserve supported init-file inputs.
- [x] Keep domain validation in Core and CLI input validation at its boundary;
  do not introduce a new schema-generation framework to shorten JSON.
- [x] Generate and preview date-free/temporal, pandas/Polars, manual/automatic
  and serverless/policy-cluster cases with real CLI checks.

**Acceptance:** Simpler basic setup with explicit advanced paths, unchanged
effective configurations for existing examples and a recorded compatibility decision.
SM-42 can build on this; this task does not implement its future feature scenarios.

### SM-34C5 — Keep generated projects small and documentation consistent

**Status:** DONE, committed as `d8e4949f`. 241 combined pre-commit tests passed;
[starter reduction and saved-code evidence](73-sm34c5-smaller-generated-project.md).

**Files:** `template/{{.project_name}}/README.md.tmpl`, `src/preprocessing.py`,
`src/preview.py.tmpl` where needed, and `docs/user_guide/databricks_bundle*.md`.

**Tests:** `test_databricks_bundle_template.py`,
`test_databricks_bundle_generation.py`, `test_databricks_project_preprocessing.py`.

- [x] Fix the stale graph contract and obsolete two-notebook wording; add a
  meaningful generated-project consistency check for the current contract.
- [x] Keep README focused on configuration, preview, run and result/operator steps;
  link detailed recipes and recovery explanations to the central guides.
- [x] Keep the two recipe entrypoints and a minimal usable example. Move unused
  calculator/applier tutorials out of every generated project's active Python file.
- [x] Preserve self-contained custom-code packaging: moving examples must not
  introduce sibling-module imports that trained artifacts cannot replay.
- [x] Verify generated project preview, custom-code snapshot/replay and guide links.

**Acceptance:** Smaller usable starter output, no contradictory contract/task
instructions, and all current custom preprocessing capabilities documented.

### SM-34C6 — Retire redundant notebook lifecycle routing carefully

**Status:** DONE locally, uncommitted. 204 combined tests and 10 final output tests
passed (205 distinct cases), with lint/type checks and independent review.
[Compatibility decision and evidence](74-sm34c6-explicit-notebook-entrypoints.md).

**Files:** `job_runtime.py`, template `src/score.py`, runtime/notebook tests,
public docs and exports only where the usage audit requires it.

- [x] Inventory repository and documented callers of `run_notebook` and
  `run_bundle_action`, including tests and direct SDK examples.
- [x] Make score and fixed lifecycle notebook entrypoints explicit. Remove the
  unused lifecycle routing branch only if compatibility allows; otherwise retain
  a small delegating wrapper with a documented compatibility decision.
- [x] Preserve `run_action`/`train_local_candidate` SDK APIs and reject role/action
  overrides, unresolved references and invalid score pins as before.
- [x] Run notebook/runtime/output and relevant generated-project suites; update
  the queue and handoff with exact checks and remaining deployment limits.

**Acceptance:** One maintained notebook path per responsibility, no duplicated
business logic, no unannounced public API break. Resume SM-35 after this gate.

## Verification and tomorrow's entry point

Start by reading this file, `HANDOFF.md` and live `git status`/history. Preserve
unrelated work; do not infer a clean tree from this historical baseline.

Use focused behavioral tests first, then complete affected suites, scoped Ruff,
format and full ty. Real CLI generation is required for template changes.
Do not claim a cloud run from a successful local/CLI check. Documentation-only
queue creation requires link/consistency checks, not ML training or deployment.

C1-C6 are locally complete. Resume SM-35 from `OPEN_QUEUE.md` and the
local Bundle improvement program. C6 remains uncommitted; no scheduled automation
was created. Preserve the documented cloud deployment limits.
