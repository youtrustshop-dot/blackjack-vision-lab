"""Acquire a small pinned MIT dataset subset without executing external code.

The explicit destination should be a scratch/work directory, not the app bundle.
Every image is verified against the pinned Git blob; labels remain in a manifest.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

TRAY_SPLITS = {
    "train": [0, 1, 16, 32, 48, 52, 64, 80, 96, 112, 128, 144, 156, 160, 176, 192, 208],
    "calibration": list(range(216, 273, 8)),
    "test": list(range(280, 313, 4)),
    "overflow": [320, 328, 336, 344, 352, 360, 364],
}
SOURCES = {
    "tray": {"repo": "mhluska/blackjack-discard-tray-photos", "commit": "3d7ab1bfd0b7ea0235bea085488427fcf7520e69", "license_sha256": "921cdace26700df89b2827aff8646493c0c8226c434fc34fd1cb5a0eca3a4942"},
    "martin": {"repo": "martinabeleda/blackjack-tracker", "commit": "5145a1260a7a7750f8a5fd56d60702ea8e66c30d", "license_sha256": "7503422c6c2e8d350ffe4f86c2ecfda69421abe82b6a292fa447b534847fccd6"},
}


def read_url(url):
    with urlopen(Request(url, headers={"User-Agent": "blackjack-vision-lab-research"}), timeout=45) as response:
        return response.read()


def acquire(dataset, destination):
    spec = SOURCES[dataset]
    repo, commit = spec["repo"], spec["commit"]
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    license_data = read_url(f"https://raw.githubusercontent.com/{repo}/{commit}/LICENSE")
    if hashlib.sha256(license_data).hexdigest() != spec["license_sha256"]:
        raise ValueError("pinned MIT license checksum mismatch")
    (root / "LICENSE").write_bytes(license_data)
    tree = json.loads(read_url(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"))
    if tree.get("sha") != commit or tree.get("truncated"):
        raise ValueError("incomplete or unpinned Git tree")
    blobs = {row["path"]: row["sha"] for row in tree["tree"] if row["type"] == "blob"}
    if dataset == "tray":
        requested = [(f"src/{count + 1:03}.png", split, count) for split, counts in TRAY_SPLITS.items() for count in counts]
        requested += [("README.md", None, None)]
    else:
        names = ["cards.py", "README.md", "rank_images/README.md", "benchmark_images/benchmark_readme.txt"]
        names += [f"rank_images/{rank}.png" for rank in ("Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King")]
        names += [f"benchmark_images/{suit}{number}.png" for suit in ("club", "diamond", "heart", "spade") for number in (1, 3)]
        requested = [(name, None, None) for name in names]

    def get_one(record):
        name, split, count = record
        target = root / name
        data = target.read_bytes() if target.exists() else read_url(f"https://raw.githubusercontent.com/{repo}/{commit}/{name}")
        blob_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if blob_sha != blobs[name]:
            raise ValueError(f"pinned source Git blob mismatch: {name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        row = {"path": name, "bytes": len(data), "git_blob": blob_sha, "sha256": hashlib.sha256(data).hexdigest()}
        if split is not None:
            row.update(split=split, count=count, relative_path=name)
            row.pop("path")
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = [future.result() for future in as_completed([pool.submit(get_one, record) for record in requested])]
    manifest = {"source": f"https://github.com/{repo}", "commit": commit, "license": "MIT", "license_sha256": spec["license_sha256"]}
    if dataset == "tray":
        rows = sorted((row for row in rows if "count" in row), key=lambda row: row["count"])
        manifest.update(single_sequence=True, label_rule="card count = filename integer minus one, per source README sequential one photo per card", rows=rows)
        name = "subset-manifest.json"
    else:
        manifest["rows"] = sorted(rows, key=lambda row: row["path"])
        name = "asset-manifest.json"
    (root / name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"status": "completed", "dataset": dataset, "files": len(rows), "manifest": str(root / name), "total_bytes": sum(row["bytes"] for row in rows)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=SOURCES)
    parser.add_argument("--dest", type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(acquire(options.dataset, options.dest), indent=2))
