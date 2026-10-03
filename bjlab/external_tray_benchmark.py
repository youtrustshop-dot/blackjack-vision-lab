"""Research-only fixed-camera discard-tray benchmark on separately licensed photos.

The predictor takes pixels and a frozen calibration. Filename-derived counts are
available only in fit/evaluation. Nothing here supplies exact shoe state or EV.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class TrayGeometry:
    # Chosen after inspecting only empty, 52-card, and 156-card training photos.
    front_strip: tuple[float, float] = (0.505, 0.525)
    vertical_roi: tuple[float, float] = (0.34, 0.755)
    base_min_y: float = 0.65
    blue_minus_red: float = 10.0
    row_support: float = 0.25
    black_level: float = 50.0
    resize_width: int = 960

    def __post_init__(self):
        if not (0 <= self.front_strip[0] < self.front_strip[1] <= 1):
            raise ValueError("invalid horizontal ROI")
        if not (0 <= self.vertical_roi[0] < self.vertical_roi[1] <= 1):
            raise ValueError("invalid vertical ROI")
        if not (self.vertical_roi[0] <= self.base_min_y < self.vertical_roi[1]):
            raise ValueError("base anchor must lie inside ROI")
        if not (0 < self.row_support <= 1) or self.resize_width < 100:
            raise ValueError("invalid measurement parameters")


def measure_photo(image: Image.Image, geometry: TrayGeometry = TrayGeometry()) -> dict:
    """Read stack front height from actual RGB pixels, without count/filename."""
    width = geometry.resize_width
    rgb = np.asarray(image.convert("RGB").resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS), dtype=np.float32)
    height = rgb.shape[0]
    left, right = (round(v * width) for v in geometry.front_strip)
    upper, lower = (round(v * height) for v in geometry.vertical_roi)
    strip = rgb[upper:lower, left:right]
    # These source photos use blue-backed cards. This is explicitly camera/card
    # specific, not a generic card-color detector or confidence probability.
    blue = (strip[..., 2] - strip[..., 0] > geometry.blue_minus_red) & (strip[..., 2] >= strip[..., 1]) & (strip.mean(axis=2) < 180)
    blue_rows = np.flatnonzero(blue.mean(axis=1) >= geometry.row_support)
    black_rows = np.flatnonzero((strip.mean(axis=2) < geometry.black_level).mean(axis=1) >= 0.6)
    black_rows = black_rows[black_rows + upper >= round(geometry.base_min_y * height)]
    if not len(black_rows):
        return {"status": "unmeasurable", "reason": "base_anchor_missing", "height_fraction": None}
    base = int(black_rows[-1] + upper)
    if not len(blue_rows):
        return {"status": "empty_or_unsupported_back", "height_fraction": 0.0, "base_y_fraction": base / height, "front_y_fraction": None}
    front = int(blue_rows[-1] + upper)
    if front >= base:
        return {"status": "unmeasurable", "reason": "front_not_above_base", "height_fraction": None}
    return {"status": "measured", "height_fraction": (base - front) / height, "base_y_fraction": base / height, "front_y_fraction": front / height}


@dataclass(frozen=True)
class PhotoTrayModel:
    slope: float
    intercept: float
    residual_radius: float | None
    training_height_range: tuple[float, float]
    geometry: TrayGeometry = TrayGeometry()

    @classmethod
    def fit(cls, train: list[tuple[float, int]], geometry: TrayGeometry = TrayGeometry()):
        rows = [(h, n) for h, n in train if h > 0 and n > 0]
        if len(rows) < 3 or len(set(h for h, _ in rows)) < 3:
            raise ValueError("at least three distinct nonempty training heights needed")
        heights, counts = np.asarray(rows, dtype=float).T
        slope, intercept = np.linalg.lstsq(np.column_stack((heights, np.ones(len(rows)))), counts, rcond=None)[0]
        if not math.isfinite(slope) or slope <= 0:
            raise ValueError("nonpositive fitted height/count relationship")
        return cls(float(slope), float(intercept), None, (float(min(heights)), float(max(heights))), geometry)

    def estimate_measurement(self, measurement: dict) -> dict:
        value = measurement.get("height_fraction")
        if value is None or value <= 0:
            return {"status": "unavailable", "reason": measurement.get("reason", "empty_or_unsupported_back"), "estimated_cards": None, "probability_correct": None}
        estimate = max(0.0, self.slope * value + self.intercept)
        interval = None if self.residual_radius is None else [max(0.0, estimate - self.residual_radius), estimate + self.residual_radius]
        return {"status": "experimental", "estimated_cards": estimate, "estimated_decks": estimate / 52, "card_interval": interval, "extrapolation": not self.training_height_range[0] <= value <= self.training_height_range[1], "probability_correct": None, "warning": "one camera, blue-backed cards; interval is an empirical residual band"}

    def predict(self, image: Image.Image) -> dict:
        return self.estimate_measurement(measure_photo(image, self.geometry))

    def calibrate(self, rows: list[tuple[float, int]]):
        residuals = [abs(self.estimate_measurement({"height_fraction": h})["estimated_cards"] - n) for h, n in rows if h > 0]
        if not residuals:
            return replace(self, residual_radius=None)
        radius = float(np.quantile(residuals, 0.9, method="higher"))
        return replace(self, residual_radius=radius)


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_rows(rows: list[dict]) -> dict:
    measured = [row for row in rows if row["prediction"]["estimated_cards"] is not None]
    errors = [abs(row["prediction"]["estimated_cards"] - row["truth_count"]) for row in measured]
    signed = [row["prediction"]["estimated_cards"] - row["truth_count"] for row in measured]
    covered = [row["prediction"]["card_interval"][0] <= row["truth_count"] <= row["prediction"]["card_interval"][1] for row in measured if row["prediction"].get("card_interval") is not None]
    rmse = float(np.sqrt(np.mean(np.square(errors)))) if errors else None
    return {"cases": len(rows), "measured_cases": len(measured), "failed_cases": len(rows) - len(measured), "mae_cards": float(np.mean(errors)) if errors else None, "mae_decks": float(np.mean(errors) / 52) if errors else None, "rmse_cards": rmse, "rmse_decks": rmse / 52 if rmse is not None else None, "signed_bias_cards": float(np.mean(signed)) if signed else None, "p95_absolute_error_cards": float(np.quantile(errors, 0.95)) if errors else None, "max_absolute_error_cards": max(errors) if errors else None, "band_cases": len(covered), "empirical_band_coverage": float(np.mean(covered)) if covered else None, "extrapolation_cases": sum(row["prediction"].get("extrapolation", False) for row in measured), "latency_p50_ms": float(np.quantile([r["latency_ms"] for r in rows], 0.5)) if rows else None, "latency_p95_ms": float(np.quantile([r["latency_ms"] for r in rows], 0.95)) if rows else None}


def run_benchmark(source_dir: Path, output_dir: Path) -> dict:
    manifest_path = source_dir / "subset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("commit") != "3d7ab1bfd0b7ea0235bea085488427fcf7520e69" or manifest.get("license") != "MIT":
        raise ValueError("unverified source pin/license")
    geometry = TrayGeometry()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Protocol is saved before any holdout pixel measurements.
    protocol = {"schema_version": 2, "source": manifest["source"], "commit": manifest["commit"], "geometry": asdict(geometry), "split_counts": {split: [r["count"] for r in manifest["rows"] if r["split"] == split] for split in ("train", "calibration", "test", "overflow")}, "model": "ordinary least squares count from normalized front stack height; absent blue support requires abstention", "calibration": "higher 90th percentile absolute residual on measurable later calibration frames; unsupported frames excluded and counted explicitly", "evaluation": "later normal-capacity frames and overflow reported separately; same pixel thresholds and OLS as initial frozen experiment", "revision_note": "initial holdout revealed unsupported red backs: no pixel tuning; only removal of false zero predictions and exclusion of unsupported calibration residuals", "limitations": ["one recording, not independent sessions", "counts from filenames/source README", "chronological test extrapolates beyond training when measurable", "empirical bands have no claimed probability coverage under temporal dependence", "empty pixels cannot distinguish an unsupported back color", "does not infer exact shoe composition"]}
    (output_dir / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    (output_dir / "SOURCE_LICENSE.txt").write_bytes((source_dir / "LICENSE").read_bytes())
    # Store source labels/digests without redistributing hundreds of MB of photos.
    (output_dir / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    split_rows = {}
    for split in ("train", "calibration"):
        values = []
        for row in manifest["rows"]:
            if row["split"] != split:
                continue
            path = source_dir / row["relative_path"]
            if _sha(path) != row["sha256"]:
                raise ValueError("source photo digest mismatch")
            with Image.open(path) as photo:
                measurement = measure_photo(photo, geometry)
            if measurement["height_fraction"] is None:
                raise ValueError(f"{split} measurement unavailable: {row['count']}")
            values.append((measurement["height_fraction"], row["count"]))
        split_rows[split] = values
    model = PhotoTrayModel.fit(split_rows["train"], geometry).calibrate(split_rows["calibration"])
    (output_dir / "frozen-model.json").write_text(json.dumps(asdict(model), indent=2), encoding="utf-8")
    model_sha = _sha(output_dir / "frozen-model.json")
    rows = []
    for row in manifest["rows"]:
        if row["split"] not in ("test", "overflow"):
            continue
        path = source_dir / row["relative_path"]
        if _sha(path) != row["sha256"]:
            raise ValueError("source photo digest mismatch")
        with Image.open(path) as photo:
            started = time.perf_counter()
            measurement = measure_photo(photo, geometry)
            prediction = model.estimate_measurement(measurement)
            elapsed = 1000 * (time.perf_counter() - started)
        rows.append({"split": row["split"], "truth_count": row["count"], "source_sha256": row["sha256"], "measurement": measurement, "prediction": prediction, "latency_ms": elapsed})
    report = {"schema_version": 2, "status": "completed", "validation_status": "experimental_failures_preserved", "deployment_ready": False, "source_commit": manifest["commit"], "source_manifest_sha256": _sha(manifest_path), "runner_sha256": _sha(Path(__file__)), "protocol_sha256": _sha(output_dir / "protocol.json"), "frozen_model_sha256": model_sha, "training_rows": len(split_rows["train"]), "training_supported_nonempty_rows": sum(h > 0 and n > 0 for h, n in split_rows["train"]), "calibration_rows": len(split_rows["calibration"]), "calibration_supported_rows": sum(h > 0 for h, _ in split_rows["calibration"]), "fit_measurements": {split: [{"height_fraction": h, "truth_count": n} for h, n in values] for split, values in split_rows.items()}, "test": evaluate_rows([r for r in rows if r["split"] == "test"]), "overflow": evaluate_rows([r for r in rows if r["split"] == "overflow"]), "rows": rows, "revision_note": protocol["revision_note"], "limitations": protocol["limitations"]}
    (output_dir / "benchmark-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = run_benchmark(args.source_dir, args.output_dir)
    print(json.dumps({key: result[key] for key in ("status", "training_rows", "calibration_rows", "test", "overflow")}, indent=2))


if __name__ == "__main__":
    main()
