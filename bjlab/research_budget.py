"""Durable shared research reservations, not an account balance or invoice.

The runner uses one canonical ledger for the entire EUR10 authorization. A new
output directory, model or process never resets it. Unknown charges stay reserved.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time
from uuid import uuid4

CANONICAL_LEDGER = Path(__file__).resolve().parents[1]/'artifacts/api-budget/eur10-total-20261004.json'


def positive(value, *, zero=False):
    result = Decimal(str(value))
    if not result.is_finite() or (result < 0 if zero else result <= 0):
        raise ValueError('A finite bounded cost is required.')
    return result


@contextmanager
def ledger_lock(path):
    # A separate stable inode is locked: atomically replacing the JSON must not
    # let a second process lock an obsolete JSON handle and spend concurrently.
    with Path(str(path)+'.lock').open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b'0'); handle.flush()
        deadline = time.monotonic()+5
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise PermissionError('Research budget ledger is busy.') from None
                time.sleep(.01)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_json(path, value):
    temporary = path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


class PersistentRequestBudget:
    def __init__(self, path, *, authorization_id, max_requests, max_usd):
        self.path = Path(path)
        self.authorization_id = authorization_id
        self.max_requests = max_requests
        self.maximum = positive(max_usd)
        if not authorization_id or type(max_requests) is not int or max_requests <= 0:
            raise ValueError('One explicit aggregate authorization and request ceiling are required.')
        # An absent/deleted ledger cannot silently become a fresh allowance.
        with ledger_lock(self.path):
            self._load()

    @classmethod
    def initialize(cls, path, *, authorization_id, max_requests, max_usd):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        maximum = positive(max_usd)
        if not authorization_id or type(max_requests) is not int or max_requests <= 0:
            raise ValueError('Positive aggregate ceilings are required.')
        marker = path.with_suffix(path.suffix+'.initialized')
        with ledger_lock(path):
            if not path.exists():
                if marker.exists():
                    raise PermissionError('Previously initialized budget is missing; do not reset it.')
                # Written before initialization: interrupted bootstrap fails closed.
                marker.write_text(authorization_id, encoding='utf-8')
                atomic_json(path, {'schema': 1, 'authorization_id': authorization_id,
                    'max_requests': max_requests, 'max_usd': str(maximum),
                    'stopped': False, 'entries': [], 'currency': 'USD'})
        return cls(path, authorization_id=authorization_id, max_requests=max_requests, max_usd=max_usd)

    def _load(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if (value['schema'] != 1 or value['authorization_id'] != self.authorization_id or
                    value['max_requests'] != self.max_requests or Decimal(value['max_usd']) != self.maximum or
                    type(value['stopped']) is not bool or not isinstance(value['entries'], list)):
                raise ValueError('Authorization changed.')
            ids = set()
            for entry in value['entries']:
                if entry['id'] in ids:
                    raise ValueError('Repeated reservation.')
                ids.add(entry['id'])
                bound = positive(entry['reserved_usd'])
                if entry['settled_upper_usd'] is not None and positive(entry['settled_upper_usd'], zero=True) > bound:
                    raise ValueError('Settlement exceeds reservation.')
            if len(ids) > self.max_requests or self._accounted(value) > self.maximum:
                raise ValueError('Ledger exceeds authorization.')
            return value
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
            raise PermissionError('Research budget ledger is missing, inconsistent or corrupt.') from None

    @staticmethod
    def _accounted(value):
        return sum((Decimal(e['settled_upper_usd'] if e['settled_upper_usd'] is not None else e['reserved_usd'])
            for e in value['entries']), Decimal(0))

    def reserve(self, cost):
        cost = positive(cost)
        with ledger_lock(self.path):
            value = self._load()
            if value['stopped'] or len(value['entries']) >= self.max_requests or self._accounted(value)+cost > self.maximum:
                raise PermissionError('Aggregate request/spend allowance exhausted.')
            identifier = uuid4().hex
            value['entries'].append({'id': identifier, 'reserved_usd': str(cost),
                'settled_upper_usd': None, 'submitted_utc': datetime.now(timezone.utc).isoformat()})
            atomic_json(self.path, value)
            return identifier

    def settle(self, identifier, upper_cost):
        cost = positive(upper_cost, zero=True)
        with ledger_lock(self.path):
            value = self._load()
            entry = next((e for e in value['entries'] if e['id'] == identifier), None)
            if entry is None or entry['settled_upper_usd'] is not None or cost > Decimal(entry['reserved_usd']):
                value['stopped'] = True
                atomic_json(self.path, value)
                raise ValueError('Unexpected settlement; aggregate budget stopped.')
            entry['settled_upper_usd'] = str(cost)
            atomic_json(self.path, value)

    def claim_submission(self, identifier, payload_sha256):
        """One network attempt per durable reservation, including crash/retry."""
        with ledger_lock(self.path):
            value = self._load()
            entry = next((e for e in value['entries'] if e['id'] == identifier), None)
            if value['stopped'] or entry is None or entry.get('submission_claimed') or entry['settled_upper_usd'] is not None:
                raise PermissionError('Missing, consumed or stopped durable request reservation.')
            if len(payload_sha256) != 64 or any(c not in '0123456789abcdef' for c in payload_sha256):
                raise ValueError('A request digest is required; never store the private request body.')
            entry.update(submission_claimed=True, payload_sha256=payload_sha256)
            atomic_json(self.path, value)

    def receipt(self):
        with ledger_lock(self.path):
            value = self._load()
            uncertain = [e for e in value['entries'] if e['settled_upper_usd'] is None]
            return {'requests_attempted': len(value['entries']), 'max_requests': self.max_requests,
                'max_usd': str(self.maximum), 'accounted_upper_usd': str(self._accounted(value)),
                'unknown_charge_requests': len(uncertain),
                'network_attempts_claimed': sum(bool(e.get('submission_claimed')) for e in value['entries']),
                'unknown_charge_reserved_usd': str(sum((Decimal(e['reserved_usd']) for e in uncertain), Decimal(0))),
                'stopped': value['stopped'], 'invoice_and_balance_verified': False,
                'scope': 'all configurations/providers under one aggregate authorization'}

    def stop(self):
        with ledger_lock(self.path):
            value = self._load(); value['stopped'] = True
            atomic_json(self.path, value)
