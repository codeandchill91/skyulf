"""Prepare two explicit fault-injection variants of the generated pandas project."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    """Keep failures isolated and retain the original generated success case for restoration."""
    source = ROOT / "pandas/skyulf_lifecycle"
    for variant in ("fit_failure", "output_failure"):
        target = ROOT / variant / "skyulf_lifecycle"
        shutil.copytree(source, target)
        path = target / "config/workflow.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        if variant == "fit_failure":
            config["pipeline"]["modeling"]["params"]["n_estimators"] = 0
        else:
            config["model_name"] += "_output_failure"
            config["prediction_table"] += "_output_failure"
            notebook = target / "src/compare_and_decide.py"
            content = notebook.read_text(encoding="utf-8")
            content = content.replace(
                "# COMMAND ----------",
                '    raise RuntimeError("SM34B injected failure after saved decision")\n\n'
                "# COMMAND ----------",
            )
            notebook.write_text(content, encoding="utf-8")
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    print("Prepared fit failure and post-decision output failure variants.")


if __name__ == "__main__":
    main()
