"""Move historical claims out of the current verification summary."""
import json
from pathlib import Path
from bjlab import __version__

root = Path(__file__).resolve().parents[1]
path = root / 'docs/REQUIREMENTS.json'
document = json.loads(path.read_text(encoding='utf-8'))
previous = document['verification']
if previous.get('version') != __version__:
    document['verification'] = {
        'version': __version__, 'status': 'pending',
        'completed_test_run': '0 tests executed for this increment',
        'frontend_tests': '0 tests executed for this increment',
        'frontend_build': '0 tests executed; build pending',
        'latest_changes_require_retest': True,
        'native_desktop_build_verified': False, 'frozen_backend_verified': False, 'release_verified': False,
        'release_evidence': None, 'source_evidence': 'docs/LIVE_RELIABILITY_VERIFICATION.json',
        'historical_v1_1_verification_before_reconciliation': previous,
    }
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
