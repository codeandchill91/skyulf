"""Project-owned search-space overrides for model training."""

from typing import Any


def build_search_space(
    model_type: str, strategy: str, params: dict[str, Any]
) -> dict[str, list[Any]] | None:
    """Return finite candidate lists, or None to use Core model defaults.

    The selected model type, strategy and fixed model parameters are provided so
    a project can adapt its search without changing installed Skyulf code. Keep
    each candidate list nonempty and choose a grid small enough for the configured
    max_candidates budget.

    For example, to narrow one model's default search:

        if model_type == "random_forest_regressor" and strategy == "grid":
            return {"max_depth": [3, 5], "n_estimators": [50, 100]}

    Fixed ``params`` can guide an override, but a searched parameter must not
    conflict with a fixed value in ``params``.
    """
    return None
