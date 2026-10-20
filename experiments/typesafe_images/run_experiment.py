"""Optional TypeSafe image observer experiment (Noul + Box) on lab screenshots.

Isolated from the solver, the advisor and the cloud ledger. Nothing here chooses
an action, a bet or an EV. No request is made unless --allow-network is given and
TYPESAFE_API_KEY is already set; the key is never printed or written.

    python experiments/typesafe_images/run_experiment.py --dry-run
    python experiments/typesafe_images/run_experiment.py --allow-network \
        --output experiments/typesafe_images/jev-1.14.0-report.json
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHOTS = ROOT / "docs" / "screenshots"
URL = "https://api.typesafe.ai/v1/systemone"
MAX_SIDE = 1280
# Price taken from https://docs.typesafe.ai/models (read 2026-10-20): USD per million input tokens.
USD_PER_MTOK_INPUT = 0.042

QUESTIONS = {
    "blackjack_table": {
        "type": "noul",
        "instructions": "Is a blackjack table with dealt playing cards visible in the screenshot?",
    },
    "action_buttons": {
        "type": "noul",
        "instructions": "Are player action buttons such as HIT, STAND or DOUBLE visible in the screenshot?",
    },
    "poker_table": {
        "type": "noul",
        "instructions": "Is a Texas Hold'em table with community cards and hole cards visible in the screenshot?",
    },
    "table_box": {
        "type": "box",
        "instructions": "The rectangular video or simulator canvas that shows the card table with the dealt cards and the action buttons, not the whole page.",
    },
}
NOUL_KEYS = ("blackjack_table", "action_buttons", "poker_table")


def iou(a: list[float], b: list[float]) -> float:
    """Boxes as [left, right, top, bottom] fractions."""
    left, right = max(a[0], b[0]), min(a[1], b[1])
    top, bottom = max(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, right - left) * max(0.0, bottom - top)
    union = (a[1] - a[0]) * (a[3] - a[2]) + (b[1] - b[0]) * (b[3] - b[2]) - inter
    return inter / union if union > 0 else 0.0


def auc(pairs: list[tuple[float, int]]) -> float | None:
    pos = [s for s, y in pairs if y]
    neg = [s for s, y in pairs if not y]
    if not pos or not neg:
        return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def load_image_b64(path: Path) -> tuple[str, str, tuple[int, int]]:
    from PIL import Image

    im = Image.open(path).convert("RGB")
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii"), "jpg", im.size


def build_request(model: str, data_b64: str, fmt: str) -> dict:
    # The image reference appears once, in the state: each reference adds another copy of the image.
    return {
        "model": model,
        "state": "Screenshot of a blackjack analysis application: IMG",
        "assets": {"IMG": {"type": "image", "format": fmt, "data_base64": data_b64}},
        "questions": QUESTIONS,
    }


def post(body: dict, key: str, timeout: float) -> dict:
    req = urllib.request.Request(
        URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "TypeSafe-Danger-Zone-Images": "true",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def summarize(rows: list[dict], labels: dict) -> dict:
    out: dict = {"noul": {}}
    ok = [r for r in rows if "answers" in r]
    for q in NOUL_KEYS:
        pairs = [(r["answers"][q]["noul"], labels[r["image"]][q]) for r in ok]
        thresholds = {}
        for t in (0.3, 0.5, 0.7, 0.9):
            tp = sum(s >= t and y for s, y in pairs)
            fp = sum(s >= t and not y for s, y in pairs)
            fn = sum(s < t and y for s, y in pairs)
            thresholds[str(t)] = {"true_positive": tp, "false_positive": fp, "missed": fn}
        out["noul"][q] = {
            "positives": sum(y for _, y in pairs),
            "cases": len(pairs),
            "auc": auc(pairs),
            "thresholds": thresholds,
        }
    ious = []
    for r in ok:
        truth = labels[r["image"]]["table_box"]
        if truth is None:
            continue
        b = r["answers"]["table_box"]["box"]
        ious.append(iou([b["left"], b["right"], b["top"], b["bottom"]], truth))
    out["box"] = {
        "cases": len(ious),
        "mean_iou": statistics.fmean(ious) if ious else None,
        "iou_at_least_0.5": sum(i >= 0.5 for i in ious),
        "iou_at_least_0.7": sum(i >= 0.7 for i in ious),
        "per_image_iou": {r["image"]: None for r in ok if labels[r["image"]]["table_box"]},
    }
    for r, i in zip([r for r in ok if labels[r["image"]]["table_box"]], ious):
        out["box"]["per_image_iou"][r["image"]] = round(i, 3)
    lat = sorted(r["seconds"] for r in ok)
    out["latency_seconds"] = {
        "p50": statistics.median(lat) if lat else None,
        "p95": lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None,
    }
    tokens = sum(r["usage"]["input_tokens"] for r in ok)
    out["usage"] = {
        "input_tokens": tokens,
        "estimated_usd": round(tokens * USD_PER_MTOK_INPUT / 1e6, 6),
        "price_note": "USD per million input tokens from docs.typesafe.ai/models on 2026-10-20; output is listed as free; currency not named on the page.",
    }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--allow-network", action="store_true", help="required to send any image")
    ap.add_argument("--dry-run", action="store_true", help="validate labels and image sizes, no request")
    ap.add_argument("--model", default="jev-1.14.0", help="Box needs Jev 1.14")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args(argv)

    labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))["images"]
    prepared = {}
    for name in labels:
        data, fmt, size = load_image_b64(SHOTS / name)
        if min(size) < 280 or max(size) > 1568 or size[0] * size[1] > 2_458_624:
            print(f"{name}: size {size} outside the documented limits", file=sys.stderr)
            return 2
        prepared[name] = (data, fmt, size)
    print(f"{len(prepared)} images ready; no request made" if args.dry_run or not args.allow_network else "")
    if args.dry_run or not args.allow_network:
        if not args.allow_network and not args.dry_run:
            print("Network not allowed: pass --allow-network to run. Nothing was sent.")
        return 0

    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        print("TYPESAFE_API_KEY is absent; no request was made", file=sys.stderr)
        return 2

    rows = []
    for name, (data, fmt, size) in prepared.items():
        t0 = time.perf_counter()
        try:
            resp = post(build_request(args.model, data, fmt), key, args.timeout)
            rows.append({"image": name, "size": list(size), "seconds": round(time.perf_counter() - t0, 3), **resp})
        except urllib.error.HTTPError as exc:  # status only: bodies could echo request details
            rows.append({"image": name, "error": f"HTTP {exc.code}"})
        except Exception as exc:  # noqa: BLE001 - type only, never the message
            rows.append({"image": name, "error": type(exc).__name__})
        print(rows[-1].get("error", "ok"), name, flush=True)

    report = {
        "status": "complete" if all("answers" in r for r in rows) else "partial_failure",
        "model_requested": args.model,
        "models_returned": sorted({r["model"] for r in rows if "model" in r}),
        "labels": "experiments/typesafe_images/labels.json (hand labels; not an independent holdout)",
        "summary": summarize(rows, labels),
        "rows": rows,
    }
    if args.output:
        args.output.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report["summary"], indent=1))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
