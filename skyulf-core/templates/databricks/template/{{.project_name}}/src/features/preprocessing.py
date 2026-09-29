"""Configure feature transformations fitted separately within each training fold.

Single-model training calls the default recipe. For multi-target training,
multi_model.py selects preprocessing_recipe independently for every model.
Available starters: default, none, frequency_only, imputer_only, combined.
Adapt their columns or add your own named function to the mapping below.
Core and custom steps run in list order. Only the selected recipe runs.
All Python files are saved with the model; inference reuses its fitted state.
"""

from .custom import preprocessing_custom

# from .custom.preprocessing_custom import frequency_encoding


def build_preprocessing(recipe="default"):
    """Select a named step list; each model and CV fold learns its own fitted state."""
    recipes = {
        "default": _default_recipe,
        "none": lambda: [],
        "frequency_only": _frequency_only,
        "imputer_only": _imputer_only,
        "combined": lambda: _imputer_only() + _frequency_only(),
    }
    if recipe not in recipes:
        raise ValueError(f"Unknown preprocessing recipe: {recipe}. Choose from {list(recipes)}.")
    return recipes[recipe]()


def _frequency_only():
    """Encode category using only this model's training frequencies; no imputation."""
    return [preprocessing_custom.frequency_encoding(columns=["category"])]


def _imputer_only():
    """Fill feature_value from this model's training mean; no custom encoding."""
    return [
        {
            "name": "impute",
            "transformer": "SimpleImputer",
            "params": {"columns": ["feature_value"], "strategy": "mean"},
        },
    ]


def _default_recipe():
    """Keep the default inactive; uncomment steps and their imports to customize it."""
    return [
        # {"name": "impute", "transformer": "SimpleImputer",
        #  "params": {"columns": ["feature_value"], "strategy": "mean"}},
        # {"name": "scale", "transformer": "StandardScaler",
        #  "params": {"columns": ["feature_value"]}},
        # frequency_encoding(columns=["category"]),
        # Temporal history belongs here, after the training/holdout split.
        # Use an observed clock in input_columns (distinct from the job's event_column).
        # {"name": "recent_value", "transformer": "RollingAggregate",
        #  "params": {"columns": ["feature_value"], "window": 5,
        #             "sort_by": "observation_time", "group_by": ["entity"],
        #             "history_mode": "carry", "history_max_rows": 1000,
        #             "history_max_bytes": 48000}},
        # {"name": "drop_clock", "transformer": "DropMissingColumns",
        #  "params": {"columns": ["observation_time"], "missing_threshold": None}},
    ]
