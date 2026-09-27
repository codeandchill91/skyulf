"""Accept SM-34B only from complete saved live run, task and notebook evidence."""

import json
import math
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
TASKS = {
    "prepare_request",
    "training_requested",
    "train_and_register",
    "compare_and_decide",
    "apply_operator_action",
    "finalize_and_report",
    "scoring_requested",
    "run_batch_scoring",
}
TRAINING = {"train_and_register", "compare_and_decide"}


def read(folder, name):
    """Read exact evidence, including files written with a PowerShell UTF-8 BOM."""
    return json.loads((folder / name).read_text(encoding="utf-8-sig"))


def result(folder, stem):
    """Reject errors or truncated notebook output and cross-check the saved result."""
    output = read(folder, f"{stem}-output.json")
    assert not output.get("error"), output.get("error")
    notebook = output["notebook_output"]
    assert not notebook.get("truncated", False)
    payload = json.loads(notebook["result"])
    assert payload == read(folder, f"{stem}-result.json"), stem
    return payload


def successful(run):
    """Require completed success before considering any notebook result."""
    assert run["state"]["life_cycle_state"] == "TERMINATED", run["state"]
    assert run["state"]["result_state"] == "SUCCESS", run["state"]


def lifecycle(folder, label, *, operator=False, score=False):
    """Verify the real eight-task graph including both excluded conditional branches."""
    run = read(folder, f"{label}-run.json")
    successful(run)
    tasks = {task["task_key"]: task for task in run["tasks"]}
    assert len(run["tasks"]) == 8 and set(tasks) == TASKS, tasks.keys()
    assert sum(len(task.get("depends_on", [])) for task in tasks.values()) == 8
    assert tasks["finalize_and_report"]["run_if"] == "ALL_DONE"
    excluded = set(TRAINING) if operator else {"apply_operator_action"}
    if not score:
        excluded.add("run_batch_scoring")
    for key, task in tasks.items():
        if key in excluded:
            assert task["state"]["life_cycle_state"] == "SKIPPED", task
            assert task["state"]["result_state"] == "EXCLUDED", task
        else:
            successful(task)
            if "notebook_task" in task:
                result(folder, f"{label}-{key}")
    published = result(folder, f"{label}-finalize_and_report")
    assert published["action"] == ("approve" if operator else "train")
    assert published["score_requested"] is score
    if score:
        child = read(folder, f"{label}-score-run.json")
        successful(child)
        assert len(child["tasks"]) == 1 and child["tasks"][0]["task_key"] == "score"
        successful(child["tasks"][0])
        parent = read(folder, f"{label}-run_batch_scoring-output.json")
        redirect = "Please refer to the logs for this run on the triggered run details page."
        assert not parent.get("error") or parent["error"] == redirect, parent.get("error")
        assert not parent.get("error_trace"), parent.get("error_trace")
        assert parent["run_job_output"]["run_id"] == child["run_id"]
    return run, published


def score_result(folder, label, count, *, child=False):
    """Check scored row counts and distinguish committed increments from true no-ops."""
    if not child:
        run = read(folder, f"{label}-run.json")
        successful(run)
        assert len(run["tasks"]) == 1 and run["tasks"][0]["task_key"] == "score"
        successful(run["tasks"][0])
    payload = result(folder, f"{label}-score")
    assert payload["action"] == "score"
    scored = payload["result"]
    assert scored["input_count"] == scored["output_count"] == count, scored
    assert scored["noop"] is (count == 0), scored
    assert scored["commit_version"] is not None, scored
    return scored


def failed_lifecycle(folder, label, failed_task):
    """Require failed cleanup/publication and no child score after the injected error."""
    run = read(folder, f"{label}-run.json")
    assert run["state"]["result_state"] == "FAILED", run["state"]
    tasks = {task["task_key"]: task for task in run["tasks"]}
    assert set(tasks) == TASKS
    assert tasks[failed_task]["state"]["result_state"] == "FAILED"
    assert tasks["finalize_and_report"]["state"]["result_state"] == "FAILED"
    for task in ("scoring_requested", "run_batch_scoring"):
        assert tasks[task]["state"]["life_cycle_state"] == "SKIPPED", tasks[task]
    completion = read(folder, f"{label}-finalize_and_report-output.json")
    assert "task outcomes" in completion["error"]
    assert not completion.get("notebook_output", {}).get("result")
    assert not (folder / f"{label}-score-run.json").exists()
    return run["run_id"]


def verify(folder=FOLDER):
    """Cross-check train, approval, incremental score, no-op and final read-only audit."""
    pandas_run, pandas = lifecycle(folder, "pandas_train", score=True)
    polars_run, polars = lifecycle(folder, "polars_train")
    approval_run, approval = lifecycle(folder, "polars_approve", operator=True, score=True)
    assert pandas["result"]["alias_change"]["new_version"] == "1"
    assert approval["result"]["new_version"] == "1"
    assert polars["next_actions"]["approve"]["candidate_version"] == "1"
    assert polars["next_actions"]["approve"]["expected_champion_version"] == "none"
    requested = read(folder, "polars_approve-request.json")["job_parameters"]
    for key, value in polars["next_actions"]["approve"].items():
        assert requested[key] == value, (key, requested)
    audit_run = read(folder, "audit-run.json")
    successful(audit_run)
    assert len(audit_run["tasks"]) == 1 and audit_run["tasks"][0]["task_key"] == "audit"
    successful(audit_run["tasks"][0])
    audit = result(folder, "audit-audit")
    assert audit["source_rows"] == 243 and audit["no_extra_control_tables"]
    summary = {
        "audit_run_id": audit_run["run_id"],
        "tables": audit["tables"],
        "training_run_ids": {"pandas": pandas_run["run_id"], "polars": polars_run["run_id"]},
        "approval_run_id": approval_run["run_id"],
    }
    deployed = read(folder, "final-job-state.json")
    for kind, expected_tasks in (("train", 8), ("score", 1)):
        assert deployed[kind]["active_runs"] == 0
        assert deployed[kind]["schedule"]["pause_status"] == "PAUSED"
        assert deployed[kind]["max_concurrent_runs"] == 1
        assert deployed[kind]["task_count"] == expected_tasks
    assert deployed["train"]["fault_injection_removed"]
    summary["final_jobs"] = deployed
    queued = read(folder, "polars_noop-queued.json")
    assert queued["run_id"] == read(folder, "polars_noop-run.json")["run_id"]
    assert queued["state"]["life_cycle_state"] == "QUEUED"
    summary["queued_score_run_id"] = queued["run_id"]
    summary["failures"] = audit["failures"]
    for label, task in (
        ("fit_failure", "train_and_register"),
        ("output_failure", "compare_and_decide"),
    ):
        run_id = failed_lifecycle(folder, label, task)
        assert audit["failures"][label]["job_run_id"] == run_id
        assert audit["failures"][label]["result_not_published"]
    for engine, candidate, label in (
        ("pandas", pandas["result"]["candidate"], "pandas_train"),
        ("polars", polars["result"], "polars_approve"),
    ):
        assert candidate["model_version"] == "1" and candidate["engine"] == engine
        assert candidate["model_name"] == (
            f"workspace.skyulf_lifecycle_test.sm34b_20260926_r1_{engine}_model"
        )
        initial = score_result(folder, label, 240, child=True)
        increment = score_result(folder, f"{engine}_increment", 3)
        noop = score_result(folder, f"{engine}_noop", 0)
        assert increment["commit_version"] == noop["commit_version"]
        assert increment["commit_version"] > initial["commit_version"]
        assert initial["source_end_version"] == 0
        assert increment["source_end_version"] == noop["source_end_version"] == 1
        for scored in (initial, increment, noop):
            assert scored["selected_model_name"] == candidate["model_name"]
            assert scored["selected_model_version"] == "1"
        checked = audit[engine]
        assert checked["run_id"] == candidate["run_id"]
        assert checked["model"] == candidate["model_name"]
        assert checked["run_status"] == "FINISHED" and checked["version"] == "1"
        assert checked["engine"] == engine and checked["snapshot_version"] == 0
        assert checked["prediction_rows"] == 243 and checked["initial_predictions_unchanged"]
        assert checked["initial_target_version"] == initial["commit_version"]
        assert checked["target_version"] == noop["commit_version"]
        assert checked["training_rows"] == candidate["training_rows"]
        assert checked["holdout_rows"] == candidate["holdout_rows"]
        assert checked["metrics"] and all(
            math.isfinite(value) for value in checked["metrics"].values()
        )
        summary[engine] = {
            **checked,
            "initial_score_run_id": read(folder, f"{label}-score-run.json")["run_id"],
            "increment_run_id": read(folder, f"{engine}_increment-run.json")["run_id"],
            "noop_run_id": read(folder, f"{engine}_noop-run.json")["run_id"],
            "initial_predictions": 240,
            "appended_predictions": 3,
            "noop_commit_version": noop["commit_version"],
        }
    (folder / "acceptance-summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    accepted = verify()
    print(f"Accepted SM-34B audit run {accepted['audit_run_id']}.")
    print(
        "Both engines: champion v1, frozen source v0, CV/heldout evidence, 240 + 3 predictions, no-op preserved."
    )
