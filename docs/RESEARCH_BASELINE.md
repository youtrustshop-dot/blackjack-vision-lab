# Exposure continuity and Poker Phase 0

This is an **unreleased source candidate** on the frozen 1.1.1 champion,
commit `4f074efd53066a95d64ca1ed53de03479a8adcba`. The published native app,
installer and desktop shortcut still identify that champion. A new native
release requires its own artifact validation.

The narrow goals are to diagnose missing blackjack exposures and verify a
deterministic heads-up poker engine. UI expansion, strategic learning, new
vision models and profitability claims are outside this increment.

## What the old 1 / 4 / 4 deficits actually meant

The original dataset and reports remain unchanged under
`experiments/live_reliability/`. Traces are retained under
`experiments/continuity_phase0/`.

| Case | Diagnosis | Resolution |
| --- | --- | --- |
| Seed 12983, round 10 | The fixture invented position-based suits and displayed a fifth 6 of spades in a four-deck shoe. Conservation correctly rejected it. | Preserve the invalid fixture as a negative test; new corpora render the simulator's actual physical card suits. |
| Seed 77271, round 3 | The next hand arrived already settled. The lifecycle only opened new player turns, so four new cards were associated with the previous round. | A witnessed empty table also permits a new settled-only round. |
| Seed 61073, round 10 | The same settled-only boundary error lost four exposures. | Apply the same lifecycle fix; preserve the original evidence. |
| Stable empty table | A normal round clearing was fed into the occlusion tracker, creating persistent lost-track issues. | Close tracks once after stable empty-table evidence; keep exposure history. |
| Corrected physical fixture, seed 77271, round 7 | A tightly cropped red 2 had OCR score 0.631 and was discarded despite being read as 2. The white-margin retry returned the same rank with score 0.9997. | Normalize the crop margin without lowering the 0.80 acceptance threshold. |

A stable total mismatch or rejected rank also withholds count reliability. If
it resolves within the same round, the complete exposure can be recovered. If
cards leave before resolution, the missing history remains compromised. An
unrevealed dealer hole card never becomes an invented rank. Motion withholds
current count certainty while stabilization is pending.

## Measured results

The physically corrected development corpus contains the same 30 game rounds
as the old test, rendered with actual suits. The unchanged 1.1.1 source obtains
41/44 timely basic decisions, 10 falsely reliable count frames and only 8/104
exact stabilized count endpoints. This distinguishes fixture correction from
runtime correction; the baseline and candidate receive the same pixels.

The candidate's **single-use final synthetic holdout** contains three new
sessions, 30 rounds and 582 observations:

- 37/37 timely correct basic recommendations; zero falsely confident actions.
- 97/97 exact stabilized count endpoints: exposed-rank inventory, running
  count and physical remaining cards.
- Zero sampled frames with an incorrectly reliable count.
- Zero final exposure deficits and zero final running-count error in each session.

This supports the declared synthetic artwork, single player hand, four-deck
hit/stand rules and observation schedule. All pixel corpora use the existing
development renderer. **Independent external provider recordings are still
required before accepting external shoe reconstruction.** It does not establish
universal recognition, physical suit recognition, unseen transient-event
recovery, browser end-to-end latency or economic advantage.

## Poker engine scope and references

`bjlab/poker_engine.py` implements heads-up no-limit Texas Hold'em cash with
integer chips, declared blinds, starting stacks at least one big blind, one
fixed runout and zero rake. It covers preflop/postflop position, the BB option,
minimum raises, short all-ins, calls/folds, unmatched refunds, showdown,
chip conservation and deterministic history replay. Observations hide the
opponent's hole cards and unrevealed board. Folded hands do not reveal private
cards merely because the hand ended.

The engine imports neither PokerKit nor Treys. The reference generator uses
**PokerKit 0.7.6** to choose actions and record all intermediate expected
states. **Treys 0.1.8 and PokerKit** independently validate hand ordering; a
reference disagreement fails generation and requires investigation.

The final held-out corpus passes:

- 2,000 fixed-deal hands and 6,908 intermediate state comparisons.
- 6,000 random ordering comparisons of five-, six- and seven-card hands.
- Zero state, evaluator or history-replay divergences.

Development and validation add 3,000 hands and 9,000 evaluator comparisons.
These are correctness tests, not win-rate or strategy-strength experiments.

The first development failure is retained. It exposed incorrect adapter card
serialization and a legal voluntary-fold difference; the adapter was corrected
and the engine accepts folding when checking is available. PokerKit emits its
warning for those deliberately covered folds.

`pot_layers` additionally verifies a three-seat accounting example against
PokerKit. Heads-up unequal contributions produce refunds; contested multiway
side pots do not expand the two-seat betting engine's supported scope.

## Frozen datasets and final evaluation

Six corpora are physically separate: blackjack and poker each have train,
validation and final-holdout directories. Here, “train” means development data;
no ML model was trained. Session groups are disjoint across partitions.

`bjlab/research_protocol.py` writes exclusive seals, makes files read-only and
verifies every file digest. Read-only flags are an operational guard, not a
security boundary. Version-controlled seal digests detect later modification.
Each final corpus has a directory-bound exclusive consumption record tied to
the candidate source fingerprint and baseline commit. Failed runs also consume
a final holdout. The final datasets published here have already been consumed;
they are historical regression evidence, never fresh final tests for a later
candidate. Future model or threshold changes require new final data.

See [registry](../experiments/continuity_phase0/registry.json),
[verification](../experiments/continuity_phase0/verification.json) and the
hash-bound corpus ZIPs. The source fingerprint binds Python modules, validation
tools, the fixture renderer and dependency declarations. Capture, transport and
display are excluded from offline observer timings.

## Reproduction

Install the optional reference packages in a project environment:

```powershell
python -m pip install -c requirements-lock.txt -e ".[dev,research]"
python -m pytest -q
```

The production app does not require these research references. The PokerKit
wheel was checked against official PyPI metadata and its SHA256 before
installation, then inspected for native/startup payloads, network/process
imports and dynamic execution calls. Static preflight is not an absolute
security guarantee; its result is retained in `pokerkit-preflight.json`.

Expand a corpus ZIP into a new directory, verify its seal against the registry,
then reproduce its **historical** results:

```powershell
python validation/tools/live_session_benchmark.py run --dataset <blackjack-corpus> --output <report.json>
python validation/tools/poker_phase0_benchmark.py run --corpus <poker-corpus>/corpus.json --output <report.json>
```

The original legacy generator remains the default for historical reproduction.
Use `generate --physical-suits` and new seeds for new physically valid
blackjack sessions. Never overwrite an existing manifest or relabel a consumed
dataset as an unseen holdout. Corpora include original synthetic pixels only;
private user screenshots are not included.

## Next acceptance gates

| Stage | Required evidence |
| --- | --- |
| External blackjack continuity | Authorized independent full recordings; separately annotated exposures and shuffle provenance; exact inventory and safe abstention measured together. |
| Poker equity/ranges | Independent exact small-state checks, blockers and range weighting; no optimal-betting inference from equity alone. |
| First strategic baseline | A declared restricted heads-up game and zero-rake CFR reference with independent correctness and applicable regret/exploitability checks. |
| Challenger evaluation | Frozen comparisons against the champion and independent opponents; uncertainty and regression guards; preserve rollback artifacts. |
| Rake/economics | Explicit opponent population, costs and uncertainty; do not transfer two-player zero-sum guarantees unchanged to a rake model. |
| Poker vision | Integrate only after state/strategy evaluation; measure perception errors separately. |

Win rate, strategic quality and economic validation remain distinct. There is
no strategic learning or validated economic edge in Phase 0.
