"""Configure fixed cleanup and training eligibility before splitting.

multi_model.py selects pre_split_recipe independently of preprocessing_recipe.
Available starters: default, none, complete_inputs. Adapt columns below.
Single-model training uses default; uncomment steps there when needed.
Custom pre-split steps cannot learn statistics or change survivor values.
scoring.py can reuse this recipe or choose separate custom scoring rules.
A target-reading filter requires SKIP_TARGET_PRE_SPLIT_STEPS=True for reuse.
"""

from .custom import pre_split_custom

# from .custom.pre_split_custom import minimum_completeness


def build_pre_split_steps(recipe="default"):
    """Select fixed eligibility steps independently for each training branch."""
    recipes = {
        "default": _default_recipe,
        "none": lambda: [],
        "complete_inputs": _complete_inputs,
    }
    if recipe not in recipes:
        raise ValueError(f"Unknown pre-split recipe: {recipe}. Choose from {list(recipes)}.")
    return recipes[recipe]()


def _complete_inputs():
    """Require at least one observed input without learning or changing values."""
    return [
        pre_split_custom.minimum_completeness(columns=["feature_value", "category"], min_present=1)
    ]


def _default_recipe():
    """Keep default filters inactive until their columns and rules are configured."""
    return [
        # {"name": "known_target", "transformer": "DropMissingRows",
        #  "params": {"subset": ["target"], "how": "any"}},
        # minimum_completeness(columns=["field_a", "field_b", "field_c"], min_present=2),
    ]
