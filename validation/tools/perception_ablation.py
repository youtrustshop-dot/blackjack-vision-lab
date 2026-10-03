"""Measure held-out RC/TC, temporal eligibility and native/pixel cost, retaining raw evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import bjlab.datasets as datasets
from bjlab.datasets import benchmark_counting_ablation
from bjlab.vision import TemplateCardDetector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("validation/results/perception-ablation"))
    parser.add_argument("--regret-samples", type=int, default=4)
    parser.add_argument("--solver-ms", type=float, default=250)
    parser.add_argument("--solver-nodes", type=int, default=15000)
    options = parser.parse_args()
    start = time.perf_counter()
    print("Starting actual held-out pixel/count temporal ablation", flush=True)
    result = benchmark_counting_ablation(options.dataset, TemplateCardDetector(), regret_samples=options.regret_samples,
                                        solver_timeout_ms=options.solver_ms, solver_max_nodes=options.solver_nodes)
    metadata = {"created_at": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                "platform": platform.platform(), "processor": platform.processor(),
                "opencv_threads": 1, "wall_seconds": time.perf_counter() - start,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "metric_source_sha256": hashlib.sha256(Path(datasets.__file__).read_bytes()).hexdigest()}
    result["runtime"] = metadata
    options.output.mkdir(parents=True, exist_ok=True)
    (options.output / "raw-results.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    summary = {key: value for key, value in result.items() if key not in {"raw_frames", "raw_groups", "regret_samples"}}
    (options.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    (options.output / "regret-samples.json").write_text(json.dumps(result["regret_samples"], indent=2, allow_nan=False), encoding="utf-8")
    manifest = json.loads((options.dataset / "manifest.json").read_text(encoding="utf-8"))
    digests = [{"image": record["image"], "sha256": hashlib.sha256((options.dataset / record["image"]).read_bytes()).hexdigest()}
               for record in manifest["records"] if record["split"] == "test"]
    (options.output / "pixel-source-digests.json").write_text(json.dumps(digests, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
