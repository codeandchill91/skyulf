# SM-36d - Databricks segmentation training and scoring

Status: WAIT. Requested 2026-09-27. Depends on SM-36; implementation has not started.

## Scope

- Inspect and reuse Core's `kmeans`, `minibatch_kmeans`, `gaussian_mixture`
  and `birch` calculators, appliers, hyperparameter metadata and evaluation.
- Add task-specific Bundle configuration with algorithm and hyperparameters,
  optional `reference_column`, and preprocessing/scaling through existing Core nodes.
- Train without a supervised target. Exclude the reference column from features
  consistently during fitting and inference, while retaining it for interpretation.
- Carry the fitted preprocessing and clustering estimator through the local artifact,
  MLflow registration, reload and existing bounded batch-scoring path.
- Report available cluster quality metrics (silhouette, Calinski-Harabasz,
  Davies-Bouldin), cluster sizes and reference breakdowns with explicit unavailable
  results for degenerate cases rather than fabricated metrics.
- Define cluster-specific comparison, quality gates and approve/rollback behavior;
  cluster IDs can change between versions and must not be treated as stable labels.
- Audit tuning/search and validation separately. Current frontend segmentation has
  no supervised target/CV/advanced tuning. Do not expose those controls without a
  supported unsupervised objective, split and evaluation contract.

## Acceptance

1. Generated projects preview and validate all four algorithms without a target.
2. Real fits on bounded pandas/Polars input preserve preprocessing and reference
   exclusion; saved/reloaded models assign new rows to clusters consistently.
3. Model-specific hyperparameters reach Core; malformed configuration fails before
   remote reads. Scaling uses the saved training transformation.
4. Local MLflow registration/reload and metric reporting work for ordinary and
   degenerate clustering fixtures; lifecycle policy is tested explicitly.
5. One bounded Databricks acceptance scenario verifies task outputs, registered
   artifact and published cluster assignments before claiming cloud support.

This task supplies the clustering portion of the broader SM-17g model-family
coverage item. No segmentation implementation or cloud acceptance is claimed yet.
