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

    def observe(self, detections, phase):
        player=tuple(d.rank for d in detections if d.zone=='player:0' and d.rank)
        dealer=tuple(d.rank for d in detections if d.zone=='dealer' and d.rank)
        token=(player,dealer,phase)
        self.hits=self.hits+1 if token==self.candidate else 1
        self.candidate=token
        result={'stable':self.hits>=self.required, 'new_round':False, 'history_gap':False,
                'player':list(player), 'dealer':list(dealer)}
        if not result['stable']:
            return result
        if phase=='settled' or not detections:
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
                self.pending_boundary=False
        self.previous=token
        return result
