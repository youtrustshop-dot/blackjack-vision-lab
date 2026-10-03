"""Independent reference adapters. References are optional development tools.

An unavailable, unsupported, or unexecuted comparison is never a passing check.
No reference source is copied into the runtime or installed by these adapters.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
from typing import Any, Iterable

from .engine import Rules, card_rank, hand_value, initial_counts, legal_actions

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "validation" / "references" / "manifest.json"
GOLDENS = ROOT / "validation" / "reference_engines" / "golden_cases.json"
ACTION_CODES = {"hit": "+", "stand": "=", "double": "D", "split": "V", "surrender": "#"}


class UnsupportedReference(ValueError):
    """The reference cannot represent the requested mathematical experiment."""


class ReferenceExecutionError(RuntimeError):
    """The reference ran but its output or configuration was not valid."""


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _load_json(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def load_manifest(path: str | Path = MANIFEST) -> dict:
    data = _load_json(path)
    if data.get("schema_version") != 1 or not isinstance(data.get("references"), list):
        raise ValueError("unsupported reference manifest")
    seen = set()
    for entry in data["references"]:
        repository, commit = entry.get("repository"), entry.get("commit")
        if not isinstance(repository, str) or repository in seen:
            raise ValueError("invalid or duplicate reference repository")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit) or commit == "0" * 40:
            raise ValueError(f"reference {repository} is not pinned to a real commit")
        seen.add(repository)
    return data


def _pin(repository: str, manifest_path: str | Path = MANIFEST) -> dict:
    entries = [e for e in load_manifest(manifest_path)["references"] if e["repository"] == repository]
    if len(entries) != 1:
        raise ValueError(f"missing pin for {repository}")
    return entries[0]


def reference_catalog(manifest_path: str | Path = MANIFEST) -> dict:
    entries = load_manifest(manifest_path)["references"]
    executable = {"kevin-lesenechal/freebj": "freebj-cli", "hhoppe/blackjack": "hhoppe-offline-python"}
    return {"schema_version": 1, "references": [dict(e, adapter=executable.get(e["repository"], "external-output-file"),
            installed_by_application=False, validation_status="not_executed") for e in entries],
            "golden_model": "infinite-shoe-dp", "golden_cases": str(GOLDENS)}


def _checkout_provenance(checkout: str | Path, pin: dict, timeout: float = 10) -> dict:
    folder = Path(checkout).resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"reference checkout missing: {folder}")
    def git(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(folder), *args], capture_output=True,
                                text=True, timeout=timeout, shell=False)
        if result.returncode:
            raise ReferenceExecutionError(result.stderr.strip() or "git verification failed")
        return result.stdout.strip()
    revision = git("rev-parse", "HEAD")
    if revision != pin["commit"]:
        raise UnsupportedReference(f"checkout revision {revision} differs from pin {pin['commit']}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise UnsupportedReference("reference checkout has modified tracked files")
    return {"repository": pin["repository"], "revision": revision, "checkout": str(folder),
            "revision_verified": True, "tracked_tree_clean": True, "license": pin.get("license")}


def _sha256(path: str | Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def freebj_rule_mapping(rules: Rules, *, fresh_shoe: bool = False) -> dict:
    """Map only rules that the pinned FreeBJ code can express independently."""
    if rules.blackjack_payout != 1.5:
        raise UnsupportedReference("FreeBJ pinned CLI fixes blackjack payout at 3:2")
    if not rules.enhc and not rules.dealer_peek:
        raise UnsupportedReference("FreeBJ AHC always checks dealer blackjack before player turns")
    if rules.enhc and rules.enhc_loss != "all":
        raise UnsupportedReference("FreeBJ has no ENHC original-bet-only option")
    if rules.enhc and rules.surrender == "late":
        raise UnsupportedReference("FreeBJ rejects late surrender with ENHC")
    max_hands = rules.max_split_hands if rules.resplit else min(2, rules.max_split_hands)
    if max_hands > 2 and rules.resplit_aces != rules.hit_split_aces:
        raise UnsupportedReference("FreeBJ cannot set ace resplitting independently of playing split aces")
    penetration = 1 if fresh_shoe else max(1, int(52 * rules.decks * rules.penetration))
    double_flags = {"any": "--db-any2", "9-11": "--db-hard-9-11", "10-11": "--db-hard-10-11", "none": "--db-none"}
    double_names = {"any": "any_two", "9-11": "hard_9_to_11", "10-11": "hard_10_to_11", "none": "no_double"}
    surrender_flags = {"none": "--no-surr", "early": "--esurr", "late": "--lsurr"}
    surrender_names = {"none": "no_surrender", "early": "early_surrender", "late": "late_surrender"}
    argv = ["--enhc" if rules.enhc else "--ahc", "--h17" if rules.hit_soft17 else "--s17",
            "--das" if rules.double_after_split else "--no-das", double_flags[rules.double_rule],
            surrender_flags[rules.surrender], "--playAA" if rules.hit_split_aces else "--no-playAA",
            "--max-splits", str(max_hands), "-d", str(rules.decks), "-p", str(penetration), "-b", "1"]
    expected = {"game_type": "enhc" if rules.enhc else "ahc", "soft17": "h17" if rules.hit_soft17 else "s17",
                "das": rules.double_after_split, "bj_pays": 1.5, "double_down": double_names[rules.double_rule],
                "surrender": surrender_names[rules.surrender], "play_ace_pairs": rules.hit_split_aces,
                "max_splits": max_hands, "decks": rules.decks, "penetration_cards": penetration}
    return {"argv": argv, "expected_rules": expected, "fresh_shoe_each_round": fresh_shoe,
            "native_split_deal_order_matches": False,
            "limitations": ["FreeBJ deals both split replacement cards before the first continuation.",
                            "Forced first action uses FreeBJ chart continuation, not native optimal continuation.",
                            "FreeBJ has no RNG seed flag in the pinned CLI."]}


def parse_freebj_output(raw: str, *, metadata_only: bool = False) -> dict:
    try:
        output = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ReferenceExecutionError("FreeBJ stdout is not one JSON document") from exc
    if not isinstance(output, dict) or not isinstance(output.get("rules"), dict):
        raise ReferenceExecutionError("FreeBJ JSON lacks rule echo")
    if "ev" in output and not metadata_only:
        try:
            _number(output["ev"], "ev")
            sd = _number(output.get("stddev"), "stddev")
            _positive_int(output.get("rounds"), "rounds")
            if sd < 0:
                raise ValueError("negative stddev")
        except ValueError as exc:
            raise ReferenceExecutionError(str(exc)) from exc
    return output


def verify_freebj_rules(output: dict, expected: dict) -> None:
    actual = output.get("rules", {})
    mismatches = {key: {"expected": value, "actual": actual.get(key)} for key, value in expected.items()
                  if key not in actual or type(actual[key]) is not type(value) and not (
                      isinstance(value, float) and isinstance(actual[key], (int, float)) and not isinstance(actual[key], bool))
                  or actual.get(key) != value}
    if mismatches:
        raise ReferenceExecutionError("FreeBJ rule mismatch: " + json.dumps(mismatches, sort_keys=True))


def independent_batch_statistics(values: Iterable[float]) -> dict:
    """Student-t interval over independent, equal-size batch means, not rounds."""
    means = [_number(v, "batch EV") for v in values]
    if len(means) < 2:
        raise ValueError("at least two independent batches are required")
    n = len(means)
    se = statistics.stdev(means) / math.sqrt(n)
    # Two-sided 95% Student t critical values; for >30 df use conservative df30.
    t95 = (None, 12.706205, 4.302653, 3.182446, 2.776445, 2.570582, 2.446912,
           2.364624, 2.306004, 2.262157, 2.228139, 2.200985, 2.178813, 2.160369,
           2.144787, 2.131450, 2.119905, 2.109816, 2.100922, 2.093024, 2.085963,
           2.079614, 2.073873, 2.068658, 2.063899, 2.059539, 2.055529, 2.051831,
           2.048407, 2.045230, 2.042272)
    critical = t95[min(n - 1, 30)]
    mean = statistics.mean(means)
    return {"mean": mean, "standard_error": se, "interval95": [mean - critical * se, mean + critical * se],
            "batches": n, "degrees_of_freedom": n - 1, "critical_value": critical,
            "method": "independent-batch-means-student-t", "approximation": "Normal batch means assumed; choose large batches."}


def write_freebj_shoe(path: str | Path, cards: Iterable[str | int]) -> Path:
    """Pinned FileShoe reads ASCII ranks, despite its manpage claiming binary."""
    ranks = tuple(card_rank(c) for c in cards)
    if not ranks:
        raise ValueError("empty shoe")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(" ".join("A" if rank == 1 else "T" if rank == 10 else str(rank)
                                for rank in ranks).encode("ascii"))
    return target


class FreeBJAdapter:
    def __init__(self, binary: str | Path | None = None, *, checkout: str | Path | None = None,
                 build_receipt: str | Path | None = None,
                 manifest_path: str | Path = MANIFEST):
        self.binary = str(binary or "freebj")
        self.checkout = checkout
        self.build_receipt = build_receipt
        self.pin = _pin("kevin-lesenechal/freebj", manifest_path)

    def build_command(self, rules: Rules, *, rounds: int = 100_000, jobs: int = 1,
                      player: Iterable[str | int] | None = None, dealer: str | int | None = None,
                      action: str | None = None, fresh_shoe: bool = False,
                      shoe_file: str | Path | None = None, dry_run: bool = False) -> tuple[list[str], dict]:
        mapping = freebj_rule_mapping(rules, fresh_shoe=fresh_shoe)
        argv = [self.binary, *mapping["argv"], "-n", str(_positive_int(rounds, "rounds")),
                "-j", str(_positive_int(jobs, "jobs"))]
        if player is not None:
            cards = tuple(card_rank(c) for c in player)
            if len(cards) < 2:
                raise ValueError("forced player needs at least two cards")
            inventory = list(initial_counts(rules.decks))
            for rank in cards + (() if dealer is None else (card_rank(dealer),)):
                inventory[rank - 1] -= 1
            if min(inventory) < 0:
                raise ValueError("forced cards exceed shoe inventory")
            argv += ["-c", ",".join("A" if c == 1 else str(c) for c in cards)]
            if action is not None and action not in legal_actions(cards, rules):
                raise UnsupportedReference("requested first action is illegal for forced hand")
        elif action is not None and action != "stand":
            raise UnsupportedReference("only always-stand is legal for every unforced initial hand")
        if dealer is not None:
            rank = card_rank(dealer)
            argv += ["--dealer", "A" if rank == 1 else str(rank)]
        if action is not None:
            if action not in ACTION_CODES:
                raise ValueError("unknown forced action")
            argv += ["-a", ACTION_CODES[action]]
        if shoe_file is not None:
            argv += ["--shoe-file", str(Path(shoe_file).resolve())]
        if dry_run:
            argv.append("--dry-run")
        return argv, mapping

    def _run(self, command: list[str], timeout: float) -> dict:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, shell=False)
        if result.returncode:
            raise ReferenceExecutionError(f"FreeBJ exit {result.returncode}: {result.stderr.strip()[:2000]}")
        return parse_freebj_output(result.stdout, metadata_only="--dry-run" in command)

    def run_batches(self, rules: Rules, *, batches: int = 12, rounds_per_batch: int = 100_000,
                    timeout_seconds: float = 60, require_pin: bool = True, **kwargs: Any) -> dict:
        base = {"engine": "freebj", "comparison_executed": False, "exact": False,
                "reference_pin": self.pin["commit"], "native_optimal_policy": False}
        try:
            _positive_int(batches, "batches")
            if batches < 2:
                raise ValueError("at least two independent batches required")
            if kwargs.get("shoe_file") is not None:
                raise UnsupportedReference("fixed FileShoe runs cannot establish independent randomized batch means")
            if not (Path(self.binary).is_file() or shutil.which(self.binary)):
                return dict(base, status="skipped", reason="FreeBJ executable is not installed")
            provenance = {"repository": self.pin["repository"], "revision": self.pin["commit"], "revision_verified": False}
            if self.checkout is not None:
                provenance = _checkout_provenance(self.checkout, self.pin)
                provenance["binary_build_revision_attested"] = False
            if require_pin and not provenance["revision_verified"]:
                return dict(base, status="skipped", reason="Pinned source checkout required for revision verification")
            executable = Path(shutil.which(self.binary) or self.binary).resolve()
            provenance["binary_path"] = str(executable)
            provenance["binary_sha256"] = _sha256(executable)
            provenance["build_provenance_note"] = "Clean checkout pin verified; executable derivation must be attested separately."
            if self.build_receipt is not None:
                receipt = _load_json(self.build_receipt)
                if (receipt.get("status") != "built" or receipt.get("revision") != self.pin["commit"]
                        or receipt.get("binary_sha256") != provenance["binary_sha256"]):
                    raise ReferenceExecutionError("FreeBJ build receipt does not match pinned revision and executable hash")
                provenance["binary_build_revision_attested"] = True
                provenance["build_receipt"] = str(Path(self.build_receipt).resolve())
                provenance["build_receipt_sha256"] = _sha256(self.build_receipt)
            else:
                provenance["binary_build_revision_attested"] = False
            command, mapping = self.build_command(rules, rounds=rounds_per_batch, **kwargs)
            dry_command = [*command, "--dry-run"]
            echo = self._run(dry_command, timeout_seconds)
            verify_freebj_rules(echo, mapping["expected_rules"])
            results = []
            for _ in range(batches):
                output = self._run(command, timeout_seconds)
                verify_freebj_rules(output, mapping["expected_rules"])
                if "ev" not in output or output.get("rounds") != rounds_per_batch:
                    raise ReferenceExecutionError("missing EV or incomplete round count")
                results.append({"ev": output["ev"], "stddev_per_round": output["stddev"], "rounds": output["rounds"]})
            stats = independent_batch_statistics(r["ev"] for r in results)
            forced = kwargs.get("player") is not None or kwargs.get("dealer") is not None
            limitations = list(mapping["limitations"])
            if forced:
                limitations.append("Pinned StandardShoe removes forced ranks from the front but random draws pop the back; the remaining order is not exchangeable conditioned on shown-card removal.")
            return dict(base, status="executed", comparison_executed=True, command=command,
                        validation_eligible=provenance["revision_verified"] and provenance["binary_build_revision_attested"] and not forced,
                        forced_cards_conditioning_matches_native=False if forced else None,
                        requested_rules=asdict(rules), effective_rules=mapping["expected_rules"], rule_echo_verified=True,
                        provenance=provenance, sampling=stats, batch_results=results,
                        continuation="FreeBJ basic chart after forced first action", conditioning="pre-peek",
                        independent_streams="Separate processes use upstream entropy; upstream exposes no seed argument.",
                        limitations=limitations, executed_at=datetime.now(timezone.utc).isoformat())
        except UnsupportedReference as exc:
            return dict(base, status="unsupported", reason=str(exc))
        except FileNotFoundError as exc:
            return dict(base, status="skipped", reason=str(exc))
        except (subprocess.TimeoutExpired, ReferenceExecutionError, ValueError, OSError) as exc:
            return dict(base, status="failed", reason=str(exc))


def hhoppe_rule_mapping(rules: Rules) -> dict:
    if rules.enhc or not rules.dealer_peek:
        raise UnsupportedReference("hhoppe obo conflates peek and OBO; adapter supports only AHC with peek")
    if rules.surrender == "early":
        raise UnsupportedReference("hhoppe Rules has no early surrender")
    if rules.double_rule != "any":
        raise UnsupportedReference("hhoppe minimum-total doubling differs from strict native ranges or no-double")
    if rules.blackjack_payout < 1:
        raise UnsupportedReference("hhoppe Rules requires blackjack payout >= 1")
    max_hands = rules.max_split_hands if rules.resplit else min(2, rules.max_split_hands)
    return {"num_decks": rules.decks, "blackjack_payout": rules.blackjack_payout,
            "hit_soft17": rules.hit_soft17, "obo": True, "late_surrender": rules.surrender == "late",
            "double_min_total": 0, "double_after_split": rules.double_after_split,
            "split_to_num_hands": 0 if max_hands == 1 else max_hands,
            "resplit_aces": rules.resplit_aces, "hit_split_aces": rules.hit_split_aces,
            "double_split_aces": rules.hit_split_aces and rules.double_after_split,
            "cut_card": 0, "num_players": 1}


class HhoppeAdapter:
    def __init__(self, checkout: str | Path, *, python: str | Path = sys.executable,
                 manifest_path: str | Path = MANIFEST):
        self.checkout, self.python = Path(checkout), str(python)
        self.pin = _pin("hhoppe/blackjack", manifest_path)

    def analyze(self, rules: Rules, player: Iterable[str | int], dealer: str | int, *,
                counts: Iterable[int] | None = None, actions: Iterable[str] | None = None,
                peek_resolved: bool = True, from_split: bool = False, effort: int = 3,
                timeout_seconds: float = 120) -> dict:
        base = {"engine": "hhoppe", "method": "external-finite-fresh-shoe-pruned-dp", "exact": False,
                "comparison_executed": False, "reference_pin": self.pin["commit"]}
        try:
            mapping = hhoppe_rule_mapping(rules)
            cards = tuple(card_rank(c) for c in player)
            upcard = card_rank(dealer)
            if len(cards) < 2 or hand_value(cards)[0] > 21:
                raise UnsupportedReference("hhoppe adapter requires a live hand of at least two cards")
            if from_split:
                raise UnsupportedReference("active split contexts cannot be represented completely")
            if sorted(cards) == [1, 10]:
                raise UnsupportedReference("reference action rewards ignore player natural; use separate payout identities")
            if not peek_resolved and upcard in (1, 10):
                raise UnsupportedReference("adapter action rewards are conditional on negative dealer peek")
            fresh = list(initial_counts(rules.decks))
            for rank in (*cards, upcard):
                fresh[rank - 1] -= 1
            if min(fresh) < 0:
                raise ValueError("observed cards exceed inventory")
            if counts is not None and tuple(counts) != tuple(fresh):
                raise UnsupportedReference("reference has no arbitrary depleted-shoe state API")
            selected = list(actions) if actions is not None else legal_actions(cards, rules)
            if not selected or any(a not in legal_actions(cards, rules) for a in selected):
                raise UnsupportedReference("invalid or illegal reference action set")
            if isinstance(effort, bool) or not isinstance(effort, int) or not 0 <= effort <= 4:
                raise ValueError("effort must be 0..4")
            provenance = _checkout_provenance(self.checkout, self.pin)
            script = ROOT / "validation" / "reference_engines" / "hhoppe_worker.py"
            request = {"checkout": str(self.checkout.resolve()), "rules": mapping,
                       "player": cards, "dealer": upcard, "actions": selected, "effort": effort}
            command = [self.python, "-I", str(script)]
            result = subprocess.run(command, input=json.dumps(request), capture_output=True,
                                    text=True, timeout=timeout_seconds, shell=False)
            if result.returncode:
                message = result.stderr.strip()[:2000]
                return dict(base, status="skipped" if "ModuleNotFoundError" in message else "failed", reason=message,
                            provenance=provenance)
            output = json.loads(result.stdout)
            ev = output.get("actions")
            if not isinstance(ev, dict) or set(ev) != set(selected):
                raise ReferenceExecutionError("reference omitted requested action results")
            for value in ev.values():
                _number(value, "action EV")
            return dict(base, status="executed", comparison_executed=True, actions=ev,
                        state={"player": list(cards), "dealer": upcard, "counts": fresh,
                               "peek_resolved": bool(peek_resolved), "from_split": False},
                        best_action=max(ev, key=ev.get), requested_rules=asdict(rules), effective_rules=mapping,
                        provenance=dict(provenance, source_sha256=output.get("source_sha256")),
                        conditioning="negative-peek", continuation="HAND_AND_INITIAL_CARDS_IN_PRIOR_SPLITS",
                        effort=effort, limitations=["Upstream EFFORT prunes states; error bound unavailable.",
                            "Split continuation forgets prior hit cards and automatically takes allowed resplits.",
                            "Fresh shoe minus current exposed cards only; cut-card effects excluded."],
                        executed_at=datetime.now(timezone.utc).isoformat())
        except UnsupportedReference as exc:
            return dict(base, status="unsupported", reason=str(exc))
        except FileNotFoundError as exc:
            return dict(base, status="skipped", reason=str(exc))
        except (subprocess.TimeoutExpired, ReferenceExecutionError, ValueError, OSError) as exc:
            return dict(base, status="failed", reason=str(exc))


def load_reference_output(path: str | Path, *, manifest_path: str | Path = MANIFEST) -> dict:
    """Validate external-output schema, provenance, and EVs without endorsing them."""
    output = _load_json(path)
    if output.get("schema_version") != 1 or output.get("status") != "executed":
        raise ValueError("external reference must explicitly record an executed experiment")
    provenance = output.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("external output requires typed provenance")
    for key in ("repository", "revision", "source_url", "executed_at", "producer", "raw_output_sha256"):
        if not isinstance(provenance.get(key), str) or not provenance[key]:
            raise ValueError(f"missing provenance {key}")
    pin = _pin(provenance["repository"], manifest_path)
    if provenance["revision"] != pin["commit"]:
        raise ValueError("external output revision does not match manifest pin")
    if not re.fullmatch(r"[0-9a-f]{64}", provenance["raw_output_sha256"]):
        raise ValueError("invalid raw output hash")
    if not provenance["source_url"].startswith(("https://", "http://")):
        raise ValueError("source URL must be an HTTP(S) provenance link")
    try:
        datetime.fromisoformat(provenance["executed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid execution timestamp") from exc
    rules = output.get("rules")
    if not isinstance(rules, dict) or set(rules) != set(asdict(Rules())):
        raise ValueError("external output must declare every native rule field")
    Rules(**rules)
    model = output.get("model")
    required_model = ("shoe", "conditioning", "continuation", "split_deal_order", "ev_units")
    if not isinstance(model, dict) or any(not isinstance(model.get(k), str) or not model[k] for k in required_model):
        raise ValueError("external output requires explicit mathematical model")
    if model["ev_units"] != "net-profit-per-original-unit":
        raise ValueError("incompatible EV units")
    if not isinstance(output.get("exact"), bool):
        raise ValueError("exact must be a boolean with a declared model")
    actions = output.get("actions")
    if not isinstance(actions, dict) or not actions or any(a not in ACTION_CODES for a in actions):
        raise ValueError("invalid action EV mapping")
    for value in actions.values():
        _number(value, "action EV")
    return dict(output, provenance_verified_against_manifest=True,
                mathematical_equivalence_verified=False, artifact_sha256=_sha256(path))


def compare_action_values(actual: dict, reference: dict, *, tolerance: float,
                          equivalent_model: bool = False) -> dict:
    """Comparison needs an explicit same-model decision by the caller."""
    tolerance = _number(tolerance, "tolerance")
    if tolerance < 0:
        raise ValueError("negative tolerance")
    if not equivalent_model:
        return {"status": "unsupported", "passed": False, "reason": "Mathematical equivalence not established"}
    actual_ev = actual.get("actions", actual.get("ev", {}))
    reference_ev = reference.get("actions", {})
    if reference.get("status") not in ("executed", "published") or not isinstance(reference_ev, dict) or not reference_ev:
        return {"status": "not_executed", "passed": False, "reason": "Reference has no executed or published results"}
    if not isinstance(actual_ev, dict) or any(actual_ev.get(a) is None for a in reference_ev):
        return {"status": "incomplete", "passed": False, "reason": "Native action EVs are incomplete"}
    differences = {a: _number(actual_ev[a], a) - _number(v, a) for a, v in reference_ev.items()}
    passed = all(abs(delta) <= tolerance for delta in differences.values())
    return {"status": "passed" if passed else "failed", "passed": passed,
            "tolerance": tolerance, "differences": differences, "compared_actions": list(differences)}


def run_golden_validation(path: str | Path = GOLDENS) -> dict:
    """Compare published infinite-deck numbers only to the replacement DP."""
    from .strategy import get_generated_strategy
    cases = _load_json(path)
    if cases.get("schema_version") != 1 or cases.get("model") != "infinite-shoe-dp":
        raise ValueError("unsupported golden case model")
    results = []
    for case in cases["cases"]:
        rules = Rules(**case["rules"])
        actual = get_generated_strategy(rules).analyze(case["player"], case["dealer"],
                   peek_resolved=case["peek_resolved"], allowed_actions=case.get("allowed_actions"))
        comparison = compare_action_values(actual, dict(case, status="published"),
                                           tolerance=case["tolerance"], equivalent_model=True)
        best_passed = actual.get("best_action") == case["best_action"]
        results.append(dict(comparison, id=case["id"], best_action=actual.get("best_action"),
                            expected_best_action=case["best_action"], best_action_passed=best_passed,
                            passed=comparison["passed"] and best_passed, source_url=case["source_url"],
                            finite_shoe_validation=False))
    return {"status": "passed" if all(r["passed"] for r in results) else "failed",
            "comparison_executed": True, "model": "infinite-shoe-dp", "results": results,
            "note": "Published values rounded to six decimals; this is not finite-shoe or split-order validation."}
