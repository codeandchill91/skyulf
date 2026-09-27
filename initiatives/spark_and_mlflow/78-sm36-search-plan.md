# SM-36: bounded Core search and optional model explanations

Date: 2026-09-27. SM-35 committed as `b67594b7` with DCO and passing hooks.
User requested continuing SM-36 after that commit. Approved scope and routing:
reports 37 and 58; the later user decision selects one base model in setup.

## Design and file map

Reuse `pipeline.modeling.type=hyperparameter_tuner`, `base_model`, and the flat
Core `TuningConfig` search fields. Generated projects directly select a tuning
strategy; ordinary model configurations remain supported by the library.
The existing workflow CV settings feed candidate evaluation once; no additional
post-search fixed-model CV is silently launched. The final holdout never enters
search or preprocessing fit. Preserve temporal metadata without making it a
required scoring feature.

- `databricks/local_search.py`: validate the registered base model, finite
  search space, strategy/budgets and metric; produce an effective Core modeling
  dictionary. Preserve fixed base parameters as singleton search axes and reject
  conflicts. Reuse all five Core strategies and their actual supported knobs,
  including bounded halving resources and optional Optuna dependencies.
  Default spaces come from the same Core catalog used by Canvas; no default
  manual JSON search-space prompt. Grid has its own candidate-product budget.
- `local_cv.py`, `workflow_config.py`, `local_retraining.py`: route model task
  checks through the base model; prepare shared search CV, train with Core,
  persist effective settings/trials/best result. SDK and durable tasks share this
  same fit path and saved-config contract.
- `databricks/local_explanations.py`: optional `pipeline.explainability` settings
  and artifacts through Core's existing SHAP API, with explicit row/feature/display
  bounds, fitted preprocessing only and visible unavailable outcomes.
- Template schema/config/preview/docs: task-filtered model/ensemble selection,
  strategy then default/custom settings (no Basic/Advanced mode), shared CV,
  distinct search/fold seeds and readable effective settings. Optional
  `src/tuning.py::build_search_space(model_type, strategy, params)` returns an
  override or None for Core defaults. Snapshot both resolved settings and source.
- Tests: offline rejection before source/registry access; real small regression
  and classification search, pandas/Polars artifacts, fold-local preprocessing,
  temporal metadata, heldout isolation, MLflow evidence and prediction parity.

## Execution

- [x] Validate search configuration with failing tests, then implement helpers.
- [x] Implement bounded optional explanation helper with focused tests.
- [x] Wire shared training/CV/validation and verify real selected artifacts.
- [x] Add progressive setup, visible reports and documented examples.
- [x] Run relevant integration/Core/template gates and independent review.
- [x] Record exact verification and limitations; update queue/handoff.

Ruling: use the already-approved selected-base-model search route (report58),
including existing supervised voting/stacking calculators; simultaneous model
branches remain SM-36b. Grid admission limits its actual Cartesian product.
Timeout is supported only where Core honors it;
never advertise a hard interruption of an estimator fit. No automatic deployment
or live test is included in this continuation request.

User refinements during execution: inspect Canvas and Core together, retain
all tuning strategies and applicable knobs, CV types and ensemble options;
use automatic model/strategy-specific spaces by default and optional Python
overrides. Expose default/custom strategy settings progressively. Canvas uses
`get_default_search_space`; ensembles use `build_tuning_search_space` and
`prepare_tuning_params`. These existing hooks are authoritative.

Verified gaps requiring focused Core fixes: standalone pipeline tuner omitted
ensemble structural preparation; temporal sorting metadata became a required
inference input; halving omitted max_resources and wrapper resource routing.
All were reproduced with focused failing tests before fixes. Nested CV must
retain truthful labels: Core fixed-model inner stability diagnostics, or tuner
inner search followed by post-selection diagnostic CV, not independently nested
hyperparameter search per outer fold.
