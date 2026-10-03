import base64
import copy
import io

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from bjlab.api import app, sessions, session_locks, perception_trackers


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
    sessions.clear(); session_locks.clear(); perception_trackers.clear()


def new_fixture(client, cards, **rules):
    response = client.post("/api/sessions", json={"rules": rules, "seed": 27})
    assert response.status_code == 200
    identity = response.json()["session_id"]
    sessions[identity].set_shoe(cards)
    return identity


def test_health_rules_and_create_validation(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/rules").json()["defaults"]["decks"] == 6
    assert client.post("/api/sessions", json={"rules": {"decks": 3}}).status_code == 422
    assert client.get("/api/sessions/absent").status_code == 404


def test_game_actions_truth_boundary_and_exports(client):
    identity = new_fixture(client, ["10", "10", "9", "7"])
    state = client.post(f"/api/sessions/{identity}/deal", json={}).json()
    assert "rank" not in state["dealer"]["cards"][1]
    assert client.get(f"/api/sessions/{identity}/truth").status_code == 403
    truth = client.get(f"/api/sessions/{identity}/truth?debug=true").json()
    assert truth["debug_only"] and truth["dealer"][1]["rank"] == "7"
    assert client.post(f"/api/sessions/{identity}/action", json={"action": "split"}).status_code == 409
    settled = client.post(f"/api/sessions/{identity}/action", json={"action": "stand"}).json()
    assert settled["round_profit"] == 1
    exported = client.get(f"/api/sessions/{identity}/export").json()
    replayed = client.post("/api/replay", json=exported).json()
    assert replayed["verified"]
    assert replayed["snapshot"] == settled
    assert client.get(f"/api/sessions/{identity}/export?format=csv").headers["content-type"].startswith("text/csv")


def test_replay_cursor_is_exact_and_corrupted_events_are_rejected(client):
    identity = new_fixture(client, ["10", "6", "8", "5", "10"])
    client.post(f"/api/sessions/{identity}/deal", json={})
    events = client.get(f"/api/sessions/{identity}/events").json()["events"]
    cursor = next(event["seq"] for event in events if event["kind"] == "card_exposed")
    response = client.post("/api/replay", json={"events": events, "to_index": cursor})
    assert response.status_code == 200
    state = response.json()["snapshot"]
    assert state["shoe"]["seen"] == 1
    assert state["dealer"]["cards"] == []
    assert state["events_count"] == cursor + 1
    broken = copy.deepcopy(events)
    broken[cursor]["payload"]["card"]["rank"] = "A"
    assert client.post("/api/replay", json={"events": broken}).status_code == 422


def test_analysis_insurance_exact_and_isolated_solver_cache(client):
    identity = new_fixture(client, ["10", "A", "9", "K"])
    client.post(f"/api/sessions/{identity}/deal", json={})
    analysis = client.post(f"/api/sessions/{identity}/analyze", json={}).json()
    assert analysis["result"]["exact"]
    assert analysis["result"]["actions"]["insurance"] == 1
    assert analysis["result"]["latency_ms"] > 0
    identity = new_fixture(client, ["10", "6", "8", "10", "5"])
    client.post(f"/api/sessions/{identity}/deal", json={})
    response = client.post(f"/api/sessions/{identity}/analyze", json={"timeout_ms": 1000})
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["status"] == "ok"
    assert analysis["result"]["actions"]["stand"] == -1
    assert analysis["result"]["best_action"] == "surrender"
    assert analysis["state"]["counts"] == list(sessions[identity].counts())
    second = client.post(f"/api/sessions/{identity}/analyze", json={"timeout_ms": 1000}).json()
    assert second["cached"] is True


def test_frame_real_pixel_detector_and_perception_gate(client):
    identity = new_fixture(client, ["2", "6", "8", "A", "10", "9", "3"])
    client.post(f"/api/sessions/{identity}/deal", json={})
    response = client.get(f"/api/sessions/{identity}/frame")
    assert response.status_code == 200
    assert Image.open(io.BytesIO(response.content)).size == (960, 600)
    early = client.post(f"/api/sessions/{identity}/perception/analyze", json={}).json()
    assert early["status"] == "gated"
    perceived = client.post(f"/api/sessions/{identity}/perception", json={"frames": 3}).json()
    assert len(perceived["detections"]) == 4
    assert sum(item["face_down"] for item in perceived["detections"]) == 1
    assert sorted(item["rank"] for item in perceived["detections"] if item["rank"]) == ["2", "6", "8"]
    assert len(perceived["state"]["counted_ids"]) == 3
    assert perceived["state"]["hidden_count"] == 1
    assert perceived["deck_estimation"]["mode"] == "KNOWN"
    assert perceived["deck_estimation"]["source"] == "configured-session"
    assert perceived["deck_estimation"]["decks"] == 6
    assert perceived["deck_estimation"]["observations"] == 3
    minimal = client.get(f"/api/sessions/{identity}/frame?card_design=minimal")
    assert minimal.status_code == 200 and minimal.content != response.content
    assert client.get(f"/api/sessions/{identity}/frame?card_design=invalid").status_code == 422
    again = client.post(f"/api/sessions/{identity}/perception", json={"frames": 3, "card_design": "minimal"}).json()
    assert len(again["state"]["counted_ids"]) == 3  # Repeated calls stay monotonic and deduplicated.
    assert again["deck_estimation"]["observations"] == 3
    analysis = client.post(f"/api/sessions/{identity}/perception/analyze", json={"timeout_ms": 50}).json()
    assert analysis["source"] == "perception"
    assert analysis["state"]["player"] == ["2", "8"]
    # Perception config assumes full 6-deck shoe; it never sees fixture truth.
    assert sum(analysis["state"]["counts"]) == 309
    assert analysis["state"]["counts"] != list(sessions[identity].counts())


def test_early_surrender_analysis_is_prepeek_and_partial_has_no_best(client):
    identity = new_fixture(client, ["10", "10", "6", "A", "2"], surrender="early")
    state = client.post(f"/api/sessions/{identity}/deal", json={}).json()
    assert state["phase"] == "early_surrender" and not state["peek_resolved"]
    response = client.post(f"/api/sessions/{identity}/analyze", json={"timeout_ms": 10000}).json()
    assert response["state"]["peeked"] is False
    assert set(response["result"]["actions"]) == {"surrender", "continue"}
    assert response["result"]["actions"]["surrender"] == -.5
    assert response["result"]["best_action"] in (None, "surrender", "continue")
    assert set(response["generated_basic"]["actions"]) == {"surrender", "continue"}


def test_manual_perception_correction_is_audited(client):
    identity = new_fixture(client, ["2", "6", "8", "A", "10", "9", "3"])
    client.post(f"/api/sessions/{identity}/deal", json={})
    perceived = client.post(f"/api/sessions/{identity}/perception", json={}).json()
    card_id = next(identity for identity, card in perceived["state"]["cards"].items() if card["rank"] == "2")
    corrected = client.post(f"/api/sessions/{identity}/perception/correct",
                            json={"card_id": card_id, "rank": "3", "suit": "S", "reason": "User reviewed crop"})
    assert corrected.status_code == 200
    assert corrected.json()["event"]["kind"] == "STATE_CORRECTION"
    assert corrected.json()["state"]["cards"][card_id]["rank"] == "3"


def test_image_upload_and_invalid_inputs(client):
    from bjlab.datasets import render_table
    image = render_table([{"rank": "K", "suit": "H", "x": 100, "y": 300}])
    stream = io.BytesIO(); image.save(stream, "PNG")
    response = client.post("/api/vision/upload", json={"image_base64": base64.b64encode(stream.getvalue()).decode()})
    assert response.status_code == 200
    assert response.json()["detections"][0]["rank"] == "K"
    assert response.json()["frame_source"] == "uploaded-image"
    assert response.json()["input"] == "uploaded image pixels only"
    assert response.json()["deck_provenance"] == "unknown"
    assert response.json()["deck_estimation"]["mode"] == "INFERRED"
    assert response.json()["deck_estimation"]["certain"] is False
    assert response.json()["deck_estimation"]["decks"] is None
    assert response.json()["deck_estimation"]["observations"] == 1
    assert response.json()["state"]["decks"] is None
    assert response.json()["state"]["composition_remaining"] is None
    assert not response.json()["summary"]["gate"]["solver_allowed"]
    declared = client.post("/api/vision/upload", json={
        "image_base64": base64.b64encode(stream.getvalue()).decode(), "decks": 2})
    assert declared.status_code == 200
    assert declared.json()["state"]["decks"] == 2
    assert sum(declared.json()["state"]["composition_remaining"]) == 103
    assert declared.json()["deck_provenance"] == "explicit-upload-parameter"
    assert declared.json()["deck_estimation"]["mode"] == "KNOWN"
    assert declared.json()["deck_estimation"]["source"] == "explicit-upload-parameter"
    assert declared.json()["deck_estimation"]["decks"] == 2
    assert client.post("/api/vision/upload", json={"image_base64": "garbage"}).status_code == 422
    assert client.post("/api/vision/upload-video", content=b"garbage", headers={"content-type": "video/mp4"}).status_code == 422
    calibrated = client.post("/api/vision/upload", json={
        "image_base64": base64.b64encode(stream.getvalue()).decode(),
        "corners": [[0, 0], [959, 0], [959, 599], [0, 599]]})
    assert calibrated.status_code == 200
    assert calibrated.json()["source_detections"][0]["rank"] == "K"
    assert calibrated.json()["calibration"]["output_size"] == [960, 600]
    assert "controlled_metadata" in calibrated.json()


def test_video_metrics_measure_decoded_inputs_and_do_not_claim_stream_fps(client, tmp_path):
    import cv2
    import numpy as np
    from bjlab.datasets import render_table
    path = tmp_path / "fixture.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 12, (960, 600))
    if not writer.isOpened():
        pytest.skip("Local OpenCV backend has no MJPEG encoder")
    pixels = cv2.cvtColor(np.asarray(render_table([{"rank": "K", "suit": "H", "x": 100, "y": 300}])), cv2.COLOR_RGB2BGR)
    for _ in range(4):
        writer.write(pixels)
    writer.release()
    response = client.post("/api/vision/upload-video?stride=1", content=path.read_bytes(), headers={"content-type": "video/avi"})
    assert response.status_code == 200
    result = response.json()
    assert result["frame_source"] == "local-video"
    assert result["processed_frames"] == result["decoded_frames"] == 4
    assert result["sampled_out_frames"] == 0
    assert result["mean_frame_ms"] > 0 and result["p95_frame_ms"] > 0
    assert result["pipeline_fps"] > 0 and result["latency_ms"] > 0
    assert result["stream_fps"] is None and result["drop_count"] is None
    assert result["state"]["decks"] is None and result["state"]["composition_remaining"] is None
    assert not result["summary"]["gate"]["solver_allowed"]
    assert result["deck_provenance"] == "unknown"
    assert "single-round" in result["segmentation"]
    assert result["deck_estimation"]["observations"] == 1
    assert result["deck_estimation"]["certain"] is False
    assert sum(result["deck_estimation"]["posterior"].values()) == pytest.approx(1)
    assert result["frames"][0]["replay_state"]["counted_ids"] == []
    assert len(result["frames"][2]["replay_state"]["counted_ids"]) == 1
    assert result["frames"][0]["event_end_index"] < result["frames"][2]["event_end_index"]
    from PIL import Image
    from bjlab.events import EventLog
    journal = EventLog.from_dict({"schema_version": 1, "events": result["events"]})
    for item in result["frames"]:
        thumbnail = Image.open(io.BytesIO(base64.b64decode(item["image_base64"])))
        assert thumbnail.format == "JPEG" and thumbnail.size == (480, 300)
        assert (item["frame_width"], item["frame_height"]) == (960, 600)
        assert (item["preview_width"], item["preview_height"]) == thumbnail.size
        assert item["replay_state"]["event_index"] == item["event_end_index"]
        assert journal.replay(to_index=item["event_end_index"]).to_dict() == item["replay_state"]
        assert all(event["index"] <= item["event_end_index"] for event in item["events"])
    declared = client.post("/api/vision/upload-video?stride=1&decks=2", content=path.read_bytes(),
                           headers={"content-type": "video/avi"}).json()
    assert declared["state"]["decks"] == 2
    assert declared["deck_provenance"] == "explicit-video-parameter"
    disabled = client.post("/api/vision/upload-video?stride=1&thumbnails=false", content=path.read_bytes(),
                           headers={"content-type": "video/avi"}).json()
    assert all(item["image_base64"] is None for item in disabled["frames"])


def test_counting_comparison_and_experiment_contract(client):
    systems = client.get("/api/counting/systems").json()["systems"]
    assert {system["name"] for system in systems} >= {"Hi-Lo", "KO", "Hi-Opt I", "Hi-Opt II", "Omega II", "Zen"}
    response = client.post("/api/counting/compare", json={"cards": ["2", "3", "A"], "decks": 6})
    assert response.status_code == 200
    assert response.json()["systems"]["Hi-Lo"]["running_count"] == 1
    custom = client.post("/api/counting/custom", json={"name": "Research", "tags": [-1,1,1,1,1,1,0,0,0,-1], "cards": ["2", "A"]})
    assert custom.status_code == 200
    assert custom.json()["counter"]["running_count"] == 0
    assert client.post("/api/counting/custom", json={"tags": [1]*10}).status_code == 422
    experiment = client.post("/api/experiments", json={"rounds": 20, "seed": 2, "regret_samples": 0})
    assert experiment.status_code == 200
    assert experiment.json()["completed_rounds"] == 20
    assert "ci95" in experiment.json()["results"]["basic"]
    assert client.post("/api/experiments", json={"policies": ["invalid"]}).status_code == 422
