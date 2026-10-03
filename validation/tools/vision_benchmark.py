"""Reproducible detection, calibration and session tracking on separate splits."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bjlab.datasets import benchmark_dataset, benchmark_tracking_dataset
from bjlab.vision import ScoreCalibrator, TemplateCardDetector


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("validation/results/vision"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.dataset / "manifest.json"
    metadata = {
        "dataset_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "python": sys.version, "platform": platform.platform(),
        "processor": platform.processor(), "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "controlled lab renderer; one CPU process; OpenCV threads=1",
    }
    start = time.perf_counter()
    detector = TemplateCardDetector()
    validation = benchmark_dataset(args.dataset, detector, split="calibration")
    print("Calibration split evaluated:", validation["frames"], "frames", flush=True)
    test = benchmark_dataset(args.dataset, detector, split="test")
    print("Test detection evaluated:", test["frames"], "frames", flush=True)
    calibrator = ScoreCalibrator().fit(
        (item["score"], item["correct"]) for item in validation["raw_score_labels"]
        if item["score"] is not None
    )
    calibration = calibrator.to_dict() | {
        "evaluation": calibrator.evaluate(
            (item["score"], item["correct"]) for item in test["raw_score_labels"]
            if item["score"] is not None
        ),
        "fit_split": "calibration", "evaluation_split": "test",
        "dataset_manifest_sha256": metadata["dataset_manifest_sha256"],
    }
    tracking = benchmark_tracking_dataset(args.dataset, detector, split="test")
    print("Test tracking evaluated:", len(tracking.get("groups", [])), "session/theme groups", flush=True)
    for filename, value in [
        ("detection-validation.json", validation), ("detection-test.json", test),
        ("calibration.json", calibration), ("tracking-test.json", tracking),
    ]:
        (args.output / filename).write_text(
            json.dumps(value, indent=2, allow_nan=False), encoding="utf-8"
        )
    metadata["wall_seconds"] = time.perf_counter() - start
    metadata["detection_test"] = {k: v for k, v in test.items() if k != "raw_score_labels"}
    metadata["tracking_test"] = {k: v for k, v in tracking.items() if k not in ("session_reports", "groups")}
    metadata["calibration"] = calibration
    (args.output / "summary.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
