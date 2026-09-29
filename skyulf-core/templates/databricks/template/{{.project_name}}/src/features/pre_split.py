"""Configure fixed cleanup and training eligibility before splitting.

Uncomment a step and its import, then adapt its source columns.
Custom pre-split steps cannot learn statistics or change survivor values.
scoring.py can reuse this recipe or choose separate custom scoring rules.
A target-reading filter requires SKIP_TARGET_PRE_SPLIT_STEPS=True for reuse.
"""

# from .custom.pre_split_custom import minimum_completeness


def build_pre_split_steps():
    """Declare ordered fixed cleanup and the selected completeness requirement."""
    return [
        # {"name": "known_target", "transformer": "DropMissingRows",
        #  "params": {"subset": ["target"], "how": "any"}},
        # minimum_completeness(columns=["field_a", "field_b", "field_c"], min_present=2),
    ]
