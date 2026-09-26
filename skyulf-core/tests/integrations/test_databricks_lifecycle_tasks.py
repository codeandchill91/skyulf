"""Durable lifecycle stages use saved MLflow artifacts across isolated calls."""

import importlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


def _module():
    """Report the missing stage adapter as an explicit feature failure."""
    name = "skyulf.integrations.databricks.lifecycle_tasks"
    assert importlib.util.find_spec(name) is not None, "Durable lifecycle adapter is missing"
    return importlib.import_module(name)


@pytest.fixture
def staged(tmp_path, monkeypatch):
    """Use real isolated MLflow stores and replace only unavailable Spark transport."""
    mlflow = pytest.importorskip("mlflow")

    from skyulf.integrations.databricks import local_retraining, local_workflow

    adapter = _module()
    store = f"sqlite:///{(tmp_path / 'registry.db').as_posix()}"
    client = mlflow.MlflowClient(tracking_uri=store, registry_uri=store)
    client.create_experiment("staged", artifact_location=(tmp_path / "runs").as_uri())
    frame = pd.DataFrame({"id": range(20), "x": range(20), "target": range(0, 40, 2)})
    monkeypatch.setattr(
        local_retraining, "read_training_snapshot", lambda spark, spec: frame.copy()
    )
    monkeypatch.setattr(local_workflow, "read_training_snapshot", lambda spark, spec: frame.copy())
    config = {
        "engine": "pandas",
        "training_table": "workspace.test.labels",
        "training_version": 4,
        "record_key_columns": ["id"],
        "input_columns": ["x"],
        "target_column": "target",
        "max_rows": 100,
        "max_input_mb": 1,
        "model_name": "workspace.test.staged",
        "pipeline": {"preprocessing": [], "modeling": {"type": "linear_regression"}},
        "metric": "heldout_rmse",
        "min_improvement": 0.0,
        "quality_threshold": 1.0,
        "score_model_selection": "champion",
        "promotion_policy": "automatic",
        "score_handoff": "after_alias_change",
        "tracking_uri": store,
        "registry_uri": store,
    }
    context = adapter.LifecycleContext(job_id="10", job_run_id="20")
    return adapter, client, config, context, frame


def _call(staged, phase, reference=None, **kwargs):
    """Call phases with JSON-only references as separate notebook tasks would."""
    adapter, _, config, context, _ = staged
    return adapter.run_lifecycle_phase(
        None,
        phase=phase,
        context=context,
        reference=reference,
        tracking_uri=config["tracking_uri"],
        **kwargs,
    )


@pytest.mark.parametrize("engine", ["pandas", "polars"])
def test_phases_roundtrip_and_only_finalize_completed_training(staged, engine, monkeypatch):
    """A fitted package survives temporary cleanup and registers only after evaluation."""
    from skyulf.integrations.databricks import local_retraining

    _, client, config, _, _ = staged
    paths = []
    original_fit = local_retraining.fit_local_workflow

    def capture_path(*args, **kwargs):
        """Observe disposable fit directories without changing the real fitting operation."""
        paths.append(Path(kwargs["artifact_path"]))
        return original_fit(*args, **kwargs)

    monkeypatch.setattr(local_retraining, "fit_local_workflow", capture_path)
    config["engine"] = engine
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    reference = prepared.reference
    run_id = reference["run_id"]
    assert prepared.output["source_table"] == "workspace.test.labels"
    assert prepared.output["source_version"] == 4
    assert prepared.output["engine"] == engine
    assert prepared.output["split_strategy"] == "random"
    assert prepared.output["expected_champion_version"] is None
    assert client.get_run(run_id).info.status == "RUNNING"
    trained = _call(staged, "train", reference)
    assert paths and all(not path.exists() for path in paths)
    assert not client.search_registered_models()
    assert trained.output["training_rows"] == 16
    registered = _call(staged, "evaluate_register", trained.reference)
    assert registered.output["candidate_version"] == "1"
    compared = _call(staged, "compare", registered.reference)
    decided = _call(staged, "decide", compared.reference)
    assert str(client.get_model_version_by_alias(config["model_name"], "champion").version) == "1"
    assert client.get_run(run_id).info.status == "RUNNING"
    finalized = _call(staged, "finalize", reference)
    assert finalized.output["status"] == "FINISHED"
    result = _call(staged, "result", reference)
    assert result.output["result"]["alias_change"] == decided.output["alias_change"]
    assert client.get_run(run_id).info.status == "FINISHED"


def test_out_of_order_foreign_and_repeated_stages_fail_closed(staged):
    """Missing evidence and duplicate attempts must never authorize registration."""
    adapter, client, config, context, _ = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    with pytest.raises(ValueError, match="predecessor"):
        _call(staged, "evaluate_register", prepared.reference)
    foreign = adapter.LifecycleContext(job_id=context.job_id, job_run_id="21")
    with pytest.raises(ValueError, match="invocation"):
        adapter.run_lifecycle_phase(
            None,
            phase="train",
            context=foreign,
            reference=prepared.reference,
            tracking_uri=config["tracking_uri"],
        )
    trained = _call(staged, "train", prepared.reference)
    with pytest.raises(ValueError, match="fresh run"):
        _call(staged, "train", prepared.reference)
    assert not client.search_registered_models()
    assert json.loads(json.dumps(trained.reference)) == trained.reference


def test_failed_evaluation_never_registers_and_finalizer_marks_failed(staged, monkeypatch):
    """Evaluation errors retain the original exception and cannot publish a successful result."""
    from skyulf.integrations.databricks import local_retraining

    _, client, config, _, _ = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    trained = _call(staged, "train", prepared.reference)
    failure = RuntimeError("holdout failed")

    def fail(*args, **kwargs):
        """Simulate the actual evaluation boundary failing."""
        raise failure

    monkeypatch.setattr(local_retraining, "evaluate_local_holdout", fail)
    with pytest.raises(RuntimeError) as caught:
        _call(staged, "evaluate_register", trained.reference)
    assert caught.value is failure
    assert not client.search_registered_models()
    finalized = _call(staged, "finalize", prepared.reference)
    assert finalized.output["status"] == "FAILED"
    with pytest.raises(ValueError, match="successful"):
        _call(staged, "result", prepared.reference)
    assert client.get_run(prepared.reference["run_id"]).info.status == "FAILED"


def test_finalized_incomplete_run_cannot_resume_training(staged):
    """A cleanup-completed failed run cannot be resumed by a late phase call."""
    _, client, config, _, _ = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    _call(staged, "finalize", prepared.reference)
    with pytest.raises(ValueError, match="fresh run"):
        _call(staged, "train", prepared.reference)
    assert not client.search_registered_models()


def test_lost_registration_response_cannot_register_twice(staged, monkeypatch):
    """An accepted mutation with a lost response remains unknown rather than retryable."""
    from skyulf.integrations.databricks import local_retraining

    _, client, config, _, _ = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    trained = _call(staged, "train", prepared.reference)
    original = local_retraining.register_model
    failure = RuntimeError("registration response lost")

    def lost_response(*args, **kwargs):
        """Let real MLflow commit the version before transport loses the result."""
        original(*args, **kwargs)
        raise failure

    monkeypatch.setattr(local_retraining, "register_model", lost_response)
    with pytest.raises(RuntimeError) as caught:
        _call(staged, "evaluate_register", trained.reference)
    assert caught.value is failure
    with pytest.raises(ValueError, match="fresh run"):
        _call(staged, "evaluate_register", trained.reference)
    versions = client.search_model_versions(f"name='{config['model_name']}'")
    assert len(versions) == 1
    assert not client.get_registered_model(config["model_name"]).aliases
    finalized = _call(staged, "finalize", prepared.reference)
    assert finalized.output["status"] == "FAILED"
    assert finalized.output["registration_outcome"] == "unknown"


def test_registration_accepts_verified_normalized_artifact_source(staged, monkeypatch):
    """Registry source normalization must not invalidate the exact recorded publication."""
    from skyulf.integrations.databricks import local_retraining

    _, client, config, _, _ = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    trained = _call(staged, "train", prepared.reference)

    def normalized_registration(model_uri, name, **kwargs):
        """Mimic a registry normalizing the accepted runs URI to its artifact location."""
        run_id = prepared.reference["run_id"]
        assert model_uri == f"runs:/{run_id}/model"
        source = client.get_run(run_id).info.artifact_uri + "/model"
        client.create_registered_model(name)
        return client.create_model_version(name, source, run_id=run_id, tags=kwargs["tags"])

    monkeypatch.setattr(local_retraining, "register_model", normalized_registration)
    registered = _call(staged, "evaluate_register", trained.reference)
    compared = _call(staged, "compare", registered.reference)
    assert compared.output["model_version"] == "1"


def test_comparison_failure_restores_exact_challenger_without_nomination(staged, monkeypatch):
    """A fresh task process retains the registered contender and records comparison error."""
    from skyulf.integrations.databricks import local_retraining
    from skyulf.integrations.mlflow.challenger import ChallengerLifecycle

    _, client, config, _, _ = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    trained = _call(staged, "train", prepared.reference)
    registered = _call(staged, "evaluate_register", trained.reference)
    failure = RuntimeError("comparison failed")

    def fail(*args, **kwargs):
        """Fail after a concrete candidate has been durably nominated."""
        raise failure

    monkeypatch.setattr(local_retraining, "compare_registered_local_models", fail)
    monkeypatch.setattr(ChallengerLifecycle, "registered", lambda *args: pytest.fail("renominated"))
    with pytest.raises(RuntimeError) as caught:
        _call(staged, "compare", registered.reference)
    assert caught.value is failure
    candidate = client.get_model_version_by_alias(config["model_name"], "challenger")
    assert str(candidate.version) == "1"
    assert candidate.tags["validation_status"] == "error"
    assert "champion" not in client.get_registered_model(config["model_name"]).aliases
    assert _call(staged, "finalize", prepared.reference).output["status"] == "FAILED"


@pytest.mark.parametrize("change", ["request", "evidence", "spec", "membership", "model", "source"])
def test_saved_provenance_or_membership_change_blocks_registration(staged, change, monkeypatch):
    """Altered artifacts or a replayed population cannot authorize candidate publication."""
    from skyulf.integrations.databricks import local_retraining

    _, client, config, _, frame = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    trained = _call(staged, "train", prepared.reference)
    run_id = prepared.reference["run_id"]
    if change in {"request", "evidence", "spec"}:
        path = {
            "request": "lifecycle/request.json",
            "evidence": "training_filter_evidence.json",
            "spec": "candidate_training_spec.json",
        }[change]
        saved = json.loads(
            Path(client.download_artifacts(run_id, path)).read_text(encoding="utf-8")
        )
        if change == "request":
            saved["config"]["training_version"] = 99
        elif change == "evidence":
            saved["project_source_sha256"] = "a" * 64
        else:
            saved["version"] = 99
        client.log_dict(run_id, saved, path)
    elif change == "membership":
        frame.loc[0, "id"] = 999
    elif change == "model":
        path = Path(client.download_artifacts(run_id, "model/MLmodel"))
        payload = path.read_text(encoding="utf-8")
        path.write_text(payload.replace(trained.output["model_digest"], "b" * 64), encoding="utf-8")
        client.log_artifact(run_id, str(path), artifact_path="model")
    else:

        def missing_source(*args, **kwargs):
            """A missing pinned Delta version must not fall back to latest."""
            raise ValueError("Pinned source is unavailable")

        monkeypatch.setattr(local_retraining, "read_training_snapshot", missing_source)
    with pytest.raises(ValueError):
        _call(staged, "evaluate_register", trained.reference)
    assert not client.search_registered_models()


@pytest.mark.parametrize("engine", ["pandas", "polars"])
def test_saved_project_recipe_and_cv_survive_changed_editable_inputs(staged, engine, tmp_path):
    """Both engines replay saved pre-split code and fold-local CV after project edits."""
    from skyulf.integrations.databricks.project import load_project_workflow

    _, client, config, _, _ = staged
    source = tmp_path / "preprocessing.py"
    source.write_text(
        "def build_preprocessing():\n"
        "    return [{'name': 'scale', 'transformer': 'StandardScaler', "
        "'params': {'columns': ['x']}}]\n"
        "def build_pre_split_steps():\n"
        "    return [{'name': 'eligible', 'transformer': 'ManualBounds', "
        "'params': {'bounds': {'x': {'lower': 1}}}}]\n",
        encoding="utf-8",
    )
    config.update(engine=engine, cv_enabled=True, cv_folds=2, promotion_policy="manual_approval")
    config.update(load_project_workflow(config, source))
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    source.write_text("raise RuntimeError('edited project must not run')\n", encoding="utf-8")
    config["training_version"] = 99
    config["pipeline"]["modeling"]["type"] = "changed"
    config["champion_version"] = "99"
    trained = _call(staged, "train", prepared.reference)
    registered = _call(staged, "evaluate_register", trained.reference)
    compared = _call(staged, "compare", registered.reference)
    decision = _call(staged, "decide", compared.reference)
    _call(staged, "finalize", prepared.reference)
    result = _call(staged, "result", prepared.reference)
    assert decision.output["alias_change"] is None
    assert result.output["score_requested"] is False
    assert set(result.output["next_actions"]) == {"approve", "reject"}
    assert trained.output["spec"]["version"] == 4
    assert trained.output["training_rows"] + trained.output["holdout_rows"] == 19
    assert "cv_rmse_mean" in client.get_run(prepared.reference["run_id"]).data.metrics


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_manual_actions_reuse_saved_evidence_without_fit_or_registration(
    staged, action, monkeypatch
):
    """Operator tasks bypass training and finish their own descriptor runs from saved evidence."""
    from skyulf.integrations.databricks import local_retraining

    adapter, client, config, _, frame = staged
    config["promotion_policy"] = "manual_approval"
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    current = prepared
    for phase in ("train", "evaluate_register", "compare", "decide"):
        current = _call(staged, phase, current.reference)
    _call(staged, "finalize", prepared.reference)
    candidate = current.output["candidate"]

    def forbidden(*args, **kwargs):
        """Detect any attempt to fit or publish another version during an operator task."""
        pytest.fail("Manual action attempted training or registration")

    monkeypatch.setattr(local_retraining, "fit_local_workflow", forbidden)
    monkeypatch.setattr(local_retraining, "register_model", forbidden)
    config["pipeline"] = {"project_python_source": "raise RuntimeError('editable project')"}
    context = adapter.LifecycleContext(job_id="10", job_run_id="21")
    operator_staged = (adapter, client, config, context, frame)
    options = {
        "candidate_version": candidate["model_version"],
        "comparison_sha256": candidate["comparison_sha256"],
        "expected_champion_version": None,
    }
    if action == "reject":
        options["rejection_reason"] = "Needs review"
    pending = _call(
        operator_staged,
        "prepare",
        config=config,
        action=action,
        experiment_name="staged",
        operator_options=options,
    )
    _call(operator_staged, "operator", pending.reference)
    result = _call(operator_staged, "result", pending.reference)
    assert result.output["score_requested"] is (action == "approve")
    assert client.get_run(pending.reference["run_id"]).info.status == "FINISHED"
    assert len(client.search_model_versions(f"name='{config['model_name']}'")) == 1


@pytest.mark.parametrize(
    "changes",
    [{"repair_count": 1}, {"execution_count": 2}, {"job_id": "{{job.id}}"}, {"execution_count": 0}],
)
def test_retry_repair_and_unresolved_invocation_rejected_before_work(staged, changes):
    """Databricks retries and unresolved metadata cannot create a new MLflow attempt."""
    adapter, client, config, _, _ = staged
    context = adapter.LifecycleContext(**{"job_id": "10", "job_run_id": "20", **changes})
    with pytest.raises(ValueError):
        adapter.run_lifecycle_phase(
            None,
            phase="prepare",
            context=context,
            tracking_uri=config["tracking_uri"],
            config=config,
            action="train",
            experiment_name="staged",
        )
    experiment = client.get_experiment_by_name("staged")
    assert not client.search_runs([experiment.experiment_id])


def test_prepare_failure_closes_created_run(staged, monkeypatch):
    """Prepare cannot depend on an excluded finalizer to close a partially created run."""
    _, client, config, _, _ = staged
    original = type(client).log_dict
    failure = RuntimeError("request upload failed")

    def fail_request(self, run_id, dictionary, artifact_file):
        """Fail only the descriptor upload after real MLflow run creation."""
        if artifact_file == "lifecycle/request.json":
            raise failure
        return original(self, run_id, dictionary, artifact_file)

    monkeypatch.setattr(type(client), "log_dict", fail_request)
    with pytest.raises(RuntimeError) as caught:
        _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    assert caught.value is failure
    experiment = client.get_experiment_by_name("staged")
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1 and runs[0].info.status == "FAILED"


def test_finalizer_failure_leaves_incomplete_and_preserves_committed_promotion(staged, monkeypatch):
    """A failed status write cannot fabricate successful output or undo a committed alias."""
    _, client, config, _, _ = staged
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    current = prepared
    for phase in ("train", "evaluate_register", "compare", "decide"):
        current = _call(staged, phase, current.reference)
    failure = RuntimeError("finalize unavailable")

    def fail(*args, **kwargs):
        """Simulate MLflow termination failure after completed promotion evidence."""
        raise failure

    monkeypatch.setattr(type(client), "set_terminated", fail)
    with pytest.raises(RuntimeError) as caught:
        _call(staged, "finalize", prepared.reference)
    assert caught.value is failure
    with pytest.raises(ValueError, match="successful"):
        _call(staged, "result", prepared.reference)
    assert (
        client.get_run(prepared.reference["run_id"]).data.tags["skyulf.lifecycle.status"]
        == "incomplete"
    )
    assert str(client.get_model_version_by_alias(config["model_name"], "champion").version) == "1"


@pytest.mark.parametrize("operation", ["evaluate_training_cv", "fit_local_workflow"])
def test_cv_and_fit_failure_never_reach_registration(staged, monkeypatch, operation):
    """The staged train boundary retains original failures before any publication is possible."""
    from skyulf.integrations.databricks import local_retraining

    _, client, config, _, _ = staged
    config.update(cv_enabled=True, cv_folds=2)
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    failure = RuntimeError("training failed")

    def fail(*args, **kwargs):
        """Raise from the selected real computation boundary before registration."""
        raise failure

    monkeypatch.setattr(local_retraining, operation, fail)
    with pytest.raises(RuntimeError) as caught:
        _call(staged, "train", prepared.reference)
    assert caught.value is failure
    assert not client.search_registered_models()
    assert _call(staged, "finalize", prepared.reference).output["status"] == "FAILED"


def test_failed_quality_gate_is_successful_training_without_score_handoff(staged):
    """A evaluated candidate that misses policy remains a valid result without scoring."""
    _, client, config, _, _ = staged
    config["quality_threshold"] = -1.0
    prepared = _call(staged, "prepare", config=config, action="train", experiment_name="staged")
    current = prepared
    for phase in ("train", "evaluate_register", "compare", "decide"):
        current = _call(staged, phase, current.reference)
    assert current.output["alias_change"] is None
    assert _call(staged, "finalize", prepared.reference).output["status"] == "FINISHED"
    result = _call(staged, "result", prepared.reference)
    assert result.output["score_requested"] is False
    assert "champion" not in client.get_registered_model(config["model_name"]).aliases
