import json
from types import SimpleNamespace

import pytest

from bjlab import model_experiments as experiment
from bjlab.model_experiments import (PHASES, CRITERIA, PhaseObservation, ObservedCard,
                                    PhasePrediction, DeterministicPhaseBaseline,
                                    ModelContractError, ModelUnavailable,
                                    LayaPhaseAdapter, JevPhaseAdapter,
                                    generate_phase_dataset, load_phase_dataset,
                                    run_phase_benchmark, classification_metrics,
                                    observation_from_perception)


def prediction(phase, model="test"):
    return PhasePrediction(phase, {p: float(p == phase) for p in PHASES}, model)


def test_seeded_feature_dataset_is_balanced_and_sessions_disjoint(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    first = generate_phase_dataset(a, sessions=10, variants=3, seed=42)
    second = generate_phase_dataset(b, sessions=10, variants=3, seed=42)
    assert first == second and a.read_bytes() == b.read_bytes()
    assert len(first) == 180
    assert load_phase_dataset(a) == first
    seen = {}
    for row in first:
        assert seen.setdefault(row["session_id"], row["split"]) == row["split"]
        assert "label" not in row["observation"] and "phase" not in row["observation"]
    report = run_phase_benchmark(a, DeterministicPhaseBaseline())
    assert report["status"] == "completed"
    assert report["completed"] == report["cases"] == 36
    assert report["metrics"]["accuracy"] == 1
    assert report["metrics"]["brier_score"] == 0
    assert report["latency_ms_p95"] >= report["latency_ms_p50"] >= 0


def test_state_truth_and_hidden_values_cannot_enter_phase_model():
    with pytest.raises(ValueError, match="Non-observable"):
        PhaseObservation.from_dict({"cards": [], "phase": "PLAYER_TURN"})
    with pytest.raises(ValueError, match="Hidden card truth"):
        ObservedCard("A", "S", "dealer", .99, True)
    observation = observation_from_perception([{"rank": "A", "suit": "S", "zone": "dealer", "score": .98,
                                                "card_id": "not-transferred", "bbox": [0, 0, 78, 110]}],
                                             buttons=["STAND"], observed_text="Your turn")
    assert observation.cards[0].rank == "A"
    assert "card_id" not in observation.to_dict()["cards"][0]


def test_multiclass_metrics_include_overconfident_errors():
    report = classification_metrics([prediction("DEALING"), prediction("PLAYER_TURN")],
                                    ["DEALING", "ROUND_END"])
    assert report["accuracy"] == .5
    assert report["brier_score"] == 1
    assert report["ece"] == .5
    assert report["confusion"]["ROUND_END"]["PLAYER_TURN"] == 1
    assert report["nll"] > 0


@pytest.mark.parametrize("probabilities", [
    {p: .1 for p in PHASES},
    {p: float("nan") if p == "UNCERTAIN" else .2 for p in PHASES},
    {"PLAYER_TURN": 1},
    {p: True if p == "UNCERTAIN" else 0 for p in PHASES},
])
def test_invalid_probabilities_are_rejected_without_repair(probabilities):
    with pytest.raises(ModelContractError):
        PhasePrediction("UNCERTAIN", probabilities, "invalid")


def test_laya_adapter_matches_official_predict_contract_without_live_dependency(monkeypatch):
    calls = []
    class Agent:
        def predict(self, state, questions):
            calls.append((state, questions))
            return {"answers": {"phase": {"choice": "UNCERTAIN", "confidence": .9,
                                            "probabilities": {p: float(p == "UNCERTAIN") for p in PHASES}}}}
    monkeypatch.setattr(experiment.importlib.util, "find_spec", lambda name: object())
    def fake_import(name):
        assert name == "laya"
        return SimpleNamespace(load=lambda checkpoint: Agent())
    monkeypatch.setattr(experiment.importlib, "import_module", fake_import)
    adapter = LayaPhaseAdapter(allow_download=True)
    result = adapter.predict(PhaseObservation())
    assert result.phase == "UNCERTAIN"
    assert calls[0][1]["phase"]["criteria"] == CRITERIA
    assert calls[0][1]["phase"]["type"] == "choice"
    assert "label" not in calls[0][0] and "phase" not in calls[0][0]


def test_jev_adapter_matches_official_system_one_typed_response_without_network(monkeypatch):
    calls, closed = [], []
    class Client:
        def __init__(self, **kwargs):
            assert "api_key" not in kwargs
            calls.append(kwargs)
        def system_one(self, *, state, questions):
            assert questions["phase"]["criteria"] == CRITERIA
            assert "label" not in state
            return SimpleNamespace(model="contract-test", choices={"phase": SimpleNamespace(
                choice="UNCERTAIN", confidence=.8,
                probabilities={p: float(p == "UNCERTAIN") for p in PHASES})})
        def close(self):
            closed.append(True)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-not-a-live-key")
    monkeypatch.setattr(experiment.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(experiment.importlib, "import_module", lambda name: SimpleNamespace(TypeSafeClient=Client))
    adapter = JevPhaseAdapter(model="contract-test", allow_network=True)
    result = adapter.predict(PhaseObservation())
    assert result.phase == "UNCERTAIN" and result.model == "jev:contract-test"
    assert calls == [{"model": "contract-test", "timeout": 20}]
    adapter.close()
    assert closed


def test_missing_models_and_credentials_are_unavailable_not_passed(monkeypatch, tmp_path):
    path = tmp_path / "data.jsonl"
    generate_phase_dataset(path, sessions=3, variants=1)
    monkeypatch.setattr(experiment.importlib.util, "find_spec", lambda name: None)
    laya = run_phase_benchmark(path, LayaPhaseAdapter())
    assert laya["status"] == "unavailable" and laya["metrics"] is None
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    jev = run_phase_benchmark(path, JevPhaseAdapter(allow_network=True))
    assert jev["status"] == "unavailable" and jev["completed"] == 0
    assert jev["metrics"] is None and "TYPESAFE_API_KEY" in jev["reason"]


def test_inference_failure_penalizes_all_cases_and_never_leaks_exception_secret(tmp_path):
    path = tmp_path / "data.jsonl"
    generate_phase_dataset(path, sessions=3, variants=1)
    class FailingModel:
        name = "failing"
        def predict(self, observation):
            raise RuntimeError("sensitive-credential-must-not-be-in-report")
    report = run_phase_benchmark(path, FailingModel())
    assert report["status"] == "partial_failure" and report["failure_rate"] == 1
    assert report["accuracy_all_cases"] == 0 and report["metrics"]["accuracy"] is None
    assert "sensitive-credential" not in json.dumps(report)
    warmup_report = run_phase_benchmark(path, FailingModel(), warmup=1)
    assert warmup_report["status"] == "failed" and warmup_report["metrics"] is None
    assert "sensitive-credential" not in json.dumps(warmup_report)


def test_dataset_session_leakage_is_blocked(tmp_path):
    path = tmp_path / "data.jsonl"
    rows = generate_phase_dataset(path, sessions=3, variants=1)
    rows[0]["split"] = "test"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="session leakage"):
        load_phase_dataset(path)
