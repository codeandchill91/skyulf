
import pandas as pd
import polars as pl
from skyulf.inference.project_code import custom_step
from skyulf.preprocessing.base import BaseCalculator, BaseApplier, fit_method, apply_method

MODE = "filter"
DECLARATION = {"effect": "filter", "required_columns": ["is_test"], "learns_from_data": False}

class EligibleApplier(BaseApplier):
    @apply_method
    def apply(self, X, y, params):
        frame = X.to_native() if hasattr(X, "to_native") else X
        if MODE == "edit":
            if isinstance(frame, pl.DataFrame):
                return frame.with_columns((pl.col("x") + 1).alias("x"))
            return frame.assign(x=frame["x"] + 1)
        if MODE == "reverse":
            return frame.reverse() if isinstance(frame, pl.DataFrame) else frame.iloc[::-1]
        if MODE == "new_column":
            return frame.with_columns(pl.lit(1).alias("extra")) if isinstance(frame, pl.DataFrame) else frame.assign(extra=1)
        if MODE == "wrong_type":
            return frame.to_pandas() if isinstance(frame, pl.DataFrame) else pl.from_pandas(frame)
        if MODE == "dtype":
            if isinstance(frame, pl.DataFrame):
                return frame.with_columns(pl.col("x").cast(pl.Int64))
            return frame.assign(x=frame["x"].astype(int))
        if MODE == "null_fill":
            frame.loc[frame["x"].isna(), "x"] = 0
            return frame
        if MODE == "inplace_drop":
            if isinstance(frame, pl.DataFrame):
                frame.drop_in_place("is_test")
            else:
                frame.drop(columns=["is_test"], inplace=True)
            return frame
        if MODE == "inplace_add":
            frame["extra"] = 1
            return frame
        if MODE == "inplace_edit":
            frame["x"] = frame["x"] + 1
            return frame
        if MODE in {"fit_drop", "fit_edit"}:
            return frame
        if isinstance(frame, pl.DataFrame):
            return frame.filter(pl.col("is_test") == "eligible")
        return frame.loc[frame["is_test"] == "eligible"]

class EligibleCalculator(BaseCalculator):
    @fit_method
    def fit(self, X, y, config):
        frame = X.to_native() if hasattr(X, "to_native") else X
        if MODE == "fit_drop":
            if isinstance(frame, pl.DataFrame):
                frame.drop_in_place("is_test")
            else:
                frame.drop(columns=["is_test"], inplace=True)
        if MODE == "fit_edit":
            frame["x"] = frame["x"] + 1
        return config

def build_pre_split_steps():
    return [
        {"name": "fixed_x", "transformer": "ValueReplacement",
         "params": {"columns": ["x"], "to_replace": 1.0, "value": 1.25}},
        {"name": "canonical_flag", "transformer": "TextCleaning",
         "params": {"columns": ["is_test"], "operations": [{"op": "trim"}]}},
        custom_step("eligible", EligibleCalculator, EligibleApplier,
                    pre_split=DECLARATION),
    ]

def build_preprocessing():
    return [{"name": "scale", "transformer": "StandardScaler",
             "params": {"columns": ["x"]}}]
