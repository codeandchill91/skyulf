"""Resolve trusted project Python recipes into the existing Core config."""

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from ...config_validation import validate_preprocessing_steps
from ...inference.project_code import (
    MAX_PROJECT_SOURCE_BYTES,
    load_project_module,
    project_source_digest,
)
from .local_ensemble import ENSEMBLE_MODELS
from .local_search import _bounded_space


def _strict_json_value(value: Any) -> Any:
    """Copy only finite JSON values from trusted project hook output."""
    if type(value) is dict:
        return _strict_json_object(value)
    if type(value) is list:
        return [_strict_json_value(item) for item in value]
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("ensemble.py must return finite JSON values.")


def _strict_json_object(value: dict[Any, Any]) -> dict[str, Any]:
    """Copy nested hook mappings while rejecting non-string JSON keys."""
    if any(type(key) is not str for key in value):
        raise ValueError("ensemble.py must return a JSON object with string keys.")
    return {key: _strict_json_value(item) for key, item in value.items()}


def _load_ensemble_hook(result: dict[str, Any], preprocessing_path: Path) -> None:
    """Apply an optional ensemble recipe before resolving any tuning override."""
    modeling = result["pipeline"].get("modeling", {})
    selected = (
        modeling.get("base_model", {})
        if modeling.get("type") == "hyperparameter_tuner"
        else modeling
    )
    if selected.get("type") not in ENSEMBLE_MODELS:
        return
    hook_path = preprocessing_path.with_name("ensemble.py")
    if not hook_path.is_file():
        return
    with hook_path.open("rb") as stream:
        payload = stream.read(MAX_PROJECT_SOURCE_BYTES + 1)
    if len(payload) > MAX_PROJECT_SOURCE_BYTES:
        raise ValueError("ensemble.py source exceeds 64 KiB.")
    source = payload.decode("utf-8")
    module = load_project_module(source)
    factory = getattr(module, "build_ensemble_params", None)
    if not callable(factory):
        raise ValueError("ensemble.py must define build_ensemble_params().")
    overrides = factory(model_type=selected["type"])
    if overrides is not None:
        if type(overrides) is not dict:
            raise ValueError("build_ensemble_params() must return a JSON object or None.")
        overrides = _strict_json_value(overrides)
        if len(json.dumps(overrides, allow_nan=False).encode("utf-8")) > MAX_PROJECT_SOURCE_BYTES:
            raise ValueError("ensemble.py returned more than 64 KiB of parameters.")
        params = selected.get("params", {})
        if type(params) is not dict:
            raise ValueError("base model params must be a JSON object.")
        selected["params"] = {**params, **overrides}
    result["pipeline"]["ensemble_python_source"] = source
    result["pipeline"]["ensemble_python_sha256"] = project_source_digest(source)


def _load_search_hook(result: dict[str, Any], preprocessing_path: Path) -> None:
    """Resolve an optional sibling tuning factory only for new tuner recipes."""
    modeling = result["pipeline"].get("modeling", {})
    if modeling.get("type") != "hyperparameter_tuner":
        return
    hook_path = preprocessing_path.with_name("tuning.py")
    if not hook_path.is_file():
        return
    with hook_path.open("rb") as stream:
        payload = stream.read(MAX_PROJECT_SOURCE_BYTES + 1)
    if len(payload) > MAX_PROJECT_SOURCE_BYTES:
        raise ValueError("tuning.py source exceeds 64 KiB.")
    source = payload.decode("utf-8")
    digest = project_source_digest(source)
    module = load_project_module(source)
    factory = getattr(module, "build_search_space", None)
    if not callable(factory):
        raise ValueError("tuning.py must define build_search_space().")
    selected = modeling.get("base_model", {})
    space = factory(
        model_type=selected["type"],
        strategy=modeling.get("strategy", "random"),
        params=deepcopy(selected.get("params", {})),
    )
    if space is not None:
        try:
            modeling["search_space"] = _bounded_space(space)
        except ValueError as exc:
            raise ValueError(f"tuning.py returned invalid search_space: {exc}") from exc
    result["pipeline"]["search_python_source"] = source
    result["pipeline"]["search_python_sha256"] = digest


def load_project_workflow(config: dict[str, Any], path: str | Path) -> dict[str, Any]:
    """Use Python-defined steps for training/preview and capture their exact source.

    Score and lifecycle approval load the saved artifact instead of this file.
    A nonempty JSON chain is rejected rather than silently overwritten.
    """
    if config.get("pipeline", {}).get("preprocessing"):
        raise ValueError("Configure preprocessing in the Python file; leave the JSON list empty.")
    if config.get("pre_split_steps"):
        raise ValueError("Configure pre_split_steps in the Python file; leave the JSON list empty.")
    with Path(path).open("rb") as stream:
        payload = stream.read(MAX_PROJECT_SOURCE_BYTES + 1)
    if len(payload) > MAX_PROJECT_SOURCE_BYTES:
        raise ValueError("Project preprocessing source exceeds 64 KiB.")
    source = payload.decode("utf-8")
    module = load_project_module(source)
    factory = getattr(module, "build_preprocessing", None)
    if not callable(factory):
        raise ValueError("preprocessing.py must define build_preprocessing().")
    steps = factory()
    if not isinstance(steps, list):
        raise ValueError("build_preprocessing() must return a list of Core steps.")
    validate_preprocessing_steps(steps)
    pre_split_factory = getattr(module, "build_pre_split_steps", None)
    if pre_split_factory is not None and not callable(pre_split_factory):
        raise ValueError("build_pre_split_steps must be a function returning Core steps.")
    pre_split_steps = pre_split_factory() if pre_split_factory is not None else []
    if not isinstance(pre_split_steps, list):
        raise ValueError("build_pre_split_steps() must return a list of Core steps.")
    validate_preprocessing_steps(pre_split_steps)
    result = deepcopy(config)
    result["pipeline"]["preprocessing"] = steps
    result["pipeline"]["project_python_source"] = source
    result["pre_split_steps"] = deepcopy(pre_split_steps)
    _load_ensemble_hook(result, Path(path))
    _load_search_hook(result, Path(path))
    return result
