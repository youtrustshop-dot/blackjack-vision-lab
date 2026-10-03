param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    & $PythonExe -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python environment creation failed." }
}
& .\.venv\Scripts\python.exe -m pip install -c requirements-lock.txt -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
Push-Location ui
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend installation failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally { Pop-Location }
Write-Host "Setup complete. Run .\run.ps1"
