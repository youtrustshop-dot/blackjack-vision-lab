"""Persistent video observations and finite-pool probability estimates.

No simulator object, session ID, future card or native card label enters this
module. Each call consumes one newly captured image from the video stream.
"""
from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
import hashlib
import json
import math
import random
import threading
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .calibration import NormalizedROI, TemplateTextDetector, extract_controlled_metadata, normalize_table
from .engine import Rules, card_rank, dealer_should_hit, hand_value, is_blackjack, legal_actions, settle
from .strategy import get_generated_strategy
from .vision import TemporalTracker
from .external_vision import AdaptiveCardDetector, OCR_RANK_MIN_SCORE
from .datasets import card_font, THEMES


PHASES = ("READY", "PLAYER", "INSURANCE", "EARLY", "SETTLED")


class ContextReader:
    """Read visible lab context labels; missing/ambiguous text stays unknown."""
    def __init__(self):
        self.digits = {}
        for value in range(10):
            prototypes = []
            for color in THEMES.values():
                tile = Image.new('RGB', (35,30), color)
                ImageDraw.Draw(tile).text((6,5),str(value),font=card_font(16),fill=(212,220,213),anchor='lt')
                mask=TemplateTextDetector._mask(np.asarray(tile)).astype(np.uint8)
                x,y,w,h=cv2.boundingRect(mask)
                prototypes.append(cv2.resize(mask[y:y+h,x:x+w],(16,24),interpolation=cv2.INTER_NEAREST).astype(bool))
            self.digits[str(value)] = prototypes
        self.phases = TemplateTextDetector(PHASES, minimum_score=.96)

    def read(self, image: Image.Image) -> dict:
        # The context band is outside dealer/player cards at canonical scale.
        if image.width != 960 or image.height < 300:
            return {}
        result = {}
        for name, x, width in (("shoe", 120, 65), ("round", 305, 65), ("hand", 470, 40), ("session", 860, 65)):
            roi=np.asarray(image.crop((x-6,255,x+width+6,285)))
            mask=TemplateTextDetector._mask(roi).astype(np.uint8)
            contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            boxes=sorted([cv2.boundingRect(c) for c in contours],key=lambda b:b[0])
            chosen=[]
            for dx,dy,dw,dh in boxes:
                if dh<8 or dw<2:continue
                glyph=cv2.resize(mask[dy:dy+dh,dx:dx+dw],(16,24),interpolation=cv2.INTER_NEAREST).astype(bool)
                scores=[]
                for digit,prototypes in self.digits.items():
                    score=max(float(np.logical_and(glyph,p).sum()/max(1,np.logical_or(glyph,p).sum())) for p in prototypes)
                    scores.append((score,digit))
                scores.sort(reverse=True)
                if scores[0][0]<.82 or scores[0][0]-scores[1][0]<.05:
                    chosen=[];break
                chosen.append(scores[0][1])
            if chosen:result[name]=int(''.join(chosen))
        phases = self.phases.detect(image, NormalizedROI(585 / 960, 255 / image.height,
                                                        300 / 960, 30 / image.height))
        names = {p.text for p in phases}
        if len(names) == 1:
            result["phase"] = next(iter(names)).lower()
        return result


def wilson(successes: int, samples: int) -> list[float]:
    p, z = successes / samples, 1.959963984540054
    denominator = 1 + z * z / samples
    center = (p + z * z / (2 * samples)) / denominator
    radius = z * math.sqrt(p * (1 - p) / samples + z * z / (4 * samples * samples)) / denominator
    return [max(0., center - radius), min(1., center + radius)]


def estimate_actions(player: list[str], upcard: str, counts: list[int], rules: Rules,
                     actions: list[str], *, samples: int = 1500, seed: int = 17,
                     peeked: bool = False, from_split: bool = False,
                     split_hands: int = 1) -> dict:
    """Monte Carlo without replacement, using generated basic continuation.

    Win means positive net profit for the active hand and any resplits caused by
    its evaluated action. Existing other hands are excluded, explicitly.
    """
    strategy = get_generated_strategy(rules)
    initial = tuple(card_rank(c) for c in player)
    up = card_rank(upcard)
    if samples < 100 or sum(counts) < 16:
        raise ValueError("At least 100 samples and 16 unobserved cards are required.")

    @lru_cache(maxsize=2048)
    def continuation(cards, split, hand_count, pending, split_aces):
        available = legal_actions(cards, rules, from_split=split, split_hands=hand_count,
                                  split_aces=split_aces, peek_resolved=peeked,
                                  can_surrender=False)
        result = strategy.analyze(cards, up, from_split=split, split_hands=hand_count,
                                  split_aces=split_aces, pending_count=pending,
                                  peek_resolved=peeked, allowed_actions=available)
        return result["best_action"]

    reports = {}
    for action in actions:
        rng = random.Random(seed)  # Paired initial random streams across actions.
        profits = []
        for _ in range(samples):
            pool = list(counts)

            def draw(excluded=0):
                total = sum(pool) - (pool[excluded - 1] if excluded else 0)
                if total <= 0:
                    raise ValueError("Insufficient cards for a simulated continuation.")
                choice = rng.randrange(total)
                for rank, count in enumerate(pool, 1):
                    if rank == excluded:
                        continue
                    if choice < count:
                        pool[rank - 1] -= 1
                        return rank
                    choice -= count
                raise AssertionError("Weighted draw failed")

            forbidden = (10 if up == 1 else 1 if up == 10 else 0) if peeked else 0
            dealer = [up, draw(forbidden)] if not rules.enhc else [up]
            # American peek stops the round before ordinary bets are added.
            prepeek_bj = rules.dealer_peek and not rules.enhc and not peeked and is_blackjack(dealer)
            if prepeek_bj and not (action == "surrender" and rules.surrender == "early"):
                profits.append(0. if is_blackjack(initial, from_split=from_split) else -1.)
                continue
            hands = [{"cards": list(initial), "wager": 1., "original": 1., "split": from_split,
                      "action": action, "surrendered": False}]
            hand_count = split_hands
            index = 0
            while index < len(hands):
                hand = hands[index]
                cards = hand["cards"]
                if len(cards) == 1:
                    cards.append(draw())
                chosen = hand["action"]
                split_aces = hand["split"] and cards[0] == 1
                if chosen is None:
                    chosen = continuation(tuple(cards), hand["split"], hand_count,
                                          len(hands) - index - 1, split_aces)
                if chosen == "continue":
                    chosen = continuation(tuple(cards), hand["split"], hand_count, 0, split_aces)
                if chosen == "split":
                    rank = cards[0]
                    first = {"cards": [rank], "wager": 1., "original": hand["original"],
                             "split": True, "action": None, "surrendered": False}
                    second = {"cards": [rank], "wager": 1., "original": 0.,
                              "split": True, "action": None, "surrendered": False}
                    hands[index:index + 1] = [first, second]
                    hand_count += 1
                    continue
                if chosen == "surrender":
                    hand["surrendered"] = True
                elif chosen == "double":
                    hand["wager"] = 2.
                    cards.append(draw())
                elif chosen == "hit":
                    cards.append(draw())
                    while hand_value(cards)[0] < 21:
                        if continuation(tuple(cards), hand["split"], hand_count,
                                        len(hands) - index - 1, split_aces) != "hit":
                            break
                        cards.append(draw())
                index += 1
            if rules.enhc:
                dealer.append(draw())
            needs_dealer = any(hand_value(h["cards"])[0] <= 21 and not h["surrendered"] and
                              not is_blackjack(h["cards"], from_split=h["split"]) for h in hands)
            if needs_dealer:
                while dealer_should_hit(dealer, rules):
                    dealer.append(draw())
            profit = sum(settle(h["cards"], dealer, rules, wager=h["wager"],
                                original_wager=h["original"], from_split=h["split"],
                                surrendered=h["surrendered"]) for h in hands)
            profits.append(profit)
        array = np.asarray(profits, dtype=float)
        wins, pushes, losses = int((array > 0).sum()), int((array == 0).sum()), int((array < 0).sum())
        mean = float(array.mean())
        margin = 1.96 * float(array.std(ddof=1)) / math.sqrt(samples)
        reports[action] = {"ev": mean, "ev_ci95": [mean - margin, mean + margin],
                           "win": wins / samples, "push": pushes / samples, "loss": losses / samples,
                           "win_ci95": wilson(wins, samples), "samples": samples}
    best = max(reports, key=lambda name: reports[name]["ev"])
    others = [r for name, r in reports.items() if name != best]
    separated = all(reports[best]["ev_ci95"][0] > r["ev_ci95"][1] for r in others)
    return {"best_action": best, "actions": reports, "method": "finite-pool Monte Carlo",
            "exact": False, "samples_per_action": samples, "seed": seed,
            "ranking_resolved": separated, "ev_units": "net profit per active-hand original wager",
            "probability_semantics": "positive / zero / negative net profit; existing other hands excluded",
            "continuation": "rule-generated replacement-model basic policy; finite-pool draws without replacement",
            "assumptions": ["Declared rules and observed composition; unseen pre-capture history is unknown.",
                            "Dealer hole card is marginalized, conditional on a visible resolved peek.",
                            "Other existing split-hand outcomes are excluded from these active-hand estimates."]}


class LiveObserver:
    def __init__(self, rules: Rules, *, samples=1500, corners=None, zones=None,
                 fresh_shoe=False, manual_turn=False, output_height=600):
        self.rules, self.samples = rules, samples
        self.corners, self.zones = corners, zones
        self.fresh_shoe, self.manual_turn, self.output_height = fresh_shoe, manual_turn, output_height
        self.tracker = TemporalTracker(stable_frames=3, lost_after=4)
        self.tracker.new_shoe(rules.decks, shoe_id="live-shoe-1")
        self.reader = ContextReader()
        self.detector = None
        self.sequence = -1
        self.last_context = {}
        self.context_candidate = None
        self.context_hits = 0
        self.round = 0
        self.phase = "waiting"
        self.empty_frames = 0
        self.decision_key = None
        self.decision = None
        self.last_access = time.monotonic()
        self.lock = threading.RLock()
        self.frame_count = 0
        self.pixel_cache_key = None
        self.pixel_evidence = None
        self.external_phase_candidate = None
        self.external_phase_hits = 0
        self.external_previous_phase = None

    def process(self, image: Image.Image, sequence: int, timestamp: float) -> dict:
        with self.lock:
            if sequence <= self.sequence:
                raise ValueError("Video frame sequence must increase; stale frame rejected.")
            if timestamp <= self.tracker.last_timestamp:
                raise ValueError("Video timestamps must increase; stale frame rejected.")
            started = time.perf_counter()
            if self.corners:
                image = Image.fromarray(normalize_table(image, self.corners,
                                         (960, self.output_height), corners_normalized=True).image_rgb)
            if self.detector is None:
                zones = self.zones or {"dealer": (0, 0, 960, 250)} | {
                    f"player:{i}": (30 + i % 2 * 440, 290 + i // 2 * 190, 440, 190)
                    for i in range(8)}
                self.detector = AdaptiveCardDetector(zones=zones)
            pixel_key = (image.size, image.mode, hashlib.sha256(image.tobytes()).digest())
            if pixel_key != self.pixel_cache_key:
                detected = self.detector.detect(image)
                self.pixel_evidence = (detected, {} if self.detector.context else self.reader.read(image),
                                       extract_controlled_metadata(image), self.detector.context)
                self.pixel_cache_key = pixel_key
            detections, context, metadata, external = self.pixel_evidence
            # Template similarity and OCR token scores have different contracts.
            # Never silently discard an OCR rank accepted by its profile.
            self.tracker.minimum_score = OCR_RANK_MIN_SCORE if external else .90
            token = tuple(context.get(k) for k in ("shoe", "round", "hand", "phase", "session"))
            self.context_hits = self.context_hits + 1 if token == self.context_candidate else 1
            self.context_candidate = token
            context_stable = self.context_hits >= 2 and all(k in context for k in ("shoe", "round", "hand", "phase"))
            # Accept visible context only after distinct consecutive video inputs.
            if context_stable:
                if (self.last_context.get("shoe") != context["shoe"] or
                        self.last_context.get("session") != context.get("session")):
                    self.tracker.new_shoe(self.rules.decks, timestamp=timestamp,
                                          shoe_id="live-shoe-" + str(context["shoe"]))
                    self.round = 0
                self.round = context["round"]
                self.phase = context["phase"]
                self.last_context = context
            elif external:
                phase = external['phase']
                self.external_phase_hits = self.external_phase_hits+1 if phase == self.external_phase_candidate else 1
                self.external_phase_candidate = phase
                self.empty_frames = self.empty_frames+1 if not detections else 0
                if self.empty_frames == 3 and self.tracker.tracks:
                    self.tracker.end_round(timestamp=timestamp)
                    self.round += 1
                if self.external_phase_hits >= 2:
                    if phase == 'player' and self.external_previous_phase == 'settled' and self.tracker.tracks:
                        self.round += 1
                        self.tracker.start_round(str(self.round), timestamp=timestamp)
                    self.external_previous_phase = phase
                if not self.round and detections:
                    self.round = 1
                self.phase = 'player' if self.manual_turn else phase
            elif not context:
                # Generic calibrated layout: clear table is an observable boundary.
                self.empty_frames = self.empty_frames + 1 if not detections else 0
                if self.empty_frames == 3 and self.tracker.tracks:
                    self.tracker.end_round(timestamp=timestamp)
                    self.round += 1
                if not self.round and detections:
                    self.round = 1
                self.phase = "player" if self.manual_turn else "waiting"
            emitted = self.tracker.update(detections, timestamp, round_id=str(self.round))
            self.sequence, self.last_access = sequence, time.monotonic()
            self.frame_count += 1
            summary = self.tracker.state_summary()
            running = sum((1 if 2 <= card_rank(rank) <= 6 else -1 if card_rank(rank) in (1, 10) else 0) * count
                          for rank, count in summary["known_rank_counts"].items())
            remaining = summary["physical_remaining"]
            reasons = list(summary["gate"]["reasons"])
            reasons.extend(external.get('reasons', []) if external else [])
            if context and not context_stable:
                reasons.append("Visible round context is changing; waiting for stable video evidence.")
            if self.detector.last_diagnostics["rejected_card_candidates"]:
                reasons.append("Some card-shaped regions could not be read.")
            cards = [c for c in summary["cards"].values() if c.get("on_table")]
            active_index = max(0, self.last_context.get("hand", 1) - 1) if context_stable else 0
            player = sorted([c for c in cards if c.get("zone") in (f"player:{active_index}", "player")],
                            key=lambda c: c.get("bbox", [0])[0])
            dealer = [c for c in cards if c.get("zone") == "dealer" and c.get("rank")]
            controls = set(external['controls']) if external else {d["text"].lower().replace(" ", "_") for d in metadata["button_detections"]}
            split_hands = max(1, len({c.get("zone") for c in cards if str(c.get("zone", "")).startswith("player")}))
            from_split = split_hands > 1
            player_ranks = [c["rank"] for c in player if c.get("rank")]
            if external and player_ranks:
                visible_totals=external.get('player_totals',{}).get(f'player:{active_index}',[])
                if visible_totals and hand_value(player_ranks)[0] not in visible_totals:
                    reasons.append("Tracked cards do not match the visible hand total. Waiting for fresh card evidence.")
            if len(player_ranks) != len(player):
                reasons.append("Active player cards are not fully visible.")
            if len(player_ranks) < 2 or len(dealer) != 1:
                reasons.append("Need at least two player cards and exactly one visible dealer upcard.")
            if self.phase not in ("player", "insurance", "early"):
                reasons.append("Waiting for a player decision in the video.")
            if context and not context_stable:
                controls = set()
            peeked = (self.rules.dealer_peek and not self.rules.enhc and self.phase == "player" and
                      bool(dealer) and card_rank(dealer[0]["rank"]) in (1, 10))
            allowed = legal_actions(player_ranks, self.rules, from_split=from_split,
                                    split_hands=split_hands, peek_resolved=peeked) if len(player_ranks) >= 2 else []
            if self.phase == "early":
                allowed = ["surrender", "continue"]
            if not self.manual_turn:
                allowed = [a for a in allowed if a in controls]
            if not allowed and self.phase != "insurance":
                reasons.append("No readable legal player controls; calibrate the table or declare a manual player turn.")
            allowed_gate = summary["gate"]["solver_allowed"] and not reasons
            decision = None
            advice = None
            if allowed_gate:
                state_key = json.dumps([player_ranks, dealer[0]["rank"], summary["composition_remaining"],
                                        allowed, peeked, from_split, split_hands, self.phase], sort_keys=True)
                if state_key != self.decision_key:
                    if self.phase == "insurance":
                        pool = summary["composition_remaining"]
                        probability = pool[9] / sum(pool)
                        insurance = 1.5 * probability - .5
                        self.decision = {"best_action": "insurance" if insurance > 0 and "insurance" in controls else "decline_insurance",
                                         "actions": {}, "insurance_blackjack_probability": probability,
                                         "insurance_ev": insurance, "method": "observable-pool insurance expectation", "exact": True}
                    else:
                        self.decision = estimate_actions(player_ranks, dealer[0]["rank"],
                                          summary["composition_remaining"], self.rules, allowed,
                                          samples=self.samples, seed=int(hashlib.sha256(state_key.encode()).hexdigest()[:8], 16),
                                          peeked=peeked, from_split=from_split, split_hands=split_hands)
                    self.decision_key = state_key
                decision = self.decision
                from .advice import recommend
                advice = recommend(player_ranks, dealer[0]["rank"], self.rules,
                    allowed=allowed if self.phase != "insurance" else ["insurance", "decline_insurance"],
                    phase=self.phase, from_split=from_split, split_hands=split_hands,
                    split_aces=from_split and bool(player_ranks) and card_rank(player_ranks[0]) == 1,
                    peeked=peeked, true_count=running / (remaining / 52) if remaining else 0.,
                    count_complete=self.fresh_shoe, estimate=decision)
            else:
                # Never retain advice through a transition, unreadable card or lost track.
                self.decision_key, self.decision = None, None
            running = sum((1 if 2 <= card_rank(rank) <= 6 else -1 if card_rank(rank) in (1, 10) else 0) * count
                          for rank, count in summary["known_rank_counts"].items())
            remaining = summary["physical_remaining"]
            gate = {"solver_allowed": bool(allowed_gate), "status": "stable" if allowed_gate else "waiting",
                    "reasons": list(dict.fromkeys(reasons))}
            return {"source": "live-video-pixels", "sequence": sequence, "timestamp": timestamp,
                    "processed_frames": self.frame_count, "detections": [d.to_dict() for d in detections],
                    "context": context, "phase": self.phase, "round": self.round, "gate": gate,
                    "decision": decision, "advice": advice, "running_count": running,
                    "true_count": running / (remaining / 52) if remaining else None,
                    "count_scope": "from declared fresh shoe" if self.fresh_shoe else "observed portion only",
                    "observed_cards": len(summary["counted_ids"]), "physical_remaining": remaining,
                    "player": player_ranks, "dealer": [c["rank"] for c in dealer],
                    "events": [e.to_dict() for e in emitted], "state": summary,
                    "processing_ms": (time.perf_counter() - started) * 1000,
                    "recognition_profile": external.get('profile', 'lab-template') if external else 'lab-template',
                    "table_bounds": external.get('table_bounds') if external else None,
                    "visible_controls": sorted(controls),
                    "scope": "lab artwork and classic green-table printed-rank OCR; unreadable or inconsistent evidence is gated"}
