"""Keep modular wizard sources and the CLI's generated schema synchronized."""

import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "templates/databricks"


def test_committed_schema_matches_sources():
    """CI must catch forgotten generation after any wizard source edit."""
    build = runpy.run_path(str(ROOT / "build_schema.py"))["render_schema"]
    assert build(ROOT / "schema") == (ROOT / "databricks_template_schema.json").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("duplicate", ["within_file", "across_files"])
def test_duplicate_properties_fail_without_overwriting(duplicate, tmp_path):
    """Duplicate names must fail loudly instead of silently replacing user prompts."""
    build = runpy.run_path(str(ROOT / "build_schema.py"))["render_schema"]
    (tmp_path / "metadata.json").write_text("{}")
    first = '{"project_name": {"order": 0}}'
    if duplicate == "within_file":
        first = '{"project_name": {"order": 0}, "project_name": {"order": 1}}'
    else:
        (tmp_path / "second.json").write_text(first)
    (tmp_path / "first.json").write_text(first)
    with pytest.raises(ValueError, match="Duplicate.*project_name"):
        build(tmp_path)


def test_schema_properties_follow_prompt_order(tmp_path):
    """Source filenames must not change the intended wizard order."""
    build = runpy.run_path(str(ROOT / "build_schema.py"))["render_schema"]
    (tmp_path / "metadata.json").write_text('{"welcome_message": "Hello"}')
    (tmp_path / "a.json").write_text('{"later": {"order": 2}}')
    (tmp_path / "z.json").write_text('{"first": {"order": 1}}')
    result = json.loads(build(tmp_path))
    assert result["welcome_message"] == "Hello"
    assert list(result["properties"]) == ["first", "later"]


def test_check_is_read_only_and_build_works_outside_template_directory(tmp_path):
    """Maintainers can regenerate from any working directory; CI never rewrites files."""
    root = tmp_path / "template"
    root.mkdir()
    shutil.copyfile(ROOT / "build_schema.py", root / "build_schema.py")
    shutil.copytree(ROOT / "schema", root / "schema")
    output = root / "databricks_template_schema.json"
    output.write_text("stale\n")
    command = [sys.executable, str(root / "build_schema.py")]
    stale = subprocess.run(command + ["--check"], cwd=tmp_path, capture_output=True, text=True)
    assert stale.returncode == 1
    assert "out of date" in stale.stderr
    assert output.read_text() == "stale\n"
    generated = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert generated.returncode == 0, generated.stderr
    check = subprocess.run(command + ["--check"], cwd=tmp_path, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert json.loads(output.read_text()) == json.loads(
        (ROOT / "databricks_template_schema.json").read_text()
    )
