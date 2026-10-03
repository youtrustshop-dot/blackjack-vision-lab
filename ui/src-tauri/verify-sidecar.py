"""Reject a cached frozen backend whose recorded inputs or payload are stale."""
from __future__ import annotations

import argparse
import json
import marshal
from pathlib import Path
import sys

from PyInstaller.archive.readers import CArchiveReader


def verify(sidecar: Path, project: Path, expected_path: Path, report_path: Path, fonts: Path) -> dict:
    expected = json.loads(expected_path.read_text(encoding="utf-8-sig"))
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    actual = report.get("build_provenance")
    if report.get("event") != "self_test" or report.get("status") != "ok" or report.get("frozen") is not True:
        raise ValueError("Cached backend did not provide a successful frozen self-test")
    if not isinstance(actual, dict) or actual.get("version") != expected.get("version"):
        raise ValueError("Cached backend build provenance is missing or has a different version")
    if not isinstance(actual.get("source_sha256"), dict) or actual["source_sha256"] != expected["source_sha256"]:
        differing = sorted(set(expected["source_sha256"]) | set(actual.get("source_sha256", {})))
        differing = [name for name in differing if expected["source_sha256"].get(name) != actual.get("source_sha256", {}).get(name)]
        raise ValueError("Cached backend recorded source hashes differ: " + ", ".join(differing))

    archive = CArchiveReader(str(sidecar))
    entries = {name.replace("\\", "/"): name for name in archive.toc}
    embedded = json.loads(archive.extract(entries["assets/build-provenance.json"]).decode("utf-8-sig"))
    if embedded != actual:
        raise ValueError("Self-test provenance differs from the executable's embedded provenance")

    checked_data = 0
    for local, prefix in ((project / "docs", "docs/"), (project / "ui/dist", "ui/dist/"),
                          (project / "bjlab/assets", "bjlab/assets/"),
                          (project / "ui/src-tauri/licenses", "assets/licenses/"), (fonts, "assets/fonts/")):
        source_files = {prefix + path.relative_to(local).as_posix(): path for path in local.rglob("*") if path.is_file()}
        bundled_files = {name for name in entries if name.startswith(prefix)}
        if source_files.keys() != bundled_files:
            raise ValueError("Cached backend payload inventory differs for " + prefix)
        for name, path in source_files.items():
            if archive.extract(entries[name]) != path.read_bytes():
                raise ValueError("Cached backend payload differs: " + name)
            checked_data += 1

    # Compare the actual bundled Python code, without executing it. This also
    # covers modules absent from the small, human-readable provenance manifest.
    pyz = archive.open_embedded_archive("PYZ.pyz")
    source_modules = {}
    for path in (project / "bjlab").rglob("*.py"):
        relative = path.relative_to(project).with_suffix("").parts
        module = ".".join(relative[:-1] if relative[-1] == "__init__" else relative)
        source_modules[module] = path
    bundled_modules = {name for name in pyz.toc if name == "bjlab" or name.startswith("bjlab.")}
    if source_modules.keys() != bundled_modules:
        raise ValueError("Cached backend bjlab module inventory differs")
    for module, path in source_modules.items():
        bundled_code = pyz.extract(module)
        source_code = compile(path.read_bytes(), bundled_code.co_filename, "exec", dont_inherit=True, optimize=0)
        if source_code != bundled_code:
            raise ValueError("Cached backend Python code differs: " + module)
    launcher = marshal.loads(archive.extract(entries["desktop_launcher"]))
    if compile((project / "desktop_launcher.py").read_bytes(), launcher.co_filename, "exec",
               dont_inherit=True, optimize=0) != launcher:
        raise ValueError("Cached backend launcher code differs")
    return {"status": "pass", "recorded_source_hashes_checked": len(expected["source_sha256"]),
            "bundled_data_files_checked": checked_data, "bundled_python_modules_checked": len(source_modules),
            "launcher_code_checked": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--self-test", type=Path, required=True)
    parser.add_argument("--fonts", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.sidecar, args.project, args.expected, args.self_test, args.fonts)))
    except (ValueError, KeyError, OSError, TypeError) as error:
        print("Cached backend verification rejected: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
