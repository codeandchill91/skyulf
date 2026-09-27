"""Adapt Bundle parameters and task values to the existing local workflow services."""

import json
import logging
import re
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..mlflow.promotion import AliasChangeReceipt
from .job_output import render_bundle_output, render_lifecycle_output
from .local_approval import resolve_candidate_comparison_digest
from .local_workflow import BundleActionResult as BundleActionResult
from .local_workflow import _next_actions as _next_actions
from .local_workflow import (
    _workflow_policies,
    resolve_target_config,
    run_action,
)
from .local_workflow import build_bundle_result as _bundle_result
from .workflow_config import validate_deployed_contract, validate_workflow_config

_OPERATOR_FIELDS = {
    "candidate_version",
    "comparison_sha256",
    "expected_champion_version",
    "rejection_reason",
    "promotion_receipt_json",
}


def _version(value: str, *, allow_none: bool = False) -> str | None:
    """Require a concrete version or an explicitly chosen bootstrap sentinel."""
    if allow_none and value == "none":
        return None
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError("Expected a concrete model version; use none only for bootstrap.")
    return value


def _operator_options(action: str, values: dict[str, str]) -> dict[str, Any]:
    """Reject incomplete and irrelevant operator inputs before any Core side effects."""
    allowed = {
        "approve": {"candidate_version", "comparison_sha256", "expected_champion_version"},
        "reject": {
            "candidate_version",
            "comparison_sha256",
            "expected_champion_version",
            "rejection_reason",
        },
        "rollback": {"promotion_receipt_json", "expected_champion_version"},
    }.get(action, set())
    if any(values.get(key, "") for key in _OPERATOR_FIELDS - allowed):
        raise ValueError(f"Unexpected operator parameters for {action}.")
    if not allowed:
        return {}
    expected = _version(
        values.get("expected_champion_version", ""), allow_none=action != "rollback"
    )
    options: dict[str, Any] = {"expected_champion_version": expected}
    if action == "rollback":
        try:
            payload = json.loads(values.get("promotion_receipt_json", ""))
            if not isinstance(payload, dict) or any(
                value is not None and not isinstance(value, str) for value in payload.values()
            ):
                raise ValueError
            receipt = AliasChangeReceipt(**payload)
            if receipt.kind != "promotion" or receipt.alias != "champion":
                raise ValueError
            if receipt.new_version != expected or receipt.prior_version is None:
                raise ValueError
            _version(receipt.prior_version)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Rollback needs a complete promotion_receipt_json matching the expected champion."
            ) from exc
        options["promotion_receipt"] = receipt
        return options
    options["candidate_version"] = _version(values.get("candidate_version", ""))
    digest = values.get("comparison_sha256", "")
    if digest and not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("comparison_sha256 must be empty or an exact 64-character digest.")
    options["comparison_sha256"] = digest
    if action == "reject":
        reason = values.get("rejection_reason", "")
        if not reason.strip() or len(reason.encode("utf-8")) > 256:
            raise ValueError("Rejection needs a reason of at most 256 UTF-8 bytes.")
        options["rejection_reason"] = reason
    return options


def run_bundle_action(
    spark: Any,
    config: dict[str, Any],
    parameters: dict[str, str],
    *,
    task_role: str,
    experiment_name: str | None = None,
    artifact_path: str | Path | None = None,
) -> BundleActionResult:
    """Run one role-bound action; score handoff follows only a successful champion transition.

    Role is fixed by the deployed notebook, never by a run parameter. This is
    input isolation, not a substitute for workspace permissions or serialized
    writer ownership. A failed Core action produces no success task value.
    """
    if "score_model_selection" not in config or "promotion_policy" not in config:
        raise ValueError(
            "Regenerate the Bundle config and job graph with both independent policies."
        )
    _, policy = _workflow_policies(config)
    if config.get("score_handoff") not in {"disabled", "after_alias_change"}:
        raise ValueError("score_handoff must be disabled or after_alias_change.")
    for key in _OPERATOR_FIELDS | {
        "lifecycle_action",
        "task_role",
        "action",
        "score_model_version",
    }:
        if key in parameters and not isinstance(parameters[key], str):
            raise ValueError("Job parameters must be strings.")
    if parameters.get("task_role") or parameters.get("action"):
        raise ValueError("Notebook role and score action cannot be overridden by job parameters.")
    if task_role == "score":
        if parameters.get("lifecycle_action"):
            raise ValueError("Score job refuses lifecycle actions.")
        action = "score"
    elif task_role == "lifecycle":
        action = parameters.get("lifecycle_action", "")
        if action not in {"train", "approve", "reject", "rollback"}:
            raise ValueError("Lifecycle action must be train, approve, reject or rollback.")
    else:
        raise ValueError("Notebook task_role must be lifecycle or score.")
    override = parameters.get("score_model_version", "")
    if override:
        if action != "score":
            raise ValueError("score_model_version is only valid on the score job.")
        config = {
            **config,
            "score_model_selection": "pinned_version",
            "model_version": _version(override),
        }
    if "config_version" in config:
        config = validate_workflow_config(config, action=action)
    options = _operator_options(action, parameters)
    if action in {"approve", "reject"} and not options["comparison_sha256"]:
        options["comparison_sha256"] = resolve_candidate_comparison_digest(
            config, options["candidate_version"], action=action
        )
    if action == "train":
        options.update(experiment_name=experiment_name, artifact_path=artifact_path)
    result = run_action(spark, config, action, **options)
    return _bundle_result(config, action, result)


def _read_notebook_config(values: dict[str, str]) -> dict[str, Any]:
    """Load and bind the project once at the notebook's configuration boundary."""
    config = json.loads(Path(values["config_path"]).read_text(encoding="utf-8"))
    required = {"training_table", "score_source_table", "prediction_table", "model_name"}
    if not isinstance(config, dict) or any(
        not isinstance(config.get(key), str) for key in required
    ):
        raise ValueError(
            "Workflow configuration must be an object with training_table, "
            "score_source_table, prediction_table and model_name bindings."
        )
    config = resolve_target_config(
        config,
        {
            name: values[name]
            for name in (
                "catalog",
                "input_schema",
                "output_schema",
                "metadata_schema",
                "resource_suffix",
            )
        },
    )
    validate_deployed_contract(config, values)
    if config.get("config_version") != 1:
        raise ValueError("config_version must be 1; migrate and regenerate/redeploy this Bundle.")
    return config


def _notebook_output(
    payload: dict[str, Any],
    dbutils: Any,
    *,
    render: Callable[[dict[str, Any]], str],
    display_html: Callable[[str], Any] | None,
    exit_notebook: bool,
) -> str:
    """Publish readable and machine output without retrying completed side effects."""
    output = json.dumps(payload, default=str, allow_nan=False)
    if display_html is not None:
        try:
            display_html(render(payload))
        except Exception:  # noqa: BLE001 - display failure must not invite mutation retries
            logging.getLogger(__name__).warning("Readable output unavailable; see JSON result.")
            print(json.dumps(payload, indent=2, default=str, allow_nan=False))
    else:
        print(json.dumps(payload, indent=2, default=str, allow_nan=False))
    if exit_notebook:
        dbutils.notebook.exit(output)
    return output


def _lifecycle_widget_context(values: dict[str, str]) -> dict[str, Any]:
    """Reject unresolved invocation values and unsupported repairs before loading files."""
    if values.get("workflow_contract") != "2":
        raise ValueError("Lifecycle tasks require graph contract 2; regenerate/redeploy together.")
    if any(values.get(key) for key in ("phase", "task_role", "action", "score_model_version")):
        raise ValueError("Notebook phase and lifecycle role cannot be overridden by parameters.")
    for key in ("job_id", "job_run_id"):
        if not isinstance(values.get(key), str) or not re.fullmatch(r"[1-9][0-9]*", values[key]):
            raise ValueError(f"{key} must be a resolved Databricks job identity.")
    if values.get("repair_count") != "0" or values.get("execution_count") != "1":
        raise ValueError(
            "Lifecycle repair/retry is unsupported. Inspect prior effects before starting a fresh run."
        )
    return {
        "job_id": values["job_id"],
        "job_run_id": values["job_run_id"],
        "repair_count": 0,
        "execution_count": 1,
    }


def _prepared_notebook_request(
    values: dict[str, str], preprocessing_path: str | Path | None
) -> dict[str, Any]:
    """Validate a new invocation and freeze project Python only for training."""
    action = values.get("lifecycle_action", "")
    if action not in {"train", "approve", "reject", "rollback"}:
        raise ValueError("Lifecycle action must be train, approve, reject or rollback.")
    config = _read_notebook_config(values)
    if action == "train" and preprocessing_path is not None:
        from .project import load_project_workflow  # noqa: PLC0415 - training-only project code

        config = load_project_workflow(
            config, Path(values["config_path"]).parent / preprocessing_path
        )
    config = validate_workflow_config(config, action=action)
    options = _operator_options(action, values)
    if action in {"approve", "reject"} and not options["comparison_sha256"]:
        options["comparison_sha256"] = resolve_candidate_comparison_digest(
            config, options["candidate_version"], action=action
        )
    return {
        "config": config,
        "action": action,
        "operator_options": options,
        "experiment_name": values.get("experiment_name"),
        "tracking_uri": config.get("tracking_uri", "databricks"),
    }


def _saved_notebook_request(values: dict[str, str]) -> dict[str, Any]:
    """Validate the frozen predecessor reference and prepared tracking URI."""
    try:
        reference = json.loads(values["reference_json"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Lifecycle task needs its saved predecessor reference.") from exc
    if not isinstance(reference, dict):
        raise ValueError("Lifecycle predecessor reference must be a JSON object.")
    tracking_uri = values.get("tracking_uri")
    if not isinstance(tracking_uri, str) or not tracking_uri or "{{" in tracking_uri:
        raise ValueError("Lifecycle task needs the prepared tracking URI.")
    return {"reference": reference, "tracking_uri": tracking_uri}


def run_lifecycle_notebook(
    spark: Any,
    dbutils: Any,
    *,
    phase: str,
    display_html: Callable[[str], Any] | None = None,
    exit_notebook: bool = True,
    preprocessing_path: str | Path | None = None,
) -> str:
    """Execute a fixed lifecycle phase using durable evidence from its predecessor.

    Only prepare reads editable configuration and project Python. Later tasks
    receive references from this job invocation and load the frozen MLflow
    evidence. Notebook metadata is a misuse guard, not workspace authorization.
    """
    values = dbutils.widgets.getAll()
    context_values = _lifecycle_widget_context(values)
    from .lifecycle_tasks import (  # noqa: PLC0415 - shared runtime helpers avoid a module cycle
        LifecycleContext,
        run_lifecycle_phase,
    )

    options = (
        _prepared_notebook_request(values, preprocessing_path)
        if phase == "prepare"
        else _saved_notebook_request(values)
    )
    task_states = (
        {
            "training": values.get("training_result_state"),
            "operator": values.get("operator_result_state"),
        }
        if phase == "complete"
        else None
    )
    outcome = run_lifecycle_phase(
        spark,
        phase=phase,
        context=LifecycleContext(**context_values),
        task_states=task_states,
        **options,
    )
    dbutils.jobs.taskValues.set(
        key="reference_json", value=json.dumps(outcome.reference, sort_keys=True)
    )
    if phase == "prepare":
        dbutils.jobs.taskValues.set(key="tracking_uri", value=options["tracking_uri"])
        dbutils.jobs.taskValues.set(
            key="training_requested", value=outcome.output["training_requested"]
        )
    if phase in {"result", "complete"}:
        dbutils.jobs.taskValues.set(key="score_requested", value=outcome.output["score_requested"])
    return _notebook_output(
        outcome.output,
        dbutils,
        render=(
            render_bundle_output
            if phase in {"result", "complete"}
            else lambda payload: render_lifecycle_output(phase, payload)
        ),
        display_html=display_html,
        exit_notebook=exit_notebook,
    )


def run_notebook(
    spark: Any,
    dbutils: Any,
    *,
    task_role: str,
    display_html: Callable[[str], Any] | None = None,
    exit_notebook: bool = True,
    preprocessing_path: str | Path | None = None,
) -> str:
    """Run the fixed role and render results, optionally deferring the notebook exit.

    Generated notebooks defer exit to a separate cell: Databricks otherwise
    replaces the readable report with the exit value in the same cell.
    A preprocessing path is relative to the config directory and used only for
    training. Scoring and operator actions retain the saved artifact's code.
    """
    values = dbutils.widgets.getAll()
    # Databricks pushes parent job parameters into Run Job children. The score
    # entrypoint ignores inherited lifecycle evidence and always dispatches score.
    # Keep role/action override guards; only lifecycle fields are discarded here.
    parameters = (
        {
            key: value
            for key, value in values.items()
            if key not in _OPERATOR_FIELDS | {"lifecycle_action"}
        }
        if task_role == "score"
        else values
    )
    config = _read_notebook_config(values)
    if (
        preprocessing_path is not None
        and task_role == "lifecycle"
        and parameters.get("lifecycle_action") == "train"
    ):
        from .project import load_project_workflow  # noqa: PLC0415 - project code is training-only

        config = load_project_workflow(
            config, Path(values["config_path"]).parent / preprocessing_path
        )
    with tempfile.TemporaryDirectory(prefix="skyulf-bundle-") as directory:
        outcome = run_bundle_action(
            spark,
            config,
            parameters,
            task_role=task_role,
            experiment_name=values.get("experiment_name"),
            artifact_path=Path(directory) / "artifact",
        )
    payload = asdict(outcome)
    if task_role == "lifecycle":
        dbutils.jobs.taskValues.set(key="score_requested", value=outcome.score_requested)
    return _notebook_output(
        payload,
        dbutils,
        render=render_bundle_output,
        display_html=display_html,
        exit_notebook=exit_notebook,
    )
