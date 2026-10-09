"""Reconcile the frozen 69-request OpenAI batch using read-only usage exports.

This does not reset the authorization, contact either provider, or treat rounded
spend/balance as a request invoice. For each timed-out request we charge ALL
reported input tokens of its model/tier group plus that request's maximum output.
This deliberately overcounts input and remains conservative if output-cost
accounting lags. Initial HTTP429 and Gemini reservations remain untouched.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import shutil

from validation.tools.api_reader_tournament import budget, config

EXPECTED = {('gpt-6-luna', 'default'): 51, ('gpt-6-luna', 'fast-tier'): 15,
            ('gpt-6.1-sol', 'default'): 3}


def verified_groups(usage_rows):
    groups = {}
    for row in usage_rows:
        if not row.get('num_model_requests'):
            continue
        key = row['model'], row['service_tier']
        if key not in EXPECTED or row.get('batch', '').lower() not in ('', 'false', 'false.0'):
            raise ValueError('Unexpected model/tier/batch in the usage export.')
        counts = [Decimal(row[k]) for k in ('num_model_requests', 'input_tokens', 'output_tokens')]
        if any(not n.is_finite() or n < 0 or n != n.to_integral_value() for n in counts):
            raise ValueError('Non-integral or missing usage counters.')
        current = groups.setdefault(key, [0, 0, 0])
        for i, value in enumerate(counts):
            current[i] += int(value)
    if {k: v[0] for k, v in groups.items()} != EXPECTED:
        raise ValueError('Export does not cover exactly the frozen 69 requests.')
    return groups


def plan(usage_rows, cost_rows, private_rows, ledger):
    groups = verified_groups(usage_rows)
    if len(private_rows) != 69 or len(ledger['entries']) < 70:
        raise ValueError('Frozen request/ledger history does not match.')
    requested = Counter()
    known_input = Counter()
    settlements = []
    for ordinal, row in enumerate(private_rows, 1):
        diagnostics = row['diagnostics']
        model = diagnostics['model_requested']
        tier = 'fast-tier' if diagnostics.get('service_tier_requested') == 'fast' else 'default'
        key = model, tier
        requested[key] += 1
        entry = ledger['entries'][ordinal]
        conf = config(model, fast=tier == 'fast-tier')
        if (diagnostics['budget']['requests_attempted'] != ordinal+1 or
                Decimal(entry['reserved_usd']) != conf.reserve_usd or not entry.get('submission_claimed')):
            raise ValueError('Durable submission sequence/configuration does not match.')
        submitted = datetime.fromisoformat(entry['submitted_utc'])
        if not any(datetime.fromtimestamp(int(r['start_time']), timezone.utc) <= submitted <
                   datetime.fromtimestamp(int(r['end_time']), timezone.utc)
                   for r in usage_rows if (r.get('model'), r.get('service_tier')) == key):
            raise ValueError('Usage window does not cover the recorded submission.')
        known_input[key] += (diagnostics.get('usage') or {}).get('input_tokens', 0)
        if entry['settled_upper_usd'] is None:
            if row['status'] != 'timeout':
                raise ValueError('Only the eight frozen funded timeouts are eligible.')
            group_inputs = groups[key][1]
            if not 0 < group_inputs <= conf.context_token_limit:
                raise ValueError('Aggregate input exceeds the audited per-request ceiling.')
            # All group input is assigned to EACH timeout; cached input is charged
            # at the more expensive audited cache-write rate. Output cap includes
            # reasoning. No reliance on delayed reported output costs being final.
            upper = conf.cost(group_inputs, conf.max_output_tokens, upper=True)
            settlements.append({'reservation_id': entry['id'], 'ordinal': ordinal,
                'model': model, 'tier': tier, 'upper_usd': str(upper)})
    if dict(requested) != EXPECTED or any(known_input[k] > groups[k][1] for k in groups):
        raise ValueError('Export counters conflict with received request usage.')
    if len(settlements) != 8:
        raise ValueError('Expected exactly eight unreconciled funded timeouts; do not repeat.')
    reported_cost = sum((Decimal(r['amount_value']) for r in cost_rows if r.get('amount_value')), Decimal(0))
    if any(r.get('amount_currency', '').lower() != 'usd' for r in cost_rows if r.get('amount_value')):
        raise ValueError('Unexpected cost currency.')
    return {'method': 'each timeout: whole same-model/tier group input + maximum request output at audited upper prices',
        'reported_period_cost_usd': str(reported_cost), 'reported_cost_is_final_invoice': False,
        'verified_requests': 69, 'groups': [{'model': k[0], 'tier': k[1], 'requests': v[0],
            'input_tokens': v[1], 'output_tokens_so_far': v[2]} for k, v in groups.items()],
        'settlements': settlements, 'retained': 'initial HTTP429, Gemini and all later attempts',
        'max_requests_unchanged': 90, 'max_usd_unchanged': '8'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usage-csv', type=Path, required=True)
    parser.add_argument('--cost-csv', type=Path, required=True)
    parser.add_argument('--frozen-private-results', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    ceiling = budget()
    usage = list(csv.DictReader(args.usage_csv.open(encoding='utf-8-sig', newline='')))
    costs = list(csv.DictReader(args.cost_csv.open(encoding='utf-8-sig', newline='')))
    rows = json.loads(args.frozen_private_results.read_text(encoding='utf-8'))['rows']
    ledger = json.loads(ceiling.path.read_text(encoding='utf-8'))
    report = plan(usage, costs, rows, ledger)
    if args.apply:
        args.evidence_dir.mkdir(parents=True, exist_ok=False)
        for source, name in ((args.usage_csv, 'usage.csv'), (args.cost_csv, 'cost.csv')):
            shutil.copyfile(source, args.evidence_dir/name)
        report['export_sha256'] = {p.name: sha256(p.read_bytes()).hexdigest()
                                   for p in args.evidence_dir.glob('*.csv')}
        report['frozen_private_results_sha256'] = sha256(args.frozen_private_results.read_bytes()).hexdigest()
        report['before'] = ceiling.receipt()
        # Preserve the proof/intent before changing any durable settlement.
        audit = args.evidence_dir/'reconciliation.json'
        audit.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        for item in report['settlements']:
            ceiling.settle(item['reservation_id'], item['upper_usd'])
        report['after'] = ceiling.receipt()
        audit.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'settlements'}, indent=2))


if __name__ == '__main__':
    main()
