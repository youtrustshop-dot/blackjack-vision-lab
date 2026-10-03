param([string]$Directory = "$env:LOCALAPPDATA\BlackjackVisionLab\clef")
$ErrorActionPreference = 'Stop'
$clefRoot = [System.IO.Path]::GetFullPath($Directory)
$clefPython = Join-Path $clefRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $clefPython)) { throw 'Optional environment missing. See scripts/install-clef.ps1.' }
$env:HF_HOME = Join-Path $clefRoot 'hf-cache'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
& $clefPython (Join-Path $PSScriptRoot 'clef-runtime.py') --model (Join-Path $clefRoot 'model')
