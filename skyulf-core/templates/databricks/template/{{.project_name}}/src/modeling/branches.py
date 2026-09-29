"""Explicit, independent targets for the optional multi_target training layout.

Each workflow overlays config/workflow.json. Top-level values are replaced,
including the entire pipeline; nested settings are never implicitly merged.
features_path is relative to this directory and defaults to ../features.
Select preprocessing_recipe and pre_split_recipe independently from the named
builders in src/features. Reuse the package and custom code across models.
Use a different features_path only when a separate feature package is needed.
Keep all known target columns out of every branch's input_columns.
Each branch owns metric, quality_threshold, quality_gates and min_improvement.
Set suitable absolute thresholds before approving a set. RMSE/MAE/log-loss are
upper limits; accuracy/F1/AUC/R2 are lower limits. The numbers below are examples,
not recommended production limits. Additional quality_gates use other metrics.
Whole-set manual/automatic selection lives in model_set.py; branch promotion
stays manual because only the complete set receives the champion alias.
"""


def build_training_branches():
    """Return named branch declarations; empty means not configured and fails preflight."""
    # To enable, uncomment this return and adapt the columns to your source table.
    # All branches inherit the same input Delta table and version from workflow.json.
    # All four use the shared feature package with different named recipes.
    # A missing recipe selector uses that builder's default. Unknown names fail.
    # Leave pipeline.preprocessing empty: the selected Python recipe fills it.
    # Adapt every preprocessing/pre-split rule to that branch's available columns.
    # CV and extra quality gates are disabled explicitly to avoid inheriting
    # classification-only settings in the three regression branches.
    # Both ensemble base estimators receive the selected branch preprocessing.
    # return {
    #     "revenue": {
    #         "workflow": {
    #             "task": "regression",
    #             "target_column": "revenue_target",
    #             "input_columns": ["feature_value", "category"],
    #             "model_name": "{catalog}.{metadata_schema}.revenue{resource_suffix}",
    #             "metric": "heldout_rmse",
    #             "quality_threshold": 10.0,  # RMSE <= 10; adapt to revenue units.
    #             "quality_gates": None,
    #             "stratify": False,
    #             "cv_enabled": False,
    #             "cv_type": "k_fold",
    #             "pipeline": {"preprocessing": [], "modeling": {
    #                 "type": "ridge_regression", "params": {"alpha": 1.0}}},
    #         },
    #         "preprocessing_recipe": "frequency_only",
    #         "pre_split_recipe": "complete_inputs",
    #         "features_path": "../features",
    #     },
    #     "cost": {
    #         "preprocessing_recipe": "imputer_only",
    #         "pre_split_recipe": "none",
    #         "workflow": {
    #             "task": "regression",
    #             "target_column": "cost_target",
    #             "input_columns": ["feature_value"],
    #             "model_name": "{catalog}.{metadata_schema}.cost{resource_suffix}",
    #             "metric": "heldout_mae",
    #             "quality_threshold": 5.0,  # MAE <= 5; adapt to cost units.
    #             "quality_gates": None,
    #             "stratify": False,
    #             "cv_enabled": False,
    #             "cv_type": "k_fold",
    #             "pipeline": {"preprocessing": [], "modeling": {
    #                 "type": "linear_regression", "params": {}}},
    #         },
    #     },
    #     "churn": {
    #         "preprocessing_recipe": "combined",
    #         "pre_split_recipe": "complete_inputs",
    #         "workflow": {
    #             "task": "classification",
    #             "target_column": "churn_target",
    #             "input_columns": ["feature_value", "category"],
    #             "model_name": "{catalog}.{metadata_schema}.churn{resource_suffix}",
    #             "metric": "heldout_f1",
    #             "quality_threshold": 0.80,  # F1 >= 0.80; choose for your task.
    #             "quality_gates": None,
    #             "stratify": False,
    #             "cv_enabled": False,
    #             "cv_type": "k_fold",
    #             "pipeline": {"preprocessing": [], "modeling": {
    #                 "type": "logistic_regression", "params": {"max_iter": 200}}},
    #         },
    #     },
    #     "demand_ensemble": {
    #         "preprocessing_recipe": "combined",
    #         "pre_split_recipe": "complete_inputs",
    #         "workflow": {
    #             "task": "regression",
    #             "target_column": "demand_target",
    #             "input_columns": ["feature_value", "category"],
    #             "model_name": "{catalog}.{metadata_schema}.demand_ensemble{resource_suffix}",
    #             "metric": "heldout_rmse",
    #             "quality_threshold": 10.0,  # Ensemble RMSE <= 10; adapt to demand units.
    #             "quality_gates": None,
    #             "stratify": False,
    #             "cv_enabled": False,
    #             "cv_type": "k_fold",
    #             "pipeline": {"preprocessing": [], "modeling": {
    #                 "type": "voting_regressor",
    #                 "params": {
    #                     "base_estimators": ["linear_regression", "ridge"],
    #                     "weights": {"linear_regression": 1.0, "ridge": 2.0},
    #                     "n_jobs": 1,
    #                 }}},
    #         },
    #     },
    # }
    return {}
