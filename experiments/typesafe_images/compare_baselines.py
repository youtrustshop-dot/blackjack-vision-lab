"""Compare Jev (Box + Noul) with the lab's current method and a trivial baseline on the same images.

Needs no network: Jev answers are read from a report written by run_experiment.py --variants.

  current   = bjlab.external_vision.ClassicCasinoDetector (largest green surface), the lab's automatic locator.
              It abstains when no compatible green table exists.
  constant  = leave-one-out mean of the other labelled boxes, a guess that never looks at the picture.
  jev       = Box answer from the report.

    python experiments/typesafe_images/compare_baselines.py --jev-report experiments/typesafe_images/jev-1.14.0-variants-report.json
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import run_experiment as exp  # noqa: E402


def current_method_box(detector, pil_image):
    """Table box [left, right, top, bottom] from the lab detector, or None when it abstains."""
    w, h = pil_image.size
    started = time.perf_counter()
    detector.detect(pil_image)
    elapsed = time.perf_counter() - started
    bounds = detector.context.get("table_bounds")
    if not bounds:
        return None, elapsed
    x, y, bw, bh = bounds
    return [x / w, (x + bw) / w, y / h, (y + bh) / h], elapsed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jev-report", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args(argv)

    from PIL import Image
    from bjlab.external_vision import ClassicCasinoDetector

    base_labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))["images"]
    jev_rows = {r["image"]: r for r in json.loads(args.jev_report.read_text(encoding="utf-8"))["rows"] if "answers" in r}
    detector = ClassicCasinoDetector()
    positives = {n: r["table_box"] for n, r in base_labels.items() if r["table_box"]}

    rows = []
    for name, row in base_labels.items():
        for variant in exp.VARIANTS:
            data, _fmt, _size, truth = exp.load_image_b64(exp.SHOTS / name, variant, row["table_box"])
            image = Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
            key = f"{name}::{variant}"
            cur, seconds = current_method_box(detector, image)
            others = [b for n, b in positives.items() if n != name]
            const = [statistics.fmean(b[i] for b in others) for i in range(4)]
            jev = jev_rows[key]["answers"]["table_box"]["box"]
            rows.append({
                "image": key, "has_table": row["blackjack_table"], "truth": truth,
                "current": cur, "current_seconds": round(seconds, 4),
                "constant": const,
                "jev": [jev["left"], jev["right"], jev["top"], jev["bottom"]],
                "jev_blackjack_table": jev_rows[key]["answers"]["blackjack_table"]["noul"],
            })

    def box_stats(method):
        cases = [r for r in rows if r["truth"]]
        ious = [exp.iou(r[method], r["truth"]) if r[method] else 0.0 for r in cases]
        answered = [exp.iou(r[method], r["truth"]) for r in cases if r[method]]
        return {
            "cases": len(cases),
            "answered": len(answered),
            "mean_iou_counting_abstentions_as_0": statistics.fmean(ious),
            "mean_iou_when_answered": statistics.fmean(answered) if answered else None,
            "iou_at_least_0.5": sum(i >= 0.5 for i in ious),
            "iou_at_least_0.7": sum(i >= 0.7 for i in ious),
        }

    def scene_stats(flag):
        tp = sum(flag(r) and r["has_table"] for r in rows)
        fp = sum(flag(r) and not r["has_table"] for r in rows)
        pos = sum(r["has_table"] for r in rows)
        return {"true_positive": tp, "positives": pos, "false_positive": fp, "negatives": len(rows) - pos}

    report = {
        "images": len(rows),
        "box_location": {m: box_stats(m) for m in ("jev", "current", "constant")},
        "table_present": {
            "jev_noul_at_0.5": scene_stats(lambda r: r["jev_blackjack_table"] >= 0.5),
            "current_detector_found_table": scene_stats(lambda r: r["current"] is not None),
        },
        "current_detector_seconds_median": statistics.median(r["current_seconds"] for r in rows),
        "notes": [
            "The current detector measures the green felt only; the hand boxes mark the whole video canvas, so its IoU is slightly penalised on green screens.",
            "Clef was not run: it needs a ~19 GB model and a CUDA GPU (docs/CLEF.md). Its recorded results use other cases.",
        ],
        "rows": rows,
    }
    if args.output:
        args.output.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
