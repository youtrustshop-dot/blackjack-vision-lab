from pathlib import Path
import json
import pytest
from bjlab.validation import ReferenceResult, compare_result, run_golden
from bjlab.engine import Rules
from bjlab.solver import Solver

def test_analytic_golden():
    assert run_golden(Path(__file__).parents[1]/"validation/golden/analytic.json")["passed"]

def test_analytic_insurance_goldens():
    corpus=json.loads((Path(__file__).parents[1]/"validation/golden/analytic.json").read_text(encoding="utf-8"))
    checked=0
    for case in corpus["cases"]:
        expected=case["reference"].get("insurance")
        if expected is None:
            continue
        result=Solver(Rules(**case.get("rules",{}))).analyze(**case["state"])
        assert result["exact"], result
        for key,value in expected.items():
            actual=result["insurance"][key]
            assert actual == value if isinstance(value,bool) else actual == pytest.approx(value,abs=1e-12)
        checked+=1
    assert checked>=8

def test_statistical_uncertainty_is_not_an_exact_tolerance():
    reference=ReferenceResult("sampling",{"stand":.01},method="monte-carlo",
                              standard_errors={"stand":.004},provenance="seeded independent batches")
    assert compare_result({"actions":{"stand":.02}},reference)["status"]=="passed"
    assert compare_result({"actions":{"stand":.04}},reference)["status"]=="failure"

def test_missing_action_never_passes():
    r=ReferenceResult("exact",{"split":.1},provenance="independent enumeration")
    assert compare_result({"actions":{"split":None}},r)["status"]=="incomplete"

def test_invalid_monte_carlo_or_units_rejected():
    with pytest.raises(ValueError):
        ReferenceResult("sampling",{"hit":-.1},method="monte-carlo",provenance="paper")
    r=ReferenceResult("exact",{"stand":.1},provenance="enumeration")
    with pytest.raises(ValueError):
        compare_result({"actions":{"stand":.1},"ev_units":"gross payout"},r)
