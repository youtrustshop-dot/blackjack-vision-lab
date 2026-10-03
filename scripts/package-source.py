"""Archive source, UI and reports; omit runtimes and primary raw card frames."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
                  ".hypothesis", "target", ".mypy_cache"}


def include(path):
    rel = path.relative_to(ROOT)
    if not path.resolve().is_relative_to(ROOT.resolve()):
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if any(part.endswith(".egg-info") for part in rel.parts):
        return False
    if path.suffix.lower() in {".pyc", ".pyo", ".zip", ".exe", ".dll", ".log", ".pdb", ".rlib", ".a"}:
        return False
    if rel.parts[0] == "datasets" and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp4"}:
        return False
    return rel.as_posix() != "docs/SOURCE_PACKAGE_MANIFEST.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT.parent / "blackjack-vision-lab-source.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    paths = sorted(path for path in ROOT.rglob("*") if path.is_file() and include(path))
    manifest = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "source, tests, docs, built UI, measured reports; not a completion certificate",
        "raw_dataset_policy": "Primary raw card frames under datasets/ remain in the project or can be regenerated with the documented seed. Their manifests and benchmarks are included. Tray experiment images and report previews are included. External source photos kept in workspace work/ are represented by acquisition hashes and source links.",
        "files": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in paths
        ],
    }
    manifest_path = ROOT / "docs" / "SOURCE_PACKAGE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths + [manifest_path]:
            archive.write(path, "blackjack-vision-lab/" + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError("Archive verification failed: " + corrupt)
    print(json.dumps({"output": str(output), "files": len(paths)+1,
                      "bytes": output.stat().st_size, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
