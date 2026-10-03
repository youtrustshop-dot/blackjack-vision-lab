# Screen sharing and backend recovery

The 0.2.0 **Live vision → Share screen** workflow uses continuous video. Choose a screen/window/tab in Chrome or Edge, calibrate four table corners when needed, and observation starts automatically. Use **Run lab demo** for an immediately working lab-video source and **Floating advisor** for compact guidance. See [the complete guide](LIVE_VISION.md).

Display access is user-selected; no audio is requested. Stop through **Stop video**, the browser's sharing control or page closure. Switching laboratory sections preserves the live stream. Late permissions/results are rejected after cancellation. The desktop shell can hand the same local URL to the system browser; keep the shell running and use Chrome/Edge.

The detector supports the lab artwork. The processed-video tests and canvas `MediaStream` browser demo do not certify arbitrary external card graphics or a personal display-picker selection.

## Backend unavailable

If the local Python service stops, its cached page may remain visible. Transport failures display recovery instructions and disable session operations. Restart `run.ps1`, then press **Reconnect**. A missing in-memory session is recreated from configured rules and seed. Export a replay before restarting if its history matters.

The desktop app launches its owned backend on an ephemeral localhost port. A browser using that port depends on the desktop app staying open. Stream failures remove advice instead of leaving old recommendations visible.

The immutable v0.1.0 binaries predate this live workflow. Use the v0.2.0 release. Historical manual-capture tools remain for offline image research; they are not the live workflow.
