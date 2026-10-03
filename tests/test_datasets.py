import hashlib
import json

import numpy as np
import pytest

from bjlab.datasets import (benchmark_dataset, detection_metrics, event_metrics,
                            generate_dataset, render_table, validate_splits, benchmark_tracking_dataset,
                            card_image)
from bjlab.vision import TemplateCardDetector


def test_all_52_cards_detect_both_designs_without_changing_corner_pixels():
    detector = TemplateCardDetector()
    for rank in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"):
        for suit in ("S", "H", "D", "C"):
            classic = np.asarray(card_image(rank, suit, card_design="classic"))
            minimal = np.asarray(card_image(rank, suit, card_design="minimal"))
            assert np.array_equal(classic[:55, :30], minimal[:55, :30])
            assert np.array_equal(classic, np.asarray(card_image(rank, suit)))
            assert not np.array_equal(classic, minimal)
            for design in ("classic", "minimal"):
                frame = render_table([{"rank": rank, "suit": suit, "x": 50, "y": 70}],
                                     width=300, height=250, card_design=design)
                detections = detector.detect(frame)
                assert len(detections) == 1, (rank, suit, design)
                assert (detections[0].rank, detections[0].suit) == (rank, suit)
    with pytest.raises(ValueError, match="design"):
        render_table([], card_design="unknown")


def test_grouped_dataset_deterministic_no_session_or_heldout_theme_leakage(tmp_path):
    a = generate_dataset(tmp_path / "a", sessions=18, frames_per_session=1, seed=13, augment=False)
    b = generate_dataset(tmp_path / "b", sessions=18, frames_per_session=1, seed=13, augment=False)
    assert a == b
    seen = {}
    for record in a["records"]:
        assert seen.setdefault(record["session_id"], record["split"]) == record["split"]
        if record["theme"] == "burgundy":
            assert record["split"] == "test"
        path_a, path_b = tmp_path / "a" / record["image"], tmp_path / "b" / record["image"]
        assert hashlib.sha256(path_a.read_bytes()).digest() == hashlib.sha256(path_b.read_bytes()).digest()
    assert {r["split"] for r in a["records"]} == {"train", "calibration", "test"}
    report = benchmark_dataset(tmp_path / "a", TemplateCardDetector())
    assert report["frames"] > 0
    assert report["precision"] == 1
    assert report["recall"] == 1
    assert report["rank_accuracy"] == 1
    assert report["suit_accuracy"] == 1
    assert report["latency_ms_p95"] >= 0


def test_session_leakage_is_rejected():
    manifest = {"records": [{"session_id": "s", "theme": "green", "split": "train"},
                             {"session_id": "s", "theme": "navy", "split": "test"}]}
    with pytest.raises(ValueError, match="Session leakage"):
        validate_splits(manifest)


def test_backs_do_not_inflate_front_rank_and_suit_accuracy():
    hidden = [{"rank": None, "suit": None, "face_down": True, "bbox": [100 * i, 0, 78, 110]}
              for i in range(1, 10)]
    truth = [{"rank": "A", "suit": "S", "face_down": False, "bbox": [0, 0, 78, 110]}, *hidden]
    predicted = [{"rank": "2", "suit": "H", "face_down": False, "bbox": [0, 0, 78, 110], "score": .99},
                 *[{**card, "score": .99} for card in hidden]]
    report = detection_metrics(predicted, truth)
    assert report["true_positives"] == 10
    assert report["visible_rank_matches"] == report["visible_suit_matches"] == 1
    assert report["rank_accuracy"] == report["suit_accuracy"] == 0
    assert report["back_true_positives"] == 9
    assert report["back_precision"] == report["back_recall"] == 1
    backs_only = detection_metrics(predicted[1:], truth[1:])
    assert backs_only["rank_accuracy"] is None and backs_only["suit_accuracy"] is None
    missing_backs = detection_metrics([], truth[1:])
    assert missing_backs["back_false_negatives"] == 9 and missing_backs["back_recall"] == 0


def test_metrics_do_not_hide_wrong_labels_duplicates_and_misses():
    truth = [{"rank": "A", "suit": "S", "bbox": [0, 0, 78, 110]},
             {"rank": "K", "suit": "H", "bbox": [100, 0, 78, 110]}]
    predicted = [{"rank": "2", "suit": "S", "bbox": [0, 0, 78, 110], "score": .98},
                 {"rank": "2", "suit": "S", "bbox": [0, 0, 78, 110], "score": .98}]
    report = detection_metrics(predicted, truth)
    assert report["true_positives"] == 1
    assert report["false_positives"] == 1
    assert report["false_negatives"] == 1
    assert report["rank_accuracy"] == 0
    assert report["precision"] == .5 and report["recall"] == .5
    events = [{"card_id": "a", "rank": "A"}, {"card_id": "a", "rank": "A"}]
    report = event_metrics(events, [{"card_id": "a", "rank": "A"}, {"card_id": "b", "rank": "K"}])
    assert report["missed_events"] == 1 and report["duplicate_events"] == 1


def test_renderer_augmentations_deterministic_and_labels_are_not_pixels():
    cards = [{"card_id": "a", "rank": "A", "suit": "S", "x": 100, "y": 80}]
    first = render_table(cards, noise_std=5, seed=8)
    second = render_table([{**cards[0], "card_id": "b"}], noise_std=5, seed=8)
    assert np.array_equal(np.asarray(first), np.asarray(second))
    with pytest.raises(ValueError):
        render_table(cards, theme="unknown")


def test_tracking_benchmark_uses_pixels_and_independent_truth(tmp_path):
    records = []
    for frame in range(6):
        hidden = frame < 3
        cards = [{"card_id": "a", "rank": "A", "suit": "S", "x": 100 + frame * 3,
                  "y": 80, "zone": "dealer"},
                 {"card_id": "b", "rank": None if hidden else "K",
                  "suit": None if hidden else "H", "face_down": hidden,
                  "x": 200, "y": 80, "zone": "dealer"}]
        path = f"frame-{frame}.png"
        render_table(cards).save(tmp_path / path)
        labels = [{**c, "bbox": [c["x"], c["y"], 78, 110]} for c in cards]
        records.append({"image": path, "session_id": "s", "theme": "green", "split": "test",
                        "frame": frame, "timestamp": frame / 10, "labels": labels})
    manifest = {"schema_version": 1, "records": records}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = benchmark_tracking_dataset(tmp_path, TemplateCardDetector())
    assert report["evaluable_groups"] == 1
    assert report["missed_events"] == 0
    assert report["duplicate_events"] == 0
    assert report["known_rank_l1_drift"] == 0
    assert report["exact_session_fraction"] == 1
    class BlankDetector:
        def detect(self, image):
            return []
    missed = benchmark_tracking_dataset(tmp_path, BlankDetector())
    assert missed["missed_events"] == 2
    assert missed["known_rank_l1_drift"] == 2
    assert missed["exact_session_fraction"] == 0
