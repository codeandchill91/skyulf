"""Generate the Databricks CLI wizard schema from topic files in schema/."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys, including nested prompt conditions."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_object(path: Path) -> dict[str, Any]:
    """Read a source object with actionable file context on invalid JSON."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object")
        return value
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def render_schema(source: Path) -> str:
    """Combine metadata and prompt definitions without silently replacing fields."""
    metadata = _read_object(source / "metadata.json")
    if "properties" in metadata:
        raise ValueError("metadata.json must not define properties; use topic files.")
    properties: dict[str, Any] = {}
    for path in sorted(source.glob("*.json")):
        if path.name == "metadata.json":
            continue
        fields = _read_object(path)
        duplicates = properties.keys() & fields.keys()
        if duplicates:
            raise ValueError(
                f"Duplicate properties in {path.name}: {', '.join(sorted(duplicates))}"
            )
        properties |= fields
    if not properties:
        raise ValueError("No prompt properties found in schema topic files.")
    metadata["properties"] = dict(sorted(properties.items(), key=lambda item: item[1]["order"]))
    return json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    """Regenerate the committed schema or check it without writing anything."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if the generated schema is stale"
    )
    options = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = root / "databricks_template_schema.json"
    rendered = render_schema(root / "schema")
    if options.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(
                "Template schema is out of date; run build_schema.py without --check.",
                file=sys.stderr,
            )
            return 1
        print("Template schema is up to date.")
        return 0
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Generated {output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
