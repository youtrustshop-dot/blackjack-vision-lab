import math

import pytest

from bjlab.engine import Rules
from bjlab.monte_carlo import basic_action, hilo_action, run_experiment, summarize
from bjlab.simulator import BlackjackSession


def setup(cards, **rules):
    session = BlackjackSession(Rules(**rules))
    session.set_shoe(cards)
    session.deal()
    return session


def test_chart_baseline_is_legal_and_handles_insurance():
    session = setup(["5", "6", "6", "10", "10", "5"])
    assert basic_action(session) == "double"
    assert hilo_action(session) in session.available_actions()
    session = setup(["10", "A", "6", "10"])
    assert basic_action(session) == "decline_insurance"


def test_forced_aces_and_pair_baseline():
    session = setup(["8", "6", "8", "10", "3", "10", "5"])
    assert basic_action(session) == "split"
    session.action("split")
    assert basic_action(session) in session.available_actions()


def test_summary_confidence_math_and_small_sample_semantics():
    result = summarize([1, -1, 1, -1])
    assert result["mean"] == 0
    assert result["standard_error"] == pytest.approx(math.sqrt(1 / 3))
    assert result["ci95"] == pytest.approx([-3.182 / math.sqrt(3), 3.182 / math.sqrt(3)])
    assert summarize([1])["ci95"] is None
    assert summarize([])["mean"] is None


def test_clustered_intervals_use_batches_and_conserve_totals():
    values = [1, 1, -1, -1]
    result = summarize(values, [[1, 1], [-1, -1]])
    assert result["independent_batches"] == 2
    assert result["standard_error"] == 1
    assert result["ci95"] == [-12.706, 12.706]
    assert result["total_profit"] == 0


def test_seeded_experiment_is_reproducible_and_paired():
    first = run_experiment(rounds=60, seed=31, regret_samples=0, max_seconds=20)
    second = run_experiment(rounds=60, seed=31, regret_samples=0, max_seconds=20)
    assert first["status"] == "complete"
    assert first["completed_rounds"] == 60
    assert first["samples"] == second["samples"]
    assert first["results"] == second["results"]
    assert first["comparisons"] == second["comparisons"]
    for policy, summary in first["results"].items():
        assert summary["rounds"] == 60
        assert summary["total_profit"] == sum(first["samples"][policy])
        assert summary["independent_batches"] == 3
    difference = first["comparisons"][0]["difference"]
    expected = first["results"]["basic"]["mean"] - first["results"]["hilo"]["mean"]
    assert difference["mean"] == pytest.approx(expected)


def test_composition_retains_budget_precision_and_fallback_labels():
    result = run_experiment(rounds=4, seed=7, policies=["composition"],
                            solver_seconds=.002, regret_samples=2, max_seconds=10)
    assert result["status"] == "complete"
    assert result["completed_rounds"] == 4
    assert result["results"]["composition"]["fallback_decisions"] >= 0
    assert result["results"]["composition"]["solver_methods"]
    assert "approximate" in result["results"]["composition"]["decision_loss"]["interpretation"]


def test_experiment_time_budget_is_reported_and_no_partial_policy_round():
    result = run_experiment(rounds=100, max_seconds=0, regret_samples=0)
    assert result["status"] == "time_budget"
    assert result["completed_rounds"] == 0
    assert result["samples"]["basic"] == result["samples"]["hilo"] == []


@pytest.mark.parametrize("kwargs", [{"rounds": 0}, {"rounds": 100001}, {"policies": ["fake"]}])
def test_experiment_validation(kwargs):
    with pytest.raises(ValueError):
        run_experiment(**kwargs)
