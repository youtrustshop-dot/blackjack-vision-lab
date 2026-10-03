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
    args = parser.parse_args()
    manifest = json.loads((RELEASE / "manifest.json").read_text(encoding="utf-8-sig"))
    entries = {item["file"]: item for item in manifest["files"]}
    for name, item in entries.items():
        path = RELEASE / name
        if path.parent.resolve() != RELEASE.resolve():
            raise RuntimeError("Manifest path escapes release directory")
        if path.stat().st_size != item["bytes"] or digest(path) != item["sha256"]:
            raise RuntimeError("Release fingerprint mismatch: " + name)
    for name in PORTABLE_FILES:
        if name not in entries:
            raise RuntimeError("Missing portable component: " + name)
    licenses = sorted(path for path in (RELEASE / "licenses").rglob("*") if path.is_file())
    if not licenses:
        raise RuntimeError("Dependency notices are missing")
    paths = [RELEASE / name for name in PORTABLE_FILES] + licenses
    paths += sorted(RELEASE.glob("*.json"))
    paths += sorted(RELEASE.glob("*.png"))
    paths += sorted(path for path in (RELEASE / "prior-fresh-core-proof").rglob("*")
                    if path.is_file() and path.suffix.lower() in {".json", ".png"})
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            archive.write(path, "Blackjack Vision Lab/" + path.relative_to(RELEASE).as_posix())
        archive.writestr("Blackjack Vision Lab/LEGGIMI.txt",
            "Estrarre l'intera cartella e avviare Blackjack Vision Lab.exe.\n"
            "Conservare insieme backend, WebView2Loader.dll e licenses.\n"
            "Windows x64 e Microsoft WebView2 richiesti; Python e Node non necessari.\n"
            "Laya rinviato. Visione validata sulle carte del laboratorio.\n")
        for name in ("DESKTOP.md", "STATUS.md"):
            archive.write(ROOT / "docs" / name, "Blackjack Vision Lab/docs/" + name)
    with zipfile.ZipFile(output) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError("Archive CRC verification failed: " + corrupt)
    print(json.dumps({"output": str(output), "created_at": datetime.now(timezone.utc).isoformat(),
                      "files": len(paths)+3, "bytes": output.stat().st_size,
                      "sha256": digest(output), "release_binary_hashes_verified": True,
                      "crc_verified": True}))


if __name__ == "__main__":
    main()
