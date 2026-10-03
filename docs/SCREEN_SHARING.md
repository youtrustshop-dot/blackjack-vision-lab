# Screen sharing and backend recovery

## Use the current source/browser version

Start `run.ps1` and keep it running. Open http://127.0.0.1:8765 in desktop
Chrome or Edge. Go to **Perception lab → Apri strumenti → Condividi finestra
o schermo**. The browser asks you to select the source. No screen is selected
automatically and audio is not requested.

The preview stays in the browser. Press **Acquisisci fotogramma**, select the
four table corners and the recognition zones in **Normalizza un’immagine**,
then press **Calibra e importa** to send that image to the local backend.
This is explicit still-frame analysis, not a continuous live tracking loop.
The existing detector is validated on the lab renderer; arbitrary card artwork
needs its own detector/calibration and evidence. Independent imports keep deck
inventory unknown unless the user explicitly supplies context.

Press **Ferma condivisione** to stop. Closing the tools, switching sections,
or closing the page also stops the owned stream. A source granted after a
cancel/unmount is immediately stopped. Integrated browsers and WebView2 may
not implement display sharing; open the localhost URL in Chrome/Edge or upload
a screenshot instead.

## Backend unavailable

The browser UI calls its local Python service. If the service is stopped, a
cached UI can remain visible while API requests fail. Transport failures now
show instructions and disable session operations. Restart `run.ps1`, then use
**Riconnetti**. If the previous server lost its in-memory session, reconnect
creates a fresh session with the configured seed and rules. Sessions survive
through an exported replay, not automatically across process restarts.

The packaged desktop application starts its own backend on a private local
port. Opening it is an alternative to running the source/browser dashboard.

## Verification and distribution boundary

- TypeScript and Vite build passed.
- Nine frontend contract tests passed: transport outage, HTTP 404 distinction,
  aborted requests, invalid responses, lazy capture, track cleanup, late grants,
  superseded requests, denied permissions and unavailable frame dimensions.
- Actual browser verification: create/deal on port 8765, lab pixel perception,
  new sharing controls visible, isolated server stop on port 18765, recovery
  banner/actions disabled, server restart, reconnect through an expired-session
  HTTP 404, and a new working session. The isolated server was stopped afterward.
- No personal screen/window was selected during automated verification. Actual
  display-picker selection is user controlled; stream ownership is tested with
  fixtures, not presented as a captured real desktop.

These changes are in the current source/browser UI. The immutable **v0.1.0**
Windows release predates these controls and retains its original binaries and
evidence. Its existing mathematical engine and local backend are unchanged.
