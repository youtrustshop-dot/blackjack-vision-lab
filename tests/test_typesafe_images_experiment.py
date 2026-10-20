"""Offline tests for the optional TypeSafe image experiment. No network, no key."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "typesafe_images" / "run_experiment.py"
spec = importlib.util.spec_from_file_location("typesafe_images_experiment", SCRIPT)
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)


def test_iou_identical_disjoint_and_half():
    assert exp.iou([0, 1, 0, 1], [0, 1, 0, 1]) == 1.0
    assert exp.iou([0, 0.4, 0, 0.4], [0.6, 1, 0.6, 1]) == 0.0
    assert abs(exp.iou([0, 1, 0, 1], [0, 0.5, 0, 1]) - 0.5) < 1e-12


def test_crop_moves_box_and_keeps_none():
    assert exp.crop_box(None) is None
    left, right, top, bottom = exp.crop_box([0.14, 1.0, 0.2, 0.8])
    assert abs(left) < 1e-12 and abs(right - 1.0) < 1e-12 and (top, bottom) == (0.2, 0.8)


def test_variants_keep_size_limits():
    from PIL import Image

    im = Image.new("RGB", (1280, 906), (10, 80, 50))
    for v in exp.VARIANTS:
        out, quality, box = exp.make_variant(im.copy(), v, [0.2, 0.6, 0.3, 0.7])
        assert min(out.size) >= 280 and quality in (30, 85)
        assert (v == "crop") == (box != [0.2, 0.6, 0.3, 0.7])


def test_auc_needs_both_classes():
    assert exp.auc([(0.9, 1), (0.8, 1)]) is None
    assert exp.auc([(0.9, 1), (0.1, 0)]) == 1.0
    assert exp.auc([(0.5, 1), (0.5, 0)]) == 0.5


def test_labels_match_existing_screenshots_and_schema():
    labels = json.loads((ROOT / "experiments" / "typesafe_images" / "labels.json").read_text(encoding="utf-8"))["images"]
    for name, row in labels.items():
        assert (ROOT / "docs" / "screenshots" / name).is_file(), name
        assert set(row) == {"blackjack_table", "action_buttons", "poker_table", "table_box"}
        if row["table_box"] is not None:
            left, right, top, bottom = row["table_box"]
            assert 0 <= left < right <= 1 and 0 <= top < bottom <= 1


def test_request_references_image_once_and_declares_asset():
    body = exp.build_request("jev-1.14.0", "AAAA", "jpg")
    text = json.dumps({k: v for k, v in body.items() if k != "assets"})
    assert text.count("IMG") == 1
    assert body["assets"]["IMG"]["data_base64"] == "AAAA"


def test_no_request_without_allow_network(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(exp.urllib.request, "urlopen", boom)
    assert exp.main([]) == 0
    assert "Nothing was sent" in capsys.readouterr().out


def test_missing_key_stops_before_any_request(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(exp.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network used")))
    assert exp.main(["--allow-network"]) == 2
