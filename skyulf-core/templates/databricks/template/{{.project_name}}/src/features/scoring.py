"""Choose which rows receive predictions and which extra result columns to publish.

Flow: input rows -> eligibility -> model prediction -> outputs -> result table.

eligibility = checks BEFORE prediction. A check returns None for an accepted row
or a text reason for an excluded row. Excluded rows stay in the result table with
an empty prediction. They are not silently deleted.

outputs = rules AFTER prediction. These add columns such as a price band or an
alert. They do not select training rows, train a model or change its prediction.

Choose a mode and, when needed, skip unavailable target checks:
- SCORING_MODE="pre_split": reuse the saved pre_split.py recipe.
- SCORING_MODE="custom": use the two custom sections below instead.
- SCORING_MODE="combined": pre-split first, custom eligibility on its survivors,
  then model prediction and custom outputs. The first exclusion reason is kept.
- SKIP_TARGET_PRE_SPLIT_STEPS=True: in pre_split/combined modes, omit filters
  that read the actual target, which is unknown at prediction time. Other steps
  still run. False: stop with an explanation if such a filter exists.
  This switch is ignored in custom mode.

Example: target='price'; pre-split checks price and floor_area for missing values.
Use mode "pre_split" and skip=True to retain the floor_area check and skip the
price check. The model's target does not change. A mixed filter reading both is
skipped as a whole; separate the steps to retain the feature-only check.

Both custom lists below are EMPTY by default. Their commented rules are examples,
not active business requirements. To use one, uncomment its dictionary inside the
returned list, adapt the columns/limits, and select "custom" or "combined". Merely
changing SCORING_MODE does not enable these examples. Function paths point to
custom/scoring_custom.py. Leave either list empty to omit those rules.
Combined custom callbacks receive the original accepted inputs; the pre-split
normalization copy is only for selection. Saved model transformations run once.
The model saves the resolved choice and code; edits apply to NEW model versions.
"""

SCORING_MODE = "pre_split"  # Options: pre_split, custom, combined
SKIP_TARGET_PRE_SPLIT_STEPS = False


def build_scoring():
    """Select reuse, custom rules or their ordered combination for this model version."""
    if SCORING_MODE not in ("pre_split", "custom", "combined"):
        raise ValueError("SCORING_MODE must be pre_split, custom or combined.")
    reuse = {"reuse_pre_split": True, "skip_target_steps": SKIP_TARGET_PRE_SPLIT_STEPS}
    if SCORING_MODE == "pre_split":
        return reuse
    custom = {"eligibility": build_eligibility_rules(), "outputs": build_output_rules()}
    return custom if SCORING_MODE == "custom" else {**reuse, **custom}


# 1. BEFORE prediction: which input rows may reach the model?
def build_eligibility_rules():
    """Return custom checks; commented examples are inactive until explicitly enabled."""
    return [
        # Example 1: the observed feature must be present.
        # feature_value=None -> excluded, reason='missing:feature_value'.
        # {
        #     "name": "observed_value",
        #     "version": "1",
        #     "function": "custom.scoring_custom.require_observed_values",
        #     "params": {"columns": ["feature_value"]},
        # },
        # Example 2: the same value must be finite and between 0 and 120 inclusive.
        # feature_value=-1 -> excluded, reason='outside_range:feature_value'.
        # Adapt the column/limits, e.g. age in [18, 100] for an adult-only model.
        # {
        #     "name": "allowed_range",
        #     "version": "1",
        #     "function": "custom.scoring_custom.require_value_range",
        #     "params": {"column": "feature_value", "minimum": 0.0, "maximum": 120.0},
        # },
    ]


# 2. AFTER prediction: which additional business columns should be returned?
def build_output_rules():
    """Return business outputs; the commented band example is inactive by default."""
    return [
        # Example 3: publish a band beside each accepted prediction.
        # prediction < 10 -> low; 10 <= prediction < 50 -> medium; >= 50 -> high.
        # For classification, column may be probability_1; check the recorded
        # class order first, then use probability thresholds such as [0.3, 0.7].
        # {
        #     "name": "prediction_band",
        #     "version": "1",
        #     "function": "custom.scoring_custom.prediction_band",
        #     "params": {
        #         "column": "prediction",
        #         "thresholds": [10.0, 50.0],
        #         "labels": ["low", "medium", "high"],
        #         "output": "band",
        #     },
        #     "columns": [{"name": "band", "dtype": "string"}],
        # },
    ]
