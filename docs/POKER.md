# Texas Hold'em lab — experimental visual input

The independent Hold'em module uses 52 physical card identities. Enter `AS KH`
or ranks with Unicode suits. The board has zero, three, four or five cards.
Known dead cards and duplicate physical cards are checked before calculation.

**Texas Hold'em lab** offers image upload/drop and continuous screen capture.
Drag one rectangle around your hole cards and another around the community
cards. Their coordinates are normalized to the actual displayed source. A
blank board requires **Empty board is confirmed as preflop**. Video requires
three stable observations. Motion or expired capture clears equity. The session
accepts flop→turn→river prefixes and resets when new hole cards appear; ambiguous
board regressions are gated. Exported events record observed card transitions.

Calibrated vision reads supported original card corners, with a printed-card
fallback. Any unknown suit, hidden card, duplicate or partial hand prevents the
calculation. External provider coverage remains experimental. Pot size, call cost,
opponent count/ranges and dead cards are explicit user inputs.

Seven-card ranking handles kickers, wheel straights, flushes, two triples,
full houses and ties. Monte Carlo samples unknown cards without replacement.
Each explicitly listed two-card range combination is equally weighted; `null`
means uniformly random. Blockers and cross-opponent collisions are rejected
jointly. Impossible or excessively sparse joint ranges fail with a readable error.

Equity is the expected share of the pot, including split pots. Win/tie/loss,
sampling intervals, pot odds `call / (pot + call)` and showdown call EV
`equity × (pot + call) − call` are separate outputs. These assume showdown with
no future betting; rake and side pots are excluded. Equity does not identify an
optimal fold/call/raise policy.

Tests cover ranking, duplicate rejection, ranges/blockers, shared-pot equity,
input limits and calibrated card identity. Treys 0.1.8 independently agreed on
all 6,000 random pair orderings. Complete external poker sessions and automatic
seat/stack/pot/action OCR remain roadmap work.

Analysis and education only. Not financial advice. No guaranteed outcomes.
