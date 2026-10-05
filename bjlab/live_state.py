"""Compact research R1 wire contract; v1/v2 and installed behavior stay frozen.

Numbers retain their observed label and named native view. Pixel coordinates
are deliberately absent, never fabricated to satisfy v2. This is the same
restricted English TOTAL attribution profile, not arbitrary-provider support.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .grounded_state import VisibleCard, grounded_gate
from .state_reader import HandObservation, ObservedCard, Rank, Suit

CONTRACT_VERSION = 'grounded-r1-live-v3'


class LiveCard(VisibleCard):
    model_config = ConfigDict(extra='forbid', strict=True, populate_by_name=True)
    zone: Literal['dealer', 'player:0'] = Field(alias='z')
    rank: Rank | None = Field(alias='r')
    suit: Suit | None = Field(alias='s')
    visibility: Literal['readable', 'partial', 'covered', 'unreadable'] = Field(alias='v')


class LiveNumber(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, populate_by_name=True)
    value: int = Field(alias='v', ge=0, le=1_000_000)
    role: Literal['player_total', 'dealer_total', 'ui', 'unknown'] = Field(alias='r')
    label: str | None = Field(alias='l', max_length=80)
    view: Literal['table', 'dealer', 'player:0', 'controls'] = Field(alias='w')

    @model_validator(mode='after')
    def observed_label_required(self):
        if self.role in ('player_total', 'dealer_total'):
            words = (self.label or '').upper().replace(':', ' ').split()
            actor = 'PLAYER' if self.role == 'player_total' else 'DEALER'
            if actor not in words or 'TOTAL' not in words:
                raise ValueError('Explicit associated PLAYER/DEALER TOTAL label required.')
        return self


class LiveObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, populate_by_name=True)
    cards: list[LiveCard] = Field(alias='c', max_length=52)
    table_state: Literal['cards_present', 'empty', 'uncertain'] = Field(alias='t')
    phase: Literal['player', 'dealer', 'waiting', 'settled', 'unknown'] = Field(alias='p')
    controls: list[Literal['hit', 'stand', 'double', 'split', 'surrender']] = Field(alias='a', max_length=5)
    numbers: list[LiveNumber] = Field(alias='n', max_length=12)
    blockers: list[Literal['split', 'insurance', 'ambiguous_roles', 'unreadable_controls', 'occluded_table']] = Field(alias='b', max_length=5)

    @model_validator(mode='after')
    def coherent_table(self):
        if bool(self.cards) != (self.table_state == 'cards_present'):
            raise ValueError('Card presence and table state disagree.')
        if len(set(self.controls)) != len(self.controls) or len(set(self.blockers)) != len(self.blockers):
            raise ValueError('Duplicate control/blocker.')
        return self

    def totals(self):
        totals, conflicts = {}, []
        for number in self.numbers:
            if number.role not in ('player_total', 'dealer_total'):
                continue
            if number.value > 100:
                conflicts.append('Attributed hand total outside supported range.')
            elif number.role in totals and totals[number.role] != number.value:
                conflicts.append('Conflicting attributed hand totals.')
            else:
                totals[number.role] = number.value
        return totals, conflicts

    def legacy_gate_view(self):
        totals, conflicts = self.totals()
        return HandObservation(cards=[ObservedCard(zone=c.zone, rank=c.rank, suit=c.suit,
            visibility='covered' if c.visibility == 'covered' else 'readable' if c.rank else 'unreadable')
            for c in self.cards], table_state=self.table_state, phase=self.phase, controls=self.controls,
            player_total=totals.get('player_total'), dealer_total=totals.get('dealer_total'),
            unknown_fields=[], blockers=list(self.blockers)+conflicts)


def live_gate(observation, **kwargs):
    return {**grounded_gate(observation, **kwargs), 'contract': CONTRACT_VERSION,
        'numeric_provenance': 'observed_label_and_named_native_view', 'number_coordinates': 'not_supported'}


def wire_schema():
    """One identical provider schema. String bounds remain local validators.

    Google's documented JSON Schema subset omits maxLength. Neither provider
    receives it here; no constraints on interpretation or provenance are dropped.
    """
    def trim(value):
        if isinstance(value, list): return [trim(v) for v in value]
        if isinstance(value, dict): return {k: trim(v) for k, v in value.items() if k not in ('title', 'maxLength')}
        return value
    return trim(LiveObservation.model_json_schema(by_alias=True))


def gemini_structured_schema():
    """VISION-020 opt-in: enforce the card count locally, not in Gemini grammar.

    One-pixel/prompt-identical A/B/A control: c.maxItems=52 gives HTTP400,
    omitting only that constraint gives HTTP200, reintroducing it gives HTTP400.
    All other wire constraints and every strict local validator remain intact.
    This is an empirical trigger in this schema/model, not a general prohibition
    of maxItems in Google's API or proof of the internal compiler's reason.
    """
    schema=wire_schema()
    schema['properties']['c'].pop('maxItems')
    return schema
