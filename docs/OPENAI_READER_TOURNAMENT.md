# OpenAI reader comparison — VISION-016

The authorized API comparison is prepared, but has **not run**. The existing
OpenAI credential is unavailable to the benchmark. Reuse permission is resolved;
do not create another key. Gemini is deferred because the user has no credential
and explicitly requested OpenAI first. API requests and incurred API cost: **0**.
Balance, free credits, auto-recharge and account model access are unknown.

The [machine-readable receipt](../validation/results/api-reader-tournament/prepared-comparison.json)
contains executed local results and hashes, not invented cloud results. This is
the next step in the existing reader tournament, not another training iteration.

## Frozen inputs and local comparison

51 planned native inputs, 44 exact unique frame IDs: 48 stills extracted from the
already consumed VISION-015 videos and three historical provider screenshots.
The videos are two physical six-round synthetic sessions rendered six ways, not
12 independent sessions. Four predeclared stage midpoints per clip cover waiting,
player decision, dealer reveal and immediate-blackjack settlement. These stages
select/annotate evaluation inputs; they never enter the reader request.

Provider inputs represent two moments; Freegames' preview repeats the original
moment at a different scale/crop. No independent provider full video exists.
Their historical phase/controls/totals are unannotated; complete-state scores are
therefore absent. 201 native table/role/control crops were inspected locally.
No desktop/bookmarks or monitor photographs were uploaded. Images, detailed
outputs, approvals and the ledger remain under ignored `artifacts/`.

| Same-pixel still measurement | Current local | Specialized local |
| --- | ---: | ---: |
| Rank/presence inventories exactly correct, including empty states | 23/51 | 36/51 |
| Complete visible states, 48 annotated synthetic inputs | 10/48 | 17/48 |
| Matched readable ranks | 71/111 | 98/111 |
| Matched zone/rank/suit tuples | 40/111 | 80/111 |
| Correct timely player states, 12 annotated opportunities | 0/12 | 4/12 |
| Accepted player states with incorrect observed rank/presence inventory | 2 | 0 |
| Historical provider readable ranks | 9/9 | 2/9 |
| Offline completed-observation CPU p95 | 230 ms | 79 ms |

These small, correlated, consumed inputs are development evidence. Empty and
intentionally blocked non-player states are not player failures. The synthetic
oracle uses the renderer's top-index visibility-mask proxy, not independent human
truth; a readable alternate corner can disagree with that proxy. Suit counts are
multiset agreement including zone/rank, not geometrically matched per-card suit
accuracy. Clipped or covered information remains unknown. No default promotion.

Both readers use exactly the same native table and declared card/control regions.
The source of nine perception components matches frozen commit `18bfd57`; weights,
thresholds and OCR are unchanged. The existing current-pixel phase context starts
fresh for each still; temporal tracking is not measured here. Learned presence
replaces the baseline's geometric back recovery, as in VISION-015. First model
loading is setup, excluded from per-frame timing. Existing outputs/timings were
retained when correcting a provider-only counter and reporting intentional blocks.

## Declared API order and limits

1. `gpt-6-luna`, Standard (`service_tier=default`), reasoning `none`, every input.
2. Same Luna with `service_tier=fast`, the 12 player samples plus three provider
   inputs, after Standard, only if account access and the shared budget permit.
3. `gpt-6.1-sol`, reasoning `low`, at most three Standard residual failures,
   provider-first then case order. This selected hard subset is diagnostic,
   never an independent accuracy estimate. No silent model substitution.

Official model/context/pricing sources, inspected on 2026-10-05:
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol), and
[Fast](https://developers.openai.com/api/docs/guides/fast-mode).
The configuration records Standard input/output and conservative cache-write
prices, the long-context multipliers and Fast's price multiplier. The actual
returned tier is recorded; an unexpected model/tier cannot release a reservation.

The working cap is **USD8 total / 90 attempts**, a lower operational cap inside the
user's **EUR10 total**, shared by all configurations/providers. The
[ECB reference](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
on 2 October was USD1.1225 per EUR; this is an informational rate, not a transaction
quote. The lower USD cap leaves room for conversion/tax uncertainty. No purchase,
payment-method, billing-upgrade or recharge action is authorized or performed.

Each paid request claims one canonical durable reservation before network access.
Atomic writes and process locks prevent concurrent spending; deletion/corruption
fails closed. Unknown timeout/failure charges retain the full-context worst-case
reservation. Only valid reported usage for an audited model/tier releases the
unused portion to a conservative price-based upper charge. This is not an invoice
or a verified account balance. Sol's full-context reservation is comparatively
large; remaining trials may consequently be marked **not executed**, never erased
from their planned denominators. The old memory-budget transport cannot bypass
the aggregate ledger.

The hard deadline is **3 seconds** from prepared input through encoded submission
and complete validated JSON, with a provisional p95 target of 2.5 seconds. A wall
clock bound covers upload and the entire response, including a slowly dripping
body; late validated observations are discarded. There are no retries. Report
p50/p95/max among completed observations together with timeouts/unexecuted cases;
successful-only percentiles cannot establish the overall target. Capture/display,
live validity and R2 continuity remain unmeasured.

Offline routing compares **A→Luna and B→Luna separately**, using each local integrity
gate without consulting truth. A wrongly accepted local result cannot be replaced
using the oracle. Combined local/API time must meet the deadline. This is a replay
of measured separate attempts, not a measured live hybrid or more paid requests.

## Reproduction and remaining blocker

Commands below use the existing project environment; no dependency installation:

```powershell
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament prepare --sessions D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004/new-sessions/validation/manifest.json --providers artifacts/vision-research/private-cases.json --reader D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004/learning-full/reader.json --output artifacts/api-reader-tournament-20261005
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament local --prepared artifacts/api-reader-tournament-20261005 --output artifacts/api-reader-tournament-20261005/local-results.json
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament access
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament run --prepared artifacts/api-reader-tournament-20261005 --local-result artifacts/api-reader-tournament-20261005/local-results.json --output artifacts/api-reader-tournament-20261005/openai-run
```

Preparation is already complete: do not overwrite the freeze or reset the ledger.
The `access` command was attempted locally and refused the missing credential
before network access; inference is pending. `access` reads only requested account model
availability; it does not probe billing through inference. `run` requires the
existing credential in the backend process, the reviewed exact hashes/configuration,
current authorization epoch and an armed runtime gate. Do not put a key in command
arguments, stdout, approval files or source. Only the location/manager of the
existing key is missing; no new reuse/spend approval is needed. Key lookup failure
does not mean an account has zero credits. Crop approval expiry requires rechecking
unchanged hashes, not a new authorization to spend.

Executed: 553 Python tests plus 10 subtests (two pre-existing warnings); 63 focused
budget/deadline/contract checks included in that suite. These are not actual API
accuracy evidence. The preserved local benchmark ran on all 51 inputs. UI/native
builds and physical advisor monitor/DPI/capture checks were not rerun. No local
training, final holdout evaluation, strategic Poker work or desktop replacement.
