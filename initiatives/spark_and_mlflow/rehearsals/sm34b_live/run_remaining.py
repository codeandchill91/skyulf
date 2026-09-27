"""Finish the authorized sequential live checks, stopping on any unexpected outcome."""

import json
import time

import control
from verify_results import verify


def wait_for(label, expected="SUCCESS"):
    """Poll an existing run without retries, and reject unexpected terminal outcomes."""
    deadline = time.monotonic() + 960
    while time.monotonic() < deadline:
        control.poll(label)
        run = json.loads((control.ROOT / f"{label}-run.json").read_text())
        state = run["state"]
        if state["life_cycle_state"] in {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"}:
            if state.get("result_state") != expected:
                raise RuntimeError(f"Unexpected {label} outcome: {state}")
            return run["run_id"]
        time.sleep(20)
    raise TimeoutError(f"Outcome unknown for {label}; inspect the saved run, do not resubmit.")


def main():
    """Run appends/no-ops, two controlled failures, restore pandas, and audit the evidence."""
    wait_for("polars_approve")
    control.cli(
        "workspace",
        "import",
        control.REMOTE + "/fixture",
        "--file",
        control.ROOT / "fixture.py",
        "--format",
        "SOURCE",
        "--language",
        "PYTHON",
        "--overwrite",
    )
    control.submit("fixture_append", "fixture", {"fixture_action": "append"})
    wait_for("fixture_append")
    for engine in ("polars", "pandas"):
        if engine == "pandas":
            control.configure(engine)
        control.start(engine + "_increment", "score", {})
        control.start(engine + "_noop", "score", {})
        wait_for(engine + "_increment")
        wait_for(engine + "_noop")
    failure_runs = {}
    for variant in ("fit_failure", "output_failure"):
        control.configure(variant)
        control.start(variant, "train", {})
        failure_runs[variant] = wait_for(variant, expected="FAILED")
    control.configure("pandas")
    control.cli(
        "workspace",
        "import",
        control.REMOTE + "/audit",
        "--file",
        control.ROOT / "audit.py",
        "--format",
        "SOURCE",
        "--language",
        "PYTHON",
    )
    control.save("failure-run-ids.json", failure_runs)
    control.submit("audit", "audit", {"failure_run_ids": json.dumps(failure_runs)})
    wait_for("audit")
    summary = verify()
    print("SM34B LIVE ACCEPTED", summary["audit_run_id"], flush=True)


if __name__ == "__main__":
    main()
