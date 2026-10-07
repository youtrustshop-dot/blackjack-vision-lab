"""Packet freshness regressions, not evidence of actual provider/capture faults."""
from dataclasses import replace

import pytest

from bjlab.hybrid_evidence import CurrentEvidence
from tests.test_r1_readers import frame


@pytest.mark.parametrize('change', ['bytes', 'name', 'removed', 'added', 'order',
    'source_size', 'table_box'])
def test_changed_detail_packet_invalidates_pending_result_with_same_table(change):
    original = frame()
    first, rest = original.details[0], original.details[1:]
    if change == 'bytes':
        changed = replace(original, details=((first[0], b'another-acquisition'),) + rest)
    elif change == 'name':
        changed = replace(original, details=(('different-role', first[1]),) + rest)
    elif change == 'removed':
        changed = replace(original, details=rest)
    elif change == 'added':
        changed = replace(original, details=original.details + (('another-view', first[1]),))
    elif change == 'order':
        changed = replace(original, details=tuple(reversed(original.details)))
    elif change == 'source_size':
        changed = replace(original, source_size=(original.source_size[0]+1, original.source_size[1]))
    else:
        changed = replace(original, table_box=(1, *original.table_box[1:]))
    assert changed.table_png == original.table_png
    evidence = CurrentEvidence()
    stamp = evidence.capture(original, source='fixture', table='one', capture_ns=1_000_000_000)
    evidence.capture(changed, source='fixture', table='one', capture_ns=1_100_000_000)
    result = evidence.revalidate(stamp, now_ns=1_120_000_000)
    assert not result['valid'] and 'pixels_or_continuity_changed' in result['reasons']


def test_detail_change_and_return_does_not_restore_old_result():
    original = frame()
    changed = replace(original, details=((original.details[0][0], b'other-crop'),) + original.details[1:])
    evidence = CurrentEvidence()
    stamp = evidence.capture(original, source='fixture', table='one', capture_ns=1_000_000_000)
    evidence.capture(changed, source='fixture', table='one', capture_ns=1_100_000_000)
    evidence.capture(original, source='fixture', table='one', capture_ns=1_200_000_000)
    assert not evidence.revalidate(stamp, now_ns=1_220_000_000)['valid']


def test_layout_mutation_without_new_capture_cannot_preserve_validity():
    original = frame()
    evidence = CurrentEvidence()
    stamp = evidence.capture(original, source='fixture', table='one', capture_ns=1_000_000_000)
    original.layout['dealer'] = (.01, .01, .2, .2)
    result = evidence.revalidate(stamp, now_ns=1_120_000_000)
    assert not result['valid'] and 'captured_packet_mutated' in result['reasons']


def test_same_named_packet_can_continue_without_resetting_original_deadline():
    original = frame()
    evidence = CurrentEvidence()
    stamp = evidence.capture(original, source='fixture', table='one', capture_ns=1_000_000_000)
    for i in range(1, 30):
        evidence.capture(replace(original, frame_id=f'capture-{i}'), source='fixture', table='one',
            capture_ns=1_000_000_000+i*100_000_000)
    assert evidence.revalidate(stamp, now_ns=3_950_000_000)['valid']
    expired = evidence.revalidate(stamp, now_ns=4_010_000_000)
    assert not expired['valid'] and 'original_evidence_deadline_expired' in expired['reasons']


def test_changed_detail_during_fallback_never_reaches_solver(monkeypatch):
    from bjlab.grounded_state import GroundedResult
    from bjlab.hybrid_evidence import hybrid_attempt
    from tests.test_grounded_reader import grounded

    # The fixture advances captures immediately; Windows may return the same
    # wall-clock tick twice. Control time instead of weakening capture rules.
    ticks = iter(range(1_000_000_000, 2_000_000_000, 1_000_000))
    monkeypatch.setattr('bjlab.hybrid_evidence.time.monotonic_ns', lambda: next(ticks))
    original = frame()
    evidence = CurrentEvidence()
    evidence.capture(original, source='fixture', table='one')

    class Local:
        name = 'contract-local'
        def read(self, captured):
            return GroundedResult(captured.frame_id, self.name, 'completed', grounded(phase='unknown'), 1, {})

    class Cloud:
        name = 'contract-cloud'
        def read(self, captured):
            changed = replace(captured, details=((captured.details[0][0], b'another-acquisition'),) + captured.details[1:])
            evidence.capture(changed, source='fixture', table='one')
            return GroundedResult(captured.frame_id, self.name, 'completed', grounded(), 1, {})

    def forbidden_solver(*args, **kwargs):
        raise AssertionError('Changed native detail must not reach the solver.')

    monkeypatch.setattr('bjlab.advice.recommend', forbidden_solver)
    result = hybrid_attempt(evidence, Local(), Cloud())
    assert result['route'] == 'fallback' and not result['presented'] and result['advice'] is None
    assert 'pixels_or_continuity_changed' in result['revalidation']['reasons']
