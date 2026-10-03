param([string]$Directory = "$env:LOCALAPPDATA\BlackjackVisionLab\clef", [string]$PythonExe = "python")
$ErrorActionPreference = 'Stop'
$clefRoot = [System.IO.Path]::GetFullPath($Directory)
New-Item -ItemType Directory -Path $clefRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $clefRoot 'temp') -Force | Out-Null
$env:TEMP = Join-Path $clefRoot 'temp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $clefRoot 'pip-cache'
$env:HF_HOME = Join-Path $clefRoot 'hf-cache'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$clefPython = Join-Path $clefRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $clefPython)) {
    & $PythonExe -m venv (Join-Path $clefRoot 'venv')
    if ($LASTEXITCODE) { throw 'Python 3.12 environment creation failed.' }
}
& $clefPython -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu126
if ($LASTEXITCODE) { throw 'CUDA PyTorch installation failed.' }
& $clefPython -m pip install -r (Join-Path $PSScriptRoot 'clef-requirements.txt')
if ($LASTEXITCODE) { throw 'Clef runtime installation failed.' }
$clefModel = Join-Path $clefRoot 'model'
& $clefPython -c "import sys; from huggingface_hub import snapshot_download; snapshot_download('Cloudflare/clef-flash', revision='17f0b0ad64efb65d273590632833508766b2aae6', local_dir=sys.argv[1], max_workers=4)" $clefModel
if ($LASTEXITCODE) { throw 'Pinned model download failed; rerun to resume.' }
Write-Host "Clef files installed in $clefRoot. Run scripts/run-clef.ps1 -Directory `"$clefRoot`"."
Write-Host 'The model is optional. Its classifier confidence is not a game outcome probability.'
