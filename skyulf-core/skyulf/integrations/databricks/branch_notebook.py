"""Run explicitly configured multi-target training without alias changes or scoring."""

import html
import json
import tempfile
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ...inference.project_code import load_project_module
from ._project_files import read_source
from .job_runtime import (
    _lifecycle_widget_context,
    _notebook_output,
    _operator_options,
    _read_notebook_config,
)
from .local_workflow import resolve_target_config
from .project import load_project_workflow


def _training_only(config: dict[str, Any]) -> None:
    """Reject policies whose activation semantics are not implemented for branches."""
    if config.get("promotion_policy") != "manual_approval":
        raise ValueError("Multi-target training requires promotion_policy=manual_approval.")
    if config.get("score_handoff") != "disabled":
        raise ValueError("Multi-target training requires score_handoff=disabled.")


def _branch_entries(path: Path) -> dict[str, Any]:
    """Load the trusted branch factory separately from each saved feature package."""
    module = load_project_module(read_source(path))
    factory = getattr(module, "build_training_branches", None)
    if not callable(factory):
        raise ValueError("branches.py must define build_training_branches().")
    entries = factory()
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Configure a nonempty branch mapping in src/modeling/branches.py.")
    return entries


def _branch_config(
    base: dict[str, Any], entry: Any, values: dict[str, str], modeling: Path
) -> dict[str, Any]:
    """Replace explicit top-level settings and capture one branch's feature recipe."""
    allowed = {"workflow", "features_path", "preprocessing_recipe", "pre_split_recipe"}
    if not isinstance(entry, dict) or set(entry) - allowed:
        raise ValueError(
            "Each branch requires workflow and optional features_path, "
            "preprocessing_recipe, pre_split_recipe."
        )
    overlay = entry.get("workflow")
    if not isinstance(overlay, dict):
        raise ValueError("Each branch workflow must be a configuration overlay.")
    config = {**deepcopy(base), **deepcopy(overlay)}
    _training_only(config)
    bindings = {
        name: values[name]
        for name in (
            "catalog",
            "input_schema",
            "output_schema",
            "metadata_schema",
            "resource_suffix",
        )
    }
    config = resolve_target_config(config, bindings)
    relative = entry.get("features_path", "../features")
    if not isinstance(relative, str) or not relative:
        raise ValueError("features_path must be a nonempty path relative to src/modeling.")
    path = (modeling / relative).resolve()
    if not path.is_relative_to(modeling.parent.resolve()):
        raise ValueError("Branch features_path must stay inside the project's src directory.")
    return load_project_workflow(
        config,
        path,
        preprocessing_recipe=entry.get("preprocessing_recipe"),
        pre_split_recipe=entry.get("pre_split_recipe"),
    )


def load_training_branch_configs(values: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Resolve independent full workflows with the deployed target's ownership rules.

    Workflow overlays replace whole top-level values, including ``pipeline``.
    They never merge nested model settings from a different target. All feature
    packages are captured before the service validates and reads remote data.
    """
    base = _read_notebook_config(values)
    _training_only(base)
    modeling = Path(values["config_path"]).parent.parent / "src/modeling"
    return {
        name: _branch_config(base, entry, values, modeling)
        for name, entry in _branch_entries(modeling / "branches.py").items()
    }


def _render_branch_result(payload: dict[str, Any]) -> str:
    """Show saved component evidence without presenting unavailable activation controls."""
    return (
        "<h2>Multi-target training results</h2>"
        "<p>Candidates registered and compared. No aliases changed; scoring was not run. "
        "Coherent activation and multi-target scoring are planned in SM-36C.</p><pre>"
        + html.escape(json.dumps(payload, indent=2, default=str, allow_nan=False))
        + "</pre>"
    )


def run_branch_training_notebook(
    spark: Any,
    dbutils: Any,
    *,
    display_html: Callable[[str], Any] | None = None,
    exit_notebook: bool = True,
) -> str:
    """Train branch candidates once per invocation; reject repair and operator actions."""
    values = dbutils.widgets.getAll()
    _lifecycle_widget_context(values)
    if values.get("lifecycle_action", "train") != "train":
        raise ValueError(
            "Multi-target entrypoint supports only train; activation is not available."
        )
    _operator_options("train", values)
    configs = load_training_branch_configs(values)
    from .local_branches import (  # noqa: PLC0415 - load training services after preflight
        prepare_training_branches,
        train_local_branches,
    )

    branches = prepare_training_branches(spark, configs)
    base = next(iter(configs.values()))
    with tempfile.TemporaryDirectory(prefix="skyulf-branches-") as directory:
        outcome = train_local_branches(
            spark,
            branches,
            tracking_uri=base.get("tracking_uri") or "databricks",
            registry_uri=base.get("registry_uri") or "databricks-uc",
            experiment_name=values["experiment_name"],
            artifact_path=directory,
        )
    return _notebook_output(
        asdict(outcome),
        dbutils,
        render=_render_branch_result,
        display_html=display_html,
        exit_notebook=exit_notebook,
    )
