"""Exercise an installed wheel without pytest or optional/backend dependencies."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from skyulf import SkyulfPipeline


def main() -> None:
    """Train, predict and round-trip a small model through the public package API."""
    frame = pd.DataFrame({"feature": np.arange(40, dtype=float)})
    frame["target"] = 3 * frame["feature"] + 2
    pipeline = SkyulfPipeline({"modeling": {"type": "linear_regression"}})
    pipeline.fit(frame, target_column="target")
    features = frame.drop(columns="target").iloc[:5]
    predictions = pipeline.predict(features)
    np.testing.assert_allclose(predictions, frame["target"].iloc[:5], atol=1e-8)

    with tempfile.TemporaryDirectory(prefix="skyulf-smoke-") as directory:
        path = Path(directory) / "model.pkl"
        pipeline.save(str(path))
        restored = SkyulfPipeline.load(str(path))
        np.testing.assert_allclose(restored.predict(features), predictions, atol=1e-8)
    print("skyulf-core wheel: training, prediction and save/load passed")


if __name__ == "__main__":
    main()
