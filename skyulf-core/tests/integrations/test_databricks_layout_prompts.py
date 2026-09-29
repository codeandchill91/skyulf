"""Training layout determines whether the wizard or branch recipes own model choices."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

SCHEMA = (
    Path(__file__).resolve().parents[2] / "templates/databricks/databricks_template_schema.json"
)
SHARED_FIELDS = {
    "training_layout",
    "project_name",
    "engine",
    "catalog",
    "schema",
    "source_table_name",
    "record_key_columns",
    "training_version",
    "max_rows",
    "max_input_mb",
    "compute_mode",
    "cluster_policy_name",
    "spark_version",
    "node_type_id",
    "cost_tag_key",
    "cost_tag_value",
    "retraining_mode",
    "retraining_cron_expression",
    "retraining_timezone_id",
    "retraining_pause_status",
}


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {
            "task": "classification",
            "cv_enabled": "true",
            "cv_type": "nested_cv",
            "cv_nested_type": "stratified_group_k_fold",
            "search_settings": "custom",
            "search_strategy": "optuna",
            "filter_unavailable_results": "true",
        },
        {
            "cv_enabled": "true",
            "cv_type": "time_series_split",
            "training_window_mode": "fixed_window",
            "search_settings": "custom",
            "search_strategy": "halving_grid",
            "scoring_mode": "scheduled",
        },
    ],
)
def test_multi_target_only_prompts_for_shared_setup(settings):
    """Branch recipes own model and split settings, even when advanced defaults are supplied."""
    properties = json.loads(SCHEMA.read_text())["properties"]
    values = {name: field["default"] for name, field in properties.items()}
    values.update(settings, training_layout="multi_target")
    visible = {
        name
        for name, field in properties.items()
        if not Draft7Validator(field.get("skip_prompt_if", False)).is_valid(values)
    }
    assert visible <= SHARED_FIELDS
    assert {
        "project_name",
        "engine",
        "catalog",
        "schema",
        "source_table_name",
        "record_key_columns",
        "training_version",
        "compute_mode",
        "retraining_mode",
    } <= visible


def test_multi_target_keeps_scheduled_training_and_policy_compute_questions():
    """Selecting branch training must retain the shared deployment controls it needs."""
    properties = json.loads(SCHEMA.read_text())["properties"]
    values = {name: field["default"] for name, field in properties.items()}
    values.update(
        training_layout="multi_target", retraining_mode="scheduled", compute_mode="policy_cluster"
    )
    fields = {
        "retraining_cron_expression",
        "retraining_timezone_id",
        "retraining_pause_status",
        "cluster_policy_name",
        "spark_version",
        "node_type_id",
        "cost_tag_key",
        "cost_tag_value",
    }
    assert all(
        not Draft7Validator(properties[name].get("skip_prompt_if", False)).is_valid(values)
        for name in fields
    )
