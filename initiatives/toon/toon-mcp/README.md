# TOON MCP Server Setup & Deployment Guide

This folder contains a ready-to-deploy **TOON MCP Server** that can be installed on any machine (macOS, Linux, or Windows) to enable token-efficient structured data serialization (Token-Oriented Object Notation) for GitHub Copilot, Claude Desktop, and VS Code.

---

## What is Included

| File | Description |
|------|-------------|
| `server.py` | Complete MCP server source code with FastMCP stdio interface |
| `test_tokens.py` | `tiktoken` benchmark script measuring token savings on sample datasets |
| `requirements.txt` | Dependencies (`toon-py>=1.0.2`, `mcp<2`, `tiktoken>=0.7.0`) |
| `install.sh` | One-command automated installer for macOS and Linux |
| `install.ps1` | One-command automated installer for Windows PowerShell |
| `AGENTS.template.md` | Template repository instructions (`AGENTS.md`) |
| `toon.instructions.template.md` | Global Copilot CLI instructions (`~/.copilot/instructions/`) |
| `README.md` | Step-by-step guidance for setting up on any machine |

---

## Automated Installation

### macOS / Linux
```bash
cd docs/toon-mcp
./install.sh
```

### Windows (PowerShell)
```powershell
cd docs\toon-mcp
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Both installers automatically:
1. Create `~/.local/share/toon-mcp/venv` (or `%USERPROFILE%\.local\share\toon-mcp\venv`)
2. Install `toon-py`, `mcp`, and `tiktoken`
3. Copy `server.py` and `test_tokens.py`
4. Set up global instructions in `~/.copilot/instructions/toon.instructions.md` (if `.copilot` exists)
5. Run the `tiktoken` token savings verification suite

---

## Manual Installation (All Platforms)

### Step 1: Create Installation Directory
- **macOS/Linux**: `~/.local/share/toon-mcp`
- **Windows**: `%USERPROFILE%\.local\share\toon-mcp`

```bash
mkdir -p ~/.local/share/toon-mcp
cp server.py ~/.local/share/toon-mcp/
```

### Step 2: Create Python Virtual Environment & Install Dependencies
Requires Python 3.10+:

```bash
# macOS / Linux
python3 -m venv ~/.local/share/toon-mcp/venv
~/.local/share/toon-mcp/venv/bin/pip install "toon-py>=1.0.2" "mcp<2"

# Windows (Command Prompt / PowerShell)
python -m venv %USERPROFILE%\.local\share\toon-mcp\venv
%USERPROFILE%\.local\share\toon-mcp\venv\Scripts\pip install "toon-py>=1.0.2" "mcp<2"
```

### Step 3: Verify Installation
```bash
# macOS / Linux
~/.local/share/toon-mcp/venv/bin/python -c "import toon_py, mcp; print('Ready!')"

# Windows
%USERPROFILE%\.local\share\toon-mcp\venv\Scripts\python -c "import toon_py, mcp; print('Ready!')"
```

---

## MCP Configuration

Add the server to your MCP client configuration:

### 1. VS Code / Copilot (`mcp.json` / Settings)
```json
{
  "mcpServers": {
    "toon": {
      "command": "/Users/<USERNAME>/.local/share/toon-mcp/venv/bin/python",
      "args": ["/Users/<USERNAME>/.local/share/toon-mcp/server.py"]
    }
  }
}
```
*(On Windows, replace paths with `C:\\Users\\<USERNAME>\\.local\\share\\toon-mcp\\venv\\Scripts\\python.exe` and `C:\\Users\\<USERNAME>\\.local\\share\\toon-mcp\\server.py`)*

### 2. Claude Desktop (`claude_desktop_config.json`)
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "toon": {
      "command": "/Users/<USERNAME>/.local/share/toon-mcp/venv/bin/python",
      "args": ["/Users/<USERNAME>/.local/share/toon-mcp/server.py"]
    }
  }
}
```

---

## Integrating with AI Agents

### Option A: Global Configuration across ALL Repositories (Recommended)
Copy `toon.instructions.template.md` into your global Copilot CLI instructions folder:

```bash
mkdir -p ~/.copilot/instructions
cp toon.instructions.template.md ~/.copilot/instructions/toon.instructions.md
```

### Option B: Per-Repository Configuration (`AGENTS.md`)
Copy `AGENTS.template.md` into your project root as `AGENTS.md` (or `.github/copilot-instructions.md`):

```bash
cp AGENTS.template.md /path/to/repo/AGENTS.md
```

This ensures AI agents reach for TOON when ingesting large uniform JSON. Savings are 30–60% **versus JSON** (~44% vs pretty, ~35% vs compact); versus a Markdown table the gain is only ~12%, so TOON is not appropriate for human-facing output.

---

## How TOON Operates & Token Scope

### Does it convert every token?
**No, only structured data.**

| Data Type | Uses TOON? | Why / How |
|---|:---:|---|
| **JSON Files & Payloads** |  **Yes** | Converts nested keys/values into concise indentation & tabular format, eliminating repetitive keys (saves 30–60% **vs JSON**; best on flat uniform record lists). |
| **API Responses & DB Records** |  **Yes** | Flattens rows into compact header tables (`items[N]{col1,col2}: val1,val2`). |
| **Security / Tool Finding Lists** |  **Yes** | Minimizes token cost when loading large result batches into context. |
| **Chat & Natural Conversation** |  No | Natural text, questions, and explanations remain normal Markdown. |
| **Source Code Files** |  No | Python, JavaScript, Go, YAML, and other project source files remain unchanged. |

### Automatic Session Execution
Once configured:
1. Every new Copilot CLI / agent session automatically loads `~/.copilot/instructions/toon.instructions.md`.
2. The `toon` MCP server (`encode_toon`, `convert_file_to_toon`, `estimate_token_savings`) is automatically initialized.
3. The LLM natively formats and parses structured payloads using TOON whenever dealing with tabular or JSON data.

