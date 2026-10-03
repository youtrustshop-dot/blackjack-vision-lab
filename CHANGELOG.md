# Changelog

## Unreleased

- Explain an unavailable local backend and offer explicit reconnection.
- Distinguish expired sessions from transport failure; reconnect recreates a
  session after a server restart and clears stale decision/perception output.
- Add user-selected display sharing, local preview and still-frame capture for
  calibration/import in supported desktop browsers.
- Stop display tracks on cancel, source end, tool closure and component unmount;
  reject late/superseded permission grants.
- Add nine frontend regression tests and run them in GitHub Actions.

See [screen sharing and recovery](docs/SCREEN_SHARING.md). The release v0.1.0
installer and portable ZIP remain the verified original artifacts.

## 0.1.0

Initial verified simulator, deterministic EV engine, counting, controlled
perception, replay, research reports and Windows desktop distribution.
