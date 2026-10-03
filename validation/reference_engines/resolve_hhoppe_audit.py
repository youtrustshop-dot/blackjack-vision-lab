"""Link frozen discrepancies to diagnostic results without rewriting originals."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original-report', type=Path, required=True)
    parser.add_argument('--failures', type=Path, required=True)
    parser.add_argument('--diagnostic', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original = json.loads(args.original_report.read_text(encoding='utf-8'))
    failures = json.loads(args.failures.read_text(encoding='utf-8'))['failures']
    diagnostic = json.loads(args.diagnostic.read_text(encoding='utf-8'))
    if diagnostic['status'] != 'complete' or diagnostic['completed_cases'] != len(failures):
        raise ValueError('Diagnostic is incomplete')
    if diagnostic['original_report_sha256'] != sha(args.original_report) or diagnostic['original_failures_sha256'] != sha(args.failures):
        raise ValueError('Original artifact hash mismatch')
    if diagnostic['tolerance'] != original['tolerance'] or diagnostic['native_sha256'] != original['native_source_sha256']:
        raise ValueError('Diagnostic changed tolerance or native source')
    result_by_id = {c['state_id']: (i, c) for i, c in enumerate(diagnostic['results'])}
    if len(result_by_id) != len(failures) or set(result_by_id) != {c['state_id'] for c in failures}:
        raise ValueError('Diagnostic state coverage differs from frozen failures')
    resolutions = []
    unresolved = best_mismatches = 0
    for failure in failures:
        index, entry = result_by_id[failure['state_id']]
        if any(failure[key] != entry[key] for key in ('rules', 'player', 'dealer', 'counts')):
            raise ValueError('Diagnostic input state changed')
        if failure['our_ev'] != entry['native_ev'] or failure['reference_ev'] != entry['original_effort3_ev']:
            raise ValueError('Frozen values changed in diagnostic')
        ev = entry['effort4_ev']
        action = failure['our_action']
        best_agrees = action in ev and max(ev.values()) - ev[action] <= original['tolerance']
        explained = bool(entry['diagnostic_comparison']['passed'] and best_agrees)
        unresolved += not explained
        best_mismatches += not best_agrees
        resolutions.append({'state_id': failure['state_id'], 'original_failed': True,
          'classification': 'explained_by_reference_tracking_truncation_in_sample' if explained else 'unresolved',
          'diagnostic_artifact': str(args.diagnostic), 'diagnostic_result_index': index,
          'effort3_max_abs_ev_difference': entry['max_abs_diff_effort3'],
          'effort4_max_abs_ev_difference': entry['max_abs_diff_effort4'],
          'best_action_agrees_at_unchanged_tolerance': best_agrees})
    result = {'schema_version': 1, 'status': 'resolved_in_sample' if unresolved == 0 else 'unresolved',
      'original_report': str(args.original_report), 'original_report_sha256': sha(args.original_report),
      'original_failure_artifact': str(args.failures), 'original_failures_sha256': sha(args.failures),
      'diagnostic_artifact': str(args.diagnostic), 'diagnostic_sha256': sha(args.diagnostic),
      'original_report_status': original['status'], 'original_cases': original['cases'],
      'original_failed_cases': len(failures), 'original_passing_cases': original['cases'] - len(failures),
      'explained_reference_pruning_cases': len(failures) - unresolved,
      'unresolved_numerical_disagreements_in_sample': unresolved,
      'diagnostic_best_action_disagreements': best_mismatches,
      'original_best_action_disagreements': sum(not c['best_action_agrees_with_tolerance'] for c in original['results']),
      'max_abs_ev_difference_effort4_diagnostic': max(e['max_abs_diff_effort4'] for e in diagnostic['results']),
      'tolerance': original['tolerance'], 'original_effort': 3, 'diagnostic_effort': 4,
      'reference_exact': False, 'native_source_changed': False, 'original_artifacts_mutated': False,
      'scope': original['scope'],
      'precision_note': '1721 original effort3 comparisons and 279 separately diagnosed effort4 failures cover the recorded 2000 samples. Original report remains failed. This does not assert effort4 was executed on the 1721 original passing cases, a proven global pruning error bound, or exactness of the reference.',
      'resolutions': resolutions, 'generated_at': datetime.now(timezone.utc).isoformat()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('resolutions', 'precision_note', 'scope')}, indent=2))
    if unresolved:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
