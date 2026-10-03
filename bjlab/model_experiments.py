"""Optional System One phase-classification experiments, isolated from strategy.

No imports of torch, Laya, TypeSafe or core solver are needed for the baseline.
External dependencies, weights and credentials are verified lazily. Missing
models are unavailable, never successful benchmark results.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Any, Iterable, Mapping, Protocol
from types import MappingProxyType

PHASES = ("DEALING", "PLAYER_TURN", "DEALER_TURN", "ROUND_END", "SHUFFLING", "UNCERTAIN")
CRITERIA = {
    "DEALING": "Initial visible cards are being distributed; the initial hand is incomplete.",
    "PLAYER_TURN": "The player has an initial hand and visible enabled player action buttons.",
    "DEALER_TURN": "Player actions have stopped and the dealer is revealing or drawing cards.",
    "ROUND_END": "A visible result announces a completed round, with deal/reset controls.",
    "SHUFFLING": "Visible shuffle/reset evidence shows a new shoe or active shuffling.",
    "UNCERTAIN": "The observations are incomplete, unreliable or contradictory; no phase is justified.",
}
INSTRUCTIONS = ("Classify the current blackjack workflow phase using only the provided observed cards, "
                "visible button labels, observed text and motion. Never recommend a playing or betting "
                "action. Select UNCERTAIN when evidence is unreliable or contradictory.")


class ModelUnavailable(RuntimeError):
    """Dependency, credentials or locally permitted weights are absent."""


class ModelContractError(ValueError):
    """A model returned a phase or distribution outside the declared contract."""


@dataclass(frozen=True)
class ObservedCard:
    rank: str | None
    suit: str | None
    zone: str
    score: float
    face_down: bool = False

    def __post_init__(self) -> None:
        if self.rank is not None and self.rank not in {"A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"}:
            raise ValueError("Invalid observed rank")
        if self.suit is not None and self.suit not in {"S", "H", "D", "C"}:
            raise ValueError("Invalid observed suit")
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise ValueError("Observation scores must be finite in [0,1]")
        if self.face_down and (self.rank is not None or self.suit is not None):
            raise ValueError("Hidden card truth cannot be included in model observations")


@dataclass(frozen=True)
class PhaseObservation:
    cards: tuple[ObservedCard, ...] = ()
    buttons: tuple[str, ...] = ()
    text: str = ""
    motion_score: float = 0
    integrity_issues: tuple[str, ...] = ()
    previous_visible_cards: int | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.motion_score) or not 0 <= self.motion_score <= 1:
            raise ValueError("Motion score must be a finite normalized observable")
        if self.previous_visible_cards is not None and (type(self.previous_visible_cards) is not int or self.previous_visible_cards < 0):
            raise ValueError("Previous visible card count must be nonnegative")
        if not isinstance(self.text, str) or len(self.text) > 12000:
            raise ValueError("Observed text must be a string of at most 12000 characters")
        if any(not isinstance(button, str) for button in self.buttons):
            raise ValueError("Button labels must be strings")

    def to_dict(self) -> dict[str, Any]:
        return {"cards": [asdict(card) for card in self.cards], "buttons": list(self.buttons),
                "text": self.text, "motion_score": self.motion_score,
                "integrity_issues": list(self.integrity_issues),
                "previous_visible_cards": self.previous_visible_cards}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PhaseObservation":
        allowed = {"cards", "buttons", "text", "motion_score", "integrity_issues", "previous_visible_cards"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Non-observable or unknown fields are not allowed: {sorted(unknown)}")
        cards = tuple(ObservedCard(**card) for card in data.get("cards", []))
        return cls(cards, tuple(data.get("buttons", [])), data.get("text", ""),
                   float(data.get("motion_score", 0)), tuple(data.get("integrity_issues", [])),
                   data.get("previous_visible_cards"))


def observation_from_perception(detections: Iterable[Any], *, buttons: Iterable[str] = (),
                                observed_text: str = "", motion_score: float = 0,
                                integrity_issues: Iterable[str] = (),
                                previous_visible_cards: int | None = None) -> PhaseObservation:
    """Build from detector/temporal observations; this function accepts no truth state."""
    cards = []
    for detection in detections:
        data = detection.to_dict() if hasattr(detection, "to_dict") else dict(detection)
        cards.append(ObservedCard(data.get("rank"), data.get("suit"), data.get("zone", "unknown"),
                                  float(data.get("score", 0)), bool(data.get("face_down", False))))
    return PhaseObservation(tuple(cards), tuple(buttons), observed_text, motion_score,
                            tuple(integrity_issues), previous_visible_cards)


@dataclass(frozen=True)
class PhasePrediction:
    phase: str
    probabilities: Mapping[str, float]
    model: str
    reported_confidence: float | None = None
    probability_semantics: str = "unvalidated_on_blackjack_phase_data"

    def __post_init__(self) -> None:
        if self.phase not in PHASES or set(self.probabilities) != set(PHASES):
            raise ModelContractError("Model must return a declared phase and all six probabilities")
        if any(type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1
               for value in self.probabilities.values()):
            raise ModelContractError("Phase probabilities must be finite values in [0,1]")
        if not math.isclose(sum(self.probabilities.values()), 1, abs_tol=1e-4):
            raise ModelContractError("Phase probabilities must sum to one; invalid output is not silently normalized")
        if self.probabilities[self.phase] < max(self.probabilities.values()) - 1e-6:
            raise ModelContractError("Selected phase is not a maximum-probability option")
        if self.reported_confidence is not None and (not math.isfinite(self.reported_confidence) or not 0 <= self.reported_confidence <= 1):
            raise ModelContractError("Reported confidence must be finite in [0,1]")
        object.__setattr__(self, "probabilities", MappingProxyType(dict(self.probabilities)))

    @property
    def selected_probability(self) -> float:
        return float(self.probabilities[self.phase])

    def to_dict(self) -> dict[str, Any]:
        return {"phase": self.phase, "probabilities": dict(self.probabilities), "model": self.model,
                "reported_confidence": self.reported_confidence,
                "selected_probability": self.selected_probability,
                "probability_semantics": self.probability_semantics}


class PhaseClassifier(Protocol):
    name: str
    def predict(self, observation: PhaseObservation) -> PhasePrediction: ...


class DeterministicPhaseBaseline:
    name = "deterministic_phase_baseline_v1"

    def predict(self, observation: PhaseObservation) -> PhasePrediction:
        o = observation
        text = o.text.lower()
        buttons = {b.upper() for b in o.buttons}
        actions = buttons & {"HIT", "STAND", "DOUBLE", "SPLIT", "SURRENDER"}
        player = [card for card in o.cards if card.zone.startswith("player")]
        dealer = [card for card in o.cards if card.zone == "dealer"]
        bad = bool(o.integrity_issues) or any(card.score < .8 for card in o.cards)
        shuffle = any(token in text for token in ("shuffling", "new shoe", "shuffle in progress")) and "not shuffling" not in text
        finished = any(token in text for token in ("round complete", "round ended", "player wins", "dealer wins", "push", "payout"))
        dealer_active = any(token in text for token in ("dealer draws", "dealer reveals", "dealer turn", "dealer drawing"))
        contradictory = (finished and bool(actions)) or (dealer_active and bool(actions)) or (shuffle and bool(actions))
        if bad or contradictory:
            phase = "UNCERTAIN"
        elif shuffle:
            phase = "SHUFFLING"
        elif finished:
            phase = "ROUND_END"
        elif len(player) >= 2 and dealer and actions:
            phase = "PLAYER_TURN"
        elif dealer_active and len(player) >= 2 and dealer:
            phase = "DEALER_TURN"
        elif o.cards and (len(player) < 2 or not dealer) and o.motion_score > .1:
            phase = "DEALING"
        else:
            phase = "UNCERTAIN"
        return PhasePrediction(phase, {p: float(p == phase) for p in PHASES}, self.name,
                               probability_semantics="deterministic_one_hot; empirical calibration not assumed")


def _parse_choice(answer: Any, *, model: str) -> PhasePrediction:
    if hasattr(answer, "model_dump"):
        answer = answer.model_dump()
    elif not isinstance(answer, Mapping):
        answer = {"choice": getattr(answer, "choice", None),
                  "probabilities": getattr(answer, "probabilities", None),
                  "confidence": getattr(answer, "confidence", None)}
    if not isinstance(answer.get("probabilities"), Mapping):
        raise ModelContractError("Choice answer has no probability mapping")
    return PhasePrediction(answer.get("choice"), dict(answer["probabilities"]), model,
                           answer.get("confidence"))


class LayaPhaseAdapter:
    """Real optional laya.load(...).predict(...) adapter, never imported by core."""
    name = "laya_phase"

    def __init__(self, *, checkpoint: str = "convaiinnovations/laya", allow_download: bool = False,
                 local_checkpoint: str | Path | None = None) -> None:
        self.checkpoint = checkpoint
        self.allow_download = allow_download
        self.local_checkpoint = str(local_checkpoint) if local_checkpoint is not None else None
        self._agent: Any = None

    def _load(self) -> Any:
        if self._agent is None:
            if importlib.util.find_spec("laya") is None:
                raise ModelUnavailable("Optional laya package is not installed")
            if self.local_checkpoint is None and not self.allow_download:
                raise ModelUnavailable("Laya weights need a local checkpoint or explicit --allow-download")
            if self.local_checkpoint is not None and not Path(self.local_checkpoint).is_dir():
                raise ModelUnavailable("Configured local Laya checkpoint directory is missing")
            sdk = importlib.import_module("laya")
            self._agent = sdk.load(self.local_checkpoint or self.checkpoint)
        return self._agent

    def predict(self, observation: PhaseObservation) -> PhasePrediction:
        agent = self._load()
        result = agent.predict(observation.to_dict(), {"phase": {"type": "choice",
                               "instructions": INSTRUCTIONS, "criteria": dict(CRITERIA)}})
        try:
            answer = result["answers"]["phase"]
        except (KeyError, TypeError) as exc:
            raise ModelContractError("Laya response lacks answers.phase") from exc
        return _parse_choice(answer, model=f"laya:{self.checkpoint}")


class JevPhaseAdapter:
    """Official TypeSafe SDK adapter. Credentials are read only from the environment."""
    name = "jev_phase"

    def __init__(self, *, model: str | None = None, allow_network: bool = False,
                 timeout_seconds: float = 20) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Network timeout must be positive and finite")
        self.model, self.allow_network, self.timeout_seconds = model, allow_network, timeout_seconds
        self._client: Any = None

    def _load(self) -> Any:
        if self._client is None:
            if not self.allow_network:
                raise ModelUnavailable("Jev inference requires explicit --allow-network")
            if not os.environ.get("TYPESAFE_API_KEY", "").strip():
                raise ModelUnavailable("TYPESAFE_API_KEY is absent; no request was made")
            if importlib.util.find_spec("typesafe_sdk") is None:
                raise ModelUnavailable("Optional typesafe-sdk package is not installed")
            sdk = importlib.import_module("typesafe_sdk")
            # SDK defaults use the documented official service. No third-party gateway.
            self._client = sdk.TypeSafeClient(model=self.model, timeout=self.timeout_seconds)
        return self._client

    def predict(self, observation: PhaseObservation) -> PhasePrediction:
        result = self._load().system_one(state=observation.to_dict(), questions={"phase": {
            "type": "choice", "instructions": INSTRUCTIONS, "criteria": dict(CRITERIA)}})
        try:
            answer = result.choices["phase"]
        except (KeyError, AttributeError, TypeError) as exc:
            raise ModelContractError("TypeSafe response lacks choices.phase") from exc
        return _parse_choice(answer, model=f"jev:{getattr(result, 'model', self.model or 'service_default')}")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def _sample_observation(phase: str, rng: random.Random, variant: int) -> PhaseObservation:
    ranks = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K")
    suits = ("S", "H", "D", "C")
    def card(zone: str, hidden: bool = False, score: float = .97) -> ObservedCard:
        return ObservedCard(None if hidden else rng.choice(ranks), None if hidden else rng.choice(suits),
                            zone, score, hidden)
    if phase == "DEALING":
        return PhaseObservation((card("dealer"), card("player:0")), (),
                                rng.choice(("Cards are being distributed", "Initial cards incoming", "Dealing cards")), .65)
    if phase == "PLAYER_TURN":
        return PhaseObservation((card("dealer"), card("dealer", True), card("player:0"), card("player:0")),
                                ("HIT", "STAND", "DOUBLE"), rng.choice(("Your turn", "Choose an action", "Player hand ready")), .02)
    if phase == "DEALER_TURN":
        return PhaseObservation((card("dealer"), card("dealer"), card("player:0"), card("player:0")), (),
                                rng.choice(("Dealer draws", "Dealer reveals the hole card", "Dealer drawing")), .45)
    if phase == "ROUND_END":
        return PhaseObservation((card("dealer"), card("dealer"), card("player:0"), card("player:0")), ("DEAL",),
                                rng.choice(("Round complete", "Player wins", "Push — payout 0")), .02)
    if phase == "SHUFFLING":
        return PhaseObservation((), ("NEW SHOE",), rng.choice(("Shuffling", "New shoe", "Shuffle in progress")), .9,
                                previous_visible_cards=4)
    if variant % 3 == 0:
        return PhaseObservation((card("player:0", score=.55),), (), "No readable status", .03,
                                ("unconfirmed card",))
    if variant % 3 == 1:
        return PhaseObservation((card("dealer"), card("player:0"), card("player:0")), ("HIT", "STAND"),
                                "Round complete but action controls still visible", .02)
    return PhaseObservation((), (), "", 0)


def generate_phase_dataset(path: str | Path, *, sessions: int = 20, variants: int = 3,
                           seed: int = 17) -> list[dict[str, Any]]:
    """Generate seeded synthetic OBSERVABLE-feature fixtures, not image benchmarks."""
    if sessions < 3 or variants < 1:
        raise ValueError("Need at least three sessions and one variant")
    rng = random.Random(seed)
    records = []
    train_end, calibration_end = max(1, int(sessions * .6)), max(2, int(sessions * .8))
    for session in range(sessions):
        split = "train" if session < train_end else "calibration" if session < calibration_end else "test"
        sid = f"phase-session-{session:04d}"
        for variant in range(variants):
            order = list(PHASES)
            rng.shuffle(order)
            for phase in order:
                observation = _sample_observation(phase, rng, variant)
                records.append({"schema_version": 1, "case_id": f"{sid}-{variant}-{phase}",
                                "session_id": sid, "split": split,
                                "observation": observation.to_dict(), "label": phase,
                                "source": "synthetic_observable_feature_fixture", "seed": seed})
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(json.dumps(row, sort_keys=True, allow_nan=False) for row in records) + "\n",
                      encoding="utf-8")
    return records


def load_phase_dataset(path: str | Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    seen_cases, sessions = set(), {}
    for row in rows:
        if row.get("schema_version") != 1 or row.get("label") not in PHASES:
            raise ValueError("Unsupported phase dataset schema or label")
        if row.get("split") not in {"train", "calibration", "test"}:
            raise ValueError("Invalid phase dataset split")
        if row["case_id"] in seen_cases:
            raise ValueError("Duplicate experiment case ID")
        seen_cases.add(row["case_id"])
        if row["session_id"] in sessions and sessions[row["session_id"]] != row["split"]:
            raise ValueError("Phase dataset has session leakage")
        sessions[row["session_id"]] = row["split"]
        PhaseObservation.from_dict(row["observation"])
    return rows


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    location = (len(values) - 1) * percentile / 100
    low, high = math.floor(location), math.ceil(location)
    return values[low] + (values[high] - values[low]) * (location - low)


def classification_metrics(predictions: Iterable[PhasePrediction], labels: Iterable[str],
                           *, bins: int = 10) -> dict[str, Any]:
    predictions, labels = list(predictions), list(labels)
    if len(predictions) != len(labels) or any(label not in PHASES for label in labels) or bins < 2:
        raise ValueError("Metrics need aligned predictions/valid labels and at least two bins")
    if not predictions:
        return {"samples": 0, "accuracy": None, "brier_score": None, "ece": None, "nll": None}
    correct = [prediction.phase == label for prediction, label in zip(predictions, labels)]
    brier = sum(sum((prediction.probabilities[p] - float(p == label)) ** 2 for p in PHASES)
                for prediction, label in zip(predictions, labels)) / len(predictions)
    # Multiclass Brier is sum over classes (range 0..2), not divided by six.
    buckets = defaultdict(list)
    for prediction, good in zip(predictions, correct):
        index = min(bins - 1, int(prediction.selected_probability * bins))
        buckets[index].append((prediction.selected_probability, good))
    ece = sum(len(group) / len(predictions) * abs(sum(p for p, _ in group) / len(group) -
                                               sum(good for _, good in group) / len(group))
              for group in buckets.values())
    confusion = {label: {predicted: 0 for predicted in PHASES} for label in PHASES}
    for prediction, label in zip(predictions, labels):
        confusion[label][prediction.phase] += 1
    return {"samples": len(predictions), "accuracy": sum(correct) / len(predictions),
            "brier_score": brier, "brier_definition": "mean sum across six classes; range 0..2",
            "ece": ece, "ece_bins": bins,
            "nll": -sum(math.log(max(1e-15, prediction.probabilities[label]))
                        for prediction, label in zip(predictions, labels)) / len(predictions),
            "confusion": confusion,
            "probability_calibration": "empirical result on this split only; no prior domain guarantee"}


def run_phase_benchmark(dataset: str | Path, classifier: PhaseClassifier, *, split: str = "test",
                        warmup: int = 0) -> dict[str, Any]:
    records = [row for row in load_phase_dataset(dataset) if row["split"] == split]
    if not records:
        return {"schema_version": 1, "status": "unavailable", "model": classifier.name,
                "reason": "Selected split has no cases", "cases": 0, "metrics": None}
    if warmup < 0:
        raise ValueError("Warmup must be nonnegative")
    predictions, labels, latencies, rows, failures = [], [], [], [], []
    try:
        for i in range(warmup):
            classifier.predict(PhaseObservation.from_dict(records[i % len(records)]["observation"]))
    except ModelUnavailable as exc:
        return {"schema_version": 1, "status": "unavailable", "model": classifier.name,
                "reason": str(exc), "cases": len(records), "completed": 0, "metrics": None,
                "failures": [], "warmup": warmup}
    except Exception as exc:
        return {"schema_version": 1, "status": "failed", "model": classifier.name,
                "reason": "Warmup failed before measured inference", "cases": len(records),
                "completed": 0, "metrics": None,
                "failures": [{"kind": "inference_error", "error_type": type(exc).__name__}],
                "warmup": warmup}
    for record in records:
        # Pass only the observable subobject, never row['label'] or the dataset row.
        observation = PhaseObservation.from_dict(record["observation"])
        started = time.perf_counter()
        try:
            prediction = classifier.predict(observation)
            elapsed = (time.perf_counter() - started) * 1000
            predictions.append(prediction)
            labels.append(record["label"])
            latencies.append(elapsed)
            rows.append({"case_id": record["case_id"], "label": record["label"],
                         "prediction": prediction.to_dict(), "latency_ms": elapsed,
                         "correct": prediction.phase == record["label"]})
            if prediction.phase != record["label"]:
                failures.append({"case_id": record["case_id"], "kind": "misclassification",
                                 "label": record["label"], "predicted": prediction.phase})
        except ModelUnavailable as exc:
            return {"schema_version": 1, "status": "unavailable", "model": classifier.name,
                    "reason": str(exc), "cases": len(records), "completed": len(predictions),
                    "metrics": None, "failures": failures, "warmup": warmup}
        except Exception as exc:
            # SDK exceptions can include request bodies/keys. Record type only.
            failures.append({"case_id": record["case_id"], "kind": "inference_error",
                             "error_type": type(exc).__name__})
    error_count = sum(f["kind"] == "inference_error" for f in failures)
    report = {"schema_version": 1, "status": "completed" if not error_count else "partial_failure",
              "model": classifier.name, "split": split, "cases": len(records), "completed": len(predictions),
              "failure_rate": error_count / len(records), "warmup": warmup,
              "latency_ms_p50": _percentile(latencies, 50), "latency_ms_p95": _percentile(latencies, 95),
              "metrics": classification_metrics(predictions, labels),
              "failures": failures, "case_results": rows,
              "accuracy_all_cases": sum(row["correct"] for row in rows) / len(records),
              "scope": "phase only; synthetic observed-feature fixtures; never blackjack strategy",
              "cold_start_included": warmup == 0}
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optional Blackjack System One phase experiments")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("dataset")
    generate.add_argument("--sessions", type=int, default=20)
    generate.add_argument("--variants", type=int, default=3)
    generate.add_argument("--seed", type=int, default=17)
    run = subparsers.add_parser("run")
    run.add_argument("dataset")
    run.add_argument("--model", choices=("baseline", "laya", "jev"), default="baseline")
    run.add_argument("--split", choices=("train", "calibration", "test"), default="test")
    run.add_argument("--warmup", type=int, default=0)
    run.add_argument("--allow-download", action="store_true")
    run.add_argument("--allow-network", action="store_true")
    run.add_argument("--local-checkpoint")
    run.add_argument("--checkpoint", default="convaiinnovations/laya")
    run.add_argument("--jev-model")
    run.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "generate":
        records = generate_phase_dataset(args.dataset, sessions=args.sessions, variants=args.variants, seed=args.seed)
        print(json.dumps({"status": "generated", "cases": len(records), "path": args.dataset}))
        return 0
    classifier: PhaseClassifier
    if args.model == "baseline":
        classifier = DeterministicPhaseBaseline()
    elif args.model == "laya":
        classifier = LayaPhaseAdapter(checkpoint=args.checkpoint, allow_download=args.allow_download,
                                     local_checkpoint=args.local_checkpoint)
    else:
        classifier = JevPhaseAdapter(model=args.jev_model, allow_network=args.allow_network)
    try:
        report = run_phase_benchmark(args.dataset, classifier, split=args.split, warmup=args.warmup)
    finally:
        if isinstance(classifier, JevPhaseAdapter):
            classifier.close()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "model": report["model"], "report": str(target)}))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
