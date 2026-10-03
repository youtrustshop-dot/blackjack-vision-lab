# Public source publication

This repository publishes the independently implemented Blackjack Vision Lab
core, React UI, Tauri shell, tests, research runners and measured reports. Version 0.2.0 adds continuous live video and English-first distribution.
At initial publication (commit `a24cf1044de53ed2325391c47710ba3227e2c222`),
the Python core, UI source and native shell files matched the verified Windows
distribution; public-facing README, licence and contributor documentation were
added for publication. Subsequent UI changes are recorded in `CHANGELOG.md`.
The original delivered source archive remains unchanged.

The repository omits the original pasted conversations, build caches, bundled
executables, compiled frontend and the large generated tray PNG collection.
Dependency notices are retained under `ui/src-tauri/licenses/`. Release binaries
and the portable ZIP are downloadable from the GitHub release; its checksums
identify the exact verified files. Historical release evidence remains under
`release/` and refers to those files, not a fresh build from every subsequent
commit. No credentials or model weights are needed to start the laboratory.

Regenerate the synthetic card dataset:

```powershell
python -m bjlab.cli dataset datasets/synthetic_cards --sessions 120 --seed 13
```

Regenerate and evaluate the original synthetic shoe/tray study:

```powershell
python -m bjlab.shoe_inference_benchmark generate experiments/shoe_inference/dataset --sessions 50 --seed 29
python -m bjlab.shoe_inference_benchmark run experiments/shoe_inference/dataset --output experiments/shoe_inference/benchmark-report.json
```

The controlled artwork detector is validated. External photographic failures
remain documented; this release does not certify arbitrary card/camera setups.
Laya/Jev actual model execution is deferred. ONNX trained weights and RLCard are
optional future work. MGP was inspected, without an unsupported numerical run.

Desktop rebuilding needs the additional pinned toolchain/font inputs described
in `DESKTOP.md`; `setup.ps1` starts the dashboard from source without them.

`SOURCE_PACKAGE_MANIFEST.json` describes the earlier complete local source
archive, including private input texts and generated assets omitted here. It is
retained as historical evidence, and is not a manifest of this public checkout.
