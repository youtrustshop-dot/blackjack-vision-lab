"""Build the clean pinned MIT reference and record compiled artifact derivation."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from bjlab.references import _pin, _checkout_provenance, _sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--node', default='node')
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    checkout = Path(args.checkout).resolve()
    node = shutil.which(args.node)
    if node is None:
        raise ValueError('Node is not installed')
    npm_cli = Path(node).parent / 'node_modules/npm/bin/npm-cli.js'
    if not npm_cli.is_file():
        raise ValueError('npm JavaScript CLI not found beside Node; no shell fallback')
    pin = _pin('mhluska/blackjack-simulator')
    _checkout_provenance(checkout, pin)
    argv = [node, str(npm_cli), 'run', 'build']
    completed = subprocess.run(argv, cwd=checkout, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=180, shell=False)
    receipt_path = Path(args.receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = receipt_path.with_suffix('.build.log')
    log_path.write_text(completed.stdout + '\n' + completed.stderr, encoding='utf-8')
    bundles = ('dist/main.js', 'dist/simulate.min.js', 'bin/cli.js')
    result = {'schema_version': 1, 'status': 'built' if completed.returncode == 0 else 'failed',
              'provenance': _checkout_provenance(checkout, pin), 'argv': argv,
              'returncode': completed.returncode, 'build_log': str(log_path.resolve()),
              'build_log_sha256': _sha256(log_path),
              'bundles': {name: _sha256(checkout/name) for name in bundles if (checkout/name).is_file()},
              'package_lock_sha256': _sha256(checkout/'package-lock.json'),
              'node_version': subprocess.run([node, '--version'], capture_output=True,
                       text=True, shell=False, check=True).stdout.strip(),
              'dependency_note': 'External development dependencies previously installed with npm ci --ignore-scripts from the pinned lock; application has no dependency on them.',
              'built_at': datetime.now(timezone.utc).isoformat()}
    receipt_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == '__main__':
    main()
