"""Round boundaries from visible stable evidence, separate from exposure history."""
from collections import Counter


class RoundLifecycle:
    def __init__(self, stable_frames=3):
        self.required=stable_frames
        self.candidate=None
        self.hits=0
        self.previous=None
        self.pending_boundary=False
        self.seen_round=False
        self.table_cleared=False
        self.round_open=False
        self.ambiguous_boundary=False

    def observe(self, detections, phase, *, clear_evidence=True):
        player=tuple(d.rank for d in detections if d.zone=='player:0' and d.rank)
        dealer=tuple(d.rank for d in detections if d.zone=='dealer' and d.rank)
        token=(player,dealer,phase)
        self.hits=self.hits+1 if token==self.candidate else 1
        self.candidate=token
        result={'stable':self.hits>=self.required, 'new_round':False, 'round_ended':False,
                'history_gap':False,
                'confirmation_hits':self.hits,'confirmation_required':self.required,
                'ambiguous_boundary':self.ambiguous_boundary,
                'player':list(player), 'dealer':list(dealer)}
        if not result['stable']:
            return result
        if not detections:
            # Close tracks while the witnessed empty table is stable, before
            # feeding empty observations into the occlusion tracker. Unknown
            # earlier hole cards remain unknown in the append-only journal.
            if clear_evidence:
                result['round_ended']=self.round_open
                self.round_open=False
                self.table_cleared=True
                self.pending_boundary=True
                self.ambiguous_boundary=False
                result['ambiguous_boundary']=False
            return result
        if (phase=='unknown' and self.previous and self.seen_round and
                not self.pending_boundary and bool(Counter(self.previous[0])-Counter(player))):
            # A stable replacement without a visible boundary can be a new
            # deal, occlusion or bad reading. Preserve pixels, not invented IDs
            # or corrections to the previous physical hand.
            self.ambiguous_boundary=True
            result.update(history_gap=True,ambiguous_boundary=True)
        if phase=='unknown' and self.table_cleared and len(player)>=2 and dealer:
            # A witnessed clear followed by a stable visible deal is sufficient
            # for exposure identity. It is not evidence of whose turn it is.
            result['new_round']=True
            self.seen_round=True
            self.round_open=True
            self.table_cleared=False
            self.pending_boundary=False
            self.ambiguous_boundary=False
            result['ambiguous_boundary']=False
        if phase=='settled' and len(player)>=2 and dealer:
            # A dealer blackjack or immediate player blackjack may never show
            # a player decision. A witnessed clear still establishes its deal.
            if not self.seen_round or self.table_cleared:
                result['new_round']=True
                self.seen_round=True
                self.round_open=True
                self.table_cleared=False
                self.ambiguous_boundary=False
                result['ambiguous_boundary']=False
            self.pending_boundary=True
        if phase=='player' and len(player)>=2 and len(dealer)==1:
            gap=False
            changed=False
            if self.previous and not self.pending_boundary:
                old_player,old_dealer,_=self.previous
                changed=(len(player)==2 and (dealer!=old_dealer or bool(Counter(old_player)-Counter(player))))
                gap=changed
            if not self.seen_round or self.pending_boundary or changed:
                result.update(new_round=True,history_gap=gap)
                self.seen_round=True
                self.round_open=True
                self.table_cleared=False
                self.pending_boundary=False
                self.ambiguous_boundary=False
                result['ambiguous_boundary']=False
        self.previous=token
        return result
