"""Search fold admission and durable selected-model evidence."""

from __future__ import annotations

import hashlib
import json
import math

import pandas as pd
import polars as pl
import pytest

from skyulf.data.dataset import SplitDataset
from skyulf.inference.local_pipeline import load_local_pipeline, save_local_pipeline
from skyulf.integrations.databricks.local_cv import LocalCVSpec
from skyulf.integrations.databricks.local_search_results import (
    post_selection_cv,
    tuning_evidence,
    validate_search_membership,
)
from skyulf.pipeline import SkyulfPipeline


def _pipeline() -> dict:
    """Define a small real search with a fixed preprocessing recipe."""
    return {
        "preprocessing": [],
        "modeling": {
            "type": "hyperparameter_tuner",
            "base_model": {
                "type": "random_forest_regressor",
                "params": {"n_estimators": 3, "n_jobs": 1},
            },
            "strategy": "grid",
            "metric": "mse",
            "n_trials": 2,
            "search_space": {"max_depth": [2, 3]},
            "cv_enabled": True,
            "cv_folds": 3,
            "cv_type": "k_fold",
            "cv_shuffle": True,
            "cv_random_state": 42,
            "random_state": 42,
            "n_jobs": 1,
        },
    }


def _artifact(tmp_path):
    """Fit and reload the actual tuple-bearing Core tuning artifact."""
    frame = pd.DataFrame({"x": range(24), "target": [2 * x + 1 for x in range(24)]})
    pipeline = SkyulfPipeline(_pipeline())
    pipeline.fit(SplitDataset(train=frame.iloc[:20], test=frame.iloc[20:]), target_column="target")
    path = tmp_path / "artifact"
    save_local_pipeline(pipeline, path)
    return load_local_pipeline(path), frame.iloc[:20]


def test_membership_rejects_small_nested_inner_class_folds() -> None:
    """Nested search cannot start if an inner stratified fold loses a class."""
    frame = pd.DataFrame({"x": range(10), "target": [0] * 8 + [1] * 2})
    config = {
        "modeling": {
            "type": "hyperparameter_tuner",
            "base_model": {"type": "random_forest_classifier"},
        }
    }
    with pytest.raises(ValueError, match="class|fold"):
        validate_search_membership(
            frame,
            config,
            LocalCVSpec(enabled=True, folds=4, method="nested_cv"),
            target_column="target",
            event_column=None,
        )


def test_membership_rejects_small_disabled_cv_shuffle_split() -> None:
    """The single fallback shuffle split still needs viable train and validation rows."""
    frame = pd.DataFrame({"x": [1, 2, 3], "target": [1, 2, 3]})
    config = {
        "modeling": {"type": "hyperparameter_tuner", "base_model": {"type": "linear_regression"}}
    }
    with pytest.raises(ValueError, match="fold|rows"):
        validate_search_membership(
            frame, config, LocalCVSpec(enabled=False), target_column="target", event_column=None
        )


def test_tuning_evidence_records_real_score_and_selected_parameters(tmp_path) -> None:
    """A persisted tuner exposes finite, JSON-safe search results."""
    artifact, _frame = _artifact(tmp_path)
    evidence = tuning_evidence(artifact)
    assert evidence is not None
    assert evidence["status"] == "completed"
    assert evidence["modeling"]["base_model"]["type"] == "random_forest_regressor"
    assert evidence["requested_metric"] == "mse"
    assert evidence["scoring_metric"] == "neg_mean_squared_error"
    assert math.isfinite(evidence["best_score"])
    assert evidence["best_params"]["max_depth"] in (2, 3)
    assert evidence["n_trials"] == len(evidence["trials"])
    json.dumps(evidence, allow_nan=False)


def test_nonfinite_trial_is_explicitly_failed_and_json_safe(tmp_path) -> None:
    """A failed Core trial cannot put NaN into durable run evidence."""
    artifact, _frame = _artifact(tmp_path)
    estimator = artifact.pipeline.model_estimator
    assert estimator is not None
    _model, result = estimator.model
    result.trials.append({"params": {"max_depth": 9}, "score": float("nan")})
    evidence = tuning_evidence(artifact)
    assert evidence is not None
    assert evidence["trials"][-1]["status"] == "failed"
    assert evidence["trials"][-1]["score"] is None
    json.dumps(evidence, allow_nan=False)


def test_nonfinite_winner_cannot_be_reported_as_completed(tmp_path) -> None:
    """A search with no finite winner cannot produce success evidence."""
    artifact, _frame = _artifact(tmp_path)
    estimator = artifact.pipeline.model_estimator
    assert estimator is not None
    _model, result = estimator.model
    result.best_score = float("nan")
    with pytest.raises(ValueError, match="finite best score"):
        tuning_evidence(artifact)


def test_source_digest_is_derived_from_saved_search_source(tmp_path) -> None:
    """Run evidence must identify the exact search source stored with the artifact."""
    artifact, _frame = _artifact(tmp_path)
    artifact.pipeline.config["search_python_source"] = "def selected():\n    return 1\n"
    evidence = tuning_evidence(artifact)
    assert evidence is not None
    assert (
        evidence["source_code_sha256"]
        == hashlib.sha256(b"def selected():\n    return 1\n").hexdigest()
    )


def test_polars_nested_membership_accepts_viable_folds() -> None:
    """Nested inner admission must preserve Polars frame semantics."""
    frame = pl.DataFrame({"x": range(24), "target": [i % 2 for i in range(24)]})
    config = {
        "modeling": {
            "type": "hyperparameter_tuner",
            "base_model": {"type": "random_forest_classifier"},
        }
    }
    validate_search_membership(
        frame,
        config,
        LocalCVSpec(enabled=True, folds=4, method="nested_cv"),
        target_column="target",
        event_column=None,
    )
    assert len(frame) == 24


def test_post_selection_cv_only_runs_for_nested_search(tmp_path) -> None:
    """Nested diagnostics score selected fixed params without a second search."""
    artifact, frame = _artifact(tmp_path)
    frame = frame.assign(event_time=pd.date_range("2025-01-01", periods=len(frame), tz="UTC"))
    assert (
        post_selection_cv(
            frame,
            artifact,
            LocalCVSpec(enabled=True, folds=3, method="k_fold"),
            target_column="target",
        )
        is None
    )
    report = post_selection_cv(
        frame,
        artifact,
        LocalCVSpec(enabled=True, folds=3, method="nested_cv"),
        target_column="target",
        event_column="event_time",
    )
    assert report is not None
    assert report["status"] == "post_selection_diagnostic"
    assert report["cv_config"]["method"] == "k_fold"
    assert report["selected_model"]["type"] == "random_forest_regressor"
