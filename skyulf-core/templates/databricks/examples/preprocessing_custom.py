"""Reference recipes and custom classes to copy into a generated project.

This example is not loaded automatically. Copy the needed classes/helpers into
src/preprocessing.py and enable them in its recipe builders. Training snapshots
that single project file; sibling modules are not packaged automatically.
Never train at module import time. Keep learned values in returned fit state.
For a local demonstration, run the adjacent run_preprocessing_examples.py.

Using these examples in your generated project's src/preprocessing.py:
    1. Open YOUR generated project's file, not the template in the Skyulf checkout.
       Keep any steps you already configured there.
    2. Copy this file's imports (polars, custom_step and the base classes/decorators).
       For centering, also copy CenterCalculator, CenterApplier and
       example_custom_step. For eligibility, copy EligibilityCalculator,
       EligibilityApplier and example_custom_pre_split.
    3. Add the chosen calls to the existing builders' returned lists. For example,
       after copying both sets of classes/helpers, the builders could be:

       def build_pre_split_steps():
           "Keep known non-test rows before splitting."
           return [example_custom_pre_split("is_test")]

       def build_preprocessing():
           "Impute a numeric feature, then learn its training mean."
           return [
               {"name": "impute", "transformer": "SimpleImputer",
                "params": {"columns": ["income"], "strategy": "mean"}},
               example_custom_step("income"),
           ]

       Replace income with your numeric feature column; include it in workflow
       input_columns. The optional is_test filter needs a Boolean source column:
       False rows remain, True/null rows are excluded. It does not need to be a
       model input. If you only want centering, leave build_pre_split_steps()
       unchanged. Edit existing builders instead of defining them a second time.
    4. Keep pipeline.preprocessing empty in config/workflow.json; the Python
       builder supplies these steps. From the generated project, check:
       python src/preview.py --action train
    5. Deploy the edited project and start a new training run. It saves this
       project's source and fitted state. Existing model versions keep their
       saved code; editing the project does not change their predictions.

Copy the definitions into src/preprocessing.py rather than importing this example
as a sibling module: only the project's single Python recipe is snapshotted.
The separate run_preprocessing_examples.py is a local demo, not a training step.
"""

import polars as pl

from skyulf.inference.project_code import custom_step
from skyulf.preprocessing.base import BaseApplier, BaseCalculator, apply_method, fit_method


def build_pre_split_steps():
    """Declare fixed cleanup and training eligibility before the final split.

    Use explicit source columns. Fixed feature edits are saved and replayed once
    on raw model inputs; row filters only select training/evaluation rows. Keep
    learned preprocessing in build_preprocessing() below.
    """
    return [
        # {"name": "missing_sentinel", "transformer": "ValueReplacement",
        #  "params": {"columns": ["feature_value"], "to_replace": -999, "value": None}},
        # {"name": "known_target", "transformer": "DropMissingRows",
        #  "params": {"subset": ["target"], "how": "any"}},
        # {"name": "valid_age", "transformer": "ManualBounds",
        #  "params": {"bounds": {"age": {"lower": 0, "upper": 120}}}},
        # {"name": "unique_observations", "transformer": "Deduplicate",
        #  "params": {"subset": ["feature_value"], "keep": "first"}},
        # example_custom_pre_split("is_test"),
    ]


def build_preprocessing():
    """Return steps in execution order; change column names to match your input."""
    return [
        # {"name": "impute", "transformer": "SimpleImputer",
        #  "params": {"columns": ["feature_value"], "strategy": "mean"}},
        # {"name": "scale", "transformer": "StandardScaler",
        #  "params": {"columns": ["feature_value"]}},
        # custom_step("center", CenterCalculator, CenterApplier,
        #             params={"column": "feature_value"}),
    ]


class CenterCalculator(BaseCalculator):
    """Example custom fit: learn a numeric mean from this training partition only."""

    @fit_method
    def fit(self, X, y, config):
        """Return learned state; CV calls this separately inside every fold."""
        frame = X.to_native() if hasattr(X, "to_native") else X
        column = config["column"]
        return {"column": column, "mean": float(frame[column].mean())}


class CenterApplier(BaseApplier):
    """Example custom apply: reuse the saved mean without learning from new rows."""

    @apply_method
    def apply(self, X, y, params):
        """Preserve engine, row order and row count while transforming one column."""
        frame = X.to_native() if hasattr(X, "to_native") else X
        column = params["column"]
        if isinstance(frame, pl.DataFrame):
            return frame.with_columns((pl.col(column) - params["mean"]).alias(column))
        return frame.assign(**{column: frame[column] - params["mean"]})


def example_custom_step(column):
    """Build the example without enabling it in the default preprocessing chain."""
    return custom_step("center", CenterCalculator, CenterApplier, params={"column": column})


class EligibilityCalculator(BaseCalculator):
    """Example fixed rule: retain the declared value without learning statistics."""

    @fit_method
    def fit(self, X, y, config):
        """Return only the developer's fixed rule, never a statistic from the data."""
        return dict(config)


class EligibilityApplier(BaseApplier):
    """Example training filter: keep rows whose flag equals the declared value."""

    @apply_method
    def apply(self, X, y, params):
        """Keep existing rows in order without editing any column or target value."""
        frame = X.to_native() if hasattr(X, "to_native") else X
        column, value = params["column"], params["keep_value"]
        if isinstance(frame, pl.DataFrame):
            return frame.filter(pl.col(column) == value)
        return frame.loc[frame[column] == value]


def example_custom_pre_split(column):
    """Opt in to retaining known non-test rows; null or true flags are excluded.

    This declaration is the developer's assertion that no statistics are learned.
    Runtime guards check row/value preservation; they do not audit arbitrary code.
    Custom value transformations belong in build_preprocessing().
    """
    return custom_step(
        "non_test_rows",
        EligibilityCalculator,
        EligibilityApplier,
        params={"column": column, "keep_value": False},
        pre_split={
            "effect": "filter",
            "required_columns": [column],
            "learns_from_data": False,
        },
    )
