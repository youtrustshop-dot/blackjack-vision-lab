param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    & $PythonExe -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Creazione ambiente Python fallita." }
}
& .\.venv\Scripts\python.exe -m pip install -c requirements-lock.txt -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Installazione dipendenze Python fallita." }
Push-Location ui
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Installazione frontend fallita." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Build frontend fallita." }
} finally { Pop-Location }
Write-Host "Installazione pronta. Eseguire .\run.ps1"
