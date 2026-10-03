# Optional Chrome / Edge tab-image helper

This Manifest V3 helper is a source distribution, not a published store extension.
It captures the visible tab only after **Capture visible tab** is clicked. It does
not record video, track a full shoe or control bets. The main application provides
continuous screen video, independent table regions and persistent observed counts.

In Chrome / Edge’s extension page, developer mode and **Load unpacked** can load
this directory. The popup’s local address must match the running lab. The default
is `http://127.0.0.1:8767`; desktop installations can use a different port shown in
the app’s browser address. Only HTTP loopback destinations are accepted.

**Copy image** can send the selected image to the main app through Ctrl + V.
**Analyze locally** posts pixels to the user-selected local lab. Unsupported
artwork requires card confirmation / table calibration. Probabilities are modeled
outcomes, not recognition confidence. The extension uses the backend’s default
rules; detailed rule configuration belongs in the main app.

Permissions: `activeTab` grants temporary access to the invoked tab; `storage`
stores the local address; `clipboardWrite` supports Copy image; host permissions
are restricted to localhost / 127.0.0.1. No general browsing history, all-site host
permission, remote analytics, content-script injection or automatic wagering is used.

Tests exercise loopback validation and reject a capture if the active tab changes.
A real browser-store / unpacked extension session is a separate manual check; the
Codex in-app browser does not install Chromium extensions.

Analysis and education only. Not financial advice. No guaranteed outcomes.
