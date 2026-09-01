# PowerShell automated installer for TOON MCP Server on Windows

$ErrorActionPreference = "Stop"

$TargetDir = "$env:USERPROFILE\.local\share\toon-mcp"
$ScriptDir = $PSScriptRoot

Write-Host "==> Setting up TOON MCP Server in $TargetDir..." -ForegroundColor Cyan
if (!(Test-Path -Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

Write-Host "==> Creating Python virtual environment..." -ForegroundColor Cyan
python -m venv "$TargetDir\venv"

$PipPath = "$TargetDir\venv\Scripts\pip.exe"
$PythonPath = "$TargetDir\venv\Scripts\python.exe"

Write-Host "==> Installing dependencies..." -ForegroundColor Cyan
& $PipPath install --upgrade pip --quiet
& $PipPath install -r "$ScriptDir\requirements.txt" --quiet

Write-Host "==> Copying server and test scripts..." -ForegroundColor Cyan
Copy-Item "$ScriptDir\server.py" "$TargetDir\server.py" -Force
Copy-Item "$ScriptDir\test_tokens.py" "$TargetDir\test_tokens.py" -Force

$CopilotDir = "$env:USERPROFILE\.copilot"
if (Test-Path -Path $CopilotDir) {
    Write-Host "==> Installing global Copilot CLI instructions..." -ForegroundColor Cyan
    $InstructionsDir = "$CopilotDir\instructions"
    if (!(Test-Path -Path $InstructionsDir)) {
        New-Item -ItemType Directory -Path $InstructionsDir -Force | Out-Null
    }
    Copy-Item "$ScriptDir\toon.instructions.template.md" "$InstructionsDir\toon.instructions.md" -Force
    Copy-Item "$ScriptDir\AGENTS.template.md" "$TargetDir\AGENTS.template.md" -Force
    Write-Host "    Per-repo agent guidance is NOT installed globally (AGENTS.md is"
    Write-Host "    project-scoped). To use it, append it to a repository's AGENTS.md:"
    Write-Host "      Get-Content $TargetDir\AGENTS.template.md | Add-Content <repo>\AGENTS.md"
}

Write-Host "==> Running token savings benchmark & tests..." -ForegroundColor Cyan
& $PythonPath "$TargetDir\test_tokens.py"

$EscapedPythonPath = "$TargetDir\venv\Scripts\python.exe".Replace("\", "\\")
$EscapedServerPath = "$TargetDir\server.py".Replace("\", "\\")

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  TOON MCP Server successfully installed!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Add the following to your MCP configuration (e.g., in VS Code settings or mcp.json):"
Write-Host @"
{
  "mcpServers": {
    "toon": {
      "command": "$EscapedPythonPath",
      "args": ["$EscapedServerPath"]
    }
  }
}
"@
Write-Host ""
