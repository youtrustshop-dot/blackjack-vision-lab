# Third-party references and licensing

The native core is independently written. No external Blackjack implementation has been copied into production code. Repository popularity and agreement by majority do not establish mathematical correctness.

The research sources below come from the supplied specification. Their precise examined revisions and licence texts must be recorded in validation/references/manifest.json before external outputs enter a golden corpus. An adapter without executed results is not an independent validation.

| Reference | Role | Known support boundary / intended check |
|---|---|---|
| [hhoppe/blackjack](https://github.com/hhoppe/blackjack) | Probabilistic/Monte Carlo mathematical reference | Probabilistic analysis documents incomplete prior split-hand state; simulations and analytical results have different scopes. |
| [kevin-lesenechal/freebj](https://github.com/kevin-lesenechal/freebj) | Rust CLI statistical validation | JSON EV is a sample estimate; match rules, policies, cut-card and wager normalization, with statistical uncertainty. |
| [mhluska/blackjack-simulator](https://github.com/mhluska/blackjack-simulator) | Hi-Lo/deviations/shoe and simulation | Its fixed policies must not be mistaken for exact arbitrary-composition EV. |
| [Neurobaby/MGPs-BJ-CA](https://github.com/Neurobaby/MGPs-BJ-CA) | Difficult split/insurance golden | Legacy Visual Basic reference; provenance and rule mapping required. |
| [AttackingOrDefending/Blackjack-Strategy-Simulator](https://github.com/AttackingOrDefending/Blackjack-Strategy-Simulator) | External best-move comparisons | Keep source outside production dependency graph; inspect AGPL licence and documented split precision. |
| [mmichie/cardsharp](https://github.com/mmichie/cardsharp) | Immutable state/events/adapters architecture | Concepts reviewed separately from copying source. |
| [roboflow/blackjack-basic-strategy](https://github.com/roboflow/blackjack-basic-strategy) | Detector comparison | Test pixels independently; model/dataset licences can differ from repository licence. |
| [martinabeleda/blackjack-tracker](https://github.com/martinabeleda/blackjack-tracker) | Calibration/perspective ideas | Legacy API; not a runtime dependency. |
| [mhluska/blackjack-discard-tray-photos](https://github.com/mhluska/blackjack-discard-tray-photos) | Discard-tray benchmark | One sequential acquisition is not evidence of cross-camera generalization. Split by session, not adjacent frames. |
| [datamllab/rlcard](https://github.com/datamllab/rlcard) | Optional future RL baseline | Simplified Blackjack does not supply the full rules/shoe/action core. |
| [he-jev/laya](https://github.com/he-jev/laya) | Optional local phase/anomaly classifier | Not required to start the lab. Model licence, calibration and local hardware must be recorded. |
| [TypeSafe Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) | Optional structured classification benchmark | API access and measured schema/task accuracy do not establish correct Blackjack strategy. |

## Differential comparison contract

Record the state, cards, dealer upcard, observed pool, hidden-card/peek conditioning, rules, legal actions, future policy, EV units, reference revision and uncertainty. Unsupported states are skipped explicitly; missing EV is not a zero. Monte Carlo comparisons use declared standard errors from independent batches. A significant unexplained mismatch creates a DifferentialFailure and fails validation. Every reference can itself contain errors.

No AGPL source may be vendored into the native core without an explicit project licence decision. External code inspection must not silently turn into a production dependency.
