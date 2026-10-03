# Mathematical models and support

All reported EV values are **net profit**, in units of an initial one-unit
wager. A doubled loss is -2 and a push is 0. Finite-shoe results and generated
replacement-model results have distinct labels. They must not be presented as
interchangeable mathematical oracles.

## Finite-shoe solver: `bjlab.solver.Solver`

`Solver(rules).analyze(player, dealer_upcard, counts, ...)` enumerates draws
without replacement, using memoized states. `counts` is a ten-integer vector
in A,2,...,9,10 order; tens combine 10/J/Q/K. It contains every unobserved
card, including the hidden dealer card. Only observed cards are subtracted.
The input pool plus the current visible hand/upcard may not exceed the
configured original shoe's rank inventory.

The dealer hole card is **never passed from the simulator**. If a negative
peek excludes some ranks, let `I` be the sum of counts of possible hole-card
ranks and `T` the total pool size. The posterior is
`P(H=r) = counts[r]/I` for allowed ranks and zero otherwise. The next player
draw has probability `(counts[r] - P(H=r))/(T-1)`. After each observed draw,
counts and this posterior are updated. Selecting an action after revealing
a sampled secret hole card would be an information leak; this solver does
not do that.

Stand enumerates the posterior hole card, then the dealer policy. Hit
optimizes later observable decisions. Double adds one card and settles a
two-unit stake. Late surrender loses half on non-blackjack dealer outcomes
and the full original bet on an unresolved dealer blackjack. Early surrender
is before the peek. For every surrender configuration, an explicit
`peek_resolved=False` quote in an AHC peek game integrates the future dealer
check: added double/split wagers only occur on its negative branch. Early
surrender remains an unconditional -1/2; late surrender is available only
after the negative check. Insurance is separately quoted before that check.
If the peek phase is omitted, early-surrender rules infer a pre-check quote
only for an initial two-card nonsplit hand with surrender still available.
Three-card hands and existing split decisions infer a completed negative
check. Supply the phase explicitly when a different quotation is intended.

For ENHC, the implementation supports `enhc_loss="all"` and
`enhc_loss="original"`. Original means **OBO**, including refund of added
bets on a dealer natural even when a doubled hand busted. It is not an
OBBO/BB+1 rule. The round's original wager is charged once, while additional
split/double wagers are refunded. Settlement callers allocate
`original_wager=1` to one split hand and zero to the others.

### Splits and precision

Split EV enumerates the **joint round**: active hand, pending hands,
completed hand totals/stakes, exposed-card pool, and total hand count.
Hands receive replacement cards sequentially: finish the first before
dealing a replacement to the next. Other dealing orders carry different
observable information and are not interchangeable.
Every twenty-one completes its hand, including split A+10 with permission to
hit split aces. Doubling an already completed twenty-one is unavailable in
the rules engine, finite solver, replacement generator and simulator.

At an existing split decision, provide `from_split=True`, `split_hands`,
`completed_hands=[{"cards": [...], "wager": 1, "from_split": true,
"original_wager": 0}]`, and `pending_hands=[[original_split_rank], ...]`.
Without complete round context the solver can calculate local EV values,
but returns `exact=False` and no definitive `best_action`.

`timeout_ms` and `max_nodes` bound a calculation. Every completed action has
its own `action_details[action].exact` flag. An unevaluated legal action has
`null` EV, `status="partial"`, `exact=False`, and `best_action=null`.
`best_evaluated_action` is diagnostic only. Missing actions must not be
treated as losing actions. Shoe exhaustion also returns a partial result:
mid-round reshuffling is not silently assumed. Floating-point arithmetic is
used for the complete enumeration; “exact” means no sampling/truncation,
not rational arithmetic or an independent proof.

`unknown_removed=N` declares unobserved burn/removed cards whose ranks were
not identified. They remain in the uncertainty pool and are integrated as
exchangeable cards; the declaration reduces physical draw availability.
If rank-dependent information is known about those cards, this exchangeable
model is insufficient and a richer posterior is required.

## Generated benchmark: `bjlab.strategy.GeneratedStrategy`

`GeneratedStrategy(rules).analyze(player, dealer, ...)` computes strategy
from equations, never from a hardcoded chart. The independent draw
probabilities are A..9 each 1/13 and all ten-valued ranks 4/13. Dealer outcomes
are generated recursively from S17/H17 and hidden-hole/peek rules. Player
continuation optimizes hit/stand using total and softness. Initial legal
double, surrender and split actions are calculated and compared.

Bounded splits/resplits are generated by a DP over the number of pending
one-card hands and the total number of hands already created. A normal
decision reduces the pending count; a resplit increases total hands and
replaces the current hand with two pending hands. The hand limit makes the
recurrence finite. Aces respect one-card/hit/resplit permissions, and A+10
after splitting receives an ordinary one-unit win. Double after split is
honored. Under replacement, draws by one hand do not deplete another hand's
distribution; linearity of EV permits adding the pending-hand contributions.

`exactWithinModel=True` means complete DP within this declared replacement
model. **`finite_shoe_exact` is always false.** Number of decks and penetration
are recorded in rules but do not alter independent replacement probabilities.
Finite-deck removal effects and cut-card effects belong to other models.

For existing sequential split hands, `pending_count` must specify how many
future one-card hands remain. All share the split rank, the first card in the
active hand. Completed hands add an action-independent constant under this
replacement model; their EV is excluded from the returned active/pending
scope. Without pending context, results are labelled local split policies,
not full-round optimal results. Future pending hands with already exposed
replacement cards or different anchors are outside this API's support.

`generate_table()` produces hard, soft, pair and separate natural rows for
all initial rank pairs versus all ten upcard values. Hard/soft rows condition
on total/softness and disable splitting; each initial unordered pair is
weighted by `P(a)P(b)` for identical ranks, otherwise `2P(a)P(b)`. Pair rows
calculate split EV. Under replacement, total/softness are sufficient for later
hit/stand decisions, so the continuation is genuinely total-dependent in
this model. The generated table is a rules-based infinite-shoe benchmark,
not a finite-deck basic-strategy chart.

`generated_basic_strategy(..., legal=[...])` returns the generated action for
simulator/Monte Carlo baselines. `counting.basic_strategy` remains a separate
legacy chart reference. Hi-Lo indices are benchmark deviations with explicit
rule/rounding assumptions; they do not become exact composition strategies.
For an early-surrender phase, `allowed_actions=["surrender", "continue"]`
compares surrender with the optimal future play after declining it; `continue`
does not place a double/split wager before the dealer check.

## Support matrix

| Feature | Finite shoe | Replacement generator |
| --- | --- | --- |
| Aces, totals, natural payout, S17/H17 | Enumerated | Full DP |
| Dealer hidden card and negative peek | Finite posterior | Replacement posterior |
| Any/9–11/10–11/no double, DAS | Supported | Supported |
| Split, bounded resplit, aces permissions | Joint sequential round; budget can stop it | Full bounded DP in replacement model |
| Early/late/no surrender | Phase-sensitive | Phase-sensitive |
| ENHC all/OBO | Supported | Supported |
| Insurance before peek | Actual pool EV | Replacement EV |
| Known decks | 1/2/4/6/8 inventory | Metadata; no removal effects |
| Uncertain deck count | Requires separate posterior/decision wrapper | Not inferred here |
| Unknown burn cards | Exchangeable with declared physical removal count | Replacement is unaffected |
| OBBO, BB+1, side bets, suited bonuses, Charlie rules | Unsupported | Unsupported |
| Mixed-rank ten splitting restrictions | Unsupported; equal-value tens may split | Same |
| Hit/double after split aces separately configurable | Hit permitted; double follows the present Rules model | Same |
| Alternate split replacement dealing order | Unsupported | Unsupported |
| Mid-round reshuffle | Explicit exhaustion; no hidden fallback | Not applicable |
| Composition-accurate finite-deck table generation | Finite analyze per supplied observable state | Not claimed |

## Validation and sources

The suite includes analytical tiny-shoe cases, exhaustive assignments of
mixed cards to hole/split hands, payout/timing checks, count conservation,
and model-specific published EV values. These tests validate behavior without
making majority votes between third-party engines an automatic oracle.

The replacement DP reproduces the S17/DAS/max-four/no-resplit-aces example
in [Wizard of Odds: Expected Returns in Infinite-Deck Blackjack](https://wizardofodds.com/games/blackjack/expected-return-infinite-deck/):
pair 8 versus 10 has stand -0.540430, hit -0.539826, double -1.079653,
split -0.480686 (rounding to six decimals). These figures validate that
specific model and configuration, not all possible rules.

The Hi-Lo tag and index reference is
[Wizard of Odds: High-Low](https://wizardofodds.com/games/blackjack/card-counting/high-low/).
The independent [hhoppe implementation](https://github.com/hhoppe/blackjack)
documents pruning and incomplete previous split-hand state in its probabilistic
analysis; adapters must retain its support/precision limitations when comparing
finite-shoe or split outputs.
## Lazy finite-shoe initial-cell analysis

`FiniteGeneratedStrategy` is a separate analysis tool; `GeneratedStrategy` remains the complete replacement-model benchmark used by the default basic policy. `get_finite_generated_strategy(rules, timeout_ms=..., max_nodes=...)` reuses a small registry keyed by rules and budgets. `generate_table()` produces a cheap manifest with every initial hard/soft/pair/natural cell marked `not_computed`. `generate_cell("hard",16,10)` computes only that cell, caches its result, and updates the manifest. Passing `cells=[("hard",16,10)]` to `generate_table` is an explicit selective computation request. `refresh=True` recomputes a cached cell after budgets or other implementation choices change; use a differently budgeted instance for a larger budget.

Each cell starts from a fresh finite shoe. Initial rank-pair probabilities are without replacement, conditioned on the dealer upcard and additionally on a negative peek when selected. Each rank combination calls the finite solver with exposed cards removed but the hidden hole card still in the pool. Hard/soft rows suppress splitting; pair rows include it. Completed action EVs are averaged using normalized physical rank-pair probabilities. A cell-wide time/node budget is shared across all initial combinations. If any combination lacks an exact EV for an action, that aggregate is `null`; a partial cell has no recommended `best_action`. Per-action precision and per-combination results remain inspectable. A table remains incomplete while any cell is partial or uncomputed.

**Continuation is optimal with full observed composition.** This differs from a finite-deck policy constrained to use only hard/soft total for all subsequent decisions. `total_only_basic_strategy_exact` is always false. A completely evaluated finite table would validate its stated initial-action aggregation model, not a globally total-only finite basic-strategy chart. Generating the latter requires a separate constrained-policy treatment; it is not implied by averaging composition-optimal future EVs.

## Expanded-node budget and a measured ordinary hand

The dealer recursion memoizes only states that require another card. Terminal bust/17–21 outcomes are constant probability vectors and do not occupy composition-specific cache entries or count as expanded nodes. A single undoubled player bust returns -1 directly. These changes preserve the outcome arithmetic and avoid retaining a large terminal graph.

`validation/reference_engines/solver_performance.py` records a concrete fresh six-deck S17 case, player 2,8 versus dealer 4. The before/after artifacts preserve identical four action EVs and best action double. Expanded nodes fell from 191,758 to 28,511; measured latency fell from 857 ms to 549 ms on this machine. A separate run under the UI's 1,500 ms / 60,000-node budget completed all legal EVs in 596 ms. These are measured samples, not latency guarantees. The corresponding independent pinned hhoppe effort-3 sample agrees within 8e-10 (its pruning precision remains explicitly approximate). Split states and larger low-total trees can still exhaust their budgets and must retain partial status.
