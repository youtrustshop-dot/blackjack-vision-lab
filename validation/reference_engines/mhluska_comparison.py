"""Pinned mhluska CLI smoke plus independent public always-stand experiment."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.engine import Rules
from bjlab.references import _pin, _checkout_provenance, _sha256, independent_batch_statistics
from unconditional_stand import native_batch


def run(argv, **kwargs):
    return subprocess.run(argv, shell=False, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=120, **kwargs)


def enum_names(text, name):
    match = re.search(r'export enum ' + re.escape(name) + r'\s*\{([^}]*)\}', text)
    if not match:
        raise ValueError('Missing upstream enum ' + name)
    return [part.strip() for part in match.group(1).split(',') if part.strip()]


def verify_receipt(path, checkout, pin):
    receipt = json.loads(Path(path).read_text(encoding='utf-8'))
    if receipt.get('status') != 'built' or receipt.get('returncode') != 0:
        raise ValueError('Reference build did not succeed')
    if receipt.get('provenance', {}).get('revision') != pin['commit']:
        raise ValueError('Build receipt revision mismatch')
    if receipt.get('package_lock_sha256') != _sha256(checkout/'package-lock.json'):
        raise ValueError('Build lock hash mismatch')
    for name in ('dist/main.js', 'dist/simulate.min.js', 'bin/cli.js'):
        if receipt.get('bundles', {}).get(name) != _sha256(checkout/name):
            raise ValueError('Built artifact hash mismatch: ' + name)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--node', default='node')
    parser.add_argument('--batches', type=int, default=12)
    parser.add_argument('--rounds', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=161803)
    parser.add_argument('--build-receipt', required=True)
    parser.add_argument('--verify-existing', help='Attach verified build provenance to an existing executed sample without resampling')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.batches < 2 or args.rounds < 100:
        raise ValueError('At least two nontrivial batches required')
    checkout = Path(args.checkout).resolve()
    pin = _pin('mhluska/blackjack-simulator')
    provenance = _checkout_provenance(checkout, pin)
    receipt = verify_receipt(args.build_receipt, checkout, pin)
    if args.verify_existing:
        result = json.loads(Path(args.verify_existing).read_text(encoding='utf-8'))
        if not result.get('comparison_executed') or result.get('provenance', {}).get('revision') != pin['commit']:
            raise ValueError('Existing artifact is not an executed pinned sample')
        recorded_hashes = result.get('provenance', {}).get('source_hashes', {})
        if any(recorded_hashes.get(name) != value for name, value in receipt['bundles'].items()):
            raise ValueError('Existing sample used a different compiled artifact')
        result['provenance']['build_receipt'] = receipt
        result['provenance']['build_receipt_sha256'] = _sha256(args.build_receipt)
        result['validation_eligible'] = True
        result['provenance_verified_at'] = datetime.now(timezone.utc).isoformat()
        output = Path(args.output)
        output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(json.dumps({'status': result['status'], 'resampled': False,
                          'validation_eligible': True, 'output': str(output)}, indent=2))
        return
    types = (checkout / 'src/types.ts').read_text(encoding='utf-8')
    moves = enum_names(types, 'Move')
    payouts = enum_names(types, 'BlackjackPayout')
    if moves.index('Stand') != 5 or moves.index('NoInsurance') != 3 or payouts.index('ThreeToTwo') != 0:
        raise ValueError('Pinned enum contract changed')
    bundle = checkout / 'dist/main.js'
    if not bundle.is_file():
        raise ValueError('Build pinned source with npm ci --ignore-scripts and npm run build first')
    # CLI smoke uses upstream basic strategy and is NOT the compared policy.
    argv = [args.node, str(checkout / 'bin/cli.js'), 'simulate', '--hands=1000',
            '--player-strategy=basic-strategy', '--player-bet-spread=1,1,1,1,1',
            '--player-spots=1,1,1,1,1', '--player-count=1', '--deck-count=6',
            '--hit-soft17=false', '--allow-double-after-split=true',
            '--allow-late-surrender=false', '--allow-resplit-aces=false',
            '--blackjack-payout=3:2', '--max-hands-allowed=4',
            '--minimum-bet=1', '--maximum-bet=100', '--penetration=0.75', '--raw=true']
    import os
    env = dict(os.environ, CORES='1')
    cli = run(argv, cwd=checkout, env=env)
    cli_receipt = {'argv': argv, 'cores': 1, 'returncode': cli.returncode,
                   'stdout': cli.stdout, 'stderr': cli.stderr,
                   'status': 'executed' if cli.returncode == 0 else 'failed',
                   'comparison_executed': False, 'policy': 'upstream basic strategy, smoke only'}
    if cli.returncode:
        result = {'schema_version': 1, 'status': 'failed', 'comparison_executed': False,
                  'provenance': provenance, 'cli_smoke': cli_receipt}
    else:
        rules = Rules(surrender='none', penetration=1/(6*52))
        native, reference, differences = [], [], []
        worker = Path(__file__).with_name('mhluska_worker.mjs')
        worker_argv = [args.node, str(worker), str(checkout)]
        for index in range(args.batches):
            request = json.dumps({'rounds': args.rounds, 'decks': rules.decks,
                                  'hit_soft17': rules.hit_soft17})
            completed = run(worker_argv, cwd=checkout, input=request)
            if completed.returncode:
                raise RuntimeError('mhluska worker failed: ' + completed.stderr)
            external = json.loads(completed.stdout)
            if external['status'] != 'executed' or external['rounds'] != args.rounds:
                raise ValueError('Unexpected upstream batch result')
            effective = external['effective_settings']
            expected = {'deckCount': 6, 'hitSoft17': False, 'playerCount': 1,
                        'allowLateSurrender': False, 'blackjackPayout': 0,
                        'minimumBet': 100, 'maximumBet': 100,
                        'penetration': rules.penetration}
            if any(effective.get(k) != v for k, v in expected.items()):
                raise ValueError('Unexpected mhluska rule echo')
            internal = native_batch(rules, args.seed + 104729 * index, args.rounds)
            native.append(internal)
            reference.append(external)
            differences.append(internal['ev'] - external['ev'])
            print(f"batch {index+1}/{args.batches}: native={internal['ev']:.6f} mhluska={external['ev']:.6f}", flush=True)
        delta = independent_batch_statistics(differences)
        passed = delta['interval95'][0] <= 0 <= delta['interval95'][1]
        provenance = _checkout_provenance(checkout, pin)
        provenance.update({'source_url': f"https://github.com/{pin['repository']}/tree/{pin['commit']}",
                           'source_hashes': {name: _sha256(checkout / name) for name in
                             ('src/game.ts', 'src/shoe.ts', 'src/player.ts', 'src/types.ts',
                              'package-lock.json', 'dist/main.js', 'bin/cli.js', 'dist/simulate.min.js')},
                           'node_version': run([args.node, '--version']).stdout.strip(),
                           'build_receipt': receipt,
                           'build_receipt_sha256': _sha256(args.build_receipt)})
        result = {'schema_version': 1, 'status': 'passed' if passed else 'failed', 'passed': passed,
                  'comparison_executed': True, 'validation_eligible': True, 'exact': False, 'rules': asdict(rules),
                  'conditioning': 'unconditional initial deal', 'shoe': 'fresh finite six-deck shoe each round',
                  'policy': 'always stand; decline insurance; fixed initial wager one',
                  'cli_smoke': cli_receipt, 'provenance': provenance,
                  'native': {'sampling': independent_batch_statistics(b['ev'] for b in native),
                             'batch_results': native, 'source_sha256': _sha256(ROOT / 'bjlab/simulator.py')},
                  'reference': {'sampling': independent_batch_statistics(b['ev'] for b in reference),
                                'batch_results': reference, 'worker_sha256': _sha256(worker),
                                'argv': worker_argv},
                  'native_minus_reference': delta,
                  'statistics': 'Independent equal-size process batch means; Student t interval for independent batch differences',
                  'limitations': ['Upstream Math.random entropy streams have no exposed reproducible seed; independence assumed.',
                                  'CLI basic strategy smoke is distinct from public Game.step stand comparison.',
                                  'No split, optimal action EV, chart, count or betting comparison.',
                                  'One preregistered fixed sample size; failed intervals retained, no repeat-until-pass.']}
    result['executed_at'] = datetime.now(timezone.utc).isoformat()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'native': result.get('native', {}).get('sampling'),
                      'reference': result.get('reference', {}).get('sampling'),
                      'difference': result.get('native_minus_reference'), 'output': str(output)}, indent=2))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
