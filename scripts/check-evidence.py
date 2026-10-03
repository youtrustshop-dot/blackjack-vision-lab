"""Fail CI when current versions or executed test counts contradict each other."""
import json
from pathlib import Path
from bjlab.evidence import evidence_errors

errors=evidence_errors(Path(__file__).resolve().parents[1])
print(json.dumps({'consistent':not errors,'errors':errors}))
raise SystemExit(bool(errors))
