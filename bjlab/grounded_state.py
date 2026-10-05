"""Versioned R1 observations with numeric provenance; legacy scores stay frozen.

This contract is an experimental image reader boundary, not session identity or
shoe certification. A partially visible face can expose either rank or suit.
"""
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .state_reader import HandObservation, ObservedCard, Rank, Suit, analysis_gate

CONTRACT_VERSION = 'grounded-r1-v2'


class VisibleCard(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    zone: Literal['dealer', 'player:0']
    rank: Rank | None
    suit: Suit | None
    visibility: Literal['readable', 'partial', 'covered', 'unreadable']

    @model_validator(mode='after')
    def visible_information_only(self):
        if self.visibility in ('covered', 'unreadable') and (self.rank is not None or self.suit is not None):
            raise ValueError('Covered/unreadable objects disclose no face information.')
        if self.visibility == 'readable' and self.rank is None:
            raise ValueError('Readable faces require a rank.')
        if self.visibility == 'partial' and self.rank is None and self.suit is None:
            raise ValueError('Partial means some face information is legible.')
        return self


class VisibleNumber(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    value: int = Field(ge=0, le=1_000_000)
    role: Literal['player_total', 'dealer_total', 'ui', 'unknown']
    label: str | None = Field(max_length=80)
    # Normalized x,y,width,height in the named native view, not source DPI.
    view: Literal['table', 'dealer', 'player:0', 'controls']
    box: list[float] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def grounded_attribution(self):
        x, y, w, h = self.box
        if not all(0 <= v <= 1 for v in self.box) or w <= 0 or h <= 0 or x+w > 1.001 or y+h > 1.001:
            raise ValueError('A visible number requires a bounded native-view region.')
        if self.role in ('player_total', 'dealer_total') and not (self.label and self.label.strip()):
            raise ValueError('A hand total requires an observed associated label.')
        if self.role in ('player_total', 'dealer_total'):
            # This owned v2 trial declares English TOTAL labels. Supporting a
            # provider's different label convention needs a separate profile,
            # not treating SESSION/BET or a nearby DEALER heading as a total.
            role_word = 'PLAYER' if self.role == 'player_total' else 'DEALER'
            words = self.label.upper().replace(':', ' ').split()
            if role_word not in words or 'TOTAL' not in words:
                raise ValueError('This v2 profile requires an explicit player/dealer TOTAL label.')
        return self


class GroundedObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    cards: list[VisibleCard] = Field(max_length=52)
    table_state: Literal['cards_present', 'empty', 'uncertain']
    phase: Literal['player', 'dealer', 'waiting', 'settled', 'unknown']
    controls: list[Literal['hit', 'stand', 'double', 'split', 'surrender']] = Field(max_length=5)
    numbers: list[VisibleNumber] = Field(max_length=12)
    unknown_fields: list[str] = Field(max_length=20)
    blockers: list[str] = Field(max_length=20)

    @model_validator(mode='after')
    def coherent_table(self):
        if bool(self.cards) != (self.table_state == 'cards_present'):
            if self.cards or self.table_state == 'cards_present':
                raise ValueError('Cards and table presence disagree.')
        if len(set(self.controls)) != len(self.controls):
            raise ValueError('Duplicate enabled controls.')
        if any(len(s) > 300 for s in self.unknown_fields+self.blockers):
            raise ValueError('Diagnostic strings must be bounded.')
        return self

    def totals(self):
        totals, conflicts = {}, []
        for item in self.numbers:
            if item.role not in ('player_total', 'dealer_total'):
                continue
            if item.value > 100:
                conflicts.append('Attributed hand total is outside the supported range.')
            elif item.role in totals and totals[item.role] != item.value:
                conflicts.append('Conflicting readings of the same hand total.')
            else:
                totals[item.role] = item.value
        return totals, conflicts

    def legacy_gate_view(self):
        """Explicit projection: only attributed totals participate in consistency.

        All UI/unknown numbers remain in this observation and in provenance
        scoring. They are never silently repaired into or from card identities.
        """
        totals, conflicts = self.totals()
        return HandObservation(cards=[ObservedCard(zone=c.zone, rank=c.rank, suit=c.suit,
            visibility='covered' if c.visibility == 'covered' else 'readable' if c.rank else 'unreadable')
            for c in self.cards], table_state=self.table_state, phase=self.phase, controls=self.controls,
            player_total=totals.get('player_total'), dealer_total=totals.get('dealer_total'),
            unknown_fields=self.unknown_fields, blockers=self.blockers+conflicts)


def grounded_gate(observation, *, capability='blackjack-image', require_turn=True):
    gate = analysis_gate(observation.legacy_gate_view(), capability=capability, require_turn=require_turn)
    if require_turn and observation.phase == 'player' and not set(observation.controls) & {'hit', 'stand'}:
        gate['reasons'].append('No enabled player decision control is observed.')
        gate['usable'] = False
    return {**gate, 'contract': CONTRACT_VERSION, 'numeric_provenance': 'retained',
            'r1_conditional_on_configured_rules': True, 'r2_certified': False}


def adapt_legacy(observation: HandObservation):
    if observation.player_total is not None or observation.dealer_total is not None:
        # There is no numeric region/label in v1. Never manufacture v2 provenance.
        raise ValueError('Legacy totals lack v2 provenance; preserve the v1 observation separately.')
    return GroundedObservation(cards=[VisibleCard(**c.model_dump()) for c in observation.cards],
        table_state=observation.table_state, phase=observation.phase, controls=observation.controls,
        numbers=[], unknown_fields=observation.unknown_fields+['numeric provenance unsupported by frozen local'],
        blockers=observation.blockers)


@dataclass
class GroundedResult:
    frame_id: str
    reader: str
    status: str
    observation: GroundedObservation | None
    elapsed_ms: float
    diagnostics: dict
