import numpy as np
from PIL import Image
import pytest

from bjlab.external_tray_benchmark import PhotoTrayModel, TrayGeometry, evaluate_rows, measure_photo


def fixture_image(size=960):
    pixels = np.full((size * 3 // 4, size, 3), [180, 170, 150], dtype=np.uint8)
    pixels[round(.55 * pixels.shape[0]):round(.60 * pixels.shape[0]), round(.48 * size):round(.56 * size)] = [25, 32, 55]
    pixels[round(.69 * pixels.shape[0]):round(.73 * pixels.shape[0]), round(.48 * size):round(.56 * size)] = [12, 12, 12]
    return Image.fromarray(pixels)


def test_pixel_measurement_and_scale_are_not_filename_or_label_features():
    a = measure_photo(fixture_image())
    b = measure_photo(fixture_image(1920))
    assert a["status"] == b["status"] == "measured"
    assert abs(a["height_fraction"] - .13) < .005
    assert abs(a["height_fraction"] - b["height_fraction"]) < .003
    assert "count" not in a


def test_missing_base_fails_and_absent_blue_has_explicit_ambiguity():
    plain = Image.new("RGB", (960, 720), (180, 170, 150))
    assert measure_photo(plain)["status"] == "unmeasurable"
    pixels = np.asarray(fixture_image()).copy()
    pixels[pixels[..., 2] > pixels[..., 0]] = [180, 170, 150]
    result = measure_photo(Image.fromarray(pixels))
    assert result["status"] == "empty_or_unsupported_back"
    model = PhotoTrayModel.fit([(.02, 20), (.04, 40), (.08, 80)])
    assert model.estimate_measurement(result)["estimated_cards"] is None
    assert model.calibrate([(0, 200)]).residual_radius is None


def test_calibration_affects_band_not_predictor_and_marks_extrapolation():
    fitted = PhotoTrayModel.fit([(.02, 20), (.04, 40), (.08, 80)])
    calibrated = fitted.calibrate([(.1, 103), (.12, 125)])
    prediction = calibrated.estimate_measurement({"height_fraction": .15})
    assert prediction["estimated_cards"] == pytest.approx(150)
    assert calibrated.slope == fitted.slope
    assert calibrated.intercept == fitted.intercept
    assert calibrated.residual_radius == pytest.approx(5)
    assert prediction["extrapolation"] is True
    assert prediction["probability_correct"] is None
    assert calibrated.estimate_measurement({"height_fraction": None})["estimated_cards"] is None


def test_invalid_geometry_and_degenerate_training_are_rejected():
    with pytest.raises(ValueError):
        TrayGeometry(front_strip=(.7, .6))
    with pytest.raises(ValueError):
        PhotoTrayModel.fit([(.1, 10), (.1, 20), (.1, 30)])


def test_failed_measurements_stay_in_report_denominator():
    rows = [
        {"truth_count": 12, "latency_ms": 2, "prediction": {"estimated_cards": 10, "card_interval": [9, 11], "extrapolation": True}},
        {"truth_count": 15, "latency_ms": 3, "prediction": {"estimated_cards": 18, "card_interval": [17, 19], "extrapolation": False}},
        {"truth_count": 15, "latency_ms": 3, "prediction": {"estimated_cards": None}},
    ]
    report = evaluate_rows(rows)
    assert report["cases"] == 3
    assert report["measured_cases"] == 2
    assert report["failed_cases"] == 1
    assert report["mae_cards"] == 2.5
    assert report["rmse_cards"] == pytest.approx(6.5 ** .5)
    assert report["empirical_band_coverage"] == 0
    assert report["extrapolation_cases"] == 1
