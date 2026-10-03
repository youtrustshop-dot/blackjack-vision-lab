param(
    [string]$PythonExe = "",
    [string]$CargoHome = "",
    [string]$RustupHome = "",
    [string]$GnuBin = "",
    [string]$ReleaseDirectory = "",
    [string]$TauriCliScript = "",
    [switch]$BackendOnly,
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$MetadataOnly
)
$ErrorActionPreference = "Stop"
$bjProject = Split-Path -Parent $PSScriptRoot
$bjVersion = (Get-Content -LiteralPath (Join-Path $bjProject "ui\src-tauri\tauri.conf.json") -Raw | ConvertFrom-Json).version
$bjWorkspace = Split-Path -Parent (Split-Path -Parent $bjProject)
$bjWork = Join-Path $bjWorkspace "work\desktop-build"
$bjRelease = if ($ReleaseDirectory) { [System.IO.Path]::GetFullPath($ReleaseDirectory) } else { Join-Path $bjProject "release" }
$bjToolchain = Join-Path $bjWorkspace "work\desktop-toolchain"
if (-not $PythonExe) { $PythonExe = Join-Path $bjWorkspace "work\venv-bjlab\Scripts\python.exe" }
if (-not $CargoHome) { $CargoHome = Join-Path $bjToolchain "cargo" }
if (-not $RustupHome) { $RustupHome = Join-Path $bjToolchain "rustup" }
if (-not $GnuBin) { $GnuBin = Join-Path $bjToolchain "w64devkit\bin" }
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Python build environment missing: $PythonExe" }
New-Item -ItemType Directory -Force -Path $bjWork, $bjRelease | Out-Null

function Assert-Exit([string]$Operation) {
    if ($LASTEXITCODE -ne 0) { throw "$Operation failed with exit code $LASTEXITCODE" }
}

function Invoke-PinnedTauri([string[]]$TauriArguments) {
    if ($TauriCliScript) {
        $bjCliPath = [System.IO.Path]::GetFullPath($TauriCliScript)
        $bjCliPackage = Join-Path (Split-Path -Parent $bjCliPath) "package.json"
        if (-not (Test-Path -LiteralPath $bjCliPath) -or
            (Get-Content -LiteralPath $bjCliPackage -Raw | ConvertFrom-Json).version -ne "2.12.1") {
            throw "A local Tauri CLI must be the pinned official 2.12.1 package"
        }
        & node.exe $bjCliPath @TauriArguments
    } else {
        & npm.cmd exec --yes --package=@tauri-apps/cli@2.12.1 -- tauri @TauriArguments
    }
    Assert-Exit "Pinned Tauri CLI"
}

$bjOriginalPath = $env:PATH
$bjOriginalLocation = Get-Location
$bjEnvironmentNames = @("CARGO_HOME", "RUSTUP_HOME", "CARGO_TARGET_DIR", "CARGO_BUILD_JOBS",
    "PYINSTALLER_CONFIG_DIR", "NPM_CONFIG_CACHE", "CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER", "RUSTFLAGS")
$bjOriginalEnvironment = @{}
foreach ($bjVariable in $bjEnvironmentNames) {
    $bjOriginalEnvironment[$bjVariable] = [Environment]::GetEnvironmentVariable($bjVariable, "Process")
}
try {
    $env:CARGO_HOME = $CargoHome
    $env:RUSTUP_HOME = $RustupHome
    $env:CARGO_TARGET_DIR = Join-Path $bjWork "cargo-target"
    $env:CARGO_BUILD_JOBS = "1"
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $bjWork "pyinstaller-cache"
    $env:NPM_CONFIG_CACHE = Join-Path $bjWork "npm-cache"
    $env:PATH = "$CargoHome\bin;$GnuBin;$bjOriginalPath"
    if ($MetadataOnly) {
        $SkipFrontend = $true
        $bjPreviousPath = Join-Path $bjWork "build-provenance.json"
        if (-not (Test-Path -LiteralPath $bjPreviousPath)) { throw "Metadata-only packaging requires a previous full build" }
        $bjPrevious = Get-Content -LiteralPath $bjPreviousPath -Raw | ConvertFrom-Json
        foreach ($bjProperty in $bjPrevious.source_sha256.PSObject.Properties) {
            if ($bjProperty.Name.StartsWith("bjlab/") -or $bjProperty.Name.StartsWith("ui/") -or $bjProperty.Name -eq "desktop_launcher.py") {
                if ((Get-FileHash -LiteralPath (Join-Path $bjProject $bjProperty.Name)).Hash.ToLowerInvariant() -ne $bjProperty.Value) {
                    throw "Runtime/frontend changed; use a full build: $($bjProperty.Name)"
                }
            }
        }
        $bjPreviousSidecar = Join-Path $bjWork "sidecar\bjlab-backend.exe"
        if (-not (Test-Path -LiteralPath $bjPreviousSidecar) -or
            (Get-Item -LiteralPath (Join-Path $bjProject "desktop_launcher.py")).LastWriteTimeUtc -gt (Get-Item -LiteralPath $bjPreviousSidecar).LastWriteTimeUtc) {
            throw "Frozen launcher changed or sidecar missing; use a full build"
        }
    }
    if (-not $SkipFrontend) {
        Set-Location -LiteralPath (Join-Path $bjProject "ui")
        & npm.cmd run build
        Assert-Exit "Frontend build"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $bjProject "ui\dist\index.html"))) { throw "Build the frontend first" }
    Copy-Item -LiteralPath (Join-Path $bjProject "ui\src-tauri\splash.html") -Destination (Join-Path $bjProject "ui\dist\splash.html") -Force
    Set-Location -LiteralPath $bjProject
    $bjIconCode = @'
from pathlib import Path
import sys
from PIL import Image, ImageDraw
root = Path(sys.argv[1]) / "ui" / "src-tauri" / "icons"
root.mkdir(parents=True, exist_ok=True)
image = Image.new("RGBA", (256,256), (17,19,24,255))
draw = ImageDraw.Draw(image)
gold=(216,184,106,255)
draw.rounded_rectangle((16,16,240,240),radius=60,fill=(43,40,30,255))
def cubic(a,b,c,d):
    return [tuple((1-t)**3*a[i]+3*(1-t)**2*t*b[i]+3*(1-t)*t*t*c[i]+t**3*d[i] for i in (0,1)) for t in [j/40 for j in range(41)]]
shape=[(128,48),(58,123)]+cubic((58,123),(21,171),(85,208),(123,160))+[(101,213),(155,213),(133,160)]+cubic((133,160),(171,208),(235,171),(197,123))
draw.polygon(shape,fill=gold)
eye=cubic((80,133),(101,105),(155,105),(176,133))+cubic((176,133),(155,162),(101,162),(80,133))
draw.polygon(eye,fill=(17,19,24,255));draw.ellipse((112,117,144,149),fill=gold)
image.save(root / "icon.png")
image.save(root / "icon.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
'@
    $bjIconScript = Join-Path $bjWork "generate-desktop-icon.py"
    $bjIconCode | Set-Content -LiteralPath $bjIconScript -Encoding utf8
    & $PythonExe $bjIconScript $bjProject
    Assert-Exit "Desktop icon generation"
    & $PythonExe -m PyInstaller --version
    Assert-Exit "PyInstaller availability (install into the build venv first)"
    # Resolve the exact shipped loader before its license/binary audit.
    & cargo.exe --version
    Assert-Exit "Cargo availability"
    $bjTarget = (& rustc.exe --print host-tuple).Trim()
    Assert-Exit "Rust host detection"
    if ($bjTarget -like "*-gnu" -and -not (Test-Path -LiteralPath (Join-Path $GnuBin "gcc.exe"))) {
        throw "GNU host requires the private w64devkit compiler: $GnuBin"
    }
    if ($bjTarget -like "*-gnu") {
        $bjRustSysroot = (& rustc.exe --print sysroot).Trim()
        $bjBundledLinker = Join-Path $bjRustSysroot "lib\rustlib\$bjTarget\bin\self-contained\x86_64-w64-mingw32-gcc.exe"
        if (-not (Test-Path -LiteralPath $bjBundledLinker)) { throw "Rust's matching GNU linker is missing: $bjBundledLinker" }
        $env:CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER = $bjBundledLinker
        $env:RUSTFLAGS = "-C link-self-contained=yes"
    }
    if ($bjTarget -notlike "x86_64-pc-windows-*") { throw "Desktop release script supports Windows x64 only: $bjTarget" }
    $bjCargoManifest = Join-Path $bjProject "ui\src-tauri\Cargo.toml"
    if (-not $MetadataOnly) {
        & cargo.exe fetch --locked --target $bjTarget --manifest-path $bjCargoManifest
        Assert-Exit "Locked desktop dependencies"
    }
    $bjVersionCode = @'
import pathlib, sys, tomllib
data = tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(next(item["version"] for item in data["package"] if item["name"] == "webview2-com-sys"))
'@
    $bjVersionScript = Join-Path $bjWork "read-webview-version.py"
    $bjVersionCode | Set-Content -LiteralPath $bjVersionScript -Encoding utf8
    $bjWebViewVersion = (& $PythonExe $bjVersionScript (Join-Path $bjProject "ui\src-tauri\Cargo.lock")).Trim()
    Assert-Exit "Pinned WebView2 loader version"
    $bjLoaderSources = @(Get-ChildItem -Path "$CargoHome\registry\src\*\webview2-com-sys-$bjWebViewVersion\x64\WebView2Loader.dll")
    if (-not $bjLoaderSources.Count) { throw "Pinned WebView2Loader.dll is missing from the private Cargo registry" }
    $bjRuntime = Join-Path $bjProject "ui\src-tauri\runtime"
    New-Item -ItemType Directory -Force -Path $bjRuntime | Out-Null
    Copy-Item -LiteralPath $bjLoaderSources[0].FullName -Destination (Join-Path $bjRuntime "WebView2Loader.dll") -Force

    if (-not $MetadataOnly) {
        & $PythonExe (Join-Path $bjProject "ui\src-tauri\build-notices.py")
        Assert-Exit "Third-party runtime and dependency notices"
    }
    $bjProvenanceFiles = @("bjlab/engine.py", "bjlab/solver.py", "bjlab/strategy.py", "bjlab/api.py", "bjlab/live.py", "bjlab/live_api.py", "bjlab/advice.py", "bjlab/advisor_api.py", "bjlab/model_api.py", "bjlab/simulator.py", "bjlab/vision.py", "bjlab/external_vision.py", "bjlab/ocr.py", "bjlab/assets/ocr/ch_PP-OCRv4_rec_infer.onnx", "desktop_launcher.py", "ui/src-tauri/src/main.rs", "ui/src-tauri/Cargo.toml", "ui/src-tauri/tauri.conf.json", "ui/dist/index.html", "docs/REQUIREMENTS.json")
    $bjProvenanceHashes = [ordered]@{}
    $bjProvenanceFiles += @("bjlab/clef_contract.py", "bjlab/poker.py", "bjlab/poker_api.py",
        "bjlab/poker_vision.py", "bjlab/round_lifecycle.py", "bjlab/table_labels.py", "bjlab/suit_symbols.py")
    foreach ($bjRelative in $bjProvenanceFiles) {
        $bjProvenancePath = Join-Path $bjProject $bjRelative
        if (Test-Path -LiteralPath $bjProvenancePath) {
            $bjProvenanceHashes[$bjRelative] = (Get-FileHash -LiteralPath $bjProvenancePath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $bjProvenance = Join-Path $bjWork "build-provenance.json"
    [ordered]@{ version = $bjVersion; source_sha256 = $bjProvenanceHashes } |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $bjProvenance -Encoding utf8
    $bjArgs = @("-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
        "--name", "bjlab-backend", "--distpath", (Join-Path $bjWork "sidecar"),
        "--workpath", (Join-Path $bjWork "pyinstaller-work"), "--specpath", $bjWork,
        "--paths", $bjProject, "--collect-submodules", "bjlab", "--collect-data", "bjlab", "--collect-all", "cv2", "--collect-all", "onnxruntime",
        "--add-data", ((Join-Path $bjProject "ui\dist") + ";ui/dist"),
        "--add-data", ((Join-Path $bjProject "docs") + ";docs"),
        "--add-data", ($bjProvenance + ";assets"),
        "--add-data", ((Join-Path $bjProject "ui\src-tauri\licenses") + ";assets/licenses"))
    if (-not $MetadataOnly) { $bjArgs += "--clean" }
    $bjFonts = Join-Path $bjToolchain "fonts"
    if (Test-Path -LiteralPath (Join-Path $bjFonts "DejaVuSans-Bold.ttf")) {
        $bjArgs += @("--add-data", ($bjFonts + ";assets/fonts"))
    } else { throw "Portable font bundle missing in $bjFonts; see docs/DESKTOP.md" }
    $bjArgs += (Join-Path $bjProject "desktop_launcher.py")
    if (-not $SkipBackend) {
        & $PythonExe @bjArgs
        Assert-Exit "Frozen backend build"
    }
    $bjSidecar = Join-Path $bjWork "sidecar\bjlab-backend.exe"
    if (-not (Test-Path -LiteralPath $bjSidecar)) { throw "Verified backend executable is missing: $bjSidecar" }
    $bjSelfTestOutput = @(& $bjSidecar --self-test)
    Assert-Exit "Frozen pixel/backend self-test"
    $bjSelfTestReport = Join-Path $bjWork "cached-sidecar-self-test.json"
    $bjSelfTestOutput -join "`n" | Set-Content -LiteralPath $bjSelfTestReport -Encoding utf8
    & $PythonExe (Join-Path $bjProject "ui\src-tauri\verify-sidecar.py") `
        --sidecar $bjSidecar --project $bjProject --expected $bjProvenance `
        --self-test $bjSelfTestReport --fonts $bjFonts
    Assert-Exit "Frozen backend source/provenance/payload freshness"
    Copy-Item -LiteralPath $bjSidecar -Destination (Join-Path $bjRelease "bjlab-backend.exe") -Force
    Copy-Item -LiteralPath (Join-Path $bjProject "ui\src-tauri\licenses") -Destination $bjRelease -Recurse -Force
    if ($BackendOnly) { Write-Host "Backend executable ready: $bjRelease\bjlab-backend.exe"; return }

    $bjBinaries = Join-Path $bjProject "ui\src-tauri\binaries"
    New-Item -ItemType Directory -Force -Path $bjBinaries | Out-Null
    Copy-Item -LiteralPath $bjSidecar -Destination (Join-Path $bjBinaries "bjlab-backend-$bjTarget.exe") -Force
    Set-Location -LiteralPath (Join-Path $bjProject "ui")
    $bjNative = Join-Path $env:CARGO_TARGET_DIR "$bjTarget\release\blackjack-vision-lab.exe"
    if ($MetadataOnly) {
        if (-not (Test-Path -LiteralPath $bjNative)) { throw "Previously built native executable is missing" }
        $bjNativeDate = (Get-Item -LiteralPath $bjNative).LastWriteTimeUtc
        foreach ($bjNativeInput in @("ui/src-tauri/src/main.rs", "ui/src-tauri/Cargo.toml", "ui/src-tauri/tauri.conf.json")) {
            if ((Get-Item -LiteralPath (Join-Path $bjProject $bjNativeInput)).LastWriteTimeUtc -gt $bjNativeDate) {
                throw "Native source/config changed; use a full build: $bjNativeInput"
            }
        }
        Invoke-PinnedTauri -TauriArguments @("bundle", "--target", $bjTarget, "--bundles", "nsis")
    } else {
        Invoke-PinnedTauri -TauriArguments @("build", "--target", $bjTarget)
    }
    Assert-Exit "Tauri desktop and NSIS build"
    Copy-Item -LiteralPath $bjNative -Destination (Join-Path $bjRelease "Blackjack Vision Lab.exe") -Force
    Copy-Item -LiteralPath (Join-Path $bjRuntime "WebView2Loader.dll") -Destination (Join-Path $bjRelease "WebView2Loader.dll") -Force
    $bjInstallers = Join-Path $env:CARGO_TARGET_DIR "$bjTarget\release\bundle\nsis"
    Get-ChildItem -LiteralPath $bjInstallers -Filter "Blackjack Vision Lab_${bjVersion}_x64-setup.exe" | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $bjRelease -Force
    }
    $bjHashes = Get-ChildItem -LiteralPath $bjRelease -File | Where-Object { $_.Extension -in @(".exe", ".dll") } | ForEach-Object {
        $bjHash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
        [ordered]@{ file = $_.Name; bytes = $_.Length; sha256 = $bjHash.Hash.ToLowerInvariant() }
    }
    [ordered]@{ version = $bjVersion; target = $bjTarget; files = @($bjHashes) } |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $bjRelease "manifest.json") -Encoding utf8
    Write-Host "Desktop artifacts ready in $bjRelease"
} finally {
    $env:PATH = $bjOriginalPath
    foreach ($bjVariable in $bjEnvironmentNames) {
        [Environment]::SetEnvironmentVariable($bjVariable, $bjOriginalEnvironment[$bjVariable], "Process")
    }
    Set-Location -LiteralPath $bjOriginalLocation
}
