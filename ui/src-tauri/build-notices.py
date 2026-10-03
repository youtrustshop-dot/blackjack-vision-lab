"""Collect notices from the actual build inputs, without changing their terms."""
from __future__ import annotations

import ast
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys
import tomllib
import zipfile

project = Path(__file__).resolve().parents[2]
workspace = project.parents[1]
target = Path(__file__).resolve().parent / "licenses"
target.mkdir(exist_ok=True)
inventory = []
original_inputs = [workspace / "work/desktop-build/pyinstaller-work/bjlab-backend/Analysis-00.toc",
                   workspace / "work/desktop-toolchain/cargo/registry/src",
                   workspace / "work/desktop-toolchain/rustup/toolchains/stable-x86_64-pc-windows-gnu/share/doc/rust/COPYRIGHT-library.html",
                   workspace / "work/desktop-toolchain/microsoft.web.webview2.1.0.3800.47.nupkg"]
if not all(path.exists() for path in original_inputs):
    # The source release retains its collected notices so a clean checkout does
    # not depend on a previous local PyInstaller analysis or download cache.
    # Changing dependencies requires refreshing these notices with their sources.
    if (target / "inventory.json").is_file() and (target / "NOTICE.md").is_file():
        print(json.dumps({"reused_source_release_notices": True,
                          "refresh_requires_original_pinned_sources": True}))
        raise SystemExit(0)
    raise RuntimeError("Pinned notice inputs unavailable; retain the source release licenses directory or fetch the matching original sources")


def copy(source: Path, relative: str) -> str:
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return relative


def is_notice(path: Path) -> bool:
    # A library such as libwinapi_oemlicense.a contains "license" in its name,
    # but is compiled code rather than a copyright or license document.
    return (path.is_file()
            and path.suffix.lower() not in {".a", ".lib", ".dll", ".exe", ".o", ".obj", ".pdb", ".pyc"}
            and any(token in path.name.upper() for token in ("LICENSE", "COPYING", "NOTICE", "COPYRIGHT"))
            and ".git" not in path.parts)


def notice_files(directory: Path):
    return sorted(path for path in directory.rglob("*") if is_notice(path))


# PyInstaller's analysis identifies Python packages actually entering the sidecar.
analysis = ast.literal_eval((workspace / "work/desktop-build/pyinstaller-work/bjlab-backend/Analysis-00.toc").read_text())
paths = set()


def visit(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            visit(item)
    elif isinstance(value, str):
        paths.add(value.casefold())


visit(analysis)
for distribution in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
    name = distribution.metadata["Name"]
    files = distribution.files or ()
    selected = name.lower() in {"pyinstaller", "pyinstaller-hooks-contrib", "onnxruntime", "flatbuffers", "protobuf"} or any(
        str(distribution.locate_file(file)).casefold() in paths for file in files)
    if not selected:
        continue
    copied = []
    for file in files:
        source = Path(distribution.locate_file(file))
        if is_notice(source):
            copied.append(copy(source, "python/" + name + "-" + distribution.version + "/" + str(file).replace("\\", "/")))
    inventory.append({"ecosystem": "python", "name": name, "version": distribution.version,
                      "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License"),
                      "files": copied})

python_license = Path(sys.base_prefix) / "LICENSE.txt"
inventory.append({"ecosystem": "runtime", "name": "CPython", "version": sys.version.split()[0],
                  "files": [copy(python_license, "runtime/CPython-LICENSE.txt")]})
font_root = workspace / "work/desktop-toolchain/fonts"
inventory.append({"ecosystem": "font", "name": "DejaVu Sans", "version": "2.37",
                  "files": [copy(path, "font/" + path.name) for path in notice_files(font_root)]})
ocr_root = project / "bjlab/assets/ocr"
inventory.append({"ecosystem": "model", "name": "PaddleOCR PP-OCRv4 recognition via RapidOCR", "version": "RapidOCR 1.4.4",
                  "license": "Apache-2.0", "source": "https://pypi.org/project/rapidocr-onnxruntime/1.4.4/",
                  "files": [copy(path, "model/paddleocr/" + path.name) for path in ocr_root.iterdir() if path.suffix in {".txt", ".json", ".md"}]})

# Include the locked Cargo graph (also build-time packages); this is a conservative
# notice inventory, not a claim that every locked package is linked into the EXE.
registry = workspace / "work/desktop-toolchain/cargo/registry/src"
lock = tomllib.loads((project / "ui/src-tauri/Cargo.lock").read_text(encoding="utf-8"))
missing = []
for package in lock["package"]:
    if not package.get("source", "").startswith("registry"):
        continue
    name, version = package["name"], package["version"]
    roots = list(registry.glob("*/" + name + "-" + version))
    if not roots:
        missing.append(name + "-" + version)
        continue
    source = roots[0]
    manifest = tomllib.loads((source / "Cargo.toml").read_text(encoding="utf-8"))
    information = manifest["package"]
    copied = [copy(path, "rust/" + name + "-" + version + "/" + path.relative_to(source).as_posix())
              for path in notice_files(source)]
    upstream = workspace / "work/desktop-toolchain/upstream-notices" / (name + "-" + version)
    if upstream.exists():
        copied += [copy(path, "rust/" + name + "-" + version + "/upstream/" + path.name)
                   for path in upstream.iterdir() if path.is_file()]
    # Retain the exact upstream source for MPL portions and any package whose
    # packaged crate omits a separate notice file. No upstream source is modified.
    if not copied or "MPL" in information.get("license", ""):
        copied.append(copy(source / "Cargo.toml", "rust/" + name + "-" + version + "/Cargo.toml"))
        archives = list((workspace / "work/desktop-toolchain/cargo/registry/cache").glob("*/" + name + "-" + version + ".crate"))
        assert archives, "Original source archive unavailable: " + name
        copied.append(copy(archives[0], "source-archives/" + archives[0].name))
    inventory.append({"ecosystem": "cargo-lock", "name": name, "version": version,
                      "license": information.get("license"), "repository": information.get("repository"), "files": copied})

rust_doc = workspace / "work/desktop-toolchain/rustup/toolchains/stable-x86_64-pc-windows-gnu/share/doc/rust"
runtime_files = [copy(rust_doc / "COPYRIGHT-library.html", "runtime/Rust-COPYRIGHT-library.html")]
runtime_files += [copy(path, "runtime/rust-licenses/" + path.name) for path in (rust_doc / "licenses").iterdir() if path.is_file()]
inventory.append({"ecosystem": "runtime", "name": "Rust standard library and GNU runtime notices",
                  "version": "1.99.0", "files": runtime_files})

for name in ("react", "react-dom", "scheduler", "lucide-react"):
    source = project / "ui/node_modules" / name
    info = json.loads((source / "package.json").read_text())
    copied = [copy(path, "javascript/" + name + "-" + info["version"] + "/" + path.relative_to(source).as_posix())
              for path in notice_files(source)]
    inventory.append({"ecosystem": "javascript", "name": name, "version": info["version"],
                      "license": info.get("license"), "files": copied})

# Microsoft SDK license is taken from the official NuGet package matching the
# shipped loader's version. Verify binary equality before using those terms.
package = workspace / "work/desktop-toolchain/microsoft.web.webview2.1.0.3800.47.nupkg"
with zipfile.ZipFile(package) as archive:
    loader = archive.read("runtimes/win-x64/native/WebView2Loader.dll")
    actual = (project / "ui/src-tauri/runtime/WebView2Loader.dll").read_bytes()
    assert hashlib.sha256(loader).digest() == hashlib.sha256(actual).digest(), "SDK loader version mismatch"
    licenses = [name for name in archive.namelist() if "LICENSE" in name.upper() and not name.endswith("/")]
    assert licenses, "Official SDK package contains no license"
    copied = []
    for name in licenses:
        relative = "runtime/Microsoft-WebView2-1.0.3800.47/" + name
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.read(name))
        copied.append(relative)
inventory.append({"ecosystem": "runtime", "name": "Microsoft WebView2 Loader", "version": "1.0.3800.47",
                  "source": "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.3800.47/microsoft.web.webview2.1.0.3800.47.nupkg",
                  "files": copied})

notice = """# Third-party notices

Blackjack Vision Lab distributes unmodified third-party components. Their
copyright notices and terms are retained in this directory. `inventory.json`
records versions and notice paths from the Python freezing inputs, React UI,
locked Cargo graph, CPython runtime, DejaVu font and official WebView2 SDK.
`source-archives/` retains exact unmodified upstream crate source for MPL portions
and packages whose crate omits a separate license file. Pinned upstream monorepo
notices retain their source URL and commit beside the original license text.
The Cargo inventory conservatively includes build dependencies and packages for
other platforms; listing a package does not assert it is linked into this EXE.

Python's license includes its Microsoft Distributable Code restrictions. Those
restrictions apply to the Microsoft runtime components and must be retained in
redistribution. The WebView2 Loader is covered by the accompanying Microsoft SDK
license. The separately installed WebView2 browser runtime is provided by
Microsoft under its own terms. These Microsoft components are supplied without
warranty by the authors of this application and remain subject to their
accompanying restrictions; do not remove the notices, misuse Microsoft's marks,
redistribute them for non-Microsoft platforms, or use them in malicious programs.

The Rust runtime notice includes GPL text and GCC Runtime Library Exception 3.1
for any applicable GNU runtime portions. The exception's terms govern those
portions; including its notice does not relicense this application's own code.
PyInstaller's accompanying license retains its bootloader distribution exception.
OpenCV/FFmpeg, NumPy/OpenBLAS and Pillow include their upstream bundled notices.

This collection does not replace the original terms or grant additional rights.
"""
(target / "NOTICE.md").write_text(notice, encoding="utf-8")
(target / "inventory.json").write_text(json.dumps({"components": inventory, "unavailable_locked_sources": missing}, indent=2), encoding="utf-8")
print(json.dumps({"components": len(inventory), "notice_files": sum(len(item["files"]) for item in inventory),
                  "unavailable_locked_sources": missing, "notice_bytes": sum(path.stat().st_size for path in target.rglob("*") if path.is_file())}))
