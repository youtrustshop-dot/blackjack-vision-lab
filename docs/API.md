# Local API contract

Run the backend using the project launcher; the interactive OpenAPI schema is at
`http://127.0.0.1:8765/docs`. The built UI is served from `ui/dist` by the same
FastAPI process. Sessions, perception trackers and solver caches are in memory.
Export an event log before restarting if it needs to be retained.

## Simulator

| Endpoint | Request | Response |
|---|---|---|
| `GET /api/health` | none | service status and information boundary |
| `GET /api/rules` | none | `defaults`, `choices` |
| `GET /api/roadmap` | none | contents of `docs/REQUIREMENTS.json` |
| `POST /api/sessions` | `{rules?:{},seed?:42,bankroll?:1000}` | ready snapshot |
| `GET /api/sessions/{id}` | none | current snapshot |
| `DELETE /api/sessions/{id}` | none | deleted identity |
| `POST /api/sessions/{id}/deal` | `{bet?:1}` | snapshot after initial deal |
| `POST /api/sessions/{id}/action` | `{action,amount?:number}` | snapshot after legal action |
| `POST /api/sessions/{id}/analyze` | `{timeout_ms?:1500,max_nodes?:60000}` | solver result, state, comparison, precision |
| `GET /api/sessions/{id}/events` | none | `{schema,events}` |
| `GET /api/sessions/{id}/export?format=json\|csv` | none | downloadable complete event log |
| `POST /api/replay` | `{events:[],to_index?:int}` | `{snapshot,verified,events_count,granularity}` |
| `GET /api/sessions/{id}/truth?debug=true` | explicit debug flag | full physical debug state |

Actions are `hit`, `stand`, `double`, `split`, `surrender`, `insurance`,
`decline_insurance`, `continue`, `deal` and `shuffle`. Always use
`snapshot.available_actions`, because rules, bankroll, hand state and early
surrender can remove actions. Early surrender is offered before insurance or a
dealer peek, using `phase="early_surrender"` and `surrender`/`continue`. After
continuing, early surrender cannot be selected again. Splits use sequential
dealing: the second split hand initially has one card and `status="waiting"`.
The replacement card is exposed when that hand's turn begins.

### Snapshot shape

```json
{
  "session_id": "uuid",
  "rules": {"decks":6,"hit_soft17":false,"blackjack_payout":1.5,
    "dealer_peek":true,"enhc":false,"enhc_loss":"all","double_rule":"any",
    "double_after_split":true,"resplit":true,"max_split_hands":4,
    "resplit_aces":false,"hit_split_aces":false,"surrender":"late","penetration":0.75},
  "phase": "player",
  "round_id": 1,
  "active_hand": 0,
  "hands": [{"cards":[{"id":"opaque physical ID","rank":"8","suit":"S","face_down":false}],
    "bet":1,"status":"active","from_split":false,"split_aces":false,
    "total":16,"soft":false,"natural":false,"profit":null}],
  "dealer": {"cards":[{"id":"id","rank":"6","suit":"D","face_down":false},
    {"id":"opaque hole ID","face_down":true}],"total":null,"soft":null},
  "shoe": {"id":"shoe-1","decks":6,"total":312,"remaining":308,"seen":3,
    "counts":[24,24,24,24,24,23,24,22,24,96],"unknown_cards":309,
    "running_count":1,"true_count":0.1683,"penetration":0.0128},
  "insurance": {"offered":false,"taken":false,"bet":0,"profit":0},
  "available_actions":["hit","stand","double","split","surrender"],
  "round_profit":0,"total_profit":0,"bankroll":1000,"events_count":7,"peek_resolved":false
}
```

Examples are illustrative; actual legality follows `available_actions`.
`counts` has ten entries in **A,2,3,4,5,6,7,8,9,10-value** order. It is the
informational pool after subtracting uniquely exposed physical cards. It
includes the unobserved dealer hole card. `remaining` is the physical draw pile,
so it differs from the sum of `counts` until the hole is exposed. A hidden card
payload contains no rank or suit; its opaque identity encodes neither.

Simulator analysis receives only `decision_state()` ranks and the observed
pool. Full split context includes `completed_hands` with normalized wagers and
original-bet allocation and `pending_hands` with only their exposed cards.
Ground truth requires `debug=true`; neither the solver nor the image detector
calls that endpoint.

Analysis returns `status`, `result`, `state`, `comparison`, and `precision`.
`result.actions` maps actions to net EVs per original wager, with `null` for
uncomputed actions. Read `result.method`, `result.exact`, `result.status`,
`result.warnings` and each `action_details` entry before claiming precision.
Incomplete optimization does not produce a certified best action. The wrapper
uses two isolated worker processes with a deadline, kills overrunning workers,
and caches up to 512 identical input/budget combinations. A busy wrapper returns
`status="busy"`; an overrun returns `status="timeout"`.
The default node budget is 60,000, capped at 150,000. Optional
`unknown_removed` reports known extra removals whose ranks were not observed;
it excludes the dealer hole card. Read the solver's associated assumptions and
precision warnings. `generated_basic` contains the policy generated from the
configured rules in a replacement model, with `exactWithinModel` and
`finite_shoe_exact=false` kept distinct.

Replay first audits the supplied prefix against the seeded canonical command
reconstruction, then reduces exactly the selected events. It never exposes
later cards, dealer draws or settlement profits. A prefix within a deal or an
action has phase `dealing` or `resolving` and no playable actions. Event indices
are zero-based and inclusive. A corrupted derived fact is rejected.

## Pixel perception

| Endpoint | Request | Response |
|---|---|---|
| `GET /api/sessions/{id}/frame` | query `theme`, `blur`, `scale`, `overlap`, `card_design` | rendered PNG from public state |
| `POST /api/sessions/{id}/perception` | `{frames?:3,theme?:"green",blur?:0,scale?:1,overlap?:0,card_design?:"classic"}` | detections, events, replay state, gate summary |
| `POST /api/sessions/{id}/perception/analyze` | analysis budgets | gated response or solver on reconstructed ranks/counts |
| `GET /api/sessions/{id}/perception/events` | none | perception event log |
| `POST /api/sessions/{id}/perception/correct` | `{card_id,rank,suit,reason}` | immutable correction event and corrected state |
| `POST /api/vision/upload` | `{image_base64,session_id?,decks?,frames?:3}` | pixel detections and reconstruction |
| `POST /api/vision/upload-video` | raw video body; query `stride?:10,max_frames?:120,decks?,thumbnails?:true,thumbnail_width?:480` | decoded sampled frames, reconstruction, gate |

Themes are `green`, `navy`, `burgundy`. Blur is Gaussian radius `0..10`, scale is
`0.4..2`, overlap is fraction `0..0.9`.
Frame/perception `card_design` is `classic` or `minimal`; corner glyphs retain
the same recognition geometry. The styles change the actual rendered pixels.
Input image limit is 12 MiB decoded and 20 megapixels; video limit is 64 MiB and
600 sampled frames. Base64 data URLs
are accepted. The video backend is local OpenCV and supports the codecs present
on the machine.
Image upload additionally accepts `corners` (TL, TR, BR, BL),
`corners_normalized`, `output_width`, `output_height`, and pixel-coordinate
`zones`. A validated perspective transform supplies normalized detections and
maps boxes back to the source image. `controlled_metadata` reports rules/button
labels recognized from pixels in the controlled font contract. Those labels
are evidence for review; they do not silently change a session's rules.
Standalone image/video imports have unknown deck inventory by default and block
solver use. Set image body `decks` or video query `decks` explicitly to declare
an inventory; an image supplied with `session_id` uses that configured session's
decks. `deck_provenance` records the source, and OCR does not fill it automatically.
Video import treats the clip as one round (`round_id="video"`): automatic round
or shoe-transition segmentation is not implemented. Multi-round/shuffle clips
therefore need explicit segmentation and must not be treated as a certified shoe.
Perception reports include `deck_estimation`: `mode=KNOWN|INFERRED`, `source`,
`decks` (null for unknown), `posterior` over candidates 1/2/4/6/8, `certain`,
`observations`, `most_likely`, `posterior_max`, `entropy_bits`, `status`,
`assumptions`, and `certainty_semantics`. A known count is a declared configuration;
it is not a pixel certification. The posterior consumes only confirmed replay
card identities with known ranks/suits, so repeated frames do not add draws.
An inferred posterior never selects the configured inventory or opens its gate.
Video query `thumbnails` defaults true; `thumbnail_width` defaults 480 and accepts
160..960. Each sampled `frames` item contains `frame_index`, `timestamp`, JPEG
`image_base64` without a data URL prefix, `image_format`, original `frame_width`
and `frame_height`, `preview_width` and `preview_height`, detections in original
pixel coordinates, `event_end_index`, emitted `events`, and `replay_state` at
that exact inclusive journal prefix. The response also includes the full
immutable `events` journal. `timestamp_basis` declares container-FPS or assumed
30-FPS indexing when FPS metadata is absent; neither is a capture timing claim.

Perception is OpenCV rectangle detection and rank/suit glyph matching on the
lab artwork. Scores are similarity scores, not calibrated probabilities.
Repeated still frames provide stabilization for the demo, not an independent
video accuracy measurement. Frame pixels encode no physical IDs or hidden
labels. Zone calibration follows the documented table geometry. Multi-hand
perception analysis needs all visible split-hand cards and a stable gate;
missing context blocks analysis. Rule settings, public action state and wager
metadata come from session control; card ranks and shoe composition for that
endpoint come exclusively from perception replay. Never-detected missing cards
cannot be certified by the integrity gate. Real camera artwork, perspective,
heavy overlaps and unusual layouts require calibration/training and validation.

Manual corrections require a reason and append `STATE_CORRECTION`; original
observations remain in the log. Repeated observations retain logical identities.
Round and shoe transitions reset the appropriate identity scope.

Perception responses measure `latency_ms`, `detection_ms`, `tracking_ms` and
`pipeline_fps`. Control-label recognition additionally reports `metadata_ms`,
`full_pixel_latency_ms` and `full_pixel_fps`; these include the actual rule/button
glyph recognition pass. A still-repeat call has one independently detected input frame
and `tracker_updates` stabilization updates. Its throughput is the inverse
wall time for that input, excluding upload/calibration, and is not a live
stream frame rate. Video responses include actual `processed_frames`,
`decoded_frames`, intentionally `sampled_out_frames`, measured mean and empirical
p95 frame processing times, and offline wall-clock throughput. Frame processing
timing includes thumbnail encoding and prefix reconstruction. `drop_count` and
`stream_fps` remain null because neither live stream drops nor capture pacing
are measured. `source_reported_fps` is decoder metadata.

## Counting and experiments

| Endpoint | Request | Response |
|---|---|---|
| `GET /api/counting/systems` | none | available tags and balance metadata |
| `POST /api/counting/compare` | `{cards:[],decks?:6,rounding?:"truncate",cards_remaining?:number}` | parallel counters on identical card events |
| `POST /api/counting/custom` | `{name,tags:[10 values],balanced?:true,cards:[],decks?:6,rounding?:"truncate",cards_remaining?:number}` | validated definition and counter |
| `POST /api/experiments` | `{rounds?:200,seed?:42,rules?:{},policies?:["basic","hilo"],max_seconds?:30,solver_seconds?:0.05,regret_samples?:12}` | samples, policy statistics, paired comparisons, EV-gap audit |

Experiment policies are `basic`, `hilo`, `composition`. Basic strategy is
generated from the chosen rules with a replacement-model DP. Hi-Lo's
count-index benchmark retains its published-style chart assumptions. Composition uses
the finite-shoe solver within its declared budget; unresolved decisions fall
back to the basic policy and increment `fallback_decisions`. Experiments retain
solver method/precision counts. Results distinguish `requested_rounds`,
`completed_rounds`, and `status="complete"|"time_budget"`.

Independent batches restart shuffled shoes using different deterministic seeds.
Policies share seed sequences within each batch, although their decisions can
consume different cards. The reported confidence interval uses a Student-t
critical value and cluster standard error across independent batches; one batch
has no interval. Paired policy differences use matched batches. Intervals
represent sampling uncertainty and do not include solver approximation error.
`decision_loss` is the sampled gap between the selected action's computed EV
and the highest computed EV. Gaps from an incomplete solver are explicitly
uncertified; omitted actions may change the maximum. Raw per-round net profits
are in `samples` for export and reanalysis.

Invalid rules/input return HTTP 422, illegal transitions return 409, unknown
session IDs return 404, and unflagged truth access returns 403. Bind the launcher
to loopback for the intended local research use.


## Continuous video observation — 0.2.0

| Endpoint | Request | Response |
|---|---|---|
| `POST /api/live` | `{rules?:{},samples?:1500,fresh_shoe?:false,manual_turn?:false,corners?:[[x,y],...],zones?:{"dealer":[x,y,w,h],"player:0":[x,y,w,h]}}` | stream ID, rule/information contract |
| `POST /api/live/{id}/frame?sequence=N&timestamp=T` | binary PNG, content type `image/png` | detections, observed player/dealer cards, event state, count, gate, sampled decision, timings |
| `GET /api/live/{id}/events` | none | observed immutable event log |
| `DELETE /api/live/{id}` | none | disposes observer |
| `POST /api/live/browser` | `{}` from local same-origin page | launches the local app in the default browser |
| `POST /api/sessions/{id}/bot-step` | `{}` | simulator's public basic-policy command result |

`GET /api/sessions/{id}/frame?live_context=true` adds visible English shoe/round/hand/phase labels to the PNG; hidden card ranks and future order remain absent. The bot/source API is separate from the live observer; live configuration forbids `session_id` and any extra native metadata. Rules/inventory are explicit declarations. Corners are four normalized points TL/TR/BR/BL, rectified to lab geometry.

Each live request consumes one supplied video image; it does not simulate additional stabilization updates. Sequence/timestamp must be finite, positive where applicable, and strictly increasing. Input limits are 8 MiB and five megapixels; configured observers are limited to eight, with idle expiry on allocation. Samples accept 100–8,000.

`decision.exact=false`, method `finite-pool Monte Carlo`. Action rows contain net `ev`, `ev_ci95`, `win`, `push`, `loss`, `win_ci95` and sampling metadata. Scope is the active hand plus new splits, excluding other already existing hands. Read the returned gate and [probability contract](LIVE_VISION.md) before using an estimate. Stale-advice timing/backpressure is enforced by the browser loop, independent of tracker stability. The API does not persist recordings or send observations to a remote model.
