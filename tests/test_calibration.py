import numpy as np
import pytest
from PIL import Image, ImageDraw

from bjlab.calibration import (NormalizedROI, normalize_table, validate_corners,
                              TemplateTextDetector, extract_controlled_metadata,
                              TesseractAdapter)
from bjlab.datasets import render_table
from bjlab.vision import CardDetection


def test_normalized_roi_roundtrip_and_crop():
    roi = NormalizedROI(.1, .2, .5, .4)
    assert roi.to_pixels(200, 100) == (20, 20, 100, 40)
    assert NormalizedROI.from_pixels((20, 20, 100, 40), 200, 100) == roi
    pixels = np.zeros((100, 200, 3), np.uint8)
    pixels[20:60, 20:120] = [120, 50, 20]
    crop = roi.crop(pixels)
    assert crop.shape == (40, 100, 3)
    assert np.all(crop == [120, 50, 20])


@pytest.mark.parametrize("values", [(-.1, 0, .2, .2), (.9, 0, .2, .2), (0, 0, 0, .2),
                                    (0, 0, .2, float("nan"))])
def test_invalid_rois_rejected(values):
    with pytest.raises(ValueError):
        NormalizedROI(*values)


def test_homography_known_checker_mapping_inverse_and_bbox():
    image = Image.new("RGB", (400, 300), "black")
    draw = ImageDraw.Draw(image)
    corners = [(50, 40), (340, 65), (320, 260), (75, 240)]
    draw.polygon(corners, fill="white")
    frame = normalize_table(image, corners, outputsize=(200, 120))
    expected = np.array([[0, 0], [199, 0], [199, 119], [0, 119]])
    assert np.allclose(frame.map_points_to_canonical(corners), expected, atol=1e-4)
    assert np.allclose(frame.map_points_to_source(expected), corners, atol=1e-4)
    points = [(100, 60), (50, 30), (150, 90)]
    assert np.allclose(frame.map_points_to_canonical(frame.map_points_to_source(points)), points, atol=1e-5)
    assert frame.image_rgb.shape == (120, 200, 3)
    assert np.mean(frame.image_rgb[4:-4, 4:-4]) > 250
    detection = CardDetection("A", "S", (20, 20, 40, 60), .98)
    mapped = frame.map_detection_to_source(detection)
    assert mapped.rank == "A" and mapped.suit == "S" and mapped.score == .98
    polygon = frame.map_points_to_source([(20, 20), (60, 20), (60, 80), (20, 80)])
    x, y, w, h = mapped.bbox
    assert np.all(polygon[:, 0] >= x) and np.all(polygon[:, 0] <= x + w)
    assert np.all(polygon[:, 1] >= y) and np.all(polygon[:, 1] <= y + h)


def test_identity_normalized_corners_preserve_checkerboard():
    yy, xx = np.indices((120, 200))
    image = np.repeat((((xx // 10 + yy // 10) % 2) * 255).astype(np.uint8)[:, :, None], 3, axis=2)
    frame = normalize_table(image, [(0, 0), (1, 0), (1, 1), (0, 1)], (200, 120), corners_normalized=True)
    assert np.array_equal(image, frame.image_rgb)
    assert np.allclose(frame.homography, np.eye(3))


@pytest.mark.parametrize("corners", [
    [(0, 0), (99, 99), (99, 0), (0, 99)],  # crossing
    [(0, 0), (99, 0), (40, 40), (0, 99)],  # concave
    [(0, 0), (99, 0), (99, 0), (0, 99)],  # duplicate
    [(0, 0), (0, 99), (99, 99), (99, 0)],  # reverse order
    [(0, 0), (100, 0), (99, 99), (0, 99)],  # outside
    [(0, 0), (99, 0), (float("nan"), 99), (0, 99)],
])
def test_invalid_nonconvex_degenerate_and_outside_corners_are_rejected(corners):
    with pytest.raises(ValueError):
        validate_corners(corners, 100, 100)


@pytest.mark.parametrize("theme", ["green", "navy", "burgundy"])
def test_rule_and_button_text_recognition_is_pixel_based_and_missing_is_unknown(theme):
    frame = render_table([], rule_labels=["H17", "ENHC", "DAS", "RSA", "LS", "BJ3:2", "D6"],
                         button_labels=["HIT", "STAND", "DOUBLE"], theme=theme)
    result = extract_controlled_metadata(frame)
    assert result["rules"] == {"soft17": "H17", "hole_card": "ENHC", "peek": None, "das": "DAS", "rsa": "RSA",
                                "surrender": "LS", "blackjack_payout": "BJ3:2", "decks": 6}
    assert {d["text"] for d in result["button_detections"]} == {"HIT", "STAND", "DOUBLE"}
    assert result["probability_of_correct_rules"] is None
    blank = extract_controlled_metadata(render_table([]))
    assert all(value is None for value in blank["rules"].values())
    assert not blank["button_detections"]


def test_conflicting_pixel_rule_labels_are_not_guessed():
    result = extract_controlled_metadata(render_table([], rule_labels=["H17", "S17", "D6", "D8"]))
    assert result["rules"]["soft17"] is None and result["rules"]["decks"] is None
    assert len(result["issues"]) == 2


def test_american_hole_card_peek_surrender_and_insurance_are_separate_pixel_fields():
    result = extract_controlled_metadata(render_table([], rule_labels=["AHC", "NPEEK", "ES"],
                                                     button_labels=["INSURANCE", "DECLINE INSURANCE", "CONTINUE"]))
    assert result["rules"]["hole_card"] == "AHC"
    assert result["rules"]["peek"] == "NPEEK"
    assert result["rules"]["surrender"] == "ES"
    assert {d["text"] for d in result["button_detections"]} == {"INSURANCE", "DECLINE INSURANCE", "CONTINUE"}
    decline_only = extract_controlled_metadata(render_table([], button_labels=["DECLINE INSURANCE"]))
    assert {d["text"] for d in decline_only["button_detections"]} == {"DECLINE INSURANCE"}
    legacy = extract_controlled_metadata(render_table([], rule_labels=["PEEK", "LS"]))
    assert legacy["rules"]["hole_card"] == "PEEK" and legacy["rules"]["peek"] == "PEEK"


def test_onnative_ocr_is_not_faked_when_tesseract_missing(tmp_path):
    with pytest.raises(RuntimeError, match="not installed"):
        TesseractAdapter(tmp_path / "missing-tesseract.exe")
