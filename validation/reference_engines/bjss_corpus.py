"""Isolated, unmodified pinned BJSS best_move.py CLI on nonsplit states."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules, initial_counts
from bjlab.solver import Solver
from bjlab.references import _pin, _checkout_provenance, _sha256, compare_action_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--output', required=True)
    parser.add_argument('--expanded', action='store_true', help='Include 16 versus ace and soft 18 versus six for both S17/H17')
    args = parser.parse_args()
    checkout = Path(args.checkout).resolve()
    pin = _pin('AttackingOrDefending/Blackjack-Strategy-Simulator')
    provenance = _checkout_provenance(checkout, pin)
    cases = []
    states = [(hit17, [10, 6], 10, 'hard16-v10') for hit17 in (False, True)]
    if args.expanded:
        states.extend((hit17, cards, dealer, label) for hit17 in (False, True)
                      for cards, dealer, label in (([10, 6], 1, 'hard16-vA'), ([1, 7], 6, 'soft18-v6')))
    for hit17, player, dealer, label in states:
        rules = Rules(hit_soft17=hit17)
        cards_text = ','.join('A' if rank == 1 else str(rank) for rank in player)
        dealer_text = 'A' if dealer == 1 else str(dealer)
        argv = [args.python, '-I', str(checkout / 'best_move.py'), '--cards='+cards_text, '--dealer-card='+dealer_text,
                '--decks=6', '--splits=1', '--hit17' if hit17 else '--stand17',
                '--das', '--peek', '--surrender']
        # -I excludes the checkout from sys.path for a directly invoked script;
        # runpy supplies the verified directory only within this subprocess.
        bootstrap = "import sys,runpy;sys.path.insert(0,sys.argv[1]);sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name='__main__')"
        argv = [args.python, '-I', '-c', bootstrap, str(checkout), *argv[2:]]
        env = dict(os.environ, MPLBACKEND='Agg')
        try:
            completed = subprocess.run(argv, cwd=checkout, env=env, capture_output=True,
                                       text=True, encoding='utf-8', errors='replace', timeout=120, shell=False)
            match = re.search(r'Profits: Stand: ([^,]+), Hit: ([^,]+), Double: ([^,]+), Split: ([^,]+), Surrender: ([^,]+), Insurance: ([^\r\n]+)', completed.stdout)
            if completed.returncode or not match:
                raise RuntimeError(completed.stderr or completed.stdout)
            values = [float(v) for v in match.groups()]
            actions = dict(zip(('stand', 'hit', 'double', 'surrender'), (values[0], values[1], values[2], values[4])))
            reference = {'status': 'executed', 'comparison_executed': True, 'exact': False,
                         'actions': actions, 'best_action': max(actions, key=actions.get),
                         'precision_note': 'No general exactness claim: upstream explicitly limits split calculation; this corpus excludes splits.',
                         'raw_stdout': completed.stdout, 'raw_stderr': completed.stderr,
                         'argv': argv, 'headless_backend': 'Agg', 'requested_rules': asdict(rules)}
            counts = list(initial_counts(6))
            for rank in (*player, dealer):
                counts[rank-1] -= 1
            native = Solver(rules).analyze(player, dealer, counts, peek_resolved=True,
                                          timeout_ms=15000, max_nodes=2000000)
            comparison = compare_action_values(native, reference, tolerance=1e-9, equivalent_model=True)
            best_agrees = native['best_action'] == reference['best_action'] and native['exact']
            case = {'id': ('H17-' if hit17 else 'S17-') + label, 'status': comparison['status'],
                    'passed': comparison['passed'] and best_agrees, 'rules': asdict(rules),
                    'player': player, 'dealer': dealer, 'counts': counts,
                    'native': native, 'reference': reference, 'comparison': comparison,
                    'best_action_agrees': best_agrees}
        except (subprocess.TimeoutExpired, RuntimeError, ValueError) as exc:
            case = {'id': ('H17-' if hit17 else 'S17-') + label, 'status': 'failed',
                    'passed': False, 'reason': str(exc), 'argv': argv}
        cases.append(case)
        print(f"{case['id']}: {case['status']}", flush=True)
    passed = all(c['passed'] for c in cases)
    result = {'schema_version': 1, 'status': 'passed' if passed else 'failed', 'passed': passed,
              'comparison_executed': any('comparison' in c for c in cases), 'exact_reference': False,
              'provenance': _checkout_provenance(checkout, pin),
              'source_url': f"https://github.com/{pin['repository']}/blob/{pin['commit']}/best_move.py",
              'source_sha256': _sha256(checkout / 'best_move.py'),
              'native_sha256': _sha256(ROOT / 'bjlab/solver.py'), 'cases': cases,
              'scope': 'Fresh six-deck initial nonsplit states shown in cases; resolved American peek, any-two double, late surrender, S17/H17.',
              'license': 'AGPL v3-or-later; external subprocess only, no upstream code copied into application.',
              'unsupported': ['Splits/resplits', 'Initial naturals', 'ENHC/OBO/no-peek equivalence', 'Early surrender', 'Restricted doubling'],
              'executed_at': datetime.now(timezone.utc).isoformat()}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'cases': len(cases), 'output': str(output)}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
