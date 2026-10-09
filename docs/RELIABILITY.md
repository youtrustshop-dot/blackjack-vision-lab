# Complete-session reliability — 1.1.1

The [1.1.1 increment](LIVE_RELIABILITY_INCREMENT.md) separates basic response
from estimates, gates unknown initial history and bounds actual server work.
New synthetic complete sessions retain missed exposures and count abstentions;
they do not replace held-out provider evaluation. Earlier 1.1 visual/Clef results
below preserve their original development scope.

The reported failures were real: a short rank crop missed overlapping cards,
and active tracks could retain cards from an earlier hand. Passing the previous
Windows screenshot did not establish reliability on FreeBlackjack.games.

## Implemented architecture

`screen video → every-frame motion monitor → bounded pixel recognition →
stable round lifecycle → current hand / exposure history → integrity gates →
basic policy / conditional finite-pool estimates → advisor`

The shared source is continuous video. Every advancing frame delivered by the
browser reaches a cheap 96×54 motion monitor. Heavy recognition has one request
in flight, at least 350 ms apart for blackjack and 500 ms for poker. Busy work is
skipped, never queued. These intervals are schedules, not guarantees about FPS.
Motion immediately clears old advice; responses from an earlier motion epoch,
source or hand are rejected. Frozen capture expires guidance.

External rounds require three stable observations before tracking can commit
new exposures. The current hand is taken from current pixels, independently of
past exposures. A seen settlement permits a new identical deal. An abrupt new
hand without its boundary, a capture gap over 2.5 seconds, or a historical hidden
card that left without a readable reveal disables count-derived estimates.
Basic policy remains available for a valid current hand. Counts become `null`,
not a plausible invented number. External shuffles require a user declaration.
This cannot prove that a never-detected card did not exist.

Printed-rank crops preserve the whole corner. EN/IT controls distinguish enabled
caption text from decorative borders. Independent visible totals cross-check the
recognized hand. The largest compatible external table is selected, preventing
smaller previews from duplicating the same cards. Unsupported split layouts,
unreadable totals or uncertain phases require confirmation.

Clef is an optional independent check on the exact captured image. It cannot
write cards or counts. A confident disagreement removes guidance; incomplete
verification remains visibly inconclusive. Late results cannot verify a new hand.
The fast path remains available when the separate runtime is offline.

## Evidence and boundaries

- Seven private reported screenshots: all 26 annotated visible ranks and all
  current hands were correct after the fix. Private screenshots stay local.
  Four small black suit symbols remain unknown; no guessed suit is supplied.
- A private screenshot replay recovered the active A+7, 9+8 and A+5 hands,
  without retaining old 3/5/K cards. Missing boundaries correctly disable count
  estimates. This is not a continuous-video or whole-shoe accuracy measurement.
- Original EN/IT side-total fixtures cover all 13 overlapping ranks, scaled
  layouts, disabled controls, wrong totals, repeated identical deals, reveals
  and capture gaps. Original suit tests include a deliberate tiny-symbol abstention.
- Actual Clef image experiments are in [the visual report](CLEF_VISUAL_VERIFICATION.json).
  All annotated raw choices were correct in this small development set, with
  below-threshold answers retained. This does not establish general accuracy.
- Hold'em hand ranking was independently compared with Treys 0.1.8 over 6,000
  pairs of random 5/6/7-card hands: zero ordering mismatches (12,000 hands).
  This checks rankings, not vision or optimal betting.

## Provider matrix

| Source | Evidence | Status |
|---|---|---|
| Original lab cards | Owned video, original image fixtures and retained multi-round tests | Controlled support |
| Windows classic blue-badge table | Private reported screenshot and retained original compressed-video regression | Compatible printed-card profile |
| FreeBlackjack.games | Seven private reports, side-total EN/IT reader and original overlap fixtures | Development regressions passed; held-out full sessions pending |
| [Pip](https://github.com/playpip/pip-web) | MIT, public play-chip Hold'em source researched | Candidate for held-out visual sessions; not yet tested |
| [mhluska simulator](https://github.com/mhluska/blackjack-simulator) | MIT mathematical reference with retained numerical studies | Numerical reference, not new visual evidence |
| Other providers / cameras | No licensed held-out complete-session corpus yet | Unsupported until evaluated |

The next acceptance programme uses disjoint licensed sessions per provider:
exact current-hand accuracy, incorrect actionable advice, missed/duplicate
exposures, final count drift, phase errors and capture-to-advice p50/p95. A new
layout does not become supported merely because one screenshot worked.

## Local replay evidence

The optional **Local video replay → Record video locally** saves WebM plus timing
metadata on this computer. It is off by default and capped at about 200 MiB.
Observation/event JSON exports remain separate. The browser may drop capture or
encoder frames; those losses are not measured by this recorder. Recording does
not upload footage, and its existence alone does not prove recognition accuracy.

The next external session gate is restricted to Freegames classic, with initial
calibration permitted and no manual player-turn flag. The exact recording slots,
annotation/freeze rules and local runner are in
[PROVIDER_SESSION_PROTOCOL.md](PROVIDER_SESSION_PROTOCOL.md). No original complete
provider video has yet been evaluated by this gate. The calibrated reader still
has unknown phase; its earlier assisted-still result is not an autonomous session.

## Can a model understand the whole game?

A video model alone does not replace memory. The implemented session combines
visible observations with stable state transitions and immutable exposure events.
It understands supported observable transitions and flags missing information.
It cannot infer hidden cards, unseen shuffles or a provider's complete rules.
Dense Clef inference on every video frame is not feasible on the measured GPU.
An evaluated detector plus temporal state and occasional independent verification
is the current design. A faster model needs its own labeled-session and latency
comparison before replacing it.
