"""Comparison contracts: exact analytical references and statistical estimates differ."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import json
import math
from pathlib import Path
from typing import Mapping
from .engine import Rules
from .solver import Solver

@dataclass(frozen=True)
class ReferenceResult:
    engine: str
    action_evs: Mapping[str, float]
    method: str = "deterministic"
    standard_errors: Mapping[str, float] = field(default_factory=dict)
    provenance: str = ""
    state_fingerprint: str = ""
    ev_units: str = "net profit per original bet"

    def __post_init__(self):
        if self.method not in ("deterministic", "monte-carlo"):
            raise ValueError("Reference method must declare deterministic or monte-carlo")
        if not self.provenance:
            raise ValueError("A reference needs provenance")
        if any(not math.isfinite(v) for v in self.action_evs.values()):
            raise ValueError("Reference EV must be finite")
        if self.method == "monte-carlo":
            if any(a not in self.standard_errors for a in self.action_evs):
                raise ValueError("Every Monte Carlo action needs its standard error")
            if any(not math.isfinite(s) or s < 0 for s in self.standard_errors.values()):
                raise ValueError("Standard errors must be nonnegative and finite")

def compare_result(ours: dict, reference: ReferenceResult, *, absolute_tolerance: float = 1e-9,
                   statistical_z: float = 4., state_id: str = "") -> dict:
    if reference.ev_units != ours.get("ev_units", reference.ev_units):
        raise ValueError("EV units differ; comparison is invalid")
    if absolute_tolerance < 0 or not math.isfinite(absolute_tolerance) or statistical_z <= 0:
        raise ValueError("Invalid comparison tolerance")
    failures, comparisons, missing = [], [], []
    for action, expected in reference.action_evs.items():
        actual = ours.get("actions", {}).get(action)
        if actual is None:
            missing.append(action)
            continue
        # The native finite-shoe solver is deterministic. Uncertainty here belongs
        # to the external sampling estimate, not an arbitrary numerical tolerance.
        se = reference.standard_errors.get(action, 0.)
        tolerance = max(absolute_tolerance, statistical_z * se)
        delta = float(actual) - expected
        row = {"action":action, "ours":actual, "reference":expected, "delta":delta,
               "tolerance":tolerance, "standard_error":se, "passes":abs(delta)<=tolerance}
        comparisons.append(row)
        if not row["passes"]:
            failures.append(row)
    return {"schema_version":1, "state_id":state_id, "reference":reference.engine,
            "method":reference.method, "provenance":reference.provenance,
            "status":"failure" if failures else "incomplete" if missing else "passed",
            "discrepancies":failures, "missing_actions":missing, "comparisons":comparisons,
            "majority_vote_used":False}

def run_golden(corpus: str | Path, output: str | Path | None = None) -> dict:
    data=json.loads(Path(corpus).read_text(encoding="utf-8"))
    results=[]
    for case in data["cases"]:
        rules=Rules(**case.get("rules", {}))
        state=case["state"]
        result=Solver(rules).analyze(**state,timeout_ms=case.get("timeout_ms",2000))
        reference=ReferenceResult(engine=case["reference"]["engine"],
            action_evs=case["reference"]["action_evs"],provenance=case["reference"]["provenance"])
        comparison=compare_result(result,reference,state_id=case["id"])
        comparison["solver_status"]=result["status"]
        comparison["exact"]=result["exact"]
        if not result["exact"] and comparison["status"]=="passed":
            comparison["status"]="incomplete"
        results.append(comparison)
    report={"schema_version":1,"cases":results,"passed":all(r["status"]=="passed" for r in results)}
    if output:
        destination=Path(output);destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report
