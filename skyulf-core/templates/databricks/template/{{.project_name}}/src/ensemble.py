"""Optional project-owned composition for voting and stacking models.

Set ``USE_EXAMPLES`` to True to try these small recipes, then edit the selected
model's dictionary for your task. Returning None keeps the model parameters in
``config/workflow.json`` and Core's estimator defaults. This file runs only for
voting/stacking training and preview; scoring uses the saved fitted artifact.
"""

from typing import Any

USE_EXAMPLES = False

_EXAMPLES: dict[str, dict[str, Any]] = {
    "voting_classifier": {
        "base_estimators": ["logistic_regression", "random_forest"],
        "voting": "soft",
        "weights": {"logistic_regression": 1.0, "random_forest": 2.0},
        "calibrate_base_models": True,
        "calibration_method": "sigmoid",
        "calibration_cv": 3,
        "tune_base_models": True,
        "n_jobs": 1,
    },
    "stacking_classifier": {
        "base_estimators": ["logistic_regression", "random_forest"],
        "final_estimator": "logistic_regression",
        "final_estimator_params": {"C": 1.0},
        "tune_base_models": True,
        "cv": 3,
        "passthrough": False,
        "n_jobs": 1,
    },
    "voting_regressor": {
        "base_estimators": ["linear_regression", "ridge"],
        "base_estimator_params": {"ridge": {"alpha": 2.0}},
        "weights": {"linear_regression": 1.0, "ridge": 2.0},
        "tune_base_models": True,
        "n_jobs": 1,
    },
    "stacking_regressor": {
        "base_estimators": ["random_forest", "ridge"],
        "final_estimator": "ridge",
        "final_estimator_params": {"alpha": 1.0},
        "tune_base_models": True,
        "cv": 3,
        "passthrough": False,
        "n_jobs": 1,
    },
}


def build_ensemble_params(model_type: str) -> dict[str, Any] | None:
    """Return a selected ensemble composition or keep JSON/Core defaults."""
    if USE_EXAMPLES:
        return _EXAMPLES[model_type]
    return None
