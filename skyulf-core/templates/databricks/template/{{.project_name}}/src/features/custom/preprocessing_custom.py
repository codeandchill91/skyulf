"""Training-only category frequencies, configured in features/preprocessing.py.

Replace selected string columns with their training frequency (count / rows).
Null and unseen values map to zero. No target values are used. Each CV fold fits
its own vocabulary; inference reuses the saved mapping without batch learning.
Cast numeric category IDs to strings upstream. Other columns and row order stay
unchanged. Do not select record-key or target columns as model features here.
"""

from collections import Counter

import pandas as pd
import polars as pl

from skyulf.inference.project_code import custom_step
from skyulf.preprocessing.base import BaseApplier, BaseCalculator, apply_method, fit_method


def _validate_columns(columns):
    """Require explicit, unique column names to avoid accidental feature selection."""
    if not isinstance(columns, (list, tuple)):
        raise ValueError("Frequency columns must be a list of column names.")
    if not columns or any(not isinstance(column, str) or not column for column in columns):
        raise ValueError("Frequency columns must be nonempty column names.")
    if len(set(columns)) != len(columns):
        raise ValueError("Frequency columns must be unique.")


def _category(value):
    """Preserve exact string identities and map missing categories to the fallback."""
    if isinstance(value, str):
        return value
    if pd.isna(value):
        return None
    raise ValueError("Frequency encoding expects strings or null; cast categories first.")


def _frequencies(series, row_count):
    """Learn observed category proportions using training rows as the denominator."""
    counts = Counter(_category(value) for value in series.to_list())
    return {key: count / row_count for key, count in counts.items() if key is not None}


class FrequencyCalculator(BaseCalculator):
    """Learn category frequencies from the current training partition only."""

    @fit_method
    def fit(self, X, y, config):
        """Freeze a per-column mapping that can be reused by held-out and score rows."""
        _validate_columns(config["columns"])
        frame = X.to_native() if hasattr(X, "to_native") else X
        if len(frame) == 0:
            raise ValueError("Frequency encoding requires nonempty training rows.")
        return {
            "frequencies": {
                column: _frequencies(frame[column], len(frame)) for column in config["columns"]
            }
        }


class FrequencyApplier(BaseApplier):
    """Replace categories with saved frequencies without changing row membership."""

    @apply_method
    def apply(self, X, y, params):
        """Use zero for missing/unseen values and preserve all unselected columns."""
        frame = X.to_native() if hasattr(X, "to_native") else X
        encoded = {
            column: [mapping.get(_category(value), 0.0) for value in frame[column].to_list()]
            for column, mapping in params["frequencies"].items()
        }
        if isinstance(frame, pl.DataFrame):
            return frame.with_columns(
                [pl.Series(column, values, dtype=pl.Float64) for column, values in encoded.items()]
            )
        result = frame.copy()
        for column, values in encoded.items():
            result[column] = pd.Series(values, index=result.index, dtype=float)
        return result


def frequency_encoding(columns):
    """Build a saved, fold-local frequency encoder for selected categorical fields."""
    _validate_columns(columns)
    return custom_step(
        "frequency_encoding",
        FrequencyCalculator,
        FrequencyApplier,
        params={"columns": list(columns)},
    )
