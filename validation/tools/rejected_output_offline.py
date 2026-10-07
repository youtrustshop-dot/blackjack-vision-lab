"""Offline contract fixtures and Windows protected-output round trip; zero API.

Fabricated outputs are NOT past Gemini/Luna responses or model-quality evidence.
No credentials, price queries, authorization epoch or live controller are used.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import socket
import time

from bjlab.paired_deadline_reader import CaptureDeadlineReader
from bjlab.grounded_cloud import GeminiConfig
from bjlab.paired_persistent_http import canonical_digest
from bjlab.private_observation_store import PrivateObservationStore
from bjlab.rejected_output_diagnostics import OwnedOutputScope, RetainingStillDiagnostic, inspect_output
from bjlab.state_reader import FrameInput
from validation.tools.api_reader_tournament import config

ROOT = Path(__file__).resolve().parents[2]


def base_output():
    return {'c': [
        {'z': 'player:0', 'r': '10', 's': 'C', 'v': 'readable'},
        {'z': 'player:0', 'r': '6', 's': 'H', 'v': 'readable'},
        {'z': 'dealer', 'r': '6', 's': 'S', 'v': 'readable'},
        {'z': 'dealer', 'r': None, 's': None, 'v': 'covered'}],
        't': 'cards_present', 'p': 'player', 'a': ['hit', 'stand'],
        'n': [{'v': 6, 'r': 'dealer_total', 'l': 'DEALER TOTAL 6', 'w': 'table'}], 'b': []}


def contract_cases():
    cases = []
    def add(name, change, expected):
        value = deepcopy(base_output()); change(value)
        cases.append((name, json.dumps(value, separators=(',', ':')), expected))
    add('explicit_total', lambda v: None, 'valid_usable_content')
    add('whitespace_label', lambda v: v['n'][0].update(l=' dealer  total : 6 '), 'valid_usable_content')
    add('unknown_ui_number', lambda v: v['n'].append({'v': 20, 'r': 'unknown', 'l': None, 'w': 'table'}), 'valid_usable_content')
    add('actor_without_total', lambda v: v['n'][0].update(l='DEALER 6'), 'pre_normalization_invariant_rejection')
    add('unlabelled_attributed_total', lambda v: v['n'][0].update(l='20'), 'pre_normalization_invariant_rejection')
    add('contradictory_suffix', lambda v: v['n'][0].update(l='DEALER TOTAL 16'), 'semantic_provenance_rejection')
    add('wrong_native_view', lambda v: v['n'][0].update(w='player:0'), 'semantic_provenance_rejection')
    add('ambiguous_actor_label', lambda v: v['n'][0].update(l='PLAYER DEALER TOTAL 6'), 'semantic_provenance_rejection')
    add('total_disagrees_with_cards', lambda v: v['n'].append({'v': 17, 'r': 'player_total', 'l': 'PLAYER TOTAL 17', 'w': 'table'}), 'r1_integrity_rejection')
    add('unknown_phase', lambda v: v.update(p='unknown'), 'r1_integrity_rejection')
    add('covered_face_claim', lambda v: v['c'][3].update(r='A'), 'pre_normalization_invariant_rejection')
    add('duplicate_controls', lambda v: v.update(a=['hit', 'hit']), 'pre_normalization_invariant_rejection')
    add('strict_number_type', lambda v: v['n'][0].update(v='6'), 'structural_validation_rejection')
    add('unexpected_field', lambda v: v.update(unexpected='private-value'), 'structural_validation_rejection')
    cases.append(('malformed_json', '{"c":', 'json_format_rejection'))
    return cases


class FixtureBudget:
    """Memory-only contract fixture, never the canonical spending allowance."""
    def __init__(self):
        self.reserved = self.settled = 0
    def reserve(self, cost):
        self.reserved += 1; return 'offline-fixture-only'
    def settle(self, identifier, cost):
        self.settled += 1
    def receipt(self):
        return {'scope': 'memory-only offline fixture', 'requests_attempted': self.reserved}
    def stop(self):
        raise AssertionError('Offline cost fixture exceeded.')


class FixtureTransport:
    timings = {}
    def __init__(self, text, *, model='gpt-6-luna', tier='fast'):
        self.text = text; self.submissions = 0; self.last_payload = None; self.deadline_ns = None
        self.model, self.tier = model, tier
    def post(self, payload, *, deadline_ns, reservation_id):
        self.submissions += 1; self.last_payload = payload; self.deadline_ns = deadline_ns
        return {'model': self.model, 'status': 'completed', 'service_tier': self.tier,
            'usage': {'input_tokens': 500, 'output_tokens': 180},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': self.text}]}],
            'headers': {'Authorization': 'fixture-envelope-header-must-never-be-saved'},
            'unrelated_provider_data': 'fixture-envelope-must-never-be-saved'}


def fixture_reader(text, *, provider='openai'):
    # Placeholder owned bytes for contract plumbing, not a recognition input.
    frame = FrameInput('offline-owned-contract-fixture', b'owned-contract-fixture-bytes', (),
        {'table': (0., 0., 1., 1.)}, (1, 1), (0, 0, 1, 1))
    hashes = tuple(sha256(p).hexdigest() for _, p in frame.images())
    cfg = GeminiConfig() if provider == 'gemini' else config(fast=True)
    transport, budget = FixtureTransport(text, model=cfg.model,
        tier='default' if provider == 'gemini' else 'fast'), FixtureBudget()
    reader = CaptureDeadlineReader(cfg, budget, hashes,
        provider=provider, transport=transport, name='offline-contract-fixture')
    scope = OwnedOutputScope('VISION-026-offline-fixture', 'fabricated-contract-output', provider,
        reader.config.model, canonical_digest(reader.payload(frame)), hashes, True)
    return frame, reader, scope


def run_offline(*, protected_roundtrip=False):
    def forbidden(*args, **kwargs):
        raise PermissionError('This diagnostic command cannot use sockets or DNS.')
    saved_socket, saved_dns = socket.socket, socket.getaddrinfo
    socket.socket = socket.getaddrinfo = forbidden
    try:
        rows = []
        for name, text, expected in contract_cases():
            public, _ = inspect_output(text)
            if public['category'] != expected or public['eligible_for_live']:
                raise AssertionError('Offline contract expectation failed: '+name)
            rows.append({'case': name, 'expected': expected, 'diagnosis': public})
        result = {'experiment': 'VISION-026', 'scope': 'fabricated contract fixtures, not model evidence',
            'provider_calls': 0, 'credentials_loaded': False, 'advisor_connected': False,
            'cases_passed': len(rows), 'cases': rows, 'protected_roundtrip': {'executed': False}}
        if protected_roundtrip:
            store = PrivateObservationStore(ROOT)
            text = next(t for n, t, _ in contract_cases() if n == 'actor_without_total')
            frame, reader, scope = fixture_reader(text, provider='gemini')
            receipt = RetainingStillDiagnostic(reader, store, scope).run(frame, capture_ns=time.monotonic_ns())
            record = store.read(receipt['retention']['record_id'])
            if (record['output_text'] != text or reader.transport.submissions != 1 or
                    receipt['category'] != 'pre_normalization_invariant_rejection' or
                    'unrelated_provider_data' in json.dumps(record)):
                raise AssertionError('Protected diagnostic fixture failed.')
            result['protected_roundtrip'] = {'executed': True, 'exact_text_recovered': True,
                'provider_envelope_excluded': True, 'public_receipt': receipt,
                'scope': 'one fabricated offline response through unchanged reader and actual Windows protection'}
        return result
    finally:
        socket.socket, socket.getaddrinfo = saved_socket, saved_dns


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protected-roundtrip', action='store_true')
    parser.add_argument('--export', action='store_true', help='Write only sanitized offline results to the new result folder.')
    parser.add_argument('--purge-expired', action='store_true', help='Delete only expired encrypted records in the private store.')
    args = parser.parse_args()
    if args.purge_expired:
        if args.export or args.protected_roundtrip:
            parser.error('Expiry purge is a separate offline action.')
        store = PrivateObservationStore(ROOT)
        print(json.dumps(store.expiry_cleanup_on_open)); raise SystemExit(0)
    result = run_offline(protected_roundtrip=args.protected_roundtrip)
    if args.export:
        folder = ROOT/'validation/results/rejected-output-diagnostics'; folder.mkdir(parents=True, exist_ok=True)
        (folder/'summary.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('experiment', 'provider_calls', 'scope', 'cases_passed')}))
