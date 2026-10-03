"""Headless commands and local web entry point."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="bjlab")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the local dashboard and API")
    serve.add_argument("--port", type=int, default=8765)
    analyze = commands.add_parser("analyze", help="Analyze a JSON state file")
    analyze.add_argument("state", type=Path)
    analyze.add_argument("--timeout-ms", type=int, default=5000)
    strategy = commands.add_parser("strategy", help="Generate a declared strategy model or finite lazy cells")
    strategy.add_argument("--model", choices=("replacement", "finite"), default="replacement")
    strategy.add_argument("--rules", type=Path)
    strategy.add_argument("--cell", nargs=3, metavar=("GROUP", "VALUE", "DEALER"))
    strategy.add_argument("--timeout-ms", type=int, default=5000)
    strategy.add_argument("--max-nodes", type=int, default=250000)
    strategy.add_argument("--output", type=Path)
    data = commands.add_parser("dataset", help="Generate labelled synthetic frames")
    data.add_argument("output", type=Path)
    data.add_argument("--sessions", type=int, default=20)
    data.add_argument("--seed", type=int, default=13)
    benchmark = commands.add_parser("vision-benchmark")
    benchmark.add_argument("dataset", type=Path)
    benchmark.add_argument("--output", type=Path)
    experiment = commands.add_parser("experiment")
    experiment.add_argument("--rounds", type=int, default=1000)
    experiment.add_argument("--seed", type=int, default=42)
    experiment.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        uvicorn.run("bjlab.api:app", host="127.0.0.1", port=args.port)
        return
    if args.command == "analyze":
        from .engine import Rules
        from .solver import Solver
        state = json.loads(args.state.read_text(encoding="utf-8"))
        rules = Rules(**state.pop("rules", {}))
        result = Solver(rules).analyze(**state, timeout_ms=args.timeout_ms)
    elif args.command == "strategy":
        from .engine import Rules
        from .strategy import get_generated_strategy, get_finite_generated_strategy
        rules = Rules(**json.loads(args.rules.read_text(encoding="utf-8"))) if args.rules else Rules()
        if args.model == "finite":
            generated = get_finite_generated_strategy(rules, timeout_ms=args.timeout_ms, max_nodes=args.max_nodes)
            result = generated.generate_cell(*args.cell) if args.cell else generated.generate_table()
        else:
            result = get_generated_strategy(rules).generate_table()
            if args.cell:
                group, value, up = args.cell
                from .engine import card_rank
                rank_names = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")
                value = rank_names[card_rank(value)-1] if group == "pairs" else str(int(value))
                up = rank_names[card_rank(up)-1]
                result = {"method": result["method"], "rules": result["rules"],
                          "finite_shoe_exact": False, "exactWithinModel": True,
                          "continuation_policy": result["continuation_policy"],
                          "group": group, "value": value, "dealer": up, "cell": result[group][value][up]}
    elif args.command == "dataset":
        from .datasets import generate_dataset
        result = generate_dataset(args.output, sessions=args.sessions, seed=args.seed)
        result = {k:v for k,v in result.items() if k != "records"} | {"frame_count": len(result["records"])}
    elif args.command == "vision-benchmark":
        from .datasets import benchmark_dataset
        from .vision import TemplateCardDetector
        result = benchmark_dataset(args.dataset, TemplateCardDetector())
    else:
        from .monte_carlo import run_experiment
        result = run_experiment(rounds=args.rounds, seed=args.seed)
    encoded = json.dumps(result, indent=2, allow_nan=False)
    if getattr(args, "output", None) and args.command != "dataset":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
