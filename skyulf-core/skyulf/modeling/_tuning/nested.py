"""Evaluate independent inner searches on untouched outer folds."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd

from .grid_random import _slice_fold_rows, fit_and_score_candidate_fold
from .metrics import resolve_metric
from .params import seed_params
from .schemas import TuningConfig, TuningResult
from .splitters import nested_inner_folds, select_cv_by_type


def _nested_configs(config: TuningConfig, problem_type: str) -> tuple[TuningConfig, TuningConfig]:
    """Reject contradictory policies and build ordinary outer and inner splitters."""
    if type(config.cv_folds) is not int or config.cv_folds < 2:
        raise ValueError("Nested CV requires cv_folds to be an integer of at least 2.")
    if config.tune_threshold:
        raise ValueError("Nested tuning does not yet support tune_threshold; disable it.")
    if problem_type not in ("classification", "regression"):
        raise ValueError("Nested tuning requires a classification or regression model.")
    method = "stratified_k_fold" if problem_type == "classification" else "k_fold"
    outer = replace(config, cv_type=method)
    return outer, replace(outer, cv_folds=nested_inner_folds(config))


def _require_fold_labels(y: Any, config: TuningConfig, problem_type: str) -> None:
    """Require every class in every stratified test fold before starting searches."""
    if problem_type == "classification":
        counts = pd.Series(np.asarray(y)).value_counts()
        if len(counts) < 2 or counts.min() < config.cv_folds:
            raise ValueError(
                "Nested CV needs at least one row per class in every inner/outer fold."
            )
    if len(y) < config.cv_folds:
        raise ValueError("Nested CV has fewer training rows than folds.")


def _outer_score(
    tuner: Any,
    X: Any,
    y: Any,
    train: Any,
    test: Any,
    cv: Any,
    config: TuningConfig,
    result: TuningResult,
    fold: int,
    preprocessing: Any,
) -> float:
    """Refit the selected recipe on outer training rows and reject incomplete evaluations."""
    errors: list[str] = []
    score = fit_and_score_candidate_fold(
        candidate_idx=0,
        fold_idx=fold,
        params=result.best_params,
        model_class=tuner.model_calculator.model_class,
        cv=cv,
        X_any=X,
        y_any=y,
        X_arr=np.asarray(X),
        y_arr=np.asarray(y),
        train_idx=train,
        val_idx=test,
        metric=result.scoring_metric or resolve_metric(config, y, tuner.problem_type),
        log_callback=None,
        preprocessing=deepcopy(preprocessing),
        fold_errors=errors,
        seed_params_overlay=seed_params(config),
        model_calculator=tuner.model_calculator,
    )
    if not np.isfinite(score):
        detail = errors[0] if errors else "nonfinite outer score"
        raise ValueError(f"Nested CV outer fold {fold + 1} failed: {detail}")
    return float(score)


def run_nested_search(
    tuner: Any,
    X: Any,
    y: Any,
    config: TuningConfig,
    *,
    preprocessing: Any = None,
    progress_callback: Callable[..., Any] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> TuningResult:
    """Search separately within outer folds, then run a distinct final training search.

    External validation data is intentionally absent from this interface. Search
    budgets apply independently to each inner search and the final search. Outer
    scores never participate in final hyperparameter selection.
    """
    outer_config, inner_config = _nested_configs(config, tuner.problem_type)
    _require_fold_labels(y, outer_config, tuner.problem_type)
    outer = select_cv_by_type(outer_config, tuner.problem_type)
    partitions = list(outer.split(np.asarray(X), np.asarray(y)))
    for train, _test in partitions:
        _require_fold_labels(_slice_fold_rows(y, train), inner_config, tuner.problem_type)

    folds = []
    for index, (train, test) in enumerate(partitions):
        if log_callback:
            log_callback(
                f"Nested CV outer fold {index + 1}/{len(partitions)}: starting inner search."
            )
        train_x, train_y = _slice_fold_rows(X, train), _slice_fold_rows(y, train)
        result = tuner.tune(
            train_x,
            train_y,
            deepcopy(inner_config),
            log_callback=log_callback,
            preprocessing=deepcopy(preprocessing),
            preprocessing_frames=(train_x, train_y) if preprocessing is not None else None,
        )
        score = _outer_score(tuner, X, y, train, test, outer, config, result, index, preprocessing)
        folds.append(
            {
                "fold": index + 1,
                "train_rows": len(train),
                "test_rows": len(test),
                "best_params": result.best_params,
                "inner_best_score": result.best_score,
                "outer_score": score,
                "n_trials": result.n_trials,
            }
        )
        if log_callback:
            log_callback(f"Nested CV outer fold {index + 1}: held-out score {score:.6g}.")

    if log_callback:
        log_callback("Nested CV complete; starting separate final search on all training rows.")
    final = tuner.tune(
        X,
        y,
        deepcopy(inner_config),
        progress_callback=progress_callback,
        log_callback=log_callback,
        preprocessing=preprocessing,
        preprocessing_frames=(X, y) if preprocessing is not None else None,
    )
    scores = [fold["outer_score"] for fold in folds]
    final.nested_cv = {
        "status": "nested_cv",
        "method": "nested_cv",
        "outer_folds": config.cv_folds,
        "inner_folds": inner_config.cv_folds,
        "scoring_metric": final.scoring_metric,
        "score_direction": "higher_is_better; sklearn negative loss remains negative",
        "mean_score": float(np.mean(scores)),
        "std_score": float(np.std(scores)),
        "folds": folds,
        "total_trials": sum(f["n_trials"] for f in folds) + final.n_trials,
        "final_search_trials": final.n_trials,
        "aggregated_metrics": {
            final.scoring_metric: {"mean": float(np.mean(scores)), "std": float(np.std(scores))}
        },
        "cv_config": {
            "method": "nested_cv",
            "n_folds": config.cv_folds,
            "inner_folds": inner_config.cv_folds,
        },
    }
    return final
