# Independent mathematical references

`bjlab.references` supplies optional development adapters. The application does not install, vendor, or depend on the reference engines. The repository manifest is `validation/references/manifest.json`: 11 upstream repositories pinned to actual 40-character commit IDs, with license and inspection metadata. Metadata inspection is not an executed validation. The adapter catalogue reports `not_executed` until an experiment produces its own result artifact.

All EVs are **net profit per original unit wager**. Payout, dealer peek conditioning, replacement versus finite shoe, continuation policy, split deal order and the original-bet-only convention must agree before an EV difference is evidence of a bug. `compare_action_values` refuses to pass without an explicit declaration of model equivalence. Missing binaries/dependencies return `skipped`; unsupported cases return `unsupported`; invalid echoes, failures and timeouts return `failed`. None is a passing comparison.

## Versioned independent analytic corpus

`validation/golden/analytic.json` contains twenty hand-derived finite-pool fixtures, with the physical assignments and arithmetic stated in each provenance record. The derivation script `extend_analytic_golden.py` imports no solver and does not harvest native outputs. The cases cover hard and soft hands, S17/H17, pre/post American peek, natural payouts, early/late surrender, single and existing-joint ENHC/OBO busted doubles, and both anchors of an ordinary split twenty-one. Eight optional insurance expectations are independently checked by `tests/test_validation.py`; `run_golden` compares the action EVs. `analytic-golden.json` records all twenty complete passing action comparisons and corpus/current source hashes.

The separate `prepeek-core-audit.json` records fifteen analytic branch checks and links the unchanged original differential reports. The audit also found and fixed concrete native errors: unresolved American peek had put added double/split bets at risk in some surrender modes; the rules engine allowed double on a completed split twenty-one, contrary to the simulator; and omitted phase information under early surrender could infer a pre-check quote for a three-card or existing split hand. Focused tests cover the latter default-phase inference. The original 2,000-state experiment used explicit negative peek and excluded two-card naturals/pair splitting, so none of these corrected branches occurred in its states. Its original runtime hashes remain preserved rather than relabelled as a new execution.

Joint split validation also includes independent exhaustive assignments of six distinguishable mixed cards to hole and two split replacements in `tests/test_solver.py`. Those yield split-eight EV `-26/15` and split-ace EV `14/15`. Along with all-ten bounded-resplit checks, this establishes the stated small-pool cases; it is not a general external depleted-shoe split corpus.

## Published infinite-shoe regression cases

`validation/reference_engines/golden_cases.json` records two small regressions from [Michael Shackleford's published infinite-deck tables](https://wizardofodds.com/games/blackjack/expected-return-infinite-deck/), inspected 2026-10-03. The source declares S17, infinite deck, DAS, up to four hands except aces, and one card to split aces. Cases compare hard 16 versus 10 (stand/hit/double) and soft 18 versus 9 (stand/hit). The source values have six decimal places, so the comparison tolerance is 0.0000006. These regressions exercise `GeneratedStrategy` **with replacement**, not `Solver` without replacement. Split EVs are deliberately absent from these goldens because a published split table's information and continuation conventions need additional reconciliation.

Run from the project directory:

```text
python validation/reference_engines/run_reference.py golden --output validation/reference_engines/results/golden.json
```

The fixture includes URL, source location, rules, allowed actions and precision. No reference chart is used to generate the native strategy.

## FreeBJ CLI adapter

The manifest pins [kevin-lesenechal/freebj](https://github.com/kevin-lesenechal/freebj) at `91e9294d51e87ed36d124cfe058571dd9c05a342` (MIT). Primary documentation is the [pinned manpage](https://github.com/kevin-lesenechal/freebj/blob/91e9294d51e87ed36d124cfe058571dd9c05a342/doc/freebj.1); the mapping was also checked against [options.rs](https://github.com/kevin-lesenechal/freebj/blob/91e9294d51e87ed36d124cfe058571dd9c05a342/src/options.rs), [game_rules.rs](https://github.com/kevin-lesenechal/freebj/blob/91e9294d51e87ed36d124cfe058571dd9c05a342/src/game_rules.rs) and [round.rs](https://github.com/kevin-lesenechal/freebj/blob/91e9294d51e87ed36d124cfe058571dd9c05a342/src/round.rs).

`FreeBJAdapter.build_command` produces an argv list; subprocesses always use `shell=False`. `-n` selects rounds, `-j` jobs, `-c` forced initial player cards, `--dealer` forced dealer upcard, `-a` forced first action (`+` hit, `=` stand, `D` double, `V` split, `#` surrender). The forced action is consumed once; subsequent choices use FreeBJ's own basic chart. This is not a native optimal-continuation experiment.

| Native rule | Mapping / scope |
| --- | --- |
| Deck count | `-d`, explicitly echoed |
| S17 / H17 | `--s17` / `--h17` |
| Blackjack payout | Only 3:2; pinned main fixes `bj_pays=1.5` |
| American hole card / peek | `--ahc`; AHC without peek unsupported |
| ENHC | `--enhc`, all added bets lost; OBO unsupported |
| Double any two / hard 9–11 / hard 10–11 / none | `--db-any2`, `--db-hard-9-11`, `--db-hard-10-11`, `--db-none` |
| DAS | `--das` / `--no-das` |
| Surrender | `--no-surr`, `--esurr`, `--lsurr`; ENHC with late surrender rejected upstream |
| Maximum resulting hands | `--max-splits`, where 1 disables splitting; no resplit maps to at most 2 |
| Hit / resplit aces | `--playAA` / `--no-playAA`; with >2 hands FreeBJ cannot vary RSA independently of playing split aces, so mismatched combinations are rejected |
| Penetration | Integer card threshold; native ratio rounded down, recorded in effective rules |
| Arbitrary depleted composition | No direct native-state API; unsupported for exact differential checks |
| Sequential split replacement / optimal split continuation | Unsupported exact equivalence: FreeBJ deals replacements to both hands before continuing the first |
| Fresh initial-state experiment | `fresh_shoe=True` uses `-p 1` so each round starts with a reshuffled shoe; override is recorded |

Before every experiment the adapter invokes `--dry-run` and checks every expected rule field, then checks each batch's rule echo and round count. This protects against CLI defaults and version mismatch. A clean checkout at the manifest SHA is required by default. A binary SHA-256 is recorded, but verifying a checkout alone does **not** prove that an arbitrary executable was built from that checkout; build derivation must be recorded separately by the build runner.

Important upstream documentation defect: the pinned manpage claims `--shoe-file` contains binary bytes 1–10, but [the pinned `FileShoe` implementation](https://github.com/kevin-lesenechal/freebj/blob/91e9294d51e87ed36d124cfe058571dd9c05a342/src/shoe/file_shoe.rs) reads **ASCII** `1`–`9`, `A`, `T`, ignoring whitespace. `write_freebj_shoe` follows the code. `FileShoe` increases stride when wrapping and cannot reshuffle; it is not an exchangeable finite-composition solver and repeating it does not create independent random batches. The sampling adapter rejects `shoe_file`.

`run_batches` launches separate, equal-sized process batches with the upstream random-shoe implementation. Its 95% interval uses sample variation of **batch mean EVs** and Student's t critical values. It does not divide the per-round standard deviation by square root of total rounds, which would ignore correlations inside shoes. Large batches make the normal approximation for batch means plausible; the upstream CLI exposes no RNG seed, so separate entropy streams are an upstream assumption recorded in the result. Multiple-comparison claims require additional treatment. The interval is sampling uncertainty, not a bound on model mismatch.

For a fixed non-natural hand against ace/ten with AHC, initial and negative-peek EVs would relate by `-p_bj + (1-p_bj)*E` if their composition models matched. However, the pinned forced-card mechanism is unsuitable for exact composition-conditioned validation: `StandardShoe.try_pick_first` removes the first matching rank from the **front**, whereas random draws pop the **back**. Remaining order is not exchangeable conditioned on the removed ranks. The adapter still permits such upstream experiments but sets `validation_eligible=false` and declares the mismatch. Exact differential validation should use an unforced unconditional policy experiment or a reference with a genuine composition-state API. Hit additionally changes continuation policy.

Example with a separately built pinned executable and checkout:

```text
python validation/reference_engines/run_reference.py freebj --checkout PATH_TO_PINNED_CHECKOUT --binary PATH_TO_FREEBJ --actions stand --batches 12 --rounds 100000 --output validation/reference_engines/results/freebj-stand.json
```

`build_freebj.py` optionally builds the verified clean source with an already installed Rust toolchain and `cargo build --release --locked`. Its build receipt records source revision, binary hash, build command, compiler version and build-log hash. Passing `--build-receipt` to the reference CLI makes the adapter verify executable derivation; only a supported unforced experiment can then be eligible for validation. A clean source checkout without a matching build receipt remains an executed experiment with unverified executable derivation.

## Executed evidence

The initial executed artifacts in `validation/reference_engines/results/` are `golden.json` and `hhoppe-hand.json` / `hhoppe-comparison.json`. The hhoppe experiment uses fresh six-deck S17, player 10,6 against dealer 10 after a negative peek, default native rules, and effort 3. Native finite enumeration's four action EVs agree with the independent pinned hhoppe output within `2.3e-16`; both choose late surrender. This checks one nonsplit hand, not general split/resplit precision, all rule combinations, depleted-shoe states or a complete strategy table. The recorded notebook precision flag remains false.

The initial `freebj-stand.json` forced-hand experiment and `differential.json` preserve a **failed** 95% consistency check: native fresh-composition pre-peek EV -0.576608463 versus FreeBJ mean -0.574256667, with interval [-0.575951593, -0.572561741]. This prompted discovery of the upstream forced-card ordering mismatch above. It is not silently discarded or treated as a pass. The earlier raw artifact records the adapter state before this mismatch was known; later adapter versions refuse validation eligibility for all forced-card experiments.

`unconditional_stand.py` supplies the appropriate separate unforced experiment: random initial hands, fresh six-deck shoes every round, always stand, never surrender, no insurance, fixed unit wager. It invokes the production native gameplay and settlement code, suppressing audit/UI serialization and replacing opaque UUID generation only; rank shuffling and gameplay are unchanged. It records independent equal-sized batch means in both engines and a Student-t interval for their differences. Native seed list, upstream entropy-stream limitation, source hashes, pinned build receipt and policy scope accompany its artifact. No solver or generated policy participates in this check.

The first unconditional run completed 12 batches of 10,000 rounds in each engine: native mean -0.1569375, FreeBJ mean -0.161391667, difference 0.004454167 with a 95% batch-difference interval [-0.000895858, 0.009804191], containing zero. Its artifact is `unconditional-stand.json`. This is a statistical consistency check with the recorded broad uncertainty, not proof of exact equivalence or an optimal-policy benchmark. No repeats were used to seek a passing interval.

`compare_executed.py` reproduces a supported hhoppe state comparison and retains native results and hashes of the reference artifact. It rejects conditional FreeBJ comparisons because of the forced-card mismatch; use `unconditional_stand.py` for the separate unforced policy experiment. Existing failed artifacts remain available.

`hhoppe-corpus.json` extends the executed independent comparison to ten fresh six-deck initial states: hard 10 versus 4, hard 12 versus 2, hard 16 versus 10, soft 18 versus 9 and soft 19 versus 6, each with S17 and H17. All 40 stand/hit/double/late-surrender EV comparisons pass the declared absolute tolerance of `1e-7`, and all ten best actions agree. Native outputs are complete finite enumerations; effort-3 reference outputs remain explicitly approximate. Four additional rule configurations (no doubling, ENHC all-bets-lost, ENHC OBO and early surrender) are recorded as unsupported and were not counted as numerical comparisons. This corpus proves agreement for the stated samples, not all rule combinations, depleted shoes or splits.

The later frozen experiment in `validation/differential/results/hhoppe-2000/report.json` covers 2,000 unique fresh-shoe nonsplit states across five deck counts and S17/H17, including 2/3/4-card totals 15–21. Its original effort-3 result remains **failed**: 279 EV discrepancies at the preset `1e-7` tolerance, zero best-action disagreements and zero incomplete native results. The pinned source's [tracked-card cap](https://github.com/hhoppe/blackjack/blob/2ff98e83adf98396beb4ac82a338db03e551264f/blackjack.py#L1092) freezes further removal after ten cards at effort 3. A separate effort-4 diagnostic, using the same input states, native source and tolerance, rechecks all 279 failures with a fourteen-card cap. All agree; maximum difference is `1.819e-10`. `hhoppe-pruning-all-failures.json` retains both EV sets, and `hhoppe-resolution.json` links each original failed state to its diagnostic result and source-artifact hashes. No unresolved numerical disagreement remains in this sampled corpus. The original report is not relabelled, and effort 4 still has no proven global error bound.

```text
python validation/reference_engines/golden_corpus.py --checkout PATH_TO_PINNED_CHECKOUT --python PATH_TO_DEV_PYTHON --output validation/reference_engines/results/hhoppe-corpus.json
```

## Hugues Hoppe notebook adapter

The manifest pins [hhoppe/blackjack](https://github.com/hhoppe/blackjack) at `2ff98e83adf98396beb4ac82a338db03e551264f` (MIT). The primary source is its [Jupytext Python notebook](https://github.com/hhoppe/blackjack/blob/2ff98e83adf98396beb4ac82a338db03e551264f/blackjack.py). `HhoppeAdapter` requires a clean pinned external checkout and launches an isolated `python -I` subprocess. `hhoppe_worker.py` extracts imports, class/function definitions and assignments from the code-library prefix before the first expected action-chart fixture. It drops top-level experiments, tests, plots, GPU detection and notebook helper calls, forces CPU operation, selects `EFFORT`, and blocks Python socket connections and `urlopen`. This is a trusted-source compatibility loader, not an operating-system security sandbox.

The external Python environment may require `hhoppe-tools`, `matplotlib`, `more-itertools`, `numba`, `numpy`, `tqdm` (and compatible CUDA support packages if required for imports). These are development-only dependencies; no installation occurs during adapter use. Local `random32.py` comes from the verified checkout. Source SHA-256, commit, rules and execution timestamp accompany results.

| Scope | Support |
| --- | --- |
| Finite fresh shoe minus current exposed hand/upcard | Supported |
| Arbitrary depleted counts, other players' observed cards | Rejected |
| AHC with negative peek resolved | Supported; calls `reward_for_action` |
| Unresolved peek against ace/ten, ENHC, no-peek AHC | Rejected: upstream `obo` combines different semantics |
| Any-two doubling | Supported |
| Strict 9–11 / 10–11 or no-double | Rejected: upstream uses minimum total, not the native upper bound |
| Surrender none / late | Supported; early rejected |
| Natural blackjack | Rejected by adapter: upstream action reward ignores initial natural; use payout identities |
| DAS / max hands / RSA / HSA | Mapped, but split analysis remains approximate |
| Active split pending/completed hand contexts | Rejected |

The worker uses `HAND_AND_INITIAL_CARDS_IN_PRIOR_SPLITS` attention and requests each legal action's EV. Upstream probabilistic analysis prunes according to `EFFORT`, forgets additional hit cards in prior split hands, and its split calculation automatically takes allowed resplits. Cut-card effects are excluded. **No hhoppe output is advertised as exact**, including at effort 4; no proven pruning error bound is available. A nonsplit stand sample can independently agree to tight numerical tolerance, but this does not establish exactness of the general notebook or native split solver.

```text
python validation/reference_engines/run_reference.py hhoppe --checkout PATH_TO_PINNED_CHECKOUT --python PATH_TO_DEV_PYTHON --player 10,6 --dealer 10 --actions stand,hit,double,surrender --effort 3 --output validation/reference_engines/results/hhoppe-hand.json
```

## Other reference engines and provenance

The other nine manifest entries are exposed by `reference_catalog()` as **file-based external-output adapters**; optional development runners below additionally execute mhluska and BJSS. They include composition calculators, simulators, reinforcement-learning environments and vision/dataset references. A repository's presence does not imply that it can validate casino rule semantics. No source from these projects is copied into the production runtime. `validation/reference_engines/capabilities.json` records the inspected primary documentation, license metadata, execution status and integration limits for the following four mathematical references.

| Reference | Inspected capability and limit | License / current execution status |
| --- | --- | --- |
| [MGP's BJ CA, pinned README](https://github.com/Neurobaby/MGPs-BJ-CA/blob/333b79f4fc093ba097f9c55ef889e04fc6b1d1ea/README.md) | Source project is a .NET Framework 3.5 Windows Forms executable; no command-line handler was found. Manual distinguishes strategy attention and exact/approximate calculations. GUI/manual export integration is not executed here. | [Permissive three-condition BSD-style LICENSE.md](https://github.com/Neurobaby/MGPs-BJ-CA/blob/333b79f4fc093ba097f9c55ef889e04fc6b1d1ea/LICENSE.md); GitHub's `NOASSERTION` metadata is incomplete classification, not absence of permission. |
| [mhluska simulator, pinned README](https://github.com/mhluska/blackjack-simulator/blob/baf76d24ae1b7b734c5fbc960080380463ac7571/README.md) | JavaScript library and simulation CLI. Pinned CLI smoke and public game-step always-stand comparison executed; no exact arbitrary-composition action-EV interface established. | [MIT](https://github.com/mhluska/blackjack-simulator/blob/baf76d24ae1b7b734c5fbc960080380463ac7571/LICENSE); executed artifacts below. |
| [CardSharp, pinned README](https://github.com/mmichie/cardsharp/blob/077182caf8851e3c44f93864e71e27978fc27665/README.md) | Python game/simulation engines and event/state APIs. Specific architectural source paths inspected; no exact finite-composition action-EV interface established. | [MIT](https://github.com/mmichie/cardsharp/blob/077182caf8851e3c44f93864e71e27978fc27665/LICENSE); source inspected, not executed. |
| [Blackjack Strategy Simulator, pinned README](https://github.com/AttackingOrDefending/Blackjack-Strategy-Simulator/blob/c7763771e6e2f90ae5a998dc70b7647103f6708d/README.md) | `best_move.py` CLI executed in isolated subprocess on six nonsplit states. Upstream split approximations and generator weighting limitations remain excluded from exact claims. | [AGPL v3, README specifies v3-or-later](https://github.com/AttackingOrDefending/Blackjack-Strategy-Simulator/blob/c7763771e6e2f90ae5a998dc70b7647103f6708d/LICENSE); blackbox execution only. |

The MGP [help PDF](https://github.com/Neurobaby/MGPs-BJ-CA/blob/333b79f4fc093ba097f9c55ef889e04fc6b1d1ea/BJ%20CA/MGP%27s%20BJ%20CA%20Help.pdf) was read across all thirteen pages, with relevant pages also rendered and visually inspected. Page 2 distinguishes TD, two-card and composition-dependent policies; pages 7–9 explain optional real-time single-split estimates, approximate busted-bet conventions and CDZ-/CD-P/CD-PN post-split attention. These split conventions need reconciliation with native full joint sequential context. No published action-EV table suitable as a numeric golden was found in this manual. `mgp-inspection.json` records PDF/license/project hashes and concrete headless CLI limitations. MGP itself remains unexecuted.

CardSharp source inspection is recorded in `cardsharp-inspection.json`, including URLs and hashes. [EventEmitter](https://github.com/mmichie/cardsharp/blob/077182caf8851e3c44f93864e71e27978fc27665/cardsharp/events/emitter.py) provides priority subscriptions, unsubscribe closures, listener-list locks and recorder game/round context. [State models](https://github.com/mmichie/cardsharp/blob/077182caf8851e3c44f93864e71e27978fc27665/cardsharp/state/models.py) use frozen dataclasses and visible dealer-card projections, but nested lists remain mutable. [Transitions](https://github.com/mmichie/cardsharp/blob/077182caf8851e3c44f93864e71e27978fc27665/cardsharp/state/transitions.py) construct new states with `replace` while publishing global EventBus side effects, so they are not entirely pure. [Async flow](https://github.com/mmichie/cardsharp/blob/077182caf8851e3c44f93864e71e27978fc27665/cardsharp/api/flow.py) supplies predicate/timeout waits and subscription cleanup. These are inspected architectural patterns, not executed blackjack correctness proof.

`mhluska-stand.json` records twelve independent process batches of 10,000 rounds per engine, random fresh six-deck S17 shoes, fixed wager, always stand and no insurance. The upstream public [`Game.step`](https://github.com/mhluska/blackjack-simulator/blob/baf76d24ae1b7b734c5fbc960080380463ac7571/src/game.ts) handles gameplay and settlement without source modification. Native mean is -0.161691667, reference mean -0.161975, difference 0.000283333 with 95% batch-difference interval [-0.010614526, 0.011181193], containing zero. Unmodified upstream `Math.random` streams have no exposed reproducible seeds. This is a broad sampling consistency check on one policy. The separate 1,000-hand basic-strategy CLI smoke is not a policy comparison. `mhluska-build.json` proves compilation of the clean pinned source and records bundle/lock/log hashes; its identical compiled hashes were attached to the original sampling artifact without resampling. Initial wrapper setup failures occurred before sampling and are retained separately.

`bjss-expanded-corpus.json` compares stand/hit/double/late-surrender EVs for hard 16 against 10, hard 16 against ace and soft 18 against 6, each S17/H17. All 24 EV differences pass `1e-9`, and best actions agree. The verified pinned `best_move.py` CLI runs with isolated Python and a noninteractive plot backend; all arguments and raw outputs are retained. Its actual option is `--splits`, despite singular spelling in README examples. This checks nonsplit fresh-shoe states after American peek, not the upstream approximate split method. No upstream code is copied into runtime.

```text
python validation/reference_engines/build_mhluska.py --checkout PATH_TO_PINNED_CHECKOUT --receipt validation/reference_engines/results/mhluska-build.json
python validation/reference_engines/mhluska_comparison.py --checkout PATH_TO_PINNED_CHECKOUT --build-receipt validation/reference_engines/results/mhluska-build.json --output validation/reference_engines/results/mhluska-stand.json
python validation/reference_engines/bjss_corpus.py --checkout PATH_TO_PINNED_CHECKOUT --python PATH_TO_DEV_PYTHON --expanded --output validation/reference_engines/results/bjss-expanded-corpus.json
```

`load_reference_output` requires schema version 1, `status="executed"`, every native `Rules` field, a boolean precision flag, finite EVs and typed provenance: pinned repository/revision, source URL, execution timestamp, producer and raw-output SHA-256. It requires explicit shoe, conditioning, continuation, split deal order and EV units. A verified manifest revision does not verify mathematical equivalence: output marks that decision false until a caller checks it.

```json
{
  "schema_version": 1, "status": "executed", "exact": false,
  "rules": {"decks": 6, "hit_soft17": false, "blackjack_payout": 1.5,
    "dealer_peek": true, "enhc": false, "enhc_loss": "all",
    "double_rule": "any", "double_after_split": true, "resplit": true,
    "max_split_hands": 4, "resplit_aces": false, "hit_split_aces": false,
    "surrender": "none", "penetration": 0.75},
  "model": {"shoe": "finite-fresh", "conditioning": "negative-peek",
    "continuation": "composition-dependent", "split_deal_order": "sequential",
    "ev_units": "net-profit-per-original-unit"},
  "actions": {"stand": -0.4},
  "provenance": {"repository": "REPOSITORY_FROM_MANIFEST", "revision": "ACTUAL_PIN",
    "source_url": "https://example.org/actual-export-source",
    "executed_at": "2026-10-03T01:00:00+00:00", "producer": "tool-and-version",
    "raw_output_sha256": "ACTUAL_64_HEX_HASH"}
}
```

The numerical EV in this schema illustration is not a golden fixture. No MGP, RLCard or vision benchmark execution is implied by an accepted artifact schema. Actual validation evidence belongs in `validation/reference_engines/results/` and should retain raw batch outputs and model restrictions.
