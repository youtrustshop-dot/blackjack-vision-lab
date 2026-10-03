"""Isolated licensed fixture comparison; external source stays outside production.

Run from product root: python experiments/external_comparison/run_martin.py
--source-dir ../../work/external-martin-5145a126 --output-dir experiments/external_comparison
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bjlab.calibration import normalize_table
from bjlab.datasets import detection_metrics
from bjlab.vision import TemplateCardDetector

cv2.setNumThreads(1)
PIN = "5145a1260a7a7750f8a5fd56d60702ea8e66c30d"
NAME_TO_RANK = dict(zip(["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King"], ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]))
TABLE_CORNERS = [(232, 210), (1028, 199), (1192, 776), (65, 764)]
TRUTH = [
    ("A", (354, 260, 97, 87)), ("2", (478, 251, 92, 85)),
    ("3", (600, 244, 84, 86)), ("4", (712, 244, 90, 86)),
    ("5", (830, 250, 94, 89)), ("6", (312, 380, 115, 104)),
    ("7", (462, 380, 102, 103)), ("8", (600, 377, 92, 103)),
    ("9", (726, 372, 97, 104)), ("10", (854, 372, 90, 104)),
    ("J", (407, 530, 122, 128)), ("Q", (556, 525, 111, 129)),
    ("K", (714, 530, 105, 128)),
]


class OpenCV3Facade:
    """Only adapt the removed three-output findContours signature."""
    def __getattr__(self, name):
        return getattr(cv2, name)

    def findContours(self, image, *args, **kwargs):
        contours, hierarchy = cv2.findContours(image, *args, **kwargs)
        return image, contours, hierarchy


def load_reviewed_martin(path: Path):
    # Source reviewed: no network/process side effects in retained functions.
    # Exclude imports, GUI entrypoints and display helpers; do not install/run
    # the old bundled virtualenv or any repository build command.
    syntax = ast.parse(path.read_text(encoding="utf-8"))
    allowed_functions = {"detect", "findCards", "loadRanks", "flattener"}
    body = [node for node in syntax.body if isinstance(node, (ast.Assign, ast.ClassDef)) or isinstance(node, ast.FunctionDef) and node.name in allowed_functions]
    module = ast.Module(body=body, type_ignores=[])
    globals_dict = {"cv2": OpenCV3Facade(), "os": os, "copy": copy, "np": np, "imutils": SimpleNamespace(rotate_bound=lambda image, angle: cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE) if angle == 90 else (_ for _ in ()).throw(ValueError("unsupported rotation")))}
    exec(compile(module, str(path), "exec"), globals_dict)
    return globals_dict["detect"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def benchmark(source_dir: Path, output_dir: Path):
    manifest = json.loads((source_dir / "asset-manifest.json").read_text(encoding="utf-8"))
    if manifest["commit"] != PIN or manifest["license"] != "MIT":
        raise ValueError("source pin/license mismatch")
    for row in manifest["rows"]:
        if digest(source_dir / row["path"]) != row["sha256"]:
            raise ValueError("external asset checksum mismatch")
    output_dir.mkdir(parents=True, exist_ok=True)
    photo_path = source_dir / "benchmark_images/club1.png"
    calibration = normalize_table(photo_path, TABLE_CORNERS, outputsize=(960, 600))
    labels = [{"rank": rank, "suit": "C", "bbox": bbox, "face_down": False} for rank, bbox in TRUTH]
    annotation = {"source_commit": PIN, "source_photo_sha256": digest(photo_path), "label_source": "README portrait order plus manual axis-aligned boxes before running predictions", "iou_threshold": .5, "table_corners": TABLE_CORNERS, "canonical_size": [960, 600], "labels": labels, "excluded_duplicates": "source README states image1/2 and image3/4 are duplicates; only club1 evaluated", "limitations": "single fixture, manual coarse boxes; source templates may share cards/photographic conditions with fixture; not an independent held-out benchmark"}
    (output_dir / "martin-annotation.json").write_text(json.dumps(annotation, indent=2), encoding="utf-8")
    (output_dir / "MARTIN_LICENSE.txt").write_bytes((source_dir / "LICENSE").read_bytes())
    (output_dir / "martin-source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    Image.fromarray(calibration.image_rgb).save(output_dir / "martin-canonical-fixture.png")
    models = []
    baseline = TemplateCardDetector()
    started = time.perf_counter()
    detections = baseline.detect(calibration.image_rgb)
    baseline_ms = 1000 * (time.perf_counter() - started)
    predicted = [calibration.map_detection_to_source(d).to_dict() for d in detections]
    baseline_metrics = detection_metrics(predicted, labels)
    baseline_metrics["rank_correct_all_ground_truth_fraction"] = baseline_metrics["rank_correct"] / len(labels)
    models.append({"name": "bjlab_controlled_template_baseline", "status": "completed", "latency_ms": baseline_ms, "metrics": baseline_metrics, "predictions": predicted, "probability_calibration": "not applied outside controlled renderer domain"})
    detector = load_reviewed_martin(source_dir / "cards.py")
    started = time.perf_counter()
    cards = detector(cv2.cvtColor(calibration.image_rgb, cv2.COLOR_RGB2BGR), str(source_dir / "rank_images"), [])
    martin_ms = 1000 * (time.perf_counter() - started)
    predictions = []
    for card in cards:
        raw_bbox = cv2.boundingRect(card.contour)
        predictions.append({"rank": NAME_TO_RANK.get(card.best_rank_match), "suit": None, "bbox": calibration.map_bbox_to_source(raw_bbox), "face_down": False, "score": card.rank_score, "score_type": "unnormalized_template_pixel_difference", "probability_correct": None})
    # The original algorithm has rank templates only; suit is unsupported.
    rank_labels = [{**label, "suit": None} for label in labels]
    metrics = detection_metrics(predictions, rank_labels)
    metrics["rank_correct_all_ground_truth_fraction"] = metrics["rank_correct"] / len(labels)
    models.append({"name": "martin_original_opencv_rank_template", "status": "completed", "latency_ms": martin_ms, "metrics": metrics, "predictions": predictions, "suit_support": False, "compatibility_changes": ["OpenCV4 findContours return tuple adapted to OpenCV3 signature", "imutils.rotate_bound(image,90) replaced with lossless cv2 clockwise 90 degree rotate", "no GUI/test entrypoints or external package execution"], "algorithm_parameters_changed": False})
    report = {"schema_version": 1, "status": "completed", "cases": 1, "ground_truth_cards": len(labels), "source_commit": PIN, "source_sha256": digest(photo_path), "runner_sha256": digest(Path(__file__)), "annotation_sha256": digest(output_dir / "martin-annotation.json"), "models": models, "limitations": annotation["limitations"]}
    (output_dir / "martin-comparison-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    preview = Image.open(photo_path).convert("RGB")
    draw = ImageDraw.Draw(preview)
    for label in labels:
        x, y, w, h = label["bbox"]
        draw.rectangle((x, y, x + w, y + h), outline=(0, 255, 0), width=2)
        draw.text((x, y - 12), label["rank"], fill=(0, 255, 0))
    preview.save(output_dir / "martin-manual-annotations.png")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    result = benchmark(options.source_dir, options.output_dir)
    print(json.dumps({"status": result["status"], "models": [{"name": m["name"], "metrics": m["metrics"], "latency_ms": m["latency_ms"]} for m in result["models"]]}, indent=2))
