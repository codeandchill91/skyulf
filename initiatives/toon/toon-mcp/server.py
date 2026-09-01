#!/usr/bin/env python3
"""TOON MCP Server for token-efficient data encoding."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from toon_py import EncodeOptions, encode

try:
    import tiktoken

    # Built once: `get_encoding` reads/parses a BPE table, so rebuilding it per
    # call would dominate the cost of counting a few kilobytes of text.
    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:  # noqa: BLE001 - tokenizer is optional; fall back to an estimate
    _ENCODER = None

mcp = FastMCP("toon-server")

# FastMCP mirrors a tool's return value into `structuredContent` whenever the
# annotated return type isn't already an object -- so a `-> str` tool sends the
# payload twice (once as a text block, once as `{"result": ...}`). For a server
# whose entire purpose is saving tokens that doubles the cost of every call and
# can make TOON *more* expensive than the JSON it replaces. Opt out everywhere.
_TOOL = {"structured_output": False}


def _encode_options(delimiter: str, length_marker: bool, indent: int) -> EncodeOptions:
    """Build EncodeOptions from the shared tool arguments."""
    return EncodeOptions(
        delimiter=delimiter,
        length_marker="#" if length_marker else None,
        indent=indent,
    )


def _count_tokens(text: str) -> int:
    """Count tokens with tiktoken, falling back to a ~3.8 chars/token estimate."""
    if _ENCODER is None:
        return max(1, round(len(text) / 3.8))
    return len(_ENCODER.encode(text))


@mcp.tool(**_TOOL)
def encode_toon(
    json_input: str,
    delimiter: str = ",",
    length_marker: bool = False,
    indent: int = 2,
) -> str:
    """Encode a JSON string or structure into compact Token-Oriented Object Notation (TOON) format.

    Args:
        json_input: Raw JSON string to convert.
        delimiter: Delimiter for tabular arrays and inline lists (',' or '\\t' or '|').
        length_marker: If True, prefixes array lengths with '#' (e.g. items[#2]).
        indent: Number of spaces for indentation level.

    Returns:
        The compact TOON formatted string.
    """
    try:
        data = json.loads(json_input)
    except Exception as err:  # noqa: BLE001 - any parse failure is reported to the caller
        return f"Error decoding JSON: {err}"

    return encode(data, _encode_options(delimiter, length_marker, indent))


@mcp.tool(**_TOOL)
def convert_file_to_toon(
    file_path: str,
    output_path: str | None = None,
    delimiter: str = ",",
    length_marker: bool = False,
    indent: int = 2,
) -> str:
    """Read a JSON file from disk and convert it into TOON format.

    When ``output_path`` is given the TOON is written there and only a short
    summary is returned, so the payload never enters the caller's context.

    Args:
        file_path: Path to the input JSON file.
        output_path: Optional path to save the converted TOON file.
        delimiter: Delimiter to use.
        length_marker: Whether to include length marker.
        indent: Indentation size.

    Returns:
        The TOON representation, or a summary when ``output_path`` is set.
    """
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return f"Error: File not found at {file_path}"

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as err:  # noqa: BLE001 - any read/parse failure is reported to the caller
        return f"Error reading or parsing file: {err}"

    encoded = encode(data, _encode_options(delimiter, length_marker, indent))

    if not output_path:
        return encoded

    # Returning the full payload here would defeat the point of writing it to
    # disk -- the caller asked for a file precisely to keep it out of context.
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(encoded, encoding="utf-8")

    src_tokens = _count_tokens(content)
    toon_tokens = _count_tokens(encoded)
    saved = (src_tokens - toon_tokens) / src_tokens * 100 if src_tokens else 0.0
    return (
        f"Wrote TOON to {out}\n"
        f"Source JSON : {len(content)} chars (~{src_tokens} tokens)\n"
        f"TOON output : {len(encoded)} chars (~{toon_tokens} tokens)\n"
        f"Token change: {saved:+.1f}% (positive = saved)\n"
        f"Read the file to view its contents."
    )


@mcp.tool(**_TOOL)
def estimate_token_savings(json_input: str) -> str:
    """Calculate and compare size and estimated token savings between JSON and TOON format.

    Args:
        json_input: The raw JSON string.

    Returns:
        A summary of characters, estimated token counts, and percentage saved.
    """
    try:
        data = json.loads(json_input)
    except Exception as err:  # noqa: BLE001 - any parse failure is reported to the caller
        return f"Error decoding JSON: {err}"

    json_compact = json.dumps(data, separators=(",", ":"))
    json_pretty = json.dumps(data, indent=2)
    toon_output = encode(data)

    # Counted with a real tokenizer rather than a chars/token constant: JSON and
    # TOON tokenize at materially different ratios (quoted keys vs bare
    # comma-separated values), so a single constant skews the two sides of the
    # comparison in opposite directions and misstates the saving.
    json_compact_tokens = _count_tokens(json_compact)
    json_pretty_tokens = _count_tokens(json_pretty)
    toon_tokens = _count_tokens(toon_output)

    savings_vs_pretty = ((json_pretty_tokens - toon_tokens) / json_pretty_tokens) * 100
    savings_vs_compact = ((json_compact_tokens - toon_tokens) / json_compact_tokens) * 100

    return (
        f"--- Size & Token Estimates ---\n"
        f"JSON (Pretty) : {len(json_pretty)} chars ({json_pretty_tokens} tokens)\n"
        f"JSON (Compact): {len(json_compact)} chars ({json_compact_tokens} tokens)\n"
        f"TOON Output   : {len(toon_output)} chars ({toon_tokens} tokens)\n"
        f"Token Savings : {savings_vs_pretty:.1f}% (vs pretty) / {savings_vs_compact:.1f}% (vs compact)\n"
        f"Note: compare against the format you would otherwise have written."
    )


if __name__ == "__main__":
    mcp.run()
