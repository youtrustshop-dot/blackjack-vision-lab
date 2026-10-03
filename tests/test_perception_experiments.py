import hashlib
import json

import pytest

from bjlab.datasets import (RANKS, SUITS, _counting_snapshot,
                            benchmark_counting_ablation, render_table)
from bjlab.events import EventLog
from bjlab.vision import TemplateCardDetector


def test_observable_count_excludes_hidden_rank_but_includes_hidden_physical_card():
    snapshot = _counting_snapshot({"one": {"rank": "5"}, "two": {"rank": "A"},
                                   "hidden": {"rank": None}}, decks=1)
    assert snapshot["running_count"] == 0
    assert snapshot["physical_remaining"] == 49
    assert snapshot["unknown_rank_observed"] == 1
    assert sum(snapshot["informational_pool"]) == 50
    full = _counting_snapshot({rank + suit: {"rank": rank} for rank in RANKS for suit in SUITS}, 1)
    assert full["running_count"] == 0
    assert full["physical_remaining"] == 0
    assert full["true_count"] is None


def test_real_pixels_confirmation_ablation_retains_occlusion_reveal_and_count_delay(tmp_path):
    records = []
    base = [
        {"card_id": "up", "rank": "6", "suit": "S", "x": 110, "y": 180, "zone": "dealer"},
        {"card_id": "hole", "rank": "7", "suit": "C", "x": 215, "y": 180, "zone": "dealer"},
        {"card_id": "p1", "rank": "5", "suit": "H", "x": 110, "y": 350, "zone": "player"},
        {"card_id": "p2", "rank": "10", "suit": "D", "x": 215, "y": 350, "zone": "player"},
    ]
    for frame in range(8):
        cards = [{**card, "face_down": card["card_id"] == "hole" and frame < 4,
                  "visible": not (card["card_id"] == "p1" and frame == 2)} for card in base]
        path = f"frame-{frame}.png"
        render_table(cards, width=960, height=600).save(tmp_path / path)
        labels = [{**card, "rank": None if card["face_down"] else card["rank"],
                   "suit": None if card["face_down"] else card["suit"],
                   "bbox": [card["x"], card["y"], 78, 110]} for card in cards if card["visible"]]
        records.append({"session_id": "s", "theme": "green", "split": "test", "image": path,
                        "timestamp": frame / 10, "frame": frame, "labels": labels})
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"records": records}), encoding="utf-8")
    before = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    report = benchmark_counting_ablation(tmp_path, TemplateCardDetector(), regret_samples=0)
    assert before == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    quick, confirmed = report["modes"]["1"], report["modes"]["3"]
    assert quick["frames"] == confirmed["frames"] == 8
    assert quick["running_count_exact_fraction"] == 1
    assert confirmed["running_count_exact_fraction"] < 1
    assert confirmed["true_count_mae"] > 0
    assert quick["normal_decision_allowed_frames"] == 3
    assert confirmed["normal_decision_allowed_frames"] == 0
    for mode in (quick, confirmed):
        assert mode["final_exact_groups"] == 1
        assert mode["missed_events"] == mode["duplicate_events"] == mode["unmatched_events"] == 0
        assert mode["normal_decision_allowed_inexact_frames"] == 0
        assert mode["mean_ev_regret"] is None
        assert mode["pixel_pipeline_p95_ms"] > 0
    for count in ("1", "3"):
        journal = EventLog.from_dict(report["raw_groups"][count][0]["events"])
        assert len(journal.replay().cards) == 4
        assert report["raw_frames"][count][-1]["running_count_error"] == 0


def test_invalid_ablation_configuration_rejected_before_any_pixels(tmp_path):
    with pytest.raises(ValueError, match="positive"):
        benchmark_counting_ablation(tmp_path, TemplateCardDetector(), confirmations=(0,))
