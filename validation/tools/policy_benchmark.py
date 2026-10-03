"""Execute seeded policies and retain raw outcomes while printing compact evidence."""
import argparse
import json
import platform
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bjlab.monte_carlo import run_experiment

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--rounds",type=int,default=100000)
    parser.add_argument("--seed",type=int,default=20261003)
    parser.add_argument("--seconds",type=float,default=120)
    parser.add_argument("--output",type=Path,default=Path("validation/results/policies-large.json"))
    args=parser.parse_args()
    print("Starting policy benchmark:",args.rounds,"requested rounds",flush=True)
    result=run_experiment(rounds=args.rounds,seed=args.seed,max_seconds=args.seconds)
    result["runtime"]={"python":sys.version,"platform":platform.platform()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({key:value for key,value in result.items() if key!="samples"},indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    main()
