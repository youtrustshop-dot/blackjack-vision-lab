"""Experiment contract checks; no detector accuracy or holdout evaluation."""
from collections import Counter

import numpy as np
import pytest

from validation.tools.independent_tournament import SPLITS, scenario_timeline, render
from validation.tools.stress_lab import PROFILES
from validation.tools.publish_tournament_baseline import exact_face_state, read_verified_truth
from validation.tools.overlap_session import digest


def test_split_groups_and_physical_sessions_are_disjoint():
    assert len({v["seed"] for v in SPLITS.values()}) == 3
    assert len({v["family"] for v in SPLITS.values()}) == 3
    # Development only: do not instantiate or inspect final holdout content.
    stages = scenario_timeline(SPLITS["development"]["seed"])
    assert sum(s["phase"] == "settled" for s in stages) == 6
    assert {s["scenario"] for s in stages} == {
        "immediate_blackjack", "hit_bust", "stand_dealer_draw", "double_dealer_draw",
        "identical_first", "identical_new_round"}
    assert not any(s["phase"] == "player" and s["scenario"] == "immediate_blackjack" for s in stages)
    assert any(s["phase"] == "player" and "double" in s["controls"] for s in stages)


def test_identical_faces_in_new_round_are_distinct_physical_instances():
    stages = scenario_timeline(SPLITS["development"]["seed"])
    first = next(s for s in stages if s["scenario"] == "identical_first" and s["phase"] == "player")
    second = next(s for s in stages if s["scenario"] == "identical_new_round" and s["phase"] == "player")
    assert first["round"] != second["round"]
    assert [c.get("rank") for c in first["cards"]] == [c.get("rank") for c in second["cards"]]
    assert [c.get("suit") for c in first["cards"]] == [c.get("suit") for c in second["cards"]]
    assert not ({c["id"] for c in first["cards"]} & {c["id"] for c in second["cards"]})
    clear_between = [s for s in stages if s["phase"] == "waiting" and s["round"] == first["round"]]
    assert clear_between and all(s["cards"] == [] for s in clear_between)


def test_pixel_input_cannot_encode_card_id_or_round_id():
    family = SPLITS["development"]
    stage = next(s for s in scenario_timeline(family["seed"]) if s["phase"] == "player")
    altered = dict(stage, round=99999, cards=[dict(c, id=f"changed-{i}") for i,c in enumerate(stage["cards"])])
    before, truth = render(stage, PROFILES["overlap"], family, 0)
    after, _ = render(altered, PROFILES["overlap"], family, 0)
    assert np.array_equal(np.asarray(before), np.asarray(after))
    covered = [c for c in truth if c["presence"] == "covered"]
    assert len(covered) == 1
    assert covered[0]["rank"] is None and covered[0]["suit"] is None and covered[0]["physical_rank"] is None


def test_rotation_and_occlusion_truth_are_pixel_visibility_not_hidden_rank():
    family = SPLITS["development"]
    stage = next(s for s in scenario_timeline(family["seed"]) if s["phase"] == "player")
    _, truth = render(stage, PROFILES["clipped"], family, 0)
    player = [c for c in truth if c["zone"] == "player:0"]
    assert any(c["presence"] == "unreadable" and c["rank"] is None for c in player)
    assert Counter(c["presence"] for c in truth)["covered"] == 1


def test_unreadable_faceup_cannot_be_exact_when_reported_as_back():
    expected = [{"zone": "player:0", "bbox": [100,100,112,156], "presence": "unreadable", "rank": None, "suit": None}]
    wrong = [{"zone": "player:0", "bbox": [100,100,112,156], "rank": None, "suit": None, "face_down": True}]
    assert exact_face_state(expected, wrong) == {"rank_exact": 0, "suit_exact": 0, "wrong_back_on_unreadable": 1, "nonempty": 1}
    correct = [dict(wrong[0], face_down=False)]
    assert exact_face_state(expected, correct) == {"rank_exact": 1, "suit_exact": 1, "wrong_back_on_unreadable": 0, "nonempty": 1}


def test_expected_back_requires_a_back_not_just_unknown_rank():
    expected = [{"zone": "dealer", "bbox": [100,100,112,156], "presence": "covered", "rank": None, "suit": None}]
    faceup = [{"zone": "dealer", "bbox": [100,100,112,156], "rank": None, "suit": None, "face_down": False}]
    assert exact_face_state(expected, faceup)["rank_exact"] == 0
    assert exact_face_state(expected, [dict(faceup[0], face_down=True)])["suit_exact"] == 1
    assert exact_face_state([], [dict(faceup[0], face_down=True)])["rank_exact"] == 0


@pytest.mark.parametrize("altered", ["truth", "video"])
def test_publication_rejects_altered_session_inputs_before_consuming_labels(tmp_path, altered):
    video = tmp_path / "own.webm"; video.write_bytes(b"original owned video fixture")
    truth = tmp_path / "own.truth.json"; truth.write_text("[]", encoding="utf-8")
    session = {"name": "own", "video": video.name, "truth": truth.name,
               "video_sha256": digest(video), "truth_sha256": digest(truth)}
    assert read_verified_truth(tmp_path, session) == []
    # Invalid JSON would fail differently if consumed before hash verification.
    (truth if altered == "truth" else video).write_bytes(b"altered invalid data")
    with pytest.raises(ValueError, match=f"Frozen {altered} changed"):
        read_verified_truth(tmp_path, session)
