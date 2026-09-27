"""Run the custom preprocessing demos on tiny pandas and Polars frames.

From the Skyulf checkout, with Skyulf installed:
python skyulf-core/templates/databricks/examples/run_preprocessing_examples.py

This local demo imports the adjacent reference file. Neither file is loaded by
Databricks jobs. For training, copy the custom classes/helpers into the generated
src/preprocessing.py and enable the desired steps in its recipe builders.
"""

import pandas as pd
import polars as pl
from preprocessing_custom import (
    CenterApplier,
    CenterCalculator,
    EligibilityApplier,
    EligibilityCalculator,
)


def run_centering_example(engine="pandas"):
    """Learn mean 3 from training rows, then reuse it on unseen values 7 and 9."""
    # Learning on the new rows would incorrectly produce [-1, 1].
    train = pd.DataFrame({"feature_value": [1.0, 3.0, 5.0]})
    unseen = pd.DataFrame({"feature_value": [7.0, 9.0]})
    if engine == "polars":
        train, unseen = pl.from_pandas(train), pl.from_pandas(unseen)
    elif engine != "pandas":
        raise ValueError("Example engine must be pandas or polars.")

    state = CenterCalculator().fit(train, {"column": "feature_value"})
    return CenterApplier().apply(unseen, state)  # Expected: [4.0, 6.0].


def run_eligibility_example(engine="pandas"):
    """Keep IDs 1 and 4; true and unknown test flags are excluded from training."""
    rows = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "feature_value": [10.0, 20.0, 30.0, 40.0],
            "is_test": [False, True, None, False],
        }
    )
    if engine == "polars":
        rows = pl.from_pandas(rows)
    elif engine != "pandas":
        raise ValueError("Example engine must be pandas or polars.")

    state = EligibilityCalculator().fit(rows, {"column": "is_test", "keep_value": False})
    return EligibilityApplier().apply(rows, state)  # Original values/order retained.


if __name__ == "__main__":
    for example_engine in ("pandas", "polars"):
        print(f"\n{example_engine}: centering [7, 9] with saved training mean 3 -> [4, 6]")
        print(run_centering_example(example_engine)["feature_value"].to_list())
        print(f"\n{example_engine}: training eligibility -> keep IDs [1, 4]")
        eligible = run_eligibility_example(example_engine)
        print({column: eligible[column].to_list() for column in eligible.columns})
