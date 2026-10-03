import json

import numpy as np
import pytest

from bjlab.shoe_inference_benchmark import (render_discard_tray, measure_discard_tray,
    DiscardTrayCalibrator, generate_inference_dataset, run_inference_benchmark, validate_temporal_holdout)


def test_tray_measurement_from_pixels_and_camera_width_normalization():
    image = render_discard_tray(100, pixels_per_card=.9, camera_scale=1)
    measurement = measure_discard_tray(image)
    assert measurement["status"] == "measured"
    assert measurement["height"] == 94 and measurement["width"] == 150
    assert measurement["normalized_height"] == 94
    zoomed = measure_discard_tray(render_discard_tray(100, camera_scale=1.1))
    assert zoomed["normalized_height"] == pytest.approx(94, abs=.5)
    blank = measure_discard_tray(np.zeros((520, 400, 3), np.uint8))
    assert blank["status"] == "unavailable" and blank["height"] is None


def test_calibrator_fits_train_and_independent_interval_without_fake_probability():
    calibrator = DiscardTrayCalibrator().fit([(13, 10), (22, 20), (49, 50)])
    calibrator.calibrate_interval([(31, 30), (40, 40), (94, 100)])
    estimate = calibrator.estimate(94)
    assert estimate["estimated_cards"] == pytest.approx(100)
    assert estimate["probability"] is None
    assert estimate["cards_interval"][0] <= 100 <= estimate["cards_interval"][1]
    with pytest.raises(ValueError):
        DiscardTrayCalibrator().estimate(94)
    with pytest.raises(ValueError):
        calibrator.calibrate_interval([])


def test_temporal_holdout_and_known_shift_benchmark_are_real_artifacts(tmp_path):
    manifest = generate_inference_dataset(tmp_path, sessions=10, seed=29)
    validate_temporal_holdout(manifest)
    assert len(manifest["shoes"]) == 10
    report = run_inference_benchmark(tmp_path)
    assert report["status"] == "completed"
    assert report["deck_summary"]["samples"] > 0
    assert 0 <= report["deck_summary"]["accuracy"] <= 1
    assert report["tray_summary"]["mae_cards"] < 1
    assert report["tray_distribution_shift"]["mae_cards"] > report["tray_summary"]["mae_cards"]
    assert report["tray_distribution_shift"]["interval_coverage"] < report["tray_summary"]["interval_coverage"]
    assert json.loads((tmp_path / "benchmark-report.json").read_text())["dataset_manifest_sha256"]
    # Chronological split validation rejects a shuffled/later training session.
    manifest["shoes"][0]["session_index"] = 999
    with pytest.raises(ValueError, match="chronologically"):
        validate_temporal_holdout(manifest)
