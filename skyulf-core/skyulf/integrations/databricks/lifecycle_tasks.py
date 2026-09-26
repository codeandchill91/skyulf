"""Fixed lifecycle phases backed by MLflow artifacts and existing Core computations.

The caller serializes these tasks in the lifecycle job. An attempt marker is
durable evidence of possible work, not an exactly-once registration guarantee.
Repairs and retries are rejected; uncertain outcomes require operator inspection.
"""

import json
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import polars as pl

from ...inference.project_code import load_project_module, project_source_digest
from ..mlflow.challenger import ChallengerLifecycle
from ..mlflow.promotion import AliasChangeReceipt, ExclusiveAliasWriterAdmission
from ..mlflow.registry import load_run_local_pipeline
from ..mlflow.tracking import _get_or_create_experiment
from ..mlflow.validation import ModelComparisonReport
from . import local_retraining as training
from . import local_workflow as workflow
from ._lifecycle_state import _PREDECESSORS, LifecycleContext, LifecyclePhaseResult, _PhaseStore
from .local_cv import LocalCVSpec
from .local_training_evidence import evidence_digest, validate_training_evidence
from .training_dates import training_date_spec

__all__ = ["LifecycleContext", "LifecyclePhaseResult", "run_lifecycle_phase"]

_TRAINING = {"train", "train_monthly"}


def _spec(payload: dict[str, Any], source: str | None) -> training.LocalTrainingSpec:
    """Restore pinned source settings after loading the saved custom-step identities."""
    if source is not None:
        load_project_module(source)
    values = dict(payload)
    values.pop("engine", None)
    for field in ("start", "holdout_start", "cutoff", "result_cutoff"):
        values[field] = None if values[field] is None else datetime.fromisoformat(values[field])
    for field in ("record_key_columns", "input_columns", "pre_split_steps"):
        values[field] = tuple(values[field])
    for field in ("event_time_parsing", "result_time_parsing"):
        values[field] = training_date_spec(values[field])
    return training.LocalTrainingSpec(**values)


def _prepare(
    spark: Any,
    store: _PhaseStore,
    config: dict[str, Any],
    action: str,
    experiment_name: str,
    operator_options: dict[str, Any],
    now: datetime | None,
) -> LifecyclePhaseResult:
    """Resolve source and champion once, then persist the complete immutable invocation."""
    if action not in _TRAINING | {"approve", "reject", "rollback"}:
        raise ValueError("Unsupported lifecycle action.")
    _, policy = workflow._workflow_policies(config)
    options = {
        key: asdict(value) if isinstance(value, AliasChangeReceipt) else value
        for key, value in operator_options.items()
    }
    request: dict[str, Any] = {
        "version": 1,
        "context": store.context.identity(),
        "config": config,
        "action": action,
        "operator_options": options,
    }
    if action in _TRAINING:
        if options:
            raise ValueError("Training cannot accept operator options.")
        if policy == "automatic" and config.get("quality_threshold") is None:
            raise ValueError("Automatic promotion requires an absolute quality_threshold.")
        spec = (
            workflow._monthly_training_spec(spark, config, now or datetime.now(UTC))
            if action == "train_monthly"
            else workflow._training_spec(config)
        )
        champion = (
            workflow.controlled_champion_version(
                config["model_name"],
                tracking_uri=config["tracking_uri"],
                registry_uri=config.get("registry_uri", "databricks-uc"),
            )
            if policy == "automatic" or "score_model_selection" in config
            else workflow._monthly_champion_version(config)
        )
        if (
            config.get("champion_version") is not None
            and str(config["champion_version"]) != champion
        ):
            raise ValueError("champion_version does not match the current champion.")
        effective = training._candidate_config(
            spec,
            config["pipeline"],
            engine=config["engine"],
            cv=LocalCVSpec.from_workflow(config),
            metric=config["metric"],
            min_improvement=config["min_improvement"],
            champion_version=champion,
            quality_threshold=config.get("quality_threshold"),
            risk_category=config.get("risk_category"),
        )
        request.update(
            spec=training._training_spec_payload(spec, config["engine"]),
            champion_version=champion,
            effective_config=effective,
        )
    # JSON normalization also detaches all caller-owned editable dictionaries.
    request = json.loads(json.dumps(request, allow_nan=False))
    experiment = _get_or_create_experiment(store.client, experiment_name)
    existing = store.client.search_runs(
        [experiment],
        filter_string=(
            f"tags.`skyulf.lifecycle.job_id` = '{store.context.job_id}' AND "
            f"tags.`skyulf.lifecycle.job_run_id` = '{store.context.job_run_id}'"
        ),
    )
    if existing:
        raise ValueError(
            "Lifecycle invocation already attempted; inspect evidence and start a fresh run."
        )
    created = store.client.create_run(
        experiment,
        run_name="candidate_training" if action in _TRAINING else f"lifecycle_{action}",
        tags={
            "skyulf.lifecycle.job_id": store.context.job_id,
            "skyulf.lifecycle.job_run_id": store.context.job_run_id,
            "skyulf.lifecycle.status": "incomplete",
        },
    )
    store.run_id = created.info.run_id
    try:
        request["run_id"] = store.run_id
        store.request = request
        store.request_digest = evidence_digest(request)
        store.log("lifecycle/request.json", request)
        store.client.set_tag(store.run_id, "skyulf.lifecycle.request", store.request_digest)
        store.begin("prepare")
        output = {
            "action": action,
            "training_requested": action in _TRAINING,
            "model_name": config["model_name"],
        }
        if action in _TRAINING:
            pinned = request["spec"]
            output.update(
                source_table=pinned["table"],
                source_version=pinned["version"],
                engine=pinned["engine"],
                split_strategy=pinned["split_strategy"],
                expected_champion_version=request["champion_version"],
            )
            output.update(
                {
                    field: pinned[field]
                    for field in ("start", "holdout_start", "cutoff", "result_cutoff")
                    if pinned[field] is not None
                }
            )
        else:
            output.update(
                {
                    field: options[field]
                    for field in ("candidate_version", "expected_champion_version")
                    if field in options
                }
            )
        return store.complete("prepare", output, None)
    except BaseException:
        with suppress(Exception):
            store.client.set_terminated(store.run_id, status="FAILED")
        raise


def _train(spark: Any, store: _PhaseStore) -> dict[str, Any]:
    """Run the SDK's shared fitting computation and upload its fitted package."""
    request = store.request
    config = request["config"]
    source = config["pipeline"].get("project_python_source")
    spec = _spec(request["spec"], source)
    with TemporaryDirectory(prefix="skyulf-phase-fit-") as directory:
        path = Path(directory) / "artifact"
        fitted = training._fit_candidate(
            spark,
            spec,
            config["pipeline"],
            run=store.run,
            pipeline_config=request["effective_config"],
            artifact_path=path,
            engine=config["engine"],
            cv=LocalCVSpec.from_workflow(config),
            risk_category=config.get("risk_category"),
        )
        training._log_fitted_candidate(
            store.run,
            fitted,
            config["pipeline"],
            engine=config["engine"],
            risk_category=config.get("risk_category"),
        )
        model_uri = training._log_local_model(
            path, run_id=store.run_id, tracking_uri=config["tracking_uri"]
        )
    return {
        "model_uri": model_uri,
        "model_digest": fitted.artifact.manifest.pipeline_sha256,
        "project_source_sha256": fitted.artifact.manifest.project_source_sha256,
        "spec": training._training_spec_payload(fitted.spec, config["engine"]),
        "training_rows": fitted.training_rows,
        "holdout_rows": fitted.holdout_rows,
        "unavailable_labels": fitted.unavailable_labels,
        "tags": fitted.tags,
    }


def _replay(spark: Any, store: _PhaseStore) -> tuple[Any, training.LocalTrainingSpec, Any]:
    """Load only the saved fit and reconstruct its exact heldout population."""
    fitted = store.receipt("train")["output"]
    config = store.request["config"]
    if fitted["model_uri"] != f"runs:/{store.run_id}/model":
        raise ValueError("Fitted model source differs from lifecycle invocation.")
    artifact = load_run_local_pipeline(
        fitted["model_uri"], digest=fitted["model_digest"], tracking_uri=config["tracking_uri"]
    )
    source = config["pipeline"].get("project_python_source")
    source_sha = None if source is None else project_source_digest(source)
    if (
        artifact.manifest.fitted_engine != config["engine"]
        or artifact.manifest.project_source_sha256 != source_sha
        or fitted["project_source_sha256"] != source_sha
        or artifact.pipeline.config != store.request["effective_config"]
    ):
        raise ValueError(
            "Fitted model engine, configuration or project source differs from invocation."
        )
    if store.read("candidate_training_spec.json") != fitted["spec"]:
        raise ValueError("Saved candidate training spec differs from phase receipt.")
    spec = _spec(fitted["spec"], source)
    enriched = {
        "holdout_key_sha256",
        "sample_key_sha256",
        "survivor_key_sha256",
        "training_evidence_sha256",
    }
    if {key: value for key, value in fitted["spec"].items() if key not in enriched} != {
        key: value for key, value in store.request["spec"].items() if key not in enriched
    }:
        raise ValueError("Saved training source differs from pinned invocation.")
    evidence = store.read("training_filter_evidence.json")
    validate_training_evidence(evidence, spec, project_source_sha256=source_sha)
    frame = training.read_training_snapshot(spark, spec)
    _, holdout, _ = training.split_labeled_snapshot(frame, spec, engine=config["engine"])
    validate_training_evidence(evidence, spec, project_source_sha256=source_sha, heldout=holdout)
    native = pl.from_pandas(holdout) if config["engine"] == "polars" else holdout
    return artifact, spec, native


def _lifecycle(store: _PhaseStore) -> ChallengerLifecycle:
    """Bind lifecycle status handling to the request's exact expected champion."""
    config = store.request["config"]
    return ChallengerLifecycle(
        config["model_name"],
        expected_champion_version=store.request["champion_version"],
        admission=ExclusiveAliasWriterAdmission(),
        tracking_uri=config["tracking_uri"],
        registry_uri=config.get("registry_uri", "databricks-uc"),
    )


def _registered(store: _PhaseStore) -> Any:
    """Resolve the persisted version and verify its source run and package identity."""
    config = store.request["config"]
    payload = store.read("lifecycle/registration.json")
    if evidence_digest(payload) != store.tags().get("skyulf.lifecycle.registration"):
        raise ValueError("Registration receipt differs from durable identity.")
    if (
        payload["run_id"] != store.run_id
        or payload["model_name"] != config["model_name"]
        or payload["requested_source"] != f"runs:/{store.run_id}/model"
        or not isinstance(payload["registered_source"], str)
        or not payload["registered_source"]
    ):
        raise ValueError("Registration receipt belongs to another invocation.")
    candidate = training.resolve_model(
        config["model_name"],
        version=payload["model_version"],
        tracking_uri=config["tracking_uri"],
        registry_uri=config.get("registry_uri", "databricks-uc"),
    )
    client = workflow._make_client(
        workflow._require_mlflow(),
        config["tracking_uri"],
        config.get("registry_uri", "databricks-uc"),
    )
    registered = client.get_model_version(candidate.name, candidate.version)
    if (
        candidate.digest != payload["model_digest"]
        or registered.run_id != store.run_id
        or registered.source != payload["registered_source"]
    ):
        raise ValueError("Registered candidate source or digest differs from durable receipt.")
    return candidate


def _evaluate_register(spark: Any, store: _PhaseStore) -> dict[str, Any]:
    """Evaluate first and record mutation intent before registering and nominating."""
    artifact, spec, holdout = _replay(spark, store)
    config = store.request["config"]
    metrics = training._evaluate_candidate(artifact, holdout, spec=spec, metric=config["metric"])
    store.run.log_metrics(metrics)
    store.log(
        "lifecycle/initial_evaluation.json", {"metrics": metrics, "dataset_id": spec.dataset_id}
    )
    fitted = store.receipt("train")["output"]
    store.client.set_tag(store.run_id, "skyulf.lifecycle.registration_intent", "started")
    registered = training.register_model(
        fitted["model_uri"],
        config["model_name"],
        tracking_uri=config["tracking_uri"],
        registry_uri=config.get("registry_uri", "databricks-uc"),
        tags={
            key: value if len(value.encode("utf-8")) <= 256 else "See training_data.json"
            for key, value in fitted["tags"].items()
        },
    )
    receipt = {
        "run_id": store.run_id,
        "model_name": config["model_name"],
        "model_version": str(registered.version),
        "model_digest": fitted["model_digest"],
        "requested_source": fitted["model_uri"],
        "registered_source": registered.source,
    }
    store.log("lifecycle/registration.json", receipt)
    store.client.set_tag(store.run_id, "skyulf.lifecycle.registration", evidence_digest(receipt))
    candidate = _registered(store)
    _lifecycle(store).registered(candidate)
    return {
        "candidate_version": candidate.version,
        "model_digest": candidate.digest,
        "metrics": metrics,
        "dataset_id": spec.dataset_id,
    }


def _compare(spark: Any, store: _PhaseStore) -> dict[str, Any]:
    """Compare pinned versions through the same registered-model computation as the SDK."""
    _, spec, holdout = _replay(spark, store)
    config = store.request["config"]
    candidate = _registered(store)
    champion_version = store.request["champion_version"]
    champion = (
        None
        if champion_version is None
        else training.resolve_model(
            config["model_name"],
            version=champion_version,
            tracking_uri=config["tracking_uri"],
            registry_uri=config.get("registry_uri", "databricks-uc"),
        )
    )
    fitted = store.receipt("train")["output"]
    result = training._compare_candidate(
        candidate,
        champion,
        holdout,
        run=store.run,
        spec=spec,
        model_name=config["model_name"],
        metric=config["metric"],
        min_improvement=config["min_improvement"],
        quality_threshold=config.get("quality_threshold"),
        tracking_uri=config["tracking_uri"],
        registry_uri=config.get("registry_uri", "databricks-uc"),
        engine=config["engine"],
        training_rows=fitted["training_rows"],
        holdout_rows=fitted["holdout_rows"],
        unavailable=fitted["unavailable_labels"],
    )
    return asdict(result)


def _candidate(payload: dict[str, Any]) -> training.LocalCandidateResult:
    """Restore the SDK result type from verified JSON comparison evidence."""
    values = dict(payload)
    values["comparison"] = ModelComparisonReport(**payload["comparison"])
    return training.LocalCandidateResult(**values)


def _decide(spark: Any, store: _PhaseStore) -> dict[str, Any]:
    """Reuse strict automatic replay for promotion or the saved manual-review decision."""
    config = store.request["config"]
    candidate = _candidate(store.receipt("compare")["output"])
    _, policy = workflow._workflow_policies(config)
    # Replay validates the unregistered package and invocation before the existing
    # promotion service independently validates the registered model and evidence.
    _, spec, _ = _replay(spark, store)
    receipt = workflow._automatic_promotion(
        spark, config, spec, candidate, promote=policy == "automatic"
    )
    return {
        "candidate": asdict(candidate),
        "alias_change": None if receipt is None else asdict(receipt),
        "promotion_policy": policy,
    }


def _operator(spark: Any, store: _PhaseStore) -> dict[str, Any]:
    """Execute a saved operator action without reading current project Python or fitting."""
    options = dict(store.request["operator_options"])
    if "promotion_receipt" in options:
        options["promotion_receipt"] = AliasChangeReceipt(**options["promotion_receipt"])
    result = workflow.run_action(spark, store.request["config"], store.request["action"], **options)
    return {"action": store.request["action"], "result": asdict(result)}


def _finalize(store: _PhaseStore) -> dict[str, Any]:
    """Treat missing or failed training phases as failure independently of later scoring."""
    try:
        store.receipt("decide")
    except Exception:  # noqa: BLE001 - absent or corrupt phase evidence is unsuccessful training
        tags = store.tags()
        registration = "not_attempted"
        if tags.get("skyulf.lifecycle.registration_intent"):
            registration = "unknown"
        if tags.get("skyulf.lifecycle.registration"):
            lifecycle = _lifecycle(store)
            lifecycle.restore(_registered(store))
            lifecycle.failed()
            registration = "recorded"
        return {"status": "FAILED", "registration_outcome": registration}
    return {"status": "FINISHED", "registration_outcome": "recorded"}


def _result(store: _PhaseStore) -> dict[str, Any]:
    """Publish a Bundle result only from successful finalized branch receipts."""
    request = store.request
    if (
        store.tags().get("skyulf.lifecycle.status") != "FINISHED"
        or store.client.get_run(store.run_id).info.status != "FINISHED"
    ):
        raise ValueError("Lifecycle has no successful finalized result.")
    if request["action"] in _TRAINING:
        if store.receipt("finalize")["output"]["status"] != "FINISHED":
            raise ValueError("Lifecycle has no successful training finalization.")
        decision = store.receipt("decide")["output"]
        candidate = _candidate(decision["candidate"])
        receipt = decision["alias_change"]
        outcome = (
            workflow.AutoTrainingOutcome(
                candidate, None if receipt is None else AliasChangeReceipt(**receipt)
            )
            if decision["promotion_policy"] == "automatic"
            else candidate
        )
    else:
        outcome = AliasChangeReceipt(**store.receipt("operator")["output"]["result"])
    from .job_runtime import _bundle_result  # noqa: PLC0415 - shared notebook result formatting

    return asdict(_bundle_result(request["config"], request["action"], outcome))


def run_lifecycle_phase(
    spark: Any,
    *,
    phase: str,
    context: LifecycleContext,
    tracking_uri: str,
    reference: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
    action: str | None = None,
    experiment_name: str | None = None,
    operator_options: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> LifecyclePhaseResult:
    """Run one fixed notebook phase with durable references and no cross-task local state.

    Only prepare accepts configuration, action and operator inputs. Finalize and
    result take the prepare reference so excluded graph branches need no task value.
    All other phases take their immediate predecessor's reference. This adapter
    requires the lifecycle job's existing serialization and never runs scoring.
    """
    context.validate()
    if phase not in {"prepare", *_PREDECESSORS}:
        raise ValueError("Unsupported fixed lifecycle phase.")
    if phase != "prepare" and any(
        value is not None for value in (config, action, experiment_name, operator_options, now)
    ):
        raise ValueError("Downstream lifecycle phases must use only the pinned invocation.")
    store = _PhaseStore(tracking_uri, context)
    if phase == "prepare":
        if reference is not None or config is None or action is None or not experiment_name:
            raise ValueError("Prepare requires config, action and experiment with no predecessor.")
        if config.get("tracking_uri", "databricks") != tracking_uri:
            raise ValueError("Tracking URI differs from invocation configuration.")
        return _prepare(
            spark,
            store,
            {**config, "tracking_uri": tracking_uri},
            action,
            experiment_name,
            operator_options or {},
            now,
        )
    if reference is None:
        raise ValueError("Lifecycle phase requires its predecessor reference.")
    store.bind(reference)
    if reference["phase"] != _PREDECESSORS[phase]:
        raise ValueError("Lifecycle phase received the wrong predecessor reference.")
    training_action = store.request["action"] in _TRAINING
    if (
        phase in {"train", "evaluate_register", "compare", "decide", "finalize"}
        and not training_action
        or phase == "operator"
        and training_action
    ):
        raise ValueError("Lifecycle phase does not belong to the pinned action branch.")
    if phase not in {"result", "finalize"} and (
        store.client.get_run(store.run_id).info.status != "RUNNING"
        or any(
            key.endswith(".attempt") and value == "failed" for key, value in store.tags().items()
        )
    ):
        raise ValueError("Lifecycle is no longer active; inspect evidence and start a fresh run.")
    store.begin(phase)
    try:
        if phase == "finalize":
            output = _finalize(store)
        elif phase == "result":
            output = _result(store)
        else:
            output = {
                "train": _train,
                "evaluate_register": _evaluate_register,
                "compare": _compare,
                "decide": _decide,
                "operator": _operator,
            }[phase](spark, store)
        completed = store.complete(phase, output, reference)
        if phase in {"finalize", "operator"}:
            status = output["status"] if phase == "finalize" else "FINISHED"
            store.client.set_terminated(store.run_id, status=status)
            store.client.set_tag(store.run_id, "skyulf.lifecycle.status", status)
        return completed
    except BaseException:
        with suppress(Exception):
            store.client.set_tag(store.run_id, f"skyulf.lifecycle.{phase}.attempt", "failed")
        if phase in {"compare", "decide"}:
            with suppress(Exception):
                lifecycle = _lifecycle(store)
                lifecycle.restore(_registered(store))
                lifecycle.failed()
        if phase == "operator":
            with suppress(Exception):
                store.client.set_terminated(store.run_id, status="FAILED")
        raise
