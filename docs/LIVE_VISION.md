# Continuous live vision — 1.0.1

## Start and configure

Open the local app in desktop Chrome or Edge. Setup declares the mode, decks, dealer rule, payout, peek/ENHC and legal actions. The standalone simulator also loads saved rules and provides its own configuration dialog. Match the declared rules to each source: pixels cannot reveal the whole rule set.

Select **Share screen** and choose a screen, window or tab in the browser picker. This supplies a real continuous `MediaStream` to a playing video element; audio is disabled. Stop with **Stop video**, the browser's stop-sharing command or page closure. Switching laboratory sections keeps observation mounted.

The first-visit guide explains configuration, sources, count scope and advice. New sessions/tables confirm saved settings unless the reuse checkbox is selected. Setup can enable that prompt again.

## Video processing

Video-frame callbacks trigger automatic observations. A worker heartbeat also checks advancing video time when rendering callbacks slow down offscreen; a frozen media clock cannot renew evidence. One request per observer is in flight. Busy observations are skipped, never queued. PNG encoding uses OffscreenCanvas where supported, with a regular canvas fallback.

Single-table observation has a 350-ms minimum interval; multi-table observation uses at least 500 ms. These are scheduling targets, not measured analysis FPS. Identical pixels reuse recognition, while each actual video observation still updates tracking and time. Source video FPS, sent observations, skipped work and displayed capture-to-response latency are separate measurements.

Advice expires 2.2 seconds after capture time without a successful fresh observation. Requests time out after six seconds. Cancellation/generation guards reject late results and upload errors clear advice. Browser/OS suspension can interrupt video and must remain visible as stale status.

The Windows WebView may lack display capture. **Open in default browser** opens the same local URL; use Chrome or Edge while keeping the desktop backend running.

## One to five independent tables

**+ Add table** registers another named observer, up to five. Each has its own rules, source, count and advisor. A shared screen is selected once; each table receives an owned stream clone. For a screen containing multiple games, select that game's four corners separately in each preview. Removing one observer stops only its clone; **Stop all sources** stops the shared source.

Tables are registered and calibrated explicitly. Automatic detection of arbitrary tables is not implemented. Poker/other mode displays video only; it has no validated poker decision engine.

**Run lab demo** creates a separate seeded simulator and a canvas-backed 15-FPS video stream. Pause the bot or use legal manual actions. The independent observer receives only pixels and declared rules, never the source simulator's session ID.

**Open simulator window** provides a playable table at `/?simulator=1`. Share it and select top-left, top-right, bottom-right and bottom-left corners. Keep geometry fixed or recalibrate. Multi-hand table height is preserved when normalizing.

## Tracking and card count

The lab detector recognizes lab card corners and visible controls. SESSION, SHOE, ROUND, HAND and PHASE are read from pixels. Two distinct observations stabilize context; three stabilize cards. New rounds reset active tracks and retain exposed history. A visible source-session or new-shoe change resets the shoe count.

The classic casino profile finds the largest green felt, reads printed rank
corners locally and verifies them against the visible hand total. English turn
messages and enabled green action buttons supply phase and available actions.
It supports the external table reported in issue diagnostics, including a full
desktop image with smaller duplicate previews. Sharing the game window gives
the clearest input. No calibration is needed for this profile. A settled-to-player
transition or three clear observations starts a new round while retaining the
observed count. External shuffles must be declared; pixels cannot establish an
unseen shuffle. Multiple player hands currently require manual active-hand
confirmation. [Recognition scope and tests](EXTERNAL_VISION.md).

Hi-Lo adds +1 for 2–6, 0 for 7–9 and −1 for tens/aces. Every confirmed exposure counts once. True count divides by estimated physical decks remaining. Declare **Observe from a new shoe** only when the complete shoe has really been observed. Restarting observation mid-game labels the count partial unless a new shoe is explicitly declared.

Unreadable, lost or changing cards, unknown active hands, unavailable legal controls and non-player phases withhold guidance. A manual-turn declaration cannot recover never-observed cards. The gate cannot prove that a card never detected was absent.

## Decisions, aces and probabilities

Every valid declared/recognized player turn has an immediate legal basic-policy recommendation. Ace values show 1 or 11 and a soft hand's alternative hard total. The offline library covers hard, soft, pair and natural hands plus 550 starting rank/dealer combinations.

Live outcomes sample finite informational-pool draws without replacement. The hidden dealer card is marginalized; a readable player phase under peek rules conditions on no dealer blackjack. ENHC/OBO, doubles, surrender and bounded split/resplit are represented. Continuation uses generated rule-dependent basic policy, rather than optimizing every future finite composition.

The UI offers 500/1,500/5,000 samples per action. Positive/push/negative means net profit of the active hand plus new splits caused by its action; other already-existing hands are excluded. EV is net profit per initial wager. Wilson outcome intervals and normal EV intervals measure sampling uncertainty, not recognition error. A separated ranking can select the composition estimate; overlapping rankings retain the basic recommendation.

The Hi-Lo index action is a reference comparison, with count-history reliability shown. Current-action EV does not measure the next round's betting edge. No outcome is guaranteed and this is not financial advice.

## Images and floating advisor

**Image & manual advice** accepts pasted, dropped or uploaded PNG/JPEG/WebP images. Lab artwork and compatible classic casino tables can be read automatically; other artwork needs confirmed player/dealer cards. Blank manual inputs show readable guidance before any request. Unicode suits and common separators are accepted. Advanced confirmation accepts split context and an observed-card list including current cards. One image supplies no temporal history.

Sharing opens a compact translucent advisor. **Pop out advisor** uses Document Picture-in-Picture when supported and requires a user click. The in-page fallback cannot stay over another application. Only the selected table's popup is shown. Advanced details expand EV, intervals, policy/count comparisons and count scope.

## Evidence and optional programs

Current tests and browser/Windows evidence are listed in [STATUS.md](STATUS.md). Historical lossless video, perspective, occlusion and external-artwork failures remain preserved. Personal screen-picker selection, arbitrary graphics and an installed extension are not certified by a hidden desktop smoke.

[Clef](CLEF.md) is an optional pinned local scene classifier, separate from card recognition and advice. [Jevbox](https://github.com/extend-hq/jevbox) is document retrieval, not a card detector. Laya remains deferred.

Browser contracts: [display capture](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia), [video-frame callbacks](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback), [background throttling](https://developer.chrome.com/blog/timer-throttling-in-chrome-88/), [Document Picture-in-Picture](https://developer.mozilla.org/en-US/docs/Web/API/Document_Picture-in-Picture_API/Using).
