"""Lifecycle contracts and pixel-only confirmation timing; not provider sessions."""
from bjlab.engine import Rules
from bjlab.live import LiveObserver
from bjlab.round_lifecycle import RoundLifecycle
from bjlab.vision import CardDetection
from side_fixture import side_table


def cards(player, dealer):
    return [CardDetection(r, None, (i*100, 300, 70, 100), 1, zone='player:0')
            for i,r in enumerate(player)]+[
        CardDetection(r, None, (i*100, 0, 70, 100), 1, zone='dealer')
        for i,r in enumerate(dealer)]


def stable(lifecycle, detections, phase, *, clear=False):
    results=[lifecycle.observe(detections, phase, clear_evidence=clear) for _ in range(3)]
    assert not results[0]['stable'] and results[-1]['stable']
    return results[-1]


def test_witnessed_clear_can_establish_a_deal_without_establishing_a_turn():
    lifecycle=RoundLifecycle()
    stable(lifecycle, [], 'waiting', clear=True)
    result=stable(lifecycle, cards(['A','6'], ['A','J']), 'unknown')
    assert result['new_round'] and not result['history_gap']
    assert lifecycle.seen_round and lifecycle.round_open
    result=lifecycle.observe(cards(['A','6'], ['A','J']), 'unknown')
    assert not result['new_round'] and not result['ambiguous_boundary']


def test_unwitnessed_replacement_is_ambiguous_and_cannot_be_silently_repaired():
    lifecycle=RoundLifecycle()
    stable(lifecycle, cards(['7','9'], ['6']), 'player')
    result=stable(lifecycle, cards(['A','5'], ['2']), 'unknown')
    assert result['ambiguous_boundary'] and result['history_gap']
    assert not result['new_round']
    # Absence of detections is not proof that the table was cleared.
    result=stable(lifecycle, [], 'unknown')
    assert result['ambiguous_boundary'] and not result['round_ended']
    result=stable(lifecycle, cards(['A','5'], ['2']), 'unknown')
    assert result['ambiguous_boundary'] and not result['new_round']
    stable(lifecycle, [], 'waiting', clear=True)
    result=stable(lifecycle, cards(['A','5'], ['2']), 'unknown')
    assert result['new_round'] and not result['ambiguous_boundary']


def test_an_unclassified_initial_deal_does_not_invent_a_round_boundary():
    lifecycle=RoundLifecycle()
    result=stable(lifecycle, cards(['A','5'], ['2']), 'unknown')
    assert not result['new_round'] and not lifecycle.seen_round


def test_pixel_path_exposes_sequential_confirmation_waits():
    observer=LiveObserver(Rules(decks=4), samples=100, fresh_shoe=False)
    image=side_table(['7','9'], ['6'])  # Visible control text, no manual turn flag.
    reports=[observer.process(image, i, 1+i*.2) for i in range(5)]
    assert [r['temporal_evidence']['round_hits'] for r in reports]==[1,2,3,4,5]
    assert [r['temporal_evidence']['exposure_commit_allowed'] for r in reports]==[False,False,True,True,True]
    assert reports[2]['temporal_evidence']['tracker_pending'][0]['hits']==1
    assert reports[3]['temporal_evidence']['tracker_pending'][0]['hits']==2
    assert [r['observed_cards'] for r in reports]==[0,0,0,0,3]
    assert reports[-1]['temporal_evidence']['tracker_pending']==[]
    assert reports[-1]['temporal_evidence']['turn_provenance']=='pixel evidence or unknown'
    assert not any(r['count_reliable'] for r in reports)


def test_unknown_boundary_does_not_rewrite_previous_exposures(monkeypatch):
    observer=LiveObserver(Rules(decks=4),samples=100,fresh_shoe=False)
    def feed(image):
        for _ in range(6):
            sequence=observer.sequence+1
            report=observer.process(image,sequence,1+sequence*.2)
        return report
    first=feed(side_table(['7','9'],['6']))
    assert first['observed_cards']==3
    original=observer.detector.detect
    def missing_turn(image):
        detections=original(image)
        # Context-loss contract only; actual pixels still provide card reads.
        if observer.detector.context['phase']!='waiting':
            observer.detector.context['phase']='unknown'
        return detections
    monkeypatch.setattr(observer.detector,'detect',missing_turn)
    result=feed(side_table(['A','5'],['2']))
    assert result['player']==['A','5'] and result['dealer']==['2']
    assert result['temporal_evidence']['ambiguous_boundary']
    assert result['observed_cards']==3 and result['advice'] is None
    assert result['state']['known_rank_counts']['7']==1
    assert result['state']['known_rank_counts']['A']==0
    assert observer.history_gap and not result['count_reliable']
    feed(side_table(blank=True))
    result=feed(side_table(['A','5'],['2']))
    assert not result['temporal_evidence']['ambiguous_boundary']
    assert result['observed_cards']==6 and result['round']==2
    assert result['advice'] is None  # Observable deal is not an observable turn.
    assert observer.history_gap and not result['count_reliable']
