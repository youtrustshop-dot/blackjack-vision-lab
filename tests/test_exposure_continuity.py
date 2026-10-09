"""Pixel-only regressions for witnessed table clearing and instant settlements."""
from bjlab.engine import Rules
from bjlab.live import LiveObserver
from bjlab.round_lifecycle import RoundLifecycle
from side_fixture import side_table


def feed(observer, image, frames=6):
    for _ in range(frames):
        sequence = observer.sequence + 1
        report = observer.process(image, sequence, 1 + sequence * .35)
    return report


def test_witnessed_clear_closes_tracks_without_claiming_an_occlusion():
    observer = LiveObserver(Rules(decks=4), fresh_shoe=True)
    feed(observer, side_table(['8', '9'], ['6']))
    settled = feed(observer, side_table(['8', '9'], ['6', 'K', '4'], settled=True, hidden=False))
    assert settled['observed_cards'] == 5
    cleared = feed(observer, side_table(blank=True))
    assert cleared['observed_cards'] == 5
    assert cleared['count_reliable']
    assert cleared['state']['tracks'] == []
    assert sum(e.kind == 'ROUND_ENDED' for e in observer.tracker.log.events) == 1


def test_instant_settlement_after_witnessed_clear_is_a_new_round():
    observer = LiveObserver(Rules(decks=4), fresh_shoe=True)
    feed(observer, side_table(['8', '9'], ['6']))
    feed(observer, side_table(['8', '9'], ['6', 'K', '4'], settled=True, hidden=False))
    feed(observer, side_table(blank=True))
    result = feed(observer, side_table(['A', '6'], ['A', 'J'], settled=True, hidden=False))
    assert result['round'] == 2
    assert result['observed_cards'] == 9
    assert result['count_reliable']
    assert result['advice'] is None
    assert sum(e.kind == 'ROUND_STARTED' for e in observer.tracker.log.events) == 2


def test_hidden_hole_never_revealed_remains_an_incomplete_count():
    observer = LiveObserver(Rules(decks=4), fresh_shoe=True)
    feed(observer, side_table(['K', '6'], ['8']))
    result = feed(observer, side_table(blank=True))
    assert not result['count_reliable']
    assert result['true_count'] is None
    assert any('never observed face up' in reason for reason in result['count_reasons'])


def test_initial_instant_settlement_starts_exactly_one_round():
    observer = LiveObserver(Rules(decks=4), fresh_shoe=True)
    result = feed(observer, side_table(['A', 'K'], ['7', '9', '6'], settled=True, hidden=False))
    assert result['round'] == 1
    assert result['observed_cards'] == 5
    result = feed(observer, side_table(['A', 'K'], ['7', '9', '6'], settled=True, hidden=False))
    assert result['round'] == 1 and result['observed_cards'] == 5


def test_total_mismatch_cannot_certify_count_and_cannot_be_repaired_by_next_hand():
    observer = LiveObserver(Rules(decks=4), fresh_shoe=True)
    feed(observer, side_table(['A', '5'], ['2']))
    mismatch = feed(observer, side_table(['A', '5'], ['2'], total=19))
    assert not mismatch['count_reliable'] and mismatch['true_count'] is None
    feed(observer, side_table(blank=True))
    result = feed(observer, side_table(['7', '8'], ['3']))
    assert observer.history_gap and not result['count_reliable']


def test_recovered_same_round_evidence_can_restore_count_before_cards_leave():
    observer = LiveObserver(Rules(decks=4), fresh_shoe=True)
    feed(observer, side_table(['A', '5'], ['2']))
    feed(observer, side_table(['A', '5'], ['2'], total=19))
    result = feed(observer, side_table(['A', '5', '3'], ['2']))
    assert result['observed_cards'] == 4 and result['count_reliable']
    assert not observer.history_gap


def test_tight_red_two_recovers_with_margin_without_lowering_score_threshold():
    observer = LiveObserver(Rules(decks=4), fresh_shoe=True)
    feed(observer, side_table(['3', '9'], ['7'], locale='it', scale=.8,
                             player_suits=['S', 'H'], dealer_suits=['D']))
    result = feed(observer, side_table(['3', '9', '2'], ['7'], locale='it', scale=.8,
                                      player_suits=['S', 'H', 'H'], dealer_suits=['D']))
    assert result['player'] == ['3', '9', '2']
    assert result['observed_cards'] == 4 and result['count_reliable']
