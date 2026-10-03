param([int]$Port = 8765, [string]$PythonExe = "")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not $PythonExe) { $PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python environment missing: run setup.ps1 or provide -PythonExe." }
Write-Host "Blackjack Vision Lab: http://127.0.0.1:$Port"
& $PythonExe -m bjlab.cli serve --port $Port
