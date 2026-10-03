import math

import cv2
import numpy as np
import pytest

from bjlab.datasets import render_table
from bjlab.events import RANKS, SUITS
from bjlab.vision import (CardDetection, DeckCountEstimator, LocalVideoSource, ONNXCardDetector,
                         ScoreCalibrator, TemplateCardDetector, TemporalTracker,
                         estimate_discard_tray)


def detection(rank="A", suit="S", x=100, y=80, score=.99, face_down=False, zone="dealer", hint=None):
    return CardDetection(rank, suit, (x, y, 78, 110), score, face_down, zone, hint)


@pytest.mark.parametrize("rank", RANKS)
@pytest.mark.parametrize("suit", SUITS)
def test_pixel_detector_recognizes_all_52_cards(rank, suit):
    cards = [{"rank": rank, "suit": suit, "x": 90, "y": 80}]
    detected = TemplateCardDetector().detect(render_table(cards))
    assert len(detected) == 1
    assert (detected[0].rank, detected[0].suit) == (rank, suit)
    assert detected[0].score >= .90
    assert detected[0].bbox == (90, 80, 78, 110)
    assert detected[0].calibrated_probability is None


@pytest.mark.parametrize("scale", [.65, 1, 1.5])
@pytest.mark.parametrize("theme", ["green", "navy", "burgundy"])
def test_pixel_detector_scaling_theme_and_mild_noise(scale, theme):
    cards = [{"rank": "8", "suit": "H", "x": 100, "y": 80, "scale": scale},
             {"rank": "J", "suit": "C", "x": 300, "y": 340, "scale": scale}]
    image = render_table(cards, theme=theme, blur=.2, brightness=.92, noise_std=1, seed=8)
    detected = TemplateCardDetector().detect(image)
    assert [(d.rank, d.suit) for d in detected] == [("8", "H"), ("J", "C")]


def test_pixel_only_no_metadata_input_and_hidden_card(tmp_path):
    cards = [{"rank": "A", "suit": "S", "x": 90, "y": 80, "card_id": "secret", "face_down": True}]
    a = render_table(cards)
    b = render_table([{**cards[0], "rank": "2", "suit": "H", "card_id": "different"}])
    assert np.array_equal(np.asarray(a), np.asarray(b))
    target = tmp_path / "frame.jpg"
    a.save(target, quality=95)
    detected = TemplateCardDetector().detect(target)
    assert len(detected) == 1 and detected[0].face_down
    assert detected[0].rank is None and detected[0].suit is None
    assert detected[0].logical_hint is None


def test_tracker_stable_consecutive_frames_count_once_movement_occlusion_reveal():
    tracker = TemporalTracker(stable_frames=3, lost_after=2)
    tracker.new_shoe(2, timestamp=0)
    for stamp in (1, 2, 3):
        tracker.update([detection(x=100 + stamp * 3), detection(None, None, x=200, face_down=True)],
                       stamp, round_id="r1")
    ids = set(tracker.log.replay().cards)
    assert len(ids) == 2
    assert tracker.log.replay().hidden_count == 1
    tracker.update([], 4)
    tracker.update([], 5)
    assert tracker.state_summary()["gate"]["status"] == "manual_review"
    for stamp in (6, 7, 8):
        tracker.update([detection(x=450), detection("K", "H", x=200)], stamp)
    state = tracker.log.replay()
    assert set(state.cards) == ids
    assert len(state.counted_ids) == 2
    assert state.known_rank_counts["A"] == 1 and state.known_rank_counts["K"] == 1
    kinds = [event.kind for event in tracker.log.events]
    assert kinds.count("CARD_CONFIRMED") == 2
    assert kinds.count("CARD_REVEALED") == 1
    assert tracker.state_summary()["gate"]["status"] == "stable"


def test_tracker_correction_moves_count_without_duplicate():
    tracker = TemporalTracker(stable_frames=2)
    tracker.new_shoe(1, timestamp=0)
    for stamp in (1, 2):
        tracker.update([detection("8", "H")], stamp, round_id="r1")
    for stamp in (3, 4):
        tracker.update([detection("9", "H")], stamp)
    state = tracker.log.replay()
    assert len(state.cards) == 1
    assert state.ranks["8"] == 0 and state.ranks["9"] == 1
    assert sum(event.kind == "STATE_CORRECTION" for event in tracker.log.events) == 1


def test_unconfirmed_label_flicker_requires_consecutive_equal_readings():
    tracker = TemporalTracker(stable_frames=3)
    tracker.new_shoe(1, timestamp=0)
    for stamp, rank in enumerate(("A", "K", "A", "A"), start=1):
        tracker.update([detection(rank)], stamp, "r1")
        assert not tracker.log.replay().cards
    tracker.update([detection("A")], 5)
    assert tracker.log.replay().ranks["A"] == 1


def test_tracker_round_boundary_allows_identical_redealt_card_and_no_leak():
    tracker = TemporalTracker(stable_frames=1)
    tracker.new_shoe(2, timestamp=0)
    tracker.update([detection()], 1, "round1")
    first = set(tracker.log.replay().cards)
    tracker.update([detection()], 2, "round2")
    state = tracker.log.replay()
    assert len(state.cards) == 2 and first < set(state.cards)
    assert state.ranks["A"] == 2
    assert sum(c["on_table"] for c in state.cards.values()) == 1


def test_tracker_low_score_provisional_and_duplicate_label_ambiguity_are_visible():
    tracker = TemporalTracker(stable_frames=1)
    tracker.new_shoe(2, timestamp=0)
    tracker.update([detection(score=.7)], 1, "r1")
    assert not tracker.log.replay().cards
    tracker.update([detection(x=100), detection(x=200)], 2)
    tracker.update([detection(x=150)], 3)
    assert tracker.state_summary()["gate"]["status"] == "manual_review"
    # A subsequent frame cannot silently erase a historical identity ambiguity.
    tracker.update([detection(x=150)], 4)
    assert tracker.log.replay().integrity_issues
    assert tracker.state_summary()["gate"]["probability_of_correct_state"] is None


def test_deck_estimator_multiplicity_eliminates_single_deck_without_inventing_certainty():
    estimator = DeckCountEstimator()
    assert estimator.estimate()["status"] == "prior_only"
    estimator.observe("a", "A", "S")
    estimator.observe("b", "A", "S")
    posterior = estimator.estimate()
    assert posterior["probabilities"]["1"] == 0
    assert math.isclose(sum(posterior["probabilities"].values()), 1)
    assert posterior["certainty"] is False
    assert sum(p > 0 for p in posterior["probabilities"].values()) == 4
    estimator.observe("b", "2", "H")
    assert estimator.estimate()["probabilities"]["1"] > 0
    assert estimator.estimate()["observations"] == 2


def test_calibration_requires_empirical_support_and_keeps_state_probability_separate():
    calibrator = ScoreCalibrator().fit([(.95, True), (.95, False), (.95, True)])
    assert calibrator.predict(.95) == pytest.approx(3 / 5)
    assert calibrator.predict(.2) is None
    metrics = calibrator.evaluate([(.95, True), (.2, False)])
    assert metrics["supported"] == 1 and metrics["unsupported"] == 1
    assert metrics["brier_score"] == pytest.approx(.16)
    with pytest.raises(ValueError):
        calibrator.predict(float("nan"))


def test_video_adapter_reads_local_rgb_frames(tmp_path):
    target = tmp_path / "fixture.avi"
    writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*"MJPG"), 10, (960, 600))
    if not writer.isOpened():
        pytest.skip("Platform MJPG encoder unavailable")
    for rank in ("A", "2", "3"):
        frame = np.asarray(render_table([{"rank": rank, "suit": "S", "x": 90, "y": 80}]))
        writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    writer.release()
    frames = list(LocalVideoSource(target).frames())
    assert len(frames) == 3
    assert [time for time, _ in frames] == pytest.approx([0, .1, .2])
    detector = TemplateCardDetector()
    assert [detector.detect(frame)[0].rank for _, frame in frames] == ["A", "2", "3"]


def test_optional_adapter_failure_and_discard_estimate_are_explicit(tmp_path):
    with pytest.raises(FileNotFoundError):
        ONNXCardDetector(tmp_path / "missing.onnx")
    estimate = estimate_discard_tray(50, pixels_per_card=1, measurement_error_pixels=2)
    assert estimate["status"] == "experimental"
    assert estimate["cards_interval"][0] < 50 < estimate["cards_interval"][1]
    assert estimate["probability"] is None
