"""Verify released binaries and archive the portable Windows application."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
PORTABLE_FILES = ("Blackjack Vision Lab.exe", "bjlab-backend.exe", "WebView2Loader.dll")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT.parent / "blackjack-vision-lab-windows.zip")
    parser.add_argument("--release", type=Path, default=RELEASE)
    args = parser.parse_args()
    release = args.release.resolve()
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8-sig"))
    entries = {item["file"]: item for item in manifest["files"]}
    for name, item in entries.items():
        path = release / name
        if path.parent.resolve() != release:
            raise RuntimeError("Manifest path escapes release directory")
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise RuntimeError("Release fingerprint mismatch: " + name)
    for name in PORTABLE_FILES:
        if name not in entries:
            raise RuntimeError("Missing portable component: " + name)
    licenses = sorted(path for path in (release / "licenses").rglob("*") if path.is_file())
    if not licenses:
        raise RuntimeError("Dependency notices are missing")
    paths = [release / name for name in PORTABLE_FILES] + licenses
    paths += sorted(release.glob("*.json"))
    paths += sorted(release.glob("*.png"))
    paths += sorted(path for path in (release / "prior-fresh-core-proof").rglob("*")
                    if path.is_file() and path.suffix.lower() in {".json", ".png"})
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            archive.write(path, "Blackjack Vision Lab/" + path.relative_to(release).as_posix())
        archive.writestr("Blackjack Vision Lab/README.txt",
            "Extract the entire folder and run Blackjack Vision Lab.exe.\n"
            "Keep the backend, WebView2Loader.dll and licenses together.\n"
            "Windows x64 and Microsoft WebView2 are required; Python and Node are not.\n"
            "English is the default; select Italiano for the secondary language.\n"
            "For live screen sharing, open the local app in Chrome or Edge and keep the desktop app running.\n"
            "Card recognition is validated on the lab artwork. See docs/LIVE_VISION.md.\n")
        for name in ("DESKTOP.md", "STATUS.md", "LIVE_VISION.md", "QUICK_START.md", "CLEF.md"):
            archive.write(ROOT / "docs" / name, "Blackjack Vision Lab/docs/" + name)
        optional = [ROOT / "scripts" / name for name in ("install-clef.ps1", "run-clef.ps1", "clef-runtime.py", "clef_vocabulary.py", "clef-requirements.txt")]
        optional += sorted(path for path in (ROOT / "extensions" / "chromium").iterdir() if path.is_file())
        for path in optional:
            archive.write(path, "Blackjack Vision Lab/" + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError("Archive CRC verification failed: " + corrupt)
    print(json.dumps({"output": str(output), "created_at": datetime.now(timezone.utc).isoformat(),
                      "files": len(paths)+6+len(optional), "bytes": output.stat().st_size,
                      "sha256": digest(output), "release_binary_hashes_verified": True,
                      "crc_verified": True}))


if __name__ == "__main__":
    main()
