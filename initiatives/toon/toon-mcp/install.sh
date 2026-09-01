#!/usr/bin/env bash
set -e

# Target directory for the TOON MCP Server
TARGET_DIR="${HOME}/.local/share/toon-mcp"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Setting up TOON MCP Server in ${TARGET_DIR}..."
mkdir -p "${TARGET_DIR}"

echo "==> Creating Python virtual environment..."
python3 -m venv "${TARGET_DIR}/venv"

echo "==> Installing dependencies..."
"${TARGET_DIR}/venv/bin/pip" install --upgrade pip --quiet
"${TARGET_DIR}/venv/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt" --quiet

echo "==> Copying server and test scripts..."
cp "${SCRIPT_DIR}/server.py" "${TARGET_DIR}/server.py"
cp "${SCRIPT_DIR}/test_tokens.py" "${TARGET_DIR}/test_tokens.py"
chmod +x "${TARGET_DIR}/server.py" "${TARGET_DIR}/test_tokens.py"

if [ -d "${HOME}/.copilot" ]; then
  echo "==> Installing global Copilot CLI instructions..."
  mkdir -p "${HOME}/.copilot/instructions"
  cp "${SCRIPT_DIR}/toon.instructions.template.md" "${HOME}/.copilot/instructions/toon.instructions.md"
  cp "${SCRIPT_DIR}/AGENTS.template.md" "${TARGET_DIR}/AGENTS.template.md"
  echo "    Per-repo agent guidance is NOT installed globally (AGENTS.md is"
  echo "    project-scoped). To use it, append it to a repository's AGENTS.md:"
  echo "      cat ${TARGET_DIR}/AGENTS.template.md >> /path/to/repo/AGENTS.md"
fi

echo "==> Running token savings benchmark & tests..."
"${TARGET_DIR}/venv/bin/python" "${TARGET_DIR}/test_tokens.py"

PYTHON_EXEC="${TARGET_DIR}/venv/bin/python"
SERVER_PATH="${TARGET_DIR}/server.py"

echo ""
echo "=========================================================="
echo "  TOON MCP Server successfully installed!"
echo "=========================================================="
echo ""
echo "Add the following to your MCP configuration (e.g., in VS Code settings or mcp.json):"
echo ""
cat <<EOF
{
  "mcpServers": {
    "toon": {
      "command": "${PYTHON_EXEC}",
      "args": ["${SERVER_PATH}"]
    }
  }
}
EOF
echo ""
