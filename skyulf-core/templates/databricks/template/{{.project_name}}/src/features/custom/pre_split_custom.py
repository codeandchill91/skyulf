"""Reusable fixed row-completeness filter, configured in features/pre_split.py.

Only null/NaN count as missing; blank strings and infinity remain values.
No statistics are learned. The surviving values, columns and order are preserved.
This declared pre-split filter applies to training selection, never scoring.
"""

import numpy as np
import pandas as pd
import polars as pl

from skyulf.inference.project_code import custom_step
from skyulf.preprocessing.base import BaseApplier, BaseCalculator, apply_method, fit_method


def _validate(columns, min_present):
    """Reject ambiguous column selections and impossible completeness requirements."""
    if not isinstance(columns, (list, tuple)):
        raise ValueError("Completeness columns must be a list of column names.")
    if not columns or any(not isinstance(column, str) or not column for column in columns):
        raise ValueError("Completeness columns must be nonempty column names.")
    if len(set(columns)) != len(columns):
        raise ValueError("Completeness columns must be unique.")
    if type(min_present) is not int or not 1 <= min_present <= len(columns):
        raise ValueError("min_present must be an integer between 1 and the number of columns.")


class CompletenessCalculator(BaseCalculator):
    """Save the fixed completeness rule without inspecting training values."""

    @fit_method
    def fit(self, X, y, config):
        """Validate and freeze the explicit column selection and minimum count."""
        _validate(config["columns"], config["min_present"])
        return {"columns": list(config["columns"]), "min_present": config["min_present"]}


class CompletenessApplier(BaseApplier):
    """Retain rows meeting the configured minimum number of observed fields."""

    @apply_method
    def apply(self, X, y, params):
        """Filter on selected fields without modifying any survivor or its position."""
        frame = X.to_native() if hasattr(X, "to_native") else X
        counts = np.zeros(len(frame), dtype=int)
        for column in params["columns"]:
            counts += pd.notna(frame[column].to_list())
        keep = counts >= params["min_present"]
        return frame.filter(pl.Series(keep)) if isinstance(frame, pl.DataFrame) else frame.loc[keep]


def minimum_completeness(columns, min_present=1):
    """Declare a fixed training filter over explicitly selected source columns."""
    _validate(columns, min_present)
    return custom_step(
        "minimum_completeness",
        CompletenessCalculator,
        CompletenessApplier,
        params={"columns": list(columns), "min_present": min_present},
        pre_split={
            "effect": "filter",
            "required_columns": list(columns),
            "learns_from_data": False,
        },
    )
