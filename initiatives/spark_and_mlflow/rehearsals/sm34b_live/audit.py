# Databricks notebook source
"""Read back SM-34B artifacts and Delta history without changing workspace state."""

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import mlflow
from mlflow.tracking import MlflowClient

from skyulf.integrations.databricks._lifecycle_state import LifecycleContext, _PhaseStore
from skyulf.integrations.databricks.delta import history

SCHEMA = "workspace.skyulf_lifecycle_test"
PREFIX = "sm34b_20260926_r1"
SOURCE = f"{SCHEMA}.{PREFIX}_source"


def artifact(client, run_id, name):
    """Download through the client so tracking credentials resolve artifact storage."""
    return json.loads(Path(client.download_artifacts(run_id, name)).read_text(encoding="utf-8"))


def audit_engine(spark, client, engine):
    """Require saved training evidence and unchanged initial predictions for one engine."""
    suffix = ""
    model = f"{SCHEMA}.{PREFIX}_{engine}_model{suffix}"
    table = f"{SCHEMA}.{PREFIX}_{engine}_predictions"
    version = client.get_model_version_by_alias(model, "champion")
    assert str(version.version) == "1", version
    run = client.get_run(version.run_id)
    assert run.info.status == "FINISHED", run.info.status
    assert run.data.tags["skyulf.lifecycle.status"] == "FINISHED"
    assert run.data.params["engine"] == run.data.tags["engine"] == engine
    assert int(run.data.params["source_version"]) == 0
    primary = "accuracy" if engine == "pandas" else "rmse"
    metrics = {
        key: value for key, value in run.data.metrics.items() if key.startswith(("heldout_", "cv_"))
    }
    assert f"heldout_{primary}" in metrics and f"cv_{primary}_mean" in metrics
    assert all(math.isfinite(value) for value in metrics.values()), metrics
    names = (
        "lifecycle/request.json",
        "training_snapshot.json",
        "candidate_training_spec.json",
        "training_pipeline_config.json",
        "skyulf_pipeline_config.json",
        "training_filter_evidence.json",
        "holdout_membership.json",
        "cross_validation.json",
    )
    evidence = {name: artifact(client, run.info.run_id, name) for name in names}
    request = evidence["lifecycle/request.json"]
    config = request["config"]
    phase_store = _PhaseStore("databricks", LifecycleContext(**request["context"]))
    phase_store.run_id = run.info.run_id
    phase_store.request_digest = run.data.tags["skyulf.lifecycle.request"]
    phase_store.request = request
    phases = ("prepare", "train", "evaluate_register", "compare", "decide", "finalize", "result")
    for phase in phases:
        receipt = phase_store.receipt(phase)
        assert receipt["phase"] == phase and receipt["run_id"] == run.info.run_id
    selected = evidence["candidate_training_spec.json"]
    assert config["training_version"] is None
    assert config["engine"] == engine and config["model_name"] == model
    for saved in (request["spec"], evidence["training_snapshot.json"], selected):
        assert saved["version"] == 0 and saved["table"] == SOURCE
        assert saved["engine"] == engine and saved["training_sample_rows"] is None
    assert evidence["training_snapshot.json"] == request["spec"]
    assert evidence["training_pipeline_config.json"] == config["pipeline"]
    assert evidence["skyulf_pipeline_config.json"] == request["effective_config"]
    effective = request["effective_config"]
    expected_model = "random_forest_classifier" if engine == "pandas" else "random_forest_regressor"
    assert effective["modeling"]["type"] == expected_model
    assert effective["modeling"]["params"]["n_estimators"] == 16
    assert [step["transformer"] for step in effective["preprocessing"]] == [
        "SimpleImputer",
        "StandardScaler",
    ]
    metadata_path = client.download_artifacts(run.info.run_id, "model/MLmodel")
    metadata = mlflow.models.Model.load(metadata_path).metadata
    assert metadata["skyulf_fitted_engine"] == engine, metadata
    counts = evidence["training_filter_evidence.json"]
    assert counts["training_rows"] > 0
    assert counts["holdout_rows"] > 0
    assert int(run.data.params["training_rows"]) == counts["training_rows"]
    assert int(run.data.params["holdout_rows"]) == counts["holdout_rows"]
    assert (
        evidence["holdout_membership.json"]["holdout_key_sha256"] == selected["holdout_key_sha256"]
    )
    cv = evidence["cross_validation.json"]
    assert cv["engine"] == engine and cv["training_rows"] == counts["training_rows"]
    assert cv["cv_config"]["n_folds"] == 3
    if engine == "pandas":
        assert counts["source_rows"] == 240
        assert config["training_window_mode"] == "full_snapshot"
        assert config["promotion_policy"] == "automatic"
        assert selected["split_strategy"] == "random" and selected["stratify"]
        assert cv["cv_config"]["cv_type"] == "stratified_k_fold"
        assert counts["training_rows"] + counts["holdout_rows"] == 240
    else:
        assert config["promotion_policy"] == "manual_approval"
        assert config["training_window_mode"] == "rolling_calendar"
        assert config["monthly_lookback_months"] == 4 and config["holdout_months"] == 1
        assert config["window_timezone"] == "UTC"
        assert config["result_cutoff"] is None and config["result_availability_lag_hours"] == 0
        assert selected["split_strategy"] == "temporal"
        assert selected["filter_unavailable_results"]
        assert selected["event_time_parsing"]["timezone"] == "Europe/Copenhagen"
        assert selected["event_time_parsing"]["format"] == "%d/%m/%Y %H:%M"
        assert selected["result_time_parsing"]["timezone"] == "Europe/Vilnius"
        assert selected["result_time_parsing"]["format"] == "%Y-%m-%d"
        assert selected["result_time_parsing"]["date_only"] == "midnight"
        assert cv["cv_config"]["cv_type"] == "time_series_split"
        assert cv["cv_config"]["time_column"] == "observed_at"
        start, holdout, cutoff = (
            datetime.fromisoformat(selected[key]) for key in ("start", "holdout_start", "cutoff")
        )
        assert all(value.day == 1 and value.hour == 0 for value in (start, holdout, cutoff))
        assert (cutoff.year - start.year) * 12 + cutoff.month - start.month == 4
        assert (cutoff.year - holdout.year) * 12 + cutoff.month - holdout.month == 1
        assert datetime.fromisoformat(selected["result_cutoff"]) >= cutoff
        result_cutoff = datetime.fromisoformat(selected["result_cutoff"])
        frozen_rows = (
            spark.read.option("versionAsOf", 0)
            .table(SOURCE)
            .select("observed_at", "confirmed_at")
            .collect()
        )
        observations = [
            (
                datetime.strptime(row.observed_at, "%d/%m/%Y %H:%M").replace(
                    tzinfo=ZoneInfo("Europe/Copenhagen")
                ),
                datetime.strptime(row.confirmed_at, "%Y-%m-%d").replace(
                    tzinfo=ZoneInfo("Europe/Vilnius")
                )
                if row.confirmed_at is not None
                else None,
            )
            for row in frozen_rows
        ]
        window = [
            (observed, confirmed)
            for observed, confirmed in observations
            if start <= observed < cutoff
        ]
        available = [
            observed
            for observed, confirmed in window
            if confirmed is not None and confirmed <= result_cutoff
        ]
        assert counts["source_rows"] == len(window)
        assert counts["training_rows"] == sum(observed < holdout for observed in available)
        assert counts["holdout_rows"] == sum(observed >= holdout for observed in available)
        assert int(run.data.params["unavailable_labels"]) == len(window) - len(available) > 0

    current = spark.table(table)
    assert current.count() == 243
    ids = {row[0] for row in current.select("record_id").collect()}
    assert ids == set(range(243)), ids
    assert current.where(current["prediction"].isNull()).count() == 0
    provenance = [
        row.asDict() for row in current.select("model_name", "model_version").distinct().collect()
    ]
    assert provenance == [{"model_name": model, "model_version": "1"}], provenance
    versions = [
        int(row[0]) for row in history(spark, table).select("version").orderBy("version").collect()
    ]
    populations = {}
    initial = None
    for number in versions:
        frame = spark.read.option("versionAsOf", number).table(table)
        populations[number] = frame.count()
        if populations[number] == 240:
            initial = frame
            initial_version = number
    assert initial is not None, populations
    assert list(populations.values()) == [0, 240, 243], populations
    retained = current.where(current["record_id"] < 240).select(*initial.columns)
    assert initial.exceptAll(retained).count() == retained.exceptAll(initial).count() == 0
    return {
        "model": model,
        "version": "1",
        "run_id": run.info.run_id,
        "run_status": run.info.status,
        "engine": engine,
        "snapshot_version": selected["version"],
        "metrics": metrics,
        "training_rows": counts["training_rows"],
        "holdout_rows": counts["holdout_rows"],
        "prediction_rows": 243,
        "initial_target_version": initial_version,
        "target_version": versions[-1],
        "target_history_counts": populations,
        "initial_predictions_unchanged": True,
        "cv": cv["cv_config"],
        "artifacts": list(names),
        "verified_phase_receipts": list(phases),
    }


def main(spark, dbutils):
    """Verify only the bounded rehearsal tables and emit a compact acceptance receipt."""
    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
    client = MlflowClient()
    assert spark.table(SOURCE).count() == 243
    assert spark.read.option("versionAsOf", 0).table(SOURCE).count() == 240
    tables = {
        row.tableName
        for row in spark.sql(f"SHOW TABLES IN {SCHEMA}").collect()
        if row.tableName.startswith(PREFIX)
    }
    expected = {f"{PREFIX}_source", f"{PREFIX}_pandas_predictions", f"{PREFIX}_polars_predictions"}
    assert tables == expected, tables
    summary = {engine: audit_engine(spark, client, engine) for engine in ("pandas", "polars")}
    failure_runs = json.loads(dbutils.widgets.get("failure_run_ids"))
    experiment = client.get_run(summary["pandas"]["run_id"]).info.experiment_id
    failures = {}
    for kind, job_run_id in failure_runs.items():
        runs = client.search_runs(
            [experiment],
            filter_string=f"tags.`skyulf.lifecycle.job_run_id` = '{job_run_id}'",
        )
        assert len(runs) == 1, (kind, len(runs))
        run = runs[0]
        tags = run.data.tags
        assert tags.get("skyulf.lifecycle.finalize.receipt"), (kind, tags)
        assert not tags.get("skyulf.lifecycle.result.receipt"), (kind, tags)
        if kind == "fit_failure":
            assert run.info.status == "FAILED"
            assert tags["skyulf.lifecycle.train.attempt"] == "failed"
            assert not tags.get("skyulf.lifecycle.registration_intent")
        else:
            assert kind == "output_failure" and run.info.status == "FINISHED"
            assert tags.get("skyulf.lifecycle.decide.receipt")
            assert not tags.get("skyulf.lifecycle.result.attempt")
            model = f"{SCHEMA}.{PREFIX}_pandas_model_output_failure"
            registered = client.get_model_version_by_alias(model, "champion")
            assert str(registered.version) == "1" and registered.run_id == run.info.run_id
            assert not spark.catalog.tableExists(
                f"{SCHEMA}.{PREFIX}_pandas_predictions_output_failure"
            )
        failures[kind] = {
            "job_run_id": job_run_id,
            "mlflow_run_id": run.info.run_id,
            "run_status": run.info.status,
            "finalization_recorded": True,
            "result_not_published": True,
        }
    assert set(failures) == {"fit_failure", "output_failure"}
    summary["failures"] = failures
    summary["tables"] = sorted(tables)
    summary["source_rows"] = 243
    summary["no_extra_control_tables"] = True
    dbutils.notebook.exit(json.dumps(summary, allow_nan=False))


if __name__ == "__main__":
    main(globals()["spark"], globals()["dbutils"])
