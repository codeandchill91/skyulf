"""Guided search setup keeps ordinary training and search contracts distinct."""

import json
from pathlib import Path

from jsonschema import Draft7Validator

TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "templates/databricks"


def _properties():
    """Read the actual initializer questions so visibility regressions are caught."""
    return json.loads((TEMPLATE_ROOT / "databricks_template_schema.json").read_text())["properties"]


def _visible(properties, name, values):
    """Apply the same skip predicate used by the template initializer."""
    return not Draft7Validator(properties[name]["skip_prompt_if"]).is_valid(values)


def test_search_questions_follow_strategy_and_keep_cv_single():
    """Search setup should expose relevant controls with Core defaults first."""
    properties = _properties()
    values = {name: item["default"] for name, item in properties.items()}
    assert "search_mode" not in properties
    assert _visible(properties, "search_strategy", values)
    assert _visible(properties, "search_settings", values)
    assert all(
        not _visible(properties, field, values) for field in ("search_space", "search_timeout")
    )
    assert _visible(properties, "search_n_trials", values)
    values.update(task="regression", search_strategy="grid")
    assert all(
        _visible(properties, field, values)
        for field in (
            "search_strategy",
            "search_max_candidates",
            "search_random_state",
            "regression_search_metric",
        )
    )
    assert not _visible(properties, "search_n_trials", values)
    assert not _visible(properties, "search_space", values)
    assert not _visible(properties, "search_timeout", values)
    assert not _visible(properties, "classification_search_metric", values)
    values.update(search_strategy="optuna", task="classification")
    assert values["search_settings"] == "default"
    assert not _visible(properties, "search_timeout", values)
    values["search_settings"] = "custom"
    assert _visible(properties, "search_timeout", values)
    assert _visible(properties, "search_n_trials", values)
    assert not _visible(properties, "search_max_candidates", values)
    assert _visible(properties, "classification_search_metric", values)
    assert not _visible(properties, "regression_search_metric", values)
    assert all(not name.startswith("search_cv_") for name in properties)
    assert set(properties["search_strategy"]["enum"]) == {
        "grid",
        "random",
        "optuna",
        "halving_grid",
        "halving_random",
    }
    values["search_strategy"] = "halving_random"
    assert all(
        _visible(properties, name, values)
        for name in ("search_factor", "search_resource", "search_min_resources")
    )
    assert not _visible(properties, "search_estimator_min_resources", values)
    values["search_resource"] = "n_estimators"
    assert _visible(properties, "search_estimator_min_resources", values)
    assert not _visible(properties, "search_min_resources", values)
    values["search_resource"] = "n_samples"
    assert all(
        not _visible(properties, name, values)
        for name in ("search_sampler", "search_pruner", "search_timeout")
    )
    values["search_strategy"] = "optuna"
    assert all(
        _visible(properties, name, values)
        for name in ("search_sampler", "search_pruner", "search_timeout")
    )
    assert all(
        not _visible(properties, name, values)
        for name in ("search_factor", "search_resource", "search_min_resources")
    )


def test_model_parameters_are_guided_for_ensembles_and_editable_for_others():
    """Ensemble selection needs a composition prompt; ordinary models retain JSON overrides."""
    properties = _properties()
    values = {name: item["default"] for name, item in properties.items()}
    assert not _visible(properties, "model_params", values)
    values["regression_model"] = "voting_regressor"
    assert _visible(properties, "model_params", values)
    values.update(task="classification", classification_model="stacking_classifier")
    assert _visible(properties, "model_params", values)


def test_search_budget_and_seed_inputs_are_bounded():
    """Guided values must reject out-of-budget trials and malformed search seeds."""
    properties = _properties()
    assert properties["search_n_trials"]["pattern"] == "^(?:[1-9]|[1-9][0-9]{1,2}|1000)$"
    assert properties["search_max_candidates"]["pattern"] == "^(?:[1-9]|[1-9][0-9]{1,3}|10000)$"
    assert properties["search_timeout"]["pattern"] == "^(?:null|[1-9][0-9]*)$"
    assert properties["search_random_state"]["pattern"] == "^(?:0|[1-9][0-9]*)$"


def test_cv_questions_follow_enabled_method():
    """Fold settings should appear only when they can affect candidate scoring."""
    properties = _properties()
    values = {name: item["default"] for name, item in properties.items()}
    assert not _visible(properties, "cv_folds", values)
    assert not _visible(properties, "cv_type", values)
    values["cv_enabled"] = "true"
    assert all(
        _visible(properties, name, values)
        for name in ("cv_folds", "cv_type", "cv_shuffle", "cv_random_state")
    )
    values["cv_type"] = "time_series_split"
    assert not _visible(properties, "cv_shuffle", values)
    assert not _visible(properties, "cv_random_state", values)
    values["cv_type"] = "shuffle_split"
    assert not _visible(properties, "cv_shuffle", values)
    assert _visible(properties, "cv_random_state", values)


def test_search_example_names_compatible_model_axis():
    """The guided example should use Core defaults and a native search metric."""
    example = json.loads((TEMPLATE_ROOT / "examples/tuning-init.example.json").read_text())
    assert "search_mode" not in example
    assert example["regression_model"] == "random_forest_regressor"
    assert example["regression_search_metric"] == "rmse"
    assert "search_space" not in example


def test_tuning_hook_is_synced_with_generated_bundle():
    """The project hook must reach the workspace where the training notebook imports it."""
    source = TEMPLATE_ROOT / "template/{{.project_name}}/src/tuning.py"
    bundle = TEMPLATE_ROOT / "template/{{.project_name}}/databricks.yml.tmpl"
    assert source.is_file()
    assert "    - src/tuning.py" in bundle.read_text()
