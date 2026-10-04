"""R1 image observations. No shoe reconstruction, hidden labels or live advice."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import time
from typing import Literal, Protocol

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .calibration import NormalizedROI
from .corner_vision import CornerCardDetector, VERSION, validate_layout
from .engine import hand_value

Rank = Literal['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
Suit = Literal['C', 'D', 'H', 'S']


class ObservedCard(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    zone: Literal['dealer', 'player:0']
    rank: Rank | None
    suit: Suit | None
    visibility: Literal['readable', 'covered', 'unreadable']

    @model_validator(mode='after')
    def consistent_presence(self):
        if (self.visibility == 'readable') != (self.rank is not None):
            raise ValueError('Readable requires an observed rank; unreadable never supplies a rank.')
        if self.visibility == 'covered' and self.suit is not None:
            raise ValueError('Covered cards cannot disclose a suit.')
        return self


class HandObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    cards: list[ObservedCard] = Field(max_length=52)
    table_state: Literal['cards_present', 'empty', 'uncertain']
    phase: Literal['player', 'dealer', 'waiting', 'settled', 'unknown']
    controls: list[Literal['hit', 'stand', 'double', 'split', 'surrender']] = Field(max_length=5)
    player_total: int | None = Field(ge=0, le=100)
    dealer_total: int | None = Field(ge=0, le=100)
    unknown_fields: list[str] = Field(max_length=20)
    blockers: list[str] = Field(max_length=20)

    @model_validator(mode='after')
    def consistent_table(self):
        if self.cards and self.table_state != 'cards_present':
            raise ValueError('Present cards require cards_present.')
        if not self.cards and self.table_state == 'cards_present':
            raise ValueError('No observed objects cannot mean cards_present.')
        if any(len(s) > 300 for s in self.unknown_fields + self.blockers):
            raise ValueError('Diagnostic strings are bounded.')
        if len(self.controls) != len(set(self.controls)):
            raise ValueError('Controls must not be duplicated.')
        return self


@dataclass(frozen=True)
class FrameInput:
    """Only native table pixels and calibration; never evaluator annotations."""
    frame_id: str
    table_png: bytes
    details: tuple[tuple[str, bytes], ...]
    layout: dict
    source_size: tuple[int, int]
    table_box: tuple[int, int, int, int]

    def images(self):
        return (('table', self.table_png),) + self.details


def png_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def prepare_frame(image: Image.Image, layout: dict) -> FrameInput:
    image = image.convert('RGB')
    if image.width * image.height > 16_000_000:
        raise ValueError('Source exceeds the bounded image experiment size.')
    regions = validate_layout(layout)
    x, y, w, h = regions['table'].to_pixels(*image.size)
    table = image.crop((x, y, x + w, y + h))
    mapped = {'table': (0., 0., 1., 1.)}
    details = []
    for name, region in regions.items():
        if name == 'table':
            continue
        rx, ry, rw, rh = region.to_pixels(*image.size)
        mapped[name] = tuple(NormalizedROI.from_pixels((rx-x, ry-y, rw, rh), w, h).to_dict().values())
        details.append((name, png_bytes(image.crop((rx, ry, rx + rw, ry + rh)))))
    encoded = png_bytes(table)
    # Identity binds both source pixels and calibration; repeated ranks are not identity.
    import json
    frame_id = sha256(image.tobytes() + json.dumps(layout, sort_keys=True).encode()).hexdigest()
    return FrameInput(frame_id, encoded, tuple(details), mapped, image.size, (x, y, w, h))


@dataclass
class ReaderResult:
    frame_id: str
    reader: str
    status: str
    observation: HandObservation | None
    elapsed_ms: float
    diagnostics: dict


class VisionReader(Protocol):
    name: str
    def read(self, frame: FrameInput) -> ReaderResult: ...


class LocalVisionReader:
    name = VERSION

    def __init__(self, *, surface_profile='legacy'):
        if surface_profile not in ('legacy', 'neutral'):
            raise ValueError('Unknown surface profile.')
        self.surface_profile = surface_profile
        if surface_profile != 'legacy':
            self.name = VERSION + ':neutral-index-v1'

    def read(self, frame):
        began = time.perf_counter()
        detector = CornerCardDetector(frame.layout, surface_profile=self.surface_profile)
        detections = detector.detect(Image.open(BytesIO(frame.table_png)))
        reasons = list(detector.context.get('reasons', []))
        if detector.last_diagnostics.get('rejected_card_candidates'):
            reasons.append('Unresolved local proposals; physical presence is not established for each proposal.')
        observation = HandObservation(
            cards=[ObservedCard(zone=d.zone, rank=d.rank, suit=d.suit, visibility=d.visibility) for d in detections],
            table_state='cards_present' if detections else 'uncertain', phase='unknown', controls=[],
            player_total=None, dealer_total=None, unknown_fields=['phase', 'controls'], blockers=reasons)
        return ReaderResult(frame.frame_id, self.name, 'completed', observation,
                            (time.perf_counter()-began)*1000, detector.last_diagnostics)


def analysis_gate(observation: HandObservation, *, capability='blackjack-image', require_turn=False):
    """Unknown suits/history do not block rank-only study. This is not live certification."""
    if capability not in ('blackjack-image', 'poker-cards'):
        raise ValueError('Unknown capability.')
    reasons = list(observation.blockers)
    if observation.table_state != 'cards_present':
        reasons.append('Table presence is not established.')
    if capability == 'poker-cards':
        if not observation.cards or any(c.rank is None or c.suit is None for c in observation.cards):
            reasons.append('Poker requires observed ranks and suits; hidden opponent cards are excluded from this R1 capability.')
    else:
        if observation.phase in ('dealer', 'waiting', 'settled'):
            reasons.append('Observed phase is not a player decision.')
        player = [c for c in observation.cards if c.zone == 'player:0']
        dealer = [c for c in observation.cards if c.zone == 'dealer' and c.visibility != 'covered']
        if len(player) < 2 or any(c.rank is None for c in player):
            reasons.append('Need at least two readable player cards.')
        if len(dealer) != 1 or dealer[0].rank is None:
            reasons.append('Need exactly one readable dealer upcard.')
        if player and all(c.rank for c in player):
            total = hand_value([c.rank for c in player])[0]
            if total > 21:
                reasons.append('Player hand has already busted.')
            if observation.player_total is not None and observation.player_total != total:
                reasons.append('Observed player total disagrees with the cards.')
        if len(dealer) == 1 and dealer[0].rank and observation.dealer_total is not None:
            if hand_value([dealer[0].rank])[0] != observation.dealer_total:
                reasons.append('Observed dealer total disagrees with the upcard.')
    if require_turn and observation.phase != 'player':
        reasons.append('Player turn is not established.')
    return {'usable': not reasons, 'reasons': reasons, 'scope': capability,
            'live_certified': False, 'shoe_history_certified': False}


def image_analysis(observation, rules):
    """Reuse the mathematical engine, with configured-rule assumptions stated."""
    gate = analysis_gate(observation)
    if not gate['usable']:
        return {'gate': gate, 'advice': None}
    from .advice import recommend
    player = [c.rank for c in observation.cards if c.zone == 'player:0']
    up = next(c.rank for c in observation.cards if c.zone == 'dealer' and c.rank)
    try:
        advice = recommend(player, up, rules, allowed=observation.controls or None, count_complete=False)
    except ValueError:
        return {'gate': {**gate, 'usable': False, 'reasons': ['Configured rules or visible controls conflict.']}, 'advice': None}
    return {'gate': gate, 'advice': advice, 'mode': 'image-study-only',
            'conditional_on_configured_rules': True, 'player_turn_verified': observation.phase == 'player'}
