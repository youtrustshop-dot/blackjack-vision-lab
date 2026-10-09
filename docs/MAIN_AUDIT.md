# Main consolidation audit — 9 October 2026

The human explicitly authorized auditing the research chain and integrating it
into `main`. This source consolidation preserves the original commits, frozen
experiments and negative results. It does not promote a reader, certify a
complete shoe or replace the installed Windows 1.1.1 release.

The reviewed starting range is
`4f074efd53066a95d64ca1ed53de03479a8adcba` (published 1.1.1) through
`2223b67e5b900476dd7910d90d92bf1038a23cd6` (PR28): 61 original commits and
311 changed paths. The 28 historical draft PRs form a stack. A new consolidation
PR targets `main` directly and uses a merge commit, retaining their source
history rather than independently merging them in an arbitrary order.

## Changes made during review

1. The preceding PR28 review repaired the acquisition clock: queue/decode time
   now consumes the lifetime of the original evidence. Its three networkless
   regressions and historical receipts remain intact.
2. `setup.ps1` now installs `[dev,research]`, matching CI. PokerKit/Treys are
   required by the full differential test suite; a clean source setup previously
   omitted them. Heavy model-training dependencies remain a separate opt-in.
3. A deadline test previously slept for 30 ms against a 10 ms test deadline.
   Under load, preparation could expire before dispatch instead of producing
   the late reply it intended to test. The first audit run retained that failure
   (983 passed, one failed). A module-local fake clock now tests the actual
   three-second contract deterministically. A separate regression verifies
   expiry before dispatch. No production timeout, validator or integrity gate
   was weakened.
4. `scripts/smoke-source.py` now starts the actual source backend without provider
   credentials, checks the built frontend, closed research defaults and seeded
   PNG simulation, then stops its own server. CI runs it after the frontend
   build. Receipts require a fresh ignored output directory and cannot overwrite
   earlier evidence.
5. [Source setup and PC migration](RUN_FROM_SOURCE.md) distinguish the current
   GitHub source, installed release, optional experiment prerequisites and
   private assets that do not travel with a clone.

## Executed checks

| Check | Result and scope |
| --- | --- |
| Full Python suite after correction | 985 passed + 10 subtests, 133.89 s; two existing dependency warnings |
| Frontend tests | 52 passed |
| TypeScript/Vite | Build passed |
| Real source startup | Six checks passed, including local session/deal/PNG; no inference credentials |
| Locked Python environment | `pip check`: no broken requirements |
| npm known-advisory audit | Zero indexed findings, production and complete locked tree |
| Python known-advisory query | 55 pinned public package/version queries to OSV; zero indexed findings |
| Historical source inspection | 237 tracked Python files parsed; 535 historical text blobs checked; no hits for the bounded credential patterns/private-path rules |
| Rust known-advisory query | 431 registry packages queried; two findings confined to the Linux dependency graph, absent from the Windows graph |
| Windows native geometry | Locked offline compile and three unit tests passed; physical monitor/DPI acceptance remains separate |
| Evidence consistency | Checked again before publication against the forward verification receipt |
| GitHub clean-checkout verification | Required on the exact consolidation head before merge |

Manual review covered capture/ROI/evidence clocks, temporal/state and numeric
provenance boundaries, stale-response rejection, cloud authorization/deadlines,
private-output retention, default API routes, native advisor boundaries, the
heads-up poker engine/references, setup and CI. This is a risk-focused source
review plus executable checks, not a claim that every line of historical output
was manually inspected or that no undiscovered vulnerability exists.

The Rust findings are `glib 0.18.5`
([VariantStrIter unsoundness](https://rustsec.org/advisories/RUSTSEC-2024-0429.html))
and `proc-macro-error 1.0.4`
([unmaintained dependency](https://rustsec.org/advisories/RUSTSEC-2024-0370.html)).
Locked offline inverse dependency graphs show both under Linux's GTK/WebKit
stack and neither in `x86_64-pc-windows-gnu`. They remain documented debt, not
zero findings. Linux native packaging is not approved by this Windows audit;
it needs a separately reviewed upstream/dependency repair. The framework and
lockfile are not silently upgraded to hide the findings.

The credential scan reads tracked text/history only. It does not read local
key files or encrypted private messages. Known-advisory queries transmit public
package names and pinned versions, not project/private inputs. No dependency
was automatically upgraded. No final holdout archive or research weights were
opened. No private inputs, environments, ledgers or credentials are added to Git.

## Preserved operational boundaries

Paid execution stays disarmed: zero provider inference requests and zero new
reservations during this audit. The canonical ledger remains byte-identical:
SHA256 `c7afb7e0c839c0d83bc0f13aee9a61b860ac83c3fc83fca0e5821cc83a3bfae8`.
Historical uncertain charges and closed lots remain closed; a source merge
does not reauthorize their unused slots. The research access policy continues
to record `inference_authorized=false`, `max_requests=0`, `max_usd=0`.

Normal source startup keeps the existing local reader and explicit research
configuration. No new model/training, cloud batch, Poker strategy, installer,
app replacement or new final evaluation is included. Source version `1.1.1`
remains distinguishable by its Git revision and source evidence from the
published desktop 1.1.1 at `4f074ef`.

## Remaining acceptance gaps

The [VISION-034 report](INTEGRATED_R1_SESSION.md) records two owned, complete,
two-round development videos. Both inventories still finish one rank-10 card
short. Clean: localized but unknown in 15 observations; overlap: missed in seven.
These are different perception failures, and the count remains uncertified.
The improvements and four observed round boundaries are useful evidence, not
a universal provider result or a new independent final holdout.

The owned browser-to-local-to-advisor path has measured warm DOM updates and
safe stale/disconnect/occlusion behavior. The live cloud hybrid remains
unpromoted; prior cloud transcription gates/failures remain visible. New source
startup checks do not measure physical screen capture, native popup paint,
dragging between monitors with different DPI or sharing while minimized. Native
geometry unit tests are not substitutes for those checks.

Poker Phase 0 and its independent engine/evaluator references are retained.
They do not constitute a full strategy solver or evidence of an economic edge.
No long-term profitability or universal card-reading claim follows from this
merge.

## Reproduce the current source checks

Use the fresh setup in [RUN_FROM_SOURCE.md](RUN_FROM_SOURCE.md), then:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
npm --prefix ui test
npm --prefix ui run build
.venv/Scripts/python.exe scripts/smoke-source.py --output artifacts/source-smoke-check
```

Use a new smoke output directory on each execution. Aggregate executed audit
evidence is in
[verification.json](../validation/results/main-consolidation/verification.json).
Local detailed receipts (including the initial failed test run and the later
successful run) remain under ignored `artifacts/main-consolidation-20261009/`.
Original experiment reports and receipts are not rewritten.
