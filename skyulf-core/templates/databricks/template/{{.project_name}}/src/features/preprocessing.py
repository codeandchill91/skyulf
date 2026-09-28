"""Configure feature transformations fitted separately within each training fold.

Uncomment a step and its import, then adapt its columns. Core and custom steps
run in the order shown in the same list. All Python
files under features are saved with the model; inference reuses fitted state.
"""

# from .custom.preprocessing_custom import frequency_encoding


def build_preprocessing():
    """Return ordered Core/custom transformations with project-specific parameters."""
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
