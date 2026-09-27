"""Run the user-authorized SM-34B rehearsal on the existing two test jobs."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
PROJECT = ROOT.parent / "sm30_live/generated/skyulf_lifecycle"
REMOTE = "/Workspace/Users/edwardwolfe99@gmail.com/skyulf_lifecycle_test/sm34b/r1"
JOBS = {"train": 155738051514173, "score": 684955889505992}
WHEEL = "skyulf_core-0.9.0-py3-none-any.whl"
PREFIX = "sm34b_20260926_r1"


def cli(*args, cwd=None):
    """Use the selected profile without shell interpolation or automatic retries."""
    result = subprocess.run(
        ["databricks", *map(str, args), "--profile", "skyulf"],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def save(name, value):
    """Retain structured requests and evidence under this rehearsal directory."""
    path = ROOT / name
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def prepare():
    """Generate current templates and back up the existing local deployment."""
    template = REPO / "skyulf-core/templates/databricks"
    properties = json.loads((template / "databricks_template_schema.json").read_text())[
        "properties"
    ]
    backup = ROOT / "before"
    if backup.exists():
        raise ValueError("Backup exists; inspect it instead of overwriting.")
    backup.mkdir()
    for name in ("config", "resources", "src"):
        shutil.copytree(PROJECT / name, backup / name)
    for name in ("databricks.yml", "README.md"):
        shutil.copyfile(PROJECT / name, backup / name)
    for engine in ("pandas", "polars"):
        classification = engine == "pandas"
        values = {key: prop["default"] for key, prop in properties.items()}
        values.update(
            project_name="skyulf_lifecycle",
            engine=engine,
            task="classification" if classification else "regression",
            catalog="workspace",
            schema="skyulf_lifecycle_test",
            source_table_name=PREFIX + "_source",
            record_key_columns="record_id",
            input_columns="x,z",
            target_column="label" if classification else "target",
            training_version="null",
            training_sample_rows="null",
            classification_model="random_forest_classifier",
            regression_model="random_forest_regressor",
            cv_enabled="true",
            cv_folds="3",
            cv_type="stratified_k_fold" if classification else "time_series_split",
            cv_shuffle="true" if classification else "false",
            stratify="true" if classification else "false",
            score_model_selection="champion",
            promotion_policy="automatic" if classification else "manual_approval",
            score_handoff="after_alias_change",
            quality_threshold="0.4" if classification else "20.0",
            retraining_mode="scheduled",
            scoring_mode="scheduled",
            retraining_pause_status="PAUSED",
            scoring_pause_status="PAUSED",
            retraining_cron_expression="0 0 3 1 1,7 ?",
            scoring_cron_expression="0 0 3 * * ?",
        )
        if not classification:
            values.update(
                split_strategy="temporal",
                training_window_mode="rolling_calendar",
                monthly_lookback_months="4",
                holdout_months="1",
                window_timezone="UTC",
                event_column="observed_at",
                event_time_kind="text",
                event_time_format="%d/%m/%Y %H:%M",
                event_time_timezone="Europe/Copenhagen",
                filter_unavailable_results="true",
                result_available_at_column="confirmed_at",
                result_time_kind="text",
                result_text_kind="date",
                result_time_format="%Y-%m-%d",
                result_time_timezone="Europe/Vilnius",
                result_date_only="midnight",
                result_cutoff="",
                result_availability_lag_hours="0",
            )
        inputs = save(engine + "-init.json", values)
        cli("bundle", "init", template, "--config-file", inputs, "--output-dir", ROOT / engine)
        generated = ROOT / engine / "skyulf_lifecycle"
        config_path = generated / "config/workflow.json"
        config = json.loads(config_path.read_text())
        config.update(
            model_name="{catalog}.{metadata_schema}." + PREFIX + "_" + engine + "_model",
            prediction_table="{catalog}.{output_schema}." + PREFIX + "_" + engine + "_predictions",
        )
        config["pipeline"]["modeling"]["params"] = {
            "n_estimators": 16,
            "max_depth": 5,
            "random_state": 42,
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        (generated / "src/preprocessing.py").write_text(
            '"""Rehearsal recipe, snapshotted into the trained artifact."""\n\n'
            "def build_pre_split_steps():\n"
            '    """Keep all source records eligible before learned preprocessing."""\n'
            "    return []\n\n"
            "def build_preprocessing():\n"
            '    """Fit imputation and scaling only on each training partition."""\n'
            "    return [\n"
            '        {"name": "impute", "transformer": "SimpleImputer",\n'
            '         "params": {"columns": ["x", "z"], "strategy": "mean"}},\n'
            '        {"name": "scale", "transformer": "StandardScaler",\n'
            '         "params": {"columns": ["x", "z"]}},\n'
            "    ]\n",
            encoding="utf-8",
        )
        preview = subprocess.run(
            [sys.executable, "src/preview.py", "--action", "train"],
            cwd=generated,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if preview.returncode:
            raise RuntimeError(preview.stdout + preview.stderr)
        (ROOT / (engine + "-preview.txt")).write_text(preview.stdout, encoding="utf-8")
    print("Generated both cases and backed up the existing deployment.")


def upload():
    """Upload the current wheel and fixture, refusing to overwrite previous evidence."""
    cli("workspace", "mkdirs", REMOTE)
    cli(
        "workspace",
        "import",
        REMOTE + "/" + WHEEL,
        "--file",
        ROOT / "dist" / WHEEL,
        "--format",
        "RAW",
    )
    cli(
        "workspace",
        "import",
        REMOTE + "/fixture",
        "--file",
        ROOT / "fixture.py",
        "--format",
        "SOURCE",
        "--language",
        "PYTHON",
    )
    print("Uploaded wheel and fixture.")


def configure(engine):
    """Deploy the selected current template only while both test jobs are idle."""
    if engine not in {"pandas", "polars", "fit_failure", "output_failure"}:
        raise ValueError(engine)
    for job_id in JOBS.values():
        active = json.loads(
            cli("jobs", "list-runs", "--job-id", job_id, "--active-only", "--output", "json")
        )
        if active:
            raise ValueError("Test job is active; wait before changing its configuration.")
    generated = ROOT / engine / "skyulf_lifecycle"
    for folder in ("config", "resources", "src"):
        for source in (generated / folder).glob("*"):
            if source.is_file():
                shutil.copyfile(source, PROJECT / folder / source.name)
    for name in ("databricks.yml", "README.md"):
        shutil.copyfile(generated / name, PROJECT / name)
    shutil.copyfile(ROOT / "dist" / WHEEL, PROJECT / "dist" / WHEEL)
    path = PROJECT / "resources/workflow.jobs.yml"
    jobs = yaml.safe_load(path.read_text())
    for job in jobs["resources"]["jobs"].values():
        job["timeout_seconds"] = 900
        job["environments"][0]["spec"]["dependencies"][0] = REMOTE + "/" + WHEEL
        for task in job["tasks"]:
            if "condition_task" not in task:
                task.update(timeout_seconds=900, max_retries=0)
    path.write_text(yaml.safe_dump(jobs, sort_keys=False), encoding="utf-8")
    for operation in ("validate", "deploy"):
        args = ["bundle", operation, "-t", "dev"]
        if operation == "validate":
            args.append("--strict")
        (ROOT / f"{engine}-{operation}.log").write_text(cli(*args, cwd=PROJECT), encoding="utf-8")
    for key, job_id in JOBS.items():
        deployed = json.loads(cli("jobs", "get", job_id, "--output", "json"))
        save(engine + "-" + key + "-deployed.json", deployed)
        assert deployed["settings"]["schedule"]["pause_status"] == "PAUSED"
        if key == "train":
            assert len(deployed["settings"]["tasks"]) == 8
            assert (
                next(
                    p["default"]
                    for p in deployed["settings"]["parameters"]
                    if p["name"] == "lifecycle_action"
                )
                == "train"
            )
    print("Deployed", engine, "to existing two jobs; both schedules paused.")


def submit(label, task, parameters=None):
    """Run one bounded auxiliary notebook without a persistent job."""
    request = save(
        label + "-request.json",
        {
            "run_name": "SM34B " + label,
            "timeout_seconds": 900,
            "idempotency_token": "sm34b-r1-" + label,
            "tasks": [
                {
                    "task_key": task,
                    "notebook_task": {
                        "notebook_path": REMOTE + "/" + task,
                        "base_parameters": parameters or {},
                    },
                    "environment_key": "skyulf",
                    "timeout_seconds": 900,
                    "max_retries": 0,
                    "disable_auto_optimization": True,
                }
            ],
            "environments": [
                {
                    "environment_key": "skyulf",
                    "spec": {
                        "client": "4",
                        "dependencies": [REMOTE + "/" + WHEEL, "mlflow==3.16.1"],
                    },
                }
            ],
        },
    )
    result = json.loads(
        cli("jobs", "submit", "--json", "@" + str(request), "--no-wait", "--output", "json")
    )
    save(label + "-start.json", result)
    print(label, result)


def start(label, job, parameters):
    """Run the real Bundle with an idempotency key and retain its exact request."""
    request = save(
        label + "-request.json",
        {
            "job_id": JOBS[job],
            "job_parameters": parameters,
            "idempotency_token": "sm34b-r1-" + label,
        },
    )
    result = json.loads(
        cli("jobs", "run-now", "--json", "@" + str(request), "--no-wait", "--output", "json")
    )
    save(label + "-start.json", result)
    print(label, result)


def poll(label):
    """Collect current task states and terminal outputs without waiting or rerunning."""
    started = json.loads((ROOT / (label + "-start.json")).read_text())
    run = json.loads(
        cli("jobs", "get-run", started["run_id"], "--include-resolved-values", "--output", "json")
    )
    save(label + "-run.json", run)
    print(label, run["state"], run.get("run_page_url"))
    for task in run.get("tasks", []):
        state = task.get("state", {})
        print(task["task_key"], state.get("life_cycle_state"), state.get("result_state"))
        if state.get("life_cycle_state") != "TERMINATED" or not (
            task.get("notebook_task") or task.get("run_job_task")
        ):
            continue
        cached = ROOT / (label + "-" + task["task_key"] + "-output.json")
        if cached.exists():
            continue
        output = json.loads(cli("jobs", "get-run-output", task["run_id"], "--output", "json"))
        save(label + "-" + task["task_key"] + "-output.json", output)
        if output.get("notebook_output", {}).get("result"):
            result = json.loads(output["notebook_output"]["result"])
            save(label + "-" + task["task_key"] + "-result.json", result)
            visible = {
                key: value
                for key, value in result.items()
                if key
                in {
                    "action",
                    "status",
                    "candidate_version",
                    "training_rows",
                    "holdout_rows",
                    "source_version",
                    "score_requested",
                    "metrics",
                }
            }
            print(json.dumps(visible))
        if output.get("error"):
            print(output["error"], output.get("error_trace", "")[-5000:])
        if output.get("run_job_output"):
            child = json.loads(
                cli("jobs", "get-run", output["run_job_output"]["run_id"], "--output", "json")
            )
            save(label + "-score-run.json", child)
            child_output = json.loads(
                cli("jobs", "get-run-output", child["tasks"][0]["run_id"], "--output", "json")
            )
            save(label + "-score-output.json", child_output)
            if child_output.get("notebook_output", {}).get("result"):
                save(
                    label + "-score-result.json",
                    json.loads(child_output["notebook_output"]["result"]),
                )
            print("child score", child["state"], child_output.get("error"))


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "prepare":
        prepare()
    elif command == "upload":
        upload()
    elif command == "configure":
        configure(sys.argv[2])
    elif command == "fixture":
        submit("fixture_" + sys.argv[2], "fixture", {"fixture_action": sys.argv[2]})
    elif command == "start":
        start(
            sys.argv[2],
            sys.argv[3],
            json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) > 4 else {},
        )
    elif command == "poll":
        poll(sys.argv[2])
    elif command == "audit":
        cli(
            "workspace",
            "import",
            REMOTE + "/audit",
            "--file",
            ROOT / "audit.py",
            "--format",
            "SOURCE",
            "--language",
            "PYTHON",
        )
        submit("audit", "audit")
    else:
        raise ValueError(command)
