# OpenAI reader comparison — VISION-016

The authorized OpenAI comparison has now executed using the existing key, frozen
pixels and unchanged local readers. After the first HTTP429, the user reported a
EUR10 credit top-up and explicitly requested another attempt. This separately
claimed attempt made **69 submissions: 51 Luna Standard, 15 paired Luna Fast,
3 selected Sol**. The shared ledger retains 70 lifetime attempts, including the
original failure. No cap was increased, uncertain reservation released, account
settings changed or credit purchase made by the agent. Gemini remains deferred.

**Luna Fast is a promising perception candidate, not an accepted player-state
reader.** All 15 requested/returned Fast responses completed before 2.5s, with
39/39 annotated rank/suit tuples. However, none of the 12 synthetic player inputs
passes the unchanged integrity gate. The renderer's unlabelled decorative 20 is
interpreted as a dealer total. Visibility-proxy disagreements also remain. Keep
the negative evidence; no live integration, release replacement or model promotion.

The [funded aggregate receipt](../validation/results/api-reader-tournament/funded-comparison.json)
preserves actual results and a post-run diagnostic audit, with private outputs
identified by hash only. The [first failure receipt](../validation/results/api-reader-tournament/access-attempt.json)
and [zero-call preparation](../validation/results/api-reader-tournament/prepared-comparison.json)
remain historical records. The first response retained only HTTP429, not a
provider error code; its cause remains unverified and its 2557ms was time to an
error, not a successful observation. Account balance, invoice and auto-recharge
settings remain unverified. Runtime inference is disarmed after the comparison.

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
No desktop/bookmarks or monitor photographs were uploaded. The funded attempt
submitted all planned synthetic and provider-development crops. Images, individual
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

## Actual API comparison and diagnostic limits

| Measured stage | Luna Standard | Luna Fast | Sol residual |
| --- | ---: | ---: | ---: |
| Submissions | 51 | 15 paired | 3 selected |
| Completed validated observations | 43 | 15 | 2 |
| Timeouts at 3s | 7 | 0 | 1 |
| Other reader failures | 1 validation failure | 0 | 0 |
| Exact rank/presence inventories | 33/51 | 11/15 | 2/3 |
| Annotated readable ranks | 87/111 | 39/39 | 3/7 |
| Matched zone/rank/suit tuples | 87/111 | 39/39 | 3/7 |
| Complete annotated synthetic states | 0/48 | 0/12 | 0/3 |
| Correct timely usable player states | 0/12 | 0/12 | No player opportunities selected |
| Completed-observation p50 / p95 / max | 2298 / 2838 / 2991ms | 1766 / 2221 / 2419ms | 2312 / 2469 / 2487ms |

Different columns have different denominators. On the **same 15 Fast inputs**, the
preserved Standard attempt completed 11, timed out three times and failed schema
validation once; its ranks/tuples were 29/39 and completed p95 2859ms. Fast's
requested and returned tiers were `fast` for all 15, with the exact requested
model ID. The two configurations ran in sequential blocks, without repeated or
randomized latency trials. Sol's three post-selected failures are not a population
accuracy or speed estimate. Completed percentiles exclude timeouts and validation
failures; all failures remain in correctness denominators. No first-token metric.

Both Luna configurations recover **9/9 historical provider ranks and tuples**,
compared with current local 9/9 ranks but only 4/9 tuples, and specialized local
2/9 ranks. This is useful consumed-development transfer evidence from two moments,
not independent provider generalization. Two of each Luna's provider states pass
the rank gate with unannotated turn evidence; they are explicitly **unverifiable
provider turn acceptances**, not demonstrated correct player advice.

The complete-state failures have two distinct diagnostic causes:

- `validation/tools/stress_lab.py` renders an unlabelled constant `20` next to
  DEALER. The evaluator declares no displayed hand totals. Every completed
  synthetic API observation (40 Standard, 12 Fast, 2 Sol) returns dealer_total=20.
  On every Fast player input the upcard is 7, so the unchanged gate rejects that
  total. This is a genuine observation/context mismatch, confounded by ambiguous
  synthetic artwork; it is not evidence that all cards were read incorrectly.
  Do not silently null the field, lower the gate or retroactively relabel results.
- Fast's complete card inventory matches eight of 12 synthetic player inputs.
  Four clipped/covered inputs disagree with the renderer's top-index visibility
  proxy, despite matching all annotated readable ranks. A diagnostic visual review
  finds alternate/partial visible indices that the proxy excludes, plus a covered
  example with a returned heart where the visible central pip is a diamond.
  These disagreements require independent annotation; do not call them all either
  hallucinations or successful recovery. The 39/39 tuple intersection excludes
  unannotated unreadable-card claims and cannot establish zero extra/wrong reads.

The single Standard validation failure retained its error type and reported
usage, but no raw invalid JSON. Its exact violated constraint is unverified.
No prompt, image, thresholds, model or scoring contract was tuned during the run.
The post-run audit is explicitly diagnostic; all original scores remain intact.

Offline **current-local→Standard** remains 0/12 timely usable player states and
retains two wrongly accepted local inventories. **Specialized-local→Standard**
remains 4/12, equal to specialized local alone. These routes use each local gate,
not oracle correctness. Three and one respectively of the summary's `completed`
hybrid rows exceed the summed 3s deadline; their observations/gates are expired.
Their raw completed-status percentiles and correctness summaries include the
pre-expiry diagnostic result and do not measure current usable hybrid states.
Neither route is promoted. Fast hybrid latency was not evaluated; there were no
additional paid calls for offline routing.

## Spend accounting and decision

Reported usage is available for 61 funded responses, including the validation
failure. Its conservative price-based upper charge totals **USD0.035521**:
Standard USD0.013754, Fast USD0.009487, Sol USD0.012280. This is not the total invoice
charge. Eight timed-out submissions and the initial HTTP429 have no reported
usage; their full-context reservations total **USD7.386864**. Therefore the
canonical ledger accounts for **USD7.422385 upper exposure**, not USD7.42 spent.
Retain every uncertain reservation; no automatic repeat or further paid run.

The user's credit purchase is not model usage. Prepaid credits decrease with API
usage; enabled auto-recharge can make additional card purchases. Current billing
setup enables auto-reload by default, so the user should verify/disable it in
[Billing](https://platform.openai.com/settings/organization/billing/overview)
if unwanted. Its actual setting was not inspected or changed. See the
[official prepaid guide](https://help.openai.com/en/articles/8264644-setting-up-and-managing-prepaid-api-billing).

**Decision:** retain Fast for further R1 research, reject promotion of the current
full-state/API/hybrid configuration. Standard misses the latency target, Sol has
too little selected evidence, and no route improves accepted player coverage.
The next bounded research question is labelled context/total provenance and
independently reviewed visibility, followed by fresh session-disjoint verification.
Keep this comparison frozen; correcting the renderer/contract later produces a
new development experiment, never a replacement score for this one. No additional
reader framework, local retraining or strategy work is part of this increment.

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

## Reproduction and preserved execution claims

Commands below use the existing project environment; no dependency installation:

```powershell
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament prepare --sessions D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004/new-sessions/validation/manifest.json --providers artifacts/vision-research/private-cases.json --reader D:/CodexResearch/blackjack-vision-lab/specialized-card-reader-20261004/learning-full/reader.json --output artifacts/api-reader-tournament-20261005
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament local --prepared artifacts/api-reader-tournament-20261005 --output artifacts/api-reader-tournament-20261005/local-results.json
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament access
.venv/Scripts/python.exe -m validation.tools.api_reader_tournament run --prepared artifacts/api-reader-tournament-20261005 --local-result artifacts/api-reader-tournament-20261005/local-results.json --output artifacts/api-reader-tournament-20261005/openai-run
```

These record the original commands, not instructions to repeat paid submissions.
The separately authorized funded attempt copied the exact frozen inputs,
configuration, oracle and local results into
`artifacts/api-reader-tournament-20261005-funded-retry`, with a parent receipt and
new execution claim. Its `run` used that directory and `openai-run` beneath it.
Both execution claims and the original shared ledger remain: do not overwrite
them, reset accounting or release unknown charges. The key was loaded from
`.env.local` into the backend subprocess only, without printing it. `run` requires
reviewed exact hashes/configuration, the authorization epoch and an armed gate;
the gate was disarmed in `finally` after the funded run. No live API reader enabled.

The exact original HTTP429 cause cannot be recovered. Successful funded responses
demonstrate usable inference access now, not a verified remaining balance or
disabled auto-recharge. No new key, purchase, recharge or account modification.
Do not put the key in command arguments, stdout, approval files or source.

Executed: 553 Python tests plus 10 subtests (two pre-existing warnings); 63 focused
budget/deadline/contract checks included in that suite. These are not actual API
accuracy evidence. The preserved local benchmark ran on all 51 inputs. The first
actual inference attempt produced only HTTP429; the funded attempt then produced
60 validated observations, eight timeouts and one validation failure across 69
submissions. Public aggregate evidence contains no private images/per-case outputs.
UI/native builds and physical advisor monitor/DPI/capture checks were not rerun.
No local training, final holdout evaluation, strategic Poker work or desktop replacement.
