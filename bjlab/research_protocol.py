"""Hash-sealed corpora and single-use final evaluation records.

Read-only files are an operational guard, not a security boundary. Digest
verification detects later modification. Keep seal digests in version control.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
from datetime import datetime, timezone


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_fingerprint(root):
    root = Path(root)
    files = [*root.glob('bjlab/*.py'), *root.glob('validation/tools/*.py'), root/'tests/side_fixture.py',
             root/'pyproject.toml', root/'requirements-lock.txt']
    entries = {path.relative_to(root).as_posix(): digest(path) for path in sorted(files)}
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def seal(directory, *, split, groups, scope):
    directory = Path(directory).resolve()
    target = directory / 'seal.json'
    if split not in ('train', 'validation', 'final_holdout') or not groups or len(set(groups)) != len(groups):
        raise ValueError('Declare a valid split and unique recording/session groups.')
    if target.exists():
        raise ValueError('A sealed corpus cannot be overwritten.')
    files = []
    for path in sorted(directory.rglob('*')):
        if not path.is_file(): continue
        if not path.resolve().is_relative_to(directory):
            raise ValueError('Corpus file escapes its directory.')
        files.append({'file': path.relative_to(directory).as_posix(), 'sha256': digest(path)})
    if not files: raise ValueError('An empty corpus cannot be sealed.')
    record = {'schema': 1, 'split': split, 'groups': list(groups), 'scope': scope,
              'files': files, 'created_utc': datetime.now(timezone.utc).isoformat()}
    with target.open('x', encoding='utf-8') as output:
        output.write(json.dumps(record, indent=2) + '\n')
    for entry in files:
        (directory / entry['file']).chmod(stat.S_IREAD)
    target.chmod(stat.S_IREAD)
    return {'seal_sha256': digest(target), 'record': record}


def verify(directory, expected_seal_digest):
    directory = Path(directory).resolve()
    path = directory / 'seal.json'
    if digest(path) != expected_seal_digest:
        raise ValueError('Frozen seal digest changed.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('schema') != 1 or not record.get('files'):
        raise ValueError('Invalid frozen corpus.')
    for entry in record['files']:
        file = (directory / entry['file']).resolve()
        if not file.is_relative_to(directory) or digest(file) != entry['sha256']:
            raise ValueError('Frozen corpus content changed or escaped its root.')
    return record


def disjoint(records):
    owners = {}
    for record in records:
        for group in record['groups']:
            if group in owners:
                raise ValueError(f'Session group {group} appears in more than one corpus.')
            owners[group] = record['split']


def consume_final(directory, expected_seal_digest, ledger, *, candidate, baseline):
    """Reserve a final evaluation before reading results; refuse any second use.

    A failed evaluation also consumes this holdout. A new candidate needs a new
    final holdout, while train/validation corpora may be reused for development.
    """
    record = verify(directory, expected_seal_digest)
    if record['split'] != 'final_holdout':
        raise ValueError('Only a final holdout uses the single-use ledger.')
    ledger = Path(ledger).resolve()
    if ledger != Path(directory).resolve()/'.final-evaluation.json':
        raise ValueError('The final evaluation ledger must be bound to its corpus directory.')
    ledger.parent.mkdir(parents=True, exist_ok=True)
    document = {'schema': 1, 'seal_sha256': expected_seal_digest, 'candidate': candidate,
                'baseline': baseline, 'consumed_utc': datetime.now(timezone.utc).isoformat()}
    with ledger.open('x', encoding='utf-8') as output:
        output.write(json.dumps(document, indent=2) + '\n')
    ledger.chmod(stat.S_IREAD)
    return document
