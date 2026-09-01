# TOON MCP Server & Token Optimization Guide

This guide details how **Token-Oriented Object Notation (`TOON`)** is installed, configured as a Model Context Protocol (MCP) server for Copilot, and enforced through `AGENTS.md` to reduce token usage by 30–60% **when ingesting uniform JSON** (the gain versus a Markdown table is only ~12%, so TOON is for context ingestion, not human-facing output).

---

## 1. Overview & Architecture

`toon-py` provides a compact, human-readable serialization format designed for passing structured data to LLMs with significantly fewer tokens than JSON by:
- Removing redundant punctuation (braces, brackets, extra quotes).
- Leveraging indentation for hierarchy.
- Compacting object arrays into clean tabular structures (`key[N]{col1,col2}: val1,val2`).
- Inlining primitive arrays (`tags[2]: a,b`).

### MCP Server Location
- **Directory**: `~/.local/share/toon-mcp`
- **Virtualenv**: `~/.local/share/toon-mcp/venv`
- **Server Entrypoint**: `~/.local/share/toon-mcp/server.py`

---

## 2. Tools Provided by TOON MCP Server

1. **`encode_toon(json_input: str, delimiter: str = ",", length_marker: bool = False, indent: int = 2) -> str`**
   - Encodes a JSON string into compact TOON representation.
2. **`convert_file_to_toon(file_path: str, output_path: str | None = None) -> str`**
   - Reads a JSON file on disk and converts it into TOON. Optionally writes output to a specified destination.
3. **`estimate_token_savings(json_input: str) -> str`**
   - Computes character count, estimated token count, and percentage reduction between JSON and TOON.

---

## 3. Configuration

### Copilot / VS Code MCP Configuration
Add the server entry to your MCP configuration (e.g., in `mcp.json` / VS Code settings):

```json
{
  "mcpServers": {
    "toon": {
      "command": "/Users/BH7043/.local/share/toon-mcp/venv/bin/python",
      "args": ["/Users/BH7043/.local/share/toon-mcp/server.py"]
    }
  }
}
```

---

## 4. Agent Instructions & Global Rules

### Global Instructions (`~/.copilot/instructions/toon.instructions.md`)
To enforce TOON across all repositories on this machine, instructions are installed at `~/.copilot/instructions/toon.instructions.md` with `applyTo: '**'`.

### Repository Instructions (`AGENTS.md`)
An `AGENTS.md` file in the project root instructs AI agents to:
- Convert large JSON datasets or API payloads to TOON format before processing.
- Understand and emit TOON-formatted structured data when compactness is beneficial.

---

## 5. Scope of TOON & Automatic Execution

- **What uses TOON**: Structured datasets (JSON documents, API responses, scan reports, tabular records).
- **What stays normal**: Natural language chat, prompts, explanations, and standard source code files.
- **Automatic Execution**: The LLM reads `toon.instructions.md` and connects to the `toon` MCP server automatically on every new session launch without manual commands.

---

## 6. Portable Setup for Other Computers
A complete standalone installation package is maintained in `docs/toon-mcp/` with automated installer scripts (`install.sh` for macOS/Linux, `install.ps1` for Windows), template files, and benchmark test suite.
