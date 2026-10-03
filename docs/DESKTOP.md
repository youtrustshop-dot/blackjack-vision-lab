# Native desktop build

The native shell is Tauri 2. It launches the frozen Python backend as a bundled
sidecar, receives its actual ephemeral localhost URL, and opens the React UI in
WebView2. Python, Node, and Rust are build dependencies; they are not needed by a
user running the packaged application. WebView2 is the platform runtime.

The backend binds `127.0.0.1` on port 0, announces readiness only after Uvicorn
has started, and remains isolated from remote interfaces. Native window closure
requests graceful shutdown of its owned sidecar. A parent-PID monitor also exits the backend if the
native parent crashes. Solver worker processes use PyInstaller's early
`multiprocessing.freeze_support()` diversion, avoiding recursive app spawning.
The Windows control reader polls available pipe bytes with
[PeekNamedPipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe)
before reading. An idle blocking stdin read would prevent frozen worker CRT
initialization; the packaged smoke explicitly exercises this case.

## Build

From the project directory:

```powershell
.\scripts\build-desktop.ps1 -PythonExe <build-venv-python.exe>
```

Use `-SkipFrontend` only when `ui/dist` was built from the current UI source.
`-BackendOnly` packages and tests the Python executable without compiling the
native shell. `-CargoHome`, `-RustupHome`, and `-GnuBin` can point to existing
private toolchains. `-SkipBackend` reuses the current, already verified frozen
sidecar from `work/desktop-build/sidecar`; use it only when backend code and
bundled UI/docs are unchanged. The Tauri CLI is pinned to version 2.12.1.
For a documentation/roadmap-only refresh after a verified full build, use
`-MetadataOnly`. It rejects changed core/UI/native inputs, refreshes the frozen
data, and uses Tauri's documented [bundle command](https://v2.tauri.app/reference/cli/#bundle)
to regenerate NSIS from the already compiled native shell.
The script uses one Cargo build job and puts intermediate
PyInstaller, Cargo, and npm files under the workspace's `work/desktop-build`.
It does not modify the global PATH or install a service.

The script requires PyInstaller in the build venv and a portable DejaVu font
bundle under `work/desktop-toolchain/fonts/DejaVuSans-Bold.ttf`. Include the font
copyright/license alongside the font. Download from the
[DejaVu upstream release](https://github.com/dejavu-fonts/dejavu-fonts/releases/tag/version_2_37).
The frozen entry point sets `BJLAB_FONT_PATH` to the bundled font. Both the
renderer and the detector generate their glyph templates from that same font.

The official Windows development prerequisites are Microsoft C++ Build Tools,
Rust's MSVC target, and WebView2. See the
[Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) and
[external binary contract](https://v2.tauri.app/develop/sidecar/).
This machine has WebView2 but no detected Visual Studio C++/Windows SDK. A
private Rust GNU target and the upstream
[w64devkit portable compiler](https://github.com/skeeto/w64devkit/releases/tag/v2.10.0)
provide an alternate build route. Link Rust with its bundled matching GCC,
using `-C link-self-contained=yes`; the w64devkit PATH supplies resource tools.
Its executable and installer
must actually compile and pass the smoke checks before being marked delivered.

Private Rust setup uses `CARGO_HOME` and `RUSTUP_HOME` under workspace `work/`,
with rustup's `--no-modify-path` option. The configuration follows the
[rustup installation documentation](https://rust-lang.github.io/rustup/installation/).

## Artifacts and verification

Successful builds copy the native executable, frozen backend and NSIS installer
to `release/`, along with `manifest.json` containing file lengths and SHA-256
hashes. The NSIS installer uses the current user's installation scope. The
portable native executable must be kept alongside `bjlab-backend.exe` and
`WebView2Loader.dll`. The official SDK loader is pinned by Cargo.lock, copied
from the matching x64 crate, and included in the installer resources. See
[Microsoft's files-to-ship guidance](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution#files-to-ship-with-the-app).
Keep the accompanying `licenses/` directory with the portable files. It contains
the official Microsoft SDK terms, CPython/runtime notices, DejaVu attribution,
React dependencies, Python package notices, the locked Cargo inventory and the
GCC Runtime Library Exception. The same notices are installed by NSIS and
included inside the frozen sidecar. `build-provenance.json` inside the sidecar
records source/UI/roadmap hashes used by the build; `--self-test` reports them.

Verification must include:

1. Frozen `bjlab-backend.exe --self-test`: engine, NumPy/OpenCV, pixel recognition
   and packaged UI assets all load without the source checkout.
2. Frozen backend HTTP smoke: health, a seeded round, isolated solver analysis,
   a rendered PNG and pixel perception.
3. Native executable launch: its owned backend binds an ephemeral local port,
   the laboratory window appears, and its HTTP UI/API responds.
4. Closing the native app stops the owned backend and worker processes.
5. Installer artifact exists and matches the manifest hash. Installation should
   be explicitly tested before claiming installer installation has been verified.

The executable is unsigned. Distribution does not imply code-signing or a
verified installation on every Windows configuration. Current implementation
status includes a frozen backend that passed its actual HTTP/worker/pixel/replay
and graceful-shutdown smoke. Inspect `release/backend-smoke.json` for measured
evidence, including zero new one-file temporary-directory leaks. Native executable
and its WebView2 window have also passed the actual HTTP/worker/pixel/window-close
smoke in `release/native-smoke.json`. The current-user installer has been tested
in a fresh workspace directory: install, launch the installed native app, call
its frozen service, close the window, and uninstall. Inspect
`release/installer-smoke.json` and `release/installer-native-smoke.json` for the
artifact hashes and measured results. NSIS retains the remembered install
location when app-data deletion is not selected; the isolated test restores
only its own newly created preference afterward.

`release/owned-window-capture.png` is an actual MSS capture of the explicit client
rectangle of the owned native window, briefly made visible for verification.
Its receipt records the bounds and capture latency. No other window or complete
screen was selected. This proves the local capture adapter; recognition of
arbitrary card artwork remains subject to the documented detector calibration.
See the project requirements audit for authoritative completion evidence.

## Version 1.0.0 live workflow

English is the default for startup, UI and installer; Italiano is secondary. For display sharing, open the local app in Chrome or Edge using the handoff button and keep the native app running. WebView2 display-media support varies, so the native shell itself is not claimed to implement the browser picker. The lab video demo works without a display picker.

Build a new version into a distinct folder to preserve historical evidence:

```powershell
.\scripts\build-desktop.ps1 -ReleaseDirectory .\release\v1.0.0
python scripts/package-windows.py --release release/v1.0.0 --output ../blackjack-vision-lab-windows-v1.0.0.zip
```

An existing official `@tauri-apps/cli` 2.12.1 installation can be supplied with
`-TauriCliScript <absolute-path-to-tauri.js>`. The script validates the pinned
package version before using it. This avoids a broken global npm installation
without modifying it; ordinary builds still use the pinned npm package.

The manifest/versioned smoke reports distinguish new artifacts from the original v0.1.0 installation reports. Existing statements about installation under `release/installer-smoke.json` refer to that original measured release, not an untested reinstall of a later build. Verify each new frozen backend's live endpoint and native readiness/shutdown against its own digest.


Reproduce the versioned checks after building:

```powershell
.venv/Scripts/python.exe scripts/smoke-desktop.py --release release/v1.0.0 --work ../../work/v1-desktop-smoke
.venv/Scripts/python.exe scripts/smoke-desktop.py --release release/v1.0.0 --work ../../work/v1-desktop-smoke --native
.venv/Scripts/python.exe scripts/smoke-installer.py --release release/v1.0.0 --work ../../work/v1-installer-smoke
```

The installer check refuses to overwrite a pre-existing user installation. It tests only a newly created workspace directory, with no shortcuts, then uses its generated uninstaller and restores its own test-created registration/preference. Native verification creates a hidden WebView and uses a bounded test-only timer through the normal graceful Exit path; it does not automate desktop windows or claim a personal display-picker test. The frozen/native/installed runtime reads video images through the live endpoint and checks exposed counts through a reveal and second hand.
