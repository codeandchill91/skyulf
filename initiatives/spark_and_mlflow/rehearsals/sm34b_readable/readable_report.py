# Databricks notebook source
"""Replay saved first-candidate output and an illustrative rollback without ML side effects."""

import hashlib
import json
from pathlib import Path

from skyulf.integrations.databricks import job_output, job_runtime

dbutils = globals()["dbutils"]
values = dbutils.widgets.getAll()
for module in (job_output, job_runtime):
    name = module.__name__.rsplit(".", 1)[-1]
    assert (
        hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() == values[name + "_sha256"]
    )

rendered = []


def display_report(html):
    """Require real Databricks HTML display before recording a successful render."""
    globals()["displayHTML"](html)
    rendered.append(html.split("<details>", 1)[0])


comparison = json.loads(values["comparison_json"])
completion = json.loads(values["completion_json"])
assert completion["result"]["comparison"]["champion_metrics"] is None
for phase, payload in (("compare_decide", comparison), ("complete", completion)):
    renderer = (
        job_output.render_bundle_output
        if phase == "complete"
        else lambda payload: job_output.render_lifecycle_output("compare_decide", payload)
    )
    output = job_runtime._notebook_output(
        payload, dbutils, render=renderer, display_html=display_report, exit_notebook=False
    )
    assert json.loads(output) == payload
assert len(rendered) == 2
assert all("No champion" in html and "heldout_rmse" in html for html in rendered)
assert "Awaiting manual review" in rendered[0]
assert "Available action: approve" in rendered[1] and "Available action: reject" in rendered[1]
assert "If rollback is needed" not in rendered[1]

# This fixture demonstrates rendering only; it does not change a model alias.
rollback_example = {
    "action": "approve",
    "result": {
        "kind": "promotion",
        "model_name": "example.model",
        "prior_version": "1",
        "new_version": "2",
    },
    "score_requested": True,
    "next_actions": {
        "rollback": {
            "lifecycle_action": "rollback",
            "expected_champion_version": "2",
            "promotion_receipt_json": '{"example":"rendering only"}',
        }
    },
}
job_runtime._notebook_output(
    rollback_example,
    dbutils,
    render=job_output.render_bundle_output,
    display_html=display_report,
    exit_notebook=False,
)
assert len(rendered) == 3
assert "Required current champion</td><td>v2" in rendered[2]
assert "Restore version</td><td>v1" in rendered[2]
receipt = json.dumps(
    {
        "rendered_reports": 3,
        "real_polars_payloads": 2,
        "rollback_example": "v2 to v1",
        "module_hashes_verified": True,
        "model_mutations": 0,
    }
)

# COMMAND ----------

dbutils.notebook.exit(receipt)
