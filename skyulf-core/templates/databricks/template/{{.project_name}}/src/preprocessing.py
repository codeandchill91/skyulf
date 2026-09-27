"""Edit this self-contained recipe; training saves it with the fitted model.

Keep custom classes in this file and imports limited to installed packages.
Sibling modules are not packaged. Keep data access and training out of imports
and recipe builders. See the Bundle guide for custom Calculator/Applier examples.
Preview and training call the two builders below; both start with no active steps.
Files in the template's examples directory are not loaded automatically.
"""


def build_pre_split_steps():
    """Declare fixed cleanup and training eligibility before the final split."""
    return [
        # {"name": "known_target", "transformer": "DropMissingRows",
        #  "params": {"subset": ["target"], "how": "any"}},
    ]


def build_preprocessing():
    """Return learned steps in order; replace column names with your features."""
    return [
        # {"name": "impute", "transformer": "SimpleImputer",
        #  "params": {"columns": ["feature_value"], "strategy": "mean"}},
        # {"name": "scale", "transformer": "StandardScaler",
        #  "params": {"columns": ["feature_value"]}},
    ]
