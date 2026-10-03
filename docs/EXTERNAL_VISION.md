# External table recognition — 1.0.1

The reported failure had two independent causes: the 1.0 detector was restricted
to the lab's font and ASCII suit labels, and empty manual placeholders were sent
as one empty card. The new classic profile recognizes printed rank corners and
the input parser validates actual entries before contacting the backend.

## Recognition contract

The source is RGB pixels only. OpenCV finds the largest green felt and white card
bodies. A bundled, hash-verified PP-OCRv4 recognition model reads corner ranks,
English turn messages, numeric hand totals and enabled button captions. There
is no game-memory access, future-shoe access, cloud request or runtime model
download. OCR token scores are internal gates, not calibrated probabilities.

The compatible profile expects top dealer cards, lower player cards, blue total
badges and green controls beneath the felt. A missed card or mismatched visible
total withholds advice. Split/multiple active player hands require explicit
manual confirmation. Other artwork, localized game captions and missing
controls are not certified by this profile. The lab detector remains available.

Three observations stabilize cards. Repeated visible exposures count once;
new cards and dealer reveals update the observed rank pool. A visible settled
phase followed by a player phase, or a cleared table, starts a new round.
Unseen earlier cards, skipped round boundaries and shuffles cannot be recovered
from a single view. Declare the decks/rules and external shuffle explicitly.

## Regression evidence

The user's supplied diagnostic image was tested privately at full desktop size,
frontend maximum size, game-window crop and table crop. It recognized player
**7, 2**, dealer **6**, total **9**, player phase and Hit/Stand/Double controls.
Eight stable video-observer submissions showed **Double**, three observed cards
and running count **+2**, without duplicate counts. These are repeated-image
observer checks, not a claim about every round of that proprietary game.
The private screenshot and third-party game artwork are not redistributed.

Original synthetic regression artwork uses printed corners and symbol pips,
independently of the old lab font/suit templates. Tests cover all 13 ranks,
three scales, duplicate preview exclusion, missed-card gates, visible controls,
hit/stand, dealer reveal, settlement, identical redeals and the single-image API.
Release verification additionally exercises the frozen OCR model and actual
HTTP image/live paths without Python or Node on the runtime PATH.

Model provenance and Apache-2.0 terms are retained in
[the model notice](../bjlab/assets/ocr/NOTICE.md).
