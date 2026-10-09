# Run the consolidated source and move to another PC

The source following desktop 1.1.1 keeps the production local reader as its
default. Research candidates, frozen comparisons and failure reports are
included for reproducibility. Merging source does not replace the installed
desktop app or promote an experimental detector.

## Windows source setup

Install Python 3.12 and Node.js 22 from their official distributions, then:

```powershell
git clone https://github.com/youtrustshop-dot/blackjack-vision-lab.git
cd blackjack-vision-lab
.\setup.ps1
.\run.ps1
```

For an existing clean checkout on main, use `git pull --ff-only` before setup.
Keep the server terminal running and open http://127.0.0.1:8765 in Chrome/Edge.
The server listens on localhost. Screen sharing still requires the browser's
user-controlled display picker. A different backend port is a different live
observer: do not mix an old browser tab with a new native candidate's address.

`setup.ps1` installs the locked application and test dependencies, including
the independent PokerKit/Treys research references. It builds the frontend.
It does not install the separate YOLO training environment, fetch weights,
read an API key, submit inference or install a desktop release. Core local
simulations/analysis require no paid API credential.

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/check-evidence.py
npm --prefix ui test
npm --prefix ui run build
.venv/Scripts/python.exe scripts/smoke-source.py --output artifacts/source-smoke-check
```

The final command starts a temporary real loopback server, removes provider
credentials from its child environment and verifies the frontend, local
simulation and closed research defaults. Use a fresh output directory each
time; it stops its own server and never overwrites previous receipts.

The opt-in owned-canvas integration is a separate local development runner:
`validation/tools/owned_local_demo.py` describes its arguments. Its normal
backend is deliberately unconfigured rather than silently enabling cloud.
Native Windows packaging remains the separate process in [DESKTOP.md](DESKTOP.md).
The browser popup does not guarantee always-on-top; native-window geometry,
screen capture while minimized and physical monitor/DPI checks have their own
acceptance criteria.

## What GitHub contains

Code, tests, public aggregate experiment results and documentation move with
the repository. Git commits preserve the original source used by each old
experiment. The installed 1.1.1 artifacts remain separately bound to their
published source. A historical final test cannot become a fresh holdout by
cloning it again.

Ignored `artifacts/`, environments, secrets, private screenshots, training
weights and raw research inputs do not move with a clone. They are unnecessary
for the default application, but required to reproduce experiments that name
them. A missing file is a missing prerequisite, not permission to substitute
another dataset or regenerate consumed evidence.

Before retiring the old PC, preserve those required private assets through
an explicit private backup. In particular, keep the canonical API budget
ledger and all uncertain-charge reservations; never initialize a new budget
because the old ledger was not copied. API execution stays disarmed on the
new computer. Never paste a key into chat or add it to Git.

Rejected-output diagnostics use current-user Windows DPAPI. Copying encrypted
files to another account/computer does not demonstrate that they can be read
there. A separate authorized migration/recovery procedure is needed before
discarding the old Windows identity. No private export is performed by setup.

## What still needs proof

The local reader's transfer to other provider graphics, complete inventory
reconstruction, live cloud fallback and physical multi-monitor behavior remain
bounded by the published evidence. The current audit checks software readiness;
it does not establish universal card recognition or long-term profitability.
