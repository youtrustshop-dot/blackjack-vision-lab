# Design — 1.0

Graphite and black surfaces support warm gold navigation and primary actions,
cyan Hit, gold Stand, violet Split and subdued error tones. Cards retain light
faces for rank/suit readability. The new eye-in-spade mark is original SVG;
desktop icons are generated from the same geometry.

The action leads, followed by hand/ace value, modeled outcomes and observed
counts. EV intervals, inventory and reasoning summaries use a collapsed
disclosure. A floating panel identifies its table; one inline panel is focused
at a time.

Native dialogs manage keyboard focus for setup, guide and rule reuse. Controls
keep visible focus. Responsive layouts stack panels and contain table scrolling.
Short reveal transitions honor `prefers-reduced-motion`.

Visual research inspected the public [PokerStars](https://www.pokerstars.com/)
landing interface for dark navigation, action contrast and panel hierarchy.
[Minimal Gallery](https://minimal.gallery/) was consulted for reference selection.
No external logos, images, card artwork or CSS were copied. Product screenshots
show the actual lab in English.

The work followed the local design-reference library’s restrained composition and
accessibility guidance. The React/Vite stack is retained without a new animation
framework. Browser-native video and Picture-in-Picture remain the capture/window
mechanisms; the app cannot bypass the system share picker.
