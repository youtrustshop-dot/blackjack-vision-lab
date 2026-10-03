"""Check current evidence separately from preserved historical claims."""
import json
from pathlib import Path
import re
import tomllib


def evidence_errors(root: Path):
    project=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    package=json.loads((root/'ui/package.json').read_text(encoding='utf-8'))
    lock=json.loads((root/'ui/package-lock.json').read_text(encoding='utf-8'))
    native=json.loads((root/'ui/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
    cargo=tomllib.loads((root/'ui/src-tauri/Cargo.toml').read_text(encoding='utf-8'))
    python=re.search(r'__version__\s*=\s*"([^"]+)"',(root/'bjlab/__init__.py').read_text()).group(1)
    verification=json.loads((root/'docs/REQUIREMENTS.json').read_text(encoding='utf-8'))['verification']
    versions={'python':python,'npm':package['version'],'npm-lock':lock['version'],
              'npm-root-lock':lock['packages']['']['version'],'tauri':native['version'],
              'cargo':cargo['package']['version'],'verification':verification['version']}
    errors=[f'{name} version {value} differs from {project}' for name,value in versions.items() if value!=project]
    counts=[re.search(r'\d+',verification.get(key,'')) for key in ('frontend_tests','frontend_build')]
    if any(value is None for value in counts) or counts[0].group()!=counts[1].group():
        errors.append('Current frontend test counts disagree.')
    evidence=verification.get('source_evidence')
    if evidence and (root/evidence).exists() and not verification.get('latest_changes_require_retest'):
        record=json.loads((root/evidence).read_text(encoding='utf-8'))
        if record.get('version')!=project:errors.append('Source evidence belongs to a different version.')
        tests=record.get('tests',{})
        if tests.get('frontend_passed')!=int(counts[0].group()):errors.append('Frontend count differs from executed evidence.')
        declared=re.search(r'\d+',verification['completed_test_run'])
        if not declared or tests.get('python_passed')!=int(declared.group()):errors.append('Python count differs from executed evidence.')
    return errors
