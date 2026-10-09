# One-layout session gate: Freegames classic

This increment targets `https://freegames.org/blackjack/`, the classic layout
shown in the supplied development screenshots. Initial table/dealer/player/
controls calibration is allowed. Player-turn confirmation during the session
is **disabled**. No model, desktop replacement or additional Poker strategy is
promoted. The installed/public 1.1.1 remains frozen at `4f074ef`.

## Current evidence and remaining dependency

There are no original complete provider videos in the existing project corpus.
The original screenshot and its clipped preview are one game moment. Existing
own-renderer sequences cannot establish provider-session reliability. The new
runner has unit verification, **zero executed provider sessions**, and no
session pass result. An existing local recording path has been requested.

The calibrated corner reader still reports unknown phase. It therefore cannot
meet the automatic-turn gate yet. The next pixel-context implementation must
use visible controls/transitions from development recordings, never annotation
phase, simulator round IDs or a manual turn flag. This document does not present
that missing implementation as complete.

## Recordings needed before another model comparison

| Slot | Purpose | Minimum content |
| --- | --- | --- |
| FG-dev-01 | Diagnose cards, controls, artwork and transitions | One original run, at least 20 rounds |
| FG-dev-02 | Develop/recheck automatic phase and temporal association | A different original run, at least 20 rounds |
| FG-verify-01 | First frozen verification | A new run, at least 20 rounds, unseen during development |
| FG-verify-02 | Second frozen verification | Another new run, at least 20 rounds, unseen during development |

Use play-money simulation or authorized replay. No automatic site interactions
are part of collection. Save original WebM/MP4/AVI locally, rather than filming
the monitor or recording the app's miniature preview. The app already offers
**Local video replay → Record video locally** for the selected source, with a
200 MiB limit and browser encoding at approximately 2 Mbps. Save its timing JSON
too. Browser capture/encoder drops are not measured. An existing screen recorder
with original source pixels is also acceptable; no new software is required.

Select the game window or its tab, with all card zones and controls visible at
native resolution. Prefer at least 30 source frames/second; record actual
resolution, measured timing and capture settings, rather than claiming that
the requested rate was achieved. Keep card corners readable (a roughly
120-pixel-high card is a collection target, not a detector guarantee). Do not
enlarge a tiny preview to manufacture source detail. Preserve black bands and
full source dimensions so calibration can be checked.

Start before an observable empty table/new deal and end after the last settled
hand clears. Include ordinary decisions, overlapping cards, reveal, immediate
settlement without a player decision, repeated identical initial ranks in
different rounds, and several complete clear/deal transitions. Collect visible
badges, clubs/face artwork and other actual hard negatives. Do not repeat frames
or slow transitions to make confirmation pass.

Development additionally needs a controlled occlusion/interruption and
recovery, without changing source dimensions, plus a same-size scroll/movement
case. A source-size change is a separate capture/calibration restart; the runner
rejects silently resized recordings. Complete ordinary verification sessions
and deliberately ambiguous negative-control clips are distinct evidence.
An unobservable boundary must remain uncertain even if the game operator knows
what happened. The operator's knowledge is not an inference input.

Four recordings of the same layout are four sessions, **not four unseen visual
families**. Re-encoding, splitting a video or copying it under a new filename
does not create independence. The manifest blocks reused hashes/run IDs;
provenance review must also check re-encoded/overlapping material. Photos and
the consumed screenshots remain diagnostic regressions only.

## Annotation and freeze

Store videos and annotations under ignored `artifacts/provider-sessions/`.
Declare local-analysis permission, source/engine family, capture-run ID,
partition, rules assumptions, calibration rectangles, source size, reviewer and
SHA256 for each file. Unknown deck/RNG/shuffle behavior stays unknown. The
runner declares a conditional rules model and never certifies the provider's
physical shoe or true count.

Annotate the **whole** timeline contiguously, including failed, short, occluded
and unknown intervals. A decision interval begins when its final required
cards/controls become visible, not when our program recognizes them. Each
interval includes current visible player/dealer ranks, independently checked
basic action and rule reference (or null when no decision is possible), round
label for evaluation only, observable/ambiguous/no boundary plus its visible
reason, and cumulative observed face-up rank inventory when known. Record
post-calibration manual interventions, including turn confirmations or restarts.

Give each physical card a unique instance ID and exactly one first face-up
exposure timestamp; a hidden card is present but has no known rank. Reveal
retains the same physical instance. Two identical cards are different instances;
two corners of the same card are not two exposures. The validator checks
inventory checkpoints against these first-exposure annotations. Use separate
component annotations for card bodies, upper corners, ranks, suits, backs and
hard negatives; the session runner does not pretend to score suit/box AP.

Review borderline transitions on native pixels before freezing. Record whether
review was human/assistant, and resolve disagreements; do not call assistant
annotations an independent human reference. Keep a truly unobservable history
marked incomplete. Such negative controls can demonstrate safe abstention;
they cannot establish count reconstruction acceptance.

The policy below is versioned before new verification data are examined:

| Gate | Frozen rule |
| --- | --- |
| Replay sampling | Nominal 350 ms single-table cadence, first actual decoded frame after cadence/measured local busy time; original PTS, no duplicated inputs |
| Decision deadline | 1500 ms after the independently annotated visibility onset, including measured local processing; browser/HTTP/display delays require a separate live test |
| Useful decision coverage | At least 95%, with all short/difficult intervals in the denominator |
| Verification support | At least two distinct complete sessions, at least 20 rounds each |
| Incorrect/stale actionable advice | Zero observed frames in this finite sample |
| Manual interventions after calibration | Zero |
| Observed inventory | Zero per-rank L1 at every annotated checkpoint; no unknown checkpoint in a count pass |
| Exposure journal | Zero missed/late and unmatched rank/role/time exposure events |
| Reliable provider shoe claim | Zero; shoe/RNG history is not established by video |

Zero observed errors is not a zero-risk guarantee. A replay pass is not a live
latency pass or a generalization guarantee. Preserve failed receipts. Freeze
all Python candidate code, the runner and key runtime versions via `--fingerprint`, files/annotations
via SHA256, and the manifest before opening verification results. Once examined,
verification becomes historical regression evidence for later candidates. A
changed fingerprint requires new verification; no retuning on a consumed test.

## Local manifest format and commands

`validation/protocols/freegames-session-plan.json` is an honest empty collection
plan, not a dataset. Populate a private manifest only after original files exist:

```json
{
  "schema": 1,
  "layout_family": "freegames-classic",
  "candidate_fingerprint": "output of --fingerprint",
  "policy": "copy the policy object from the versioned collection plan",
  "sessions": [{
    "session_id": "FG-dev-01",
    "capture_run_id": "unique original recording run",
    "partition": "development",
    "input_kind": "original-provider-video",
    "video": "FG-dev-01.webm",
    "video_sha256": "SHA256",
    "annotations": "FG-dev-01.annotations.json",
    "annotations_sha256": "SHA256",
    "source_size": [1920, 1080],
    "authorization": {"local_analysis": true, "external_upload": false},
    "provenance": "actual source, recorder, timestamps and capture settings",
    "rules_provenance": "verified rules and explicitly declared unknown assumptions",
    "annotation_review": "reviewer/method and disagreements resolved",
    "config": {
      "layout": {"table": [0, 0, 1, 1], "dealer": [0.2, 0.2, 0.6, 0.2], "player:0": [0.2, 0.5, 0.6, 0.2], "controls": [0.1, 0.8, 0.8, 0.15]},
      "rules": {"decks": 4}
    }
  }]
}
```

Those rectangles/decks are illustrative, not Freegames calibration or verified
rules. Replace them with the actual initial source calibration and documented
conditional rules. The JSON policy must be an object, not the illustrative
string above. An annotation file has `intervals`, `exposures`, and
`manual_interventions` arrays:

```json
{
  "intervals": [{"start_s": 0, "end_s": 1, "turn": "waiting", "boundary": "observable", "boundary_evidence": "empty table with visible deal controls", "history_complete": true, "observed_rank_inventory": {}, "player": [], "dealer": [], "expected_action": null, "round_label": null}],
  "exposures": [],
  "manual_interventions": []
}
```

Add every later interval and first exposure, for example
`{"instance_id":"round1-player0-card0","time_s":1.4,"rank":"K","suit":"D","zone":"player:0"}`.
An action requires `action_reference`; a post-interruption decision interval
can include `recovery_check: true`. All times use original video PTS relative
to zero. The decoder rejects missing/nonmonotonic PTS rather than guessing.

Run from the repository root:

```powershell
.venv/Scripts/python.exe -X utf8 -m validation.tools.provider_session_replay --fingerprint
.venv/Scripts/python.exe -X utf8 -m validation.tools.provider_session_replay artifacts/provider-sessions/manifest.json --check-only
.venv/Scripts/python.exe -X utf8 -m validation.tools.provider_session_replay artifacts/provider-sessions/manifest.json --private-traces artifacts/provider-sessions/traces --output artifacts/provider-sessions/receipt.json
```

The observer receives only pixels, initial regions and rules. Annotation truth
enters scoring after inference. The replay mirrors the UI's native table crop,
then rebases role regions, without resizing. Traces preserve detections, gates,
round/tracker hit counts, events and per-checkpoint rank errors. Public summaries
retain aggregates/hashes, with offline process p50/p95 and frame-budget overruns.
The early sequential confirmation windows are measured, not disguised with
extra repeated frames. No costly solver job is used to hide a vision failure.
The 350 ms nominal cadence matches the single-table UI; local processing longer
than that interval skips source samples instead of building a queue. This is a
bounded offline approximation of one upload in flight, not measured browser
transport. Late advice is checked against the annotated state at local processing
completion and counted as stale when that state has changed.

Exposure matching uses rank/role/time; unmatched events include late, wrong and
duplicate emissions. It is not geometric detector AP or a physical ID-switch
score. Inspect private spatial traces/annotations to classify unmatched events
before a promotion decision. Suit/presence component scoring and actual live
capture-to-display p50/p95 remain separate required checks. Minimized desktop,
multi-monitor/DPI and screen-sharing tests of the advisor remain unexecuted
until physically performed; HTTP replays do not satisfy them.
