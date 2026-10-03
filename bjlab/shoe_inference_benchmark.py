"""Seeded temporal-holdout evaluation of deck inference and discard-tray pixels.

The tray study uses original synthetic images, not unlicensed third-party media.
It validates the controlled image/measurement/calibration path and includes an
intentional unseen thickness shift; it does not validate physical casino trays.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import time
from typing import Any, Iterable, Mapping

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .events import RANKS, SUITS
from .vision import DeckCountEstimator, _rgb

DECKS = (1, 2, 4, 6, 8)
SOURCE_PIN = {"font_reference_only": {"repository": "https://github.com/dejavu-fonts/dejavu-fonts",
    "version": "2.37", "commit": "0eda8a319c08835009849583cd090bb5b141ce25",
    "license": "Bitstream Vera/Arev notices; DejaVu changes public domain",
    "license_url": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/version_2_37/LICENSE",
    "used_in_tray_images": False},
    "media_source": "original synthetic RGB rectangles, no fonts or external images",
    "fixture_license": "repository LICENSE applies; no third-party media redistributed"}


def render_discard_tray(cards: int, *, pixels_per_card: float = .9, intercept: float = 4,
                        camera_scale: float = 1, noise_std: float = 0, seed: int = 0,
                        theme: str = "navy") -> Image.Image:
    if type(cards) is not int or not 1 <= cards <= 450 or not .3 <= pixels_per_card <= 1.05:
        raise ValueError("Invalid physical tray rendering parameters")
    if not .8 <= camera_scale <= 1.2 or not 0 <= intercept <= 20 or noise_std < 0:
        raise ValueError("Invalid camera or augmentation settings")
    height, width = round((intercept + pixels_per_card * cards) * camera_scale), round(150 * camera_scale)
    if height > 480:
        raise ValueError("Rendered stack exceeds the controlled frame")
    background = (20, 40, 66) if theme == "navy" else (84, 30, 50)
    image = Image.new("RGB", (400, 520), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 20, 320, 500), outline=(109, 86, 55), width=4)
    left, bottom = (400 - width) // 2, 490
    draw.rectangle((left, bottom - height, left + width - 1, bottom - 1), fill=(246, 243, 232))
    for y in range(bottom - height + 3, bottom - 1, 4):
        draw.line((left + 2, y, left + width - 3, y), fill=(205, 204, 192), width=1)
    if noise_std:
        arr = np.asarray(image).astype(np.float32)
        arr += np.random.default_rng(seed).normal(0, noise_std, arr.shape)
        image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return image


def measure_discard_tray(image: Image.Image | np.ndarray | str | Path) -> dict[str, Any]:
    """Measure the controlled bright stack from pixels; accepts no card-count label."""
    cv2.setNumThreads(1)
    rgb = _rgb(image)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, np.array([0, 0, 170], np.uint8), np.array([179, 80, 255], np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w >= 50 and h >= 4 and cv2.contourArea(contour) / (w * h) >= .7:
            candidates.append((w * h, x, y, w, h))
    if not candidates:
        return {"status": "unavailable", "reason": "No supported bright tray stack found", "height": None}
    _, x, y, w, h = max(candidates)
    return {"status": "measured", "bbox": [x, y, w, h], "height": h, "width": w,
            "normalized_height": h * 150 / w,
            "normalization": "visible stack width relative to 150px controlled reference",
            "probability": None}


def _split(index: int, sessions: int) -> str:
    return "train" if index < int(sessions * .6) else "calibration" if index < int(sessions * .8) else "test"


def generate_inference_dataset(path: str | Path, *, sessions: int = 50, seed: int = 29,
                               missing_suit_rate: float = .2) -> dict[str, Any]:
    if sessions < 10 or not 0 <= missing_suit_rate <= 1:
        raise ValueError("Need at least ten sessions and a valid suit missing rate")
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    shoes, trays = [], []
    for session in range(sessions):
        sid, split = f"shoe-session-{session:04d}", _split(session, sessions)
        decks = DECKS[session % len(DECKS)]
        physical_shoe = [(rank, suit) for _ in range(decks) for rank in RANKS for suit in SUITS]
        rng.shuffle(physical_shoe)
        observations = [{"card_id": f"observed-{i:04d}", "rank": rank,
                         "suit": None if rng.random() < missing_suit_rate else suit,
                         "draw_index": i} for i, (rank, suit) in enumerate(physical_shoe[:80])]
        shoes.append({"session_id": sid, "session_index": session, "split": split,
                      "true_decks": decks, "observations": observations,
                      "checkpoints": sorted({min(len(observations), n) for n in (8, 16, 32, 52, 80)})})
        camera_scale = .94 + .03 * (session % 5)
        theme = "navy" if session < int(sessions * .8) else "burgundy"
        for cards in sorted({min(52 * decks, n) for n in (12, 24, 52, 78, 104, 156, 208, 312)}):
            scenarios = ("baseline", "thickness_shift_15pct") if split == "test" else ("baseline",)
            for scenario in scenarios:
                ppc = .9 if scenario == "baseline" else .9 * 1.15
                image = render_discard_tray(cards, pixels_per_card=ppc, camera_scale=camera_scale,
                                            noise_std=1 if split != "test" else 2,
                                            seed=seed + len(trays), theme=theme)
                relative = f"{split}/{sid}-{cards:03d}-{scenario}.png"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                image.save(target, compress_level=1)
                trays.append({"image": relative, "image_sha256": sha256(target.read_bytes()).hexdigest(),
                              "session_id": sid, "session_index": session, "split": split,
                              "scenario": scenario, "true_cards": cards,
                              "truth_render_parameters": {"pixels_per_card": ppc,
                                                           "camera_scale": camera_scale, "theme": theme}})
    manifest = {"schema_version": 1, "seed": seed, "sessions": sessions,
                "deck_candidates": list(DECKS), "missing_suit_rate": missing_suit_rate,
                "split_policy": "chronological sessions 60% train / 20% calibration / 20% future test",
                "shoes": shoes, "trays": trays, "provenance": SOURCE_PIN,
                "generator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
                "estimator_sha256": sha256(Path(__file__).with_name("vision.py").read_bytes()).hexdigest(),
                "scope": "synthetic uniform shoes and controlled tray pixels; no external media"}
    validate_temporal_holdout(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    return manifest


def validate_temporal_holdout(manifest: Mapping[str, Any]) -> None:
    sessions, order = {}, defaultdict(set)
    for row in [*manifest.get("shoes", []), *manifest.get("trays", [])]:
        split, sid, index = row["split"], row["session_id"], row["session_index"]
        if split not in {"train", "calibration", "test"} or type(index) is not int:
            raise ValueError("Invalid temporal split or session index")
        if sid in sessions and sessions[sid] != split:
            raise ValueError("Session leakage in shoe inference study")
        sessions[sid] = split
        order[split].add(index)
    if not all(order[split] for split in ("train", "calibration", "test")):
        raise ValueError("Each temporal split needs independent sessions")
    if max(order["train"]) >= min(order["calibration"]) or max(order["calibration"]) >= min(order["test"]):
        raise ValueError("Holdout sessions must be chronologically later than calibration and train")


class DiscardTrayCalibrator:
    """Linear height calibration plus held-out residual interval, fitted separately."""
    def __init__(self) -> None:
        self.slope: float | None = None
        self.intercept: float | None = None
        self.radius: float | None = None
        self.train_samples = self.calibration_samples = 0

    def fit(self, samples: Iterable[tuple[float, int]]) -> "DiscardTrayCalibrator":
        data = list(samples)
        if len(data) < 3 or len({cards for _, cards in data}) < 2:
            raise ValueError("Tray calibration needs several known heights and card counts")
        if any(not math.isfinite(height) or height <= 0 or cards <= 0 for height, cards in data):
            raise ValueError("Invalid training measurement")
        heights = np.asarray([height for height, _ in data], dtype=np.float64)
        counts = np.asarray([cards for _, cards in data], dtype=np.float64)
        slope, intercept = np.linalg.lstsq(np.column_stack((counts, np.ones(len(data)))), heights, rcond=None)[0]
        if slope <= 0 or not math.isfinite(slope):
            raise ValueError("Height/card calibration must have a positive slope")
        self.slope, self.intercept = float(slope), float(intercept)
        self.radius = None
        self.train_samples = len(data)
        return self

    def point_estimate(self, height: float) -> float:
        if self.slope is None or self.intercept is None:
            raise ValueError("Fit tray height calibration first")
        if not math.isfinite(height) or height <= 0:
            raise ValueError("Tray height must be finite and positive")
        return max(0, (height - self.intercept) / self.slope)

    def calibrate_interval(self, samples: Iterable[tuple[float, int]], *, coverage: float = .95) -> None:
        if not 0 < coverage < 1:
            raise ValueError("Interval coverage must be between zero and one")
        residuals = sorted(abs(self.point_estimate(height) - cards) for height, cards in samples)
        if not residuals:
            raise ValueError("Independent calibration residuals are required")
        index = min(len(residuals) - 1, math.ceil((len(residuals) + 1) * coverage) - 1)
        self.radius, self.calibration_samples = residuals[index], len(residuals)

    def estimate(self, height: float) -> dict[str, Any]:
        cards = self.point_estimate(height)
        interval = None if self.radius is None else [max(0, cards - self.radius), cards + self.radius]
        return {"estimated_cards": cards, "cards_interval": interval, "estimated_decks": cards / 52,
                "probability": None, "status": "experimental_controlled_renderer",
                "interval_semantics": "residual quantile from held-out calibration sessions; empirical coverage; no domain-shift guarantee"}

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "slope_pixels_per_card": self.slope, "intercept_pixels": self.intercept,
                "interval_radius_cards": self.radius, "train_samples": self.train_samples,
                "calibration_samples": self.calibration_samples}


def _deck_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"samples": 0, "accuracy": None, "brier_score": None, "ece": None}
    brier = sum(sum((row["posterior"][str(d)] - float(d == row["true_decks"])) ** 2 for d in DECKS)
                for row in rows) / len(rows)
    bins = defaultdict(list)
    for row in rows:
        bins[min(9, int(row["confidence"] * 10))].append(row)
    ece = sum(len(group) / len(rows) * abs(sum(row["confidence"] for row in group) / len(group) -
                                        sum(row["correct"] for row in group) / len(group)) for group in bins.values())
    return {"samples": len(rows), "accuracy": sum(row["correct"] for row in rows) / len(rows),
            "brier_score": brier, "ece": ece, "mean_posterior_max": sum(row["confidence"] for row in rows) / len(rows),
            "mean_entropy_bits": sum(row["entropy_bits"] for row in rows) / len(rows),
            "scope": "synthetic shuffled-shoe assumptions, finite deck candidate set"}


def run_inference_benchmark(path: str | Path, *, output: str | Path | None = None) -> dict[str, Any]:
    root = Path(path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    validate_temporal_holdout(manifest)
    deck_rows = []
    for shoe in manifest["shoes"]:
        if shoe["split"] != "test":
            continue
        estimator = DeckCountEstimator()
        for n, observed in enumerate(shoe["observations"], 1):
            estimator.observe(observed["card_id"], observed["rank"], observed["suit"])
            if n in shoe["checkpoints"]:
                prediction = estimator.estimate()
                deck_rows.append({"session_id": shoe["session_id"], "observed_cards": n,
                                  "true_decks": shoe["true_decks"], "prediction": prediction["most_likely"],
                                  "posterior": prediction["probabilities"], "confidence": prediction["posterior_max"],
                                  "entropy_bits": prediction["entropy_bits"],
                                  "correct": prediction["most_likely"] == shoe["true_decks"]})
    measured, failures = [], []
    for tray in manifest["trays"]:
        source = root / tray["image"]
        if sha256(source.read_bytes()).hexdigest() != tray["image_sha256"]:
            raise ValueError("Tray image hash does not match pinned manifest")
        start = time.perf_counter()
        measurement = measure_discard_tray(source)
        latency = (time.perf_counter() - start) * 1000
        if measurement["status"] != "measured":
            failures.append({"image": tray["image"], "reason": measurement["reason"]})
            continue
        measured.append({**tray, "measurement": measurement, "latency_ms": latency})
    calibrator = DiscardTrayCalibrator().fit((row["measurement"]["normalized_height"], row["true_cards"])
                                           for row in measured if row["split"] == "train")
    calibrator.calibrate_interval((row["measurement"]["normalized_height"], row["true_cards"])
                                 for row in measured if row["split"] == "calibration")
    tray_rows = []
    for row in measured:
        if row["split"] == "test":
            estimate = calibrator.estimate(row["measurement"]["normalized_height"])
            lower, upper = estimate["cards_interval"]
            tray_rows.append({"image": row["image"], "session_id": row["session_id"], "scenario": row["scenario"],
                              "true_cards": row["true_cards"], **estimate,
                              "absolute_error_cards": abs(estimate["estimated_cards"] - row["true_cards"]),
                              "covered": lower <= row["true_cards"] <= upper,
                              "measurement": row["measurement"], "latency_ms": row["latency_ms"]})
    def tray_summary(scenario: str) -> dict[str, Any]:
        rows = [row for row in tray_rows if row["scenario"] == scenario]
        return {"samples": len(rows), "mae_cards": float(np.mean([row["absolute_error_cards"] for row in rows])) if rows else None,
                "p95_error_cards": float(np.percentile([row["absolute_error_cards"] for row in rows], 95)) if rows else None,
                "interval_coverage": sum(row["covered"] for row in rows) / len(rows) if rows else None,
                "latency_ms_p95": float(np.percentile([row["latency_ms"] for row in rows], 95)) if rows else None}
    report = {"schema_version": 1, "status": "completed" if not failures else "partial_failure",
              "dataset_manifest_sha256": sha256((root / "manifest.json").read_bytes()).hexdigest(),
              "benchmark_runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "seed": manifest["seed"], "temporal_holdout": True, "deck_summary": _deck_metrics(deck_rows),
              "deck_by_checkpoint": {str(n): _deck_metrics([row for row in deck_rows if row["observed_cards"] == n])
                                     for n in sorted({row["observed_cards"] for row in deck_rows})},
              "deck_rows": deck_rows, "tray_calibration": calibrator.to_dict(),
              "tray_summary": tray_summary("baseline"), "tray_distribution_shift": tray_summary("thickness_shift_15pct"),
              "tray_rows": tray_rows, "measurement_failures": failures, "provenance": manifest["provenance"],
              "scope": "controlled synthetic validation only; real discard trays remain unvalidated",
              "probabilities_claim": "deck posteriors evaluated empirically here; tray intervals are not probabilities"}
    destination = Path(output) if output is not None else root / "benchmark-report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "run"))
    parser.add_argument("dataset")
    parser.add_argument("--sessions", type=int, default=50)
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    if args.command == "generate":
        manifest = generate_inference_dataset(args.dataset, sessions=args.sessions, seed=args.seed)
        print(json.dumps({"status": "generated", "shoes": len(manifest["shoes"]), "tray_images": len(manifest["trays"])}))
        return 0
    report = run_inference_benchmark(args.dataset, output=args.output)
    print(json.dumps({key: report[key] for key in ("status", "deck_summary", "tray_summary", "tray_distribution_shift")}))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
