# Optional local Clef experiment

The source is [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash),
pinned at `17f0b0ad64efb65d273590632833508766b2aae6`, with Apache-2.0 terms. Its
typed classification head accepts images. It is separate from the blackjack engine.

## Installation

The model is approximately 19 GB plus the CUDA environment. A drive with at least
35 GB free is useful. Python 3.12, a CUDA-compatible NVIDIA GPU and a supported
driver are optional requirements. Hardware and quantization need an actual test.

```powershell
.\scripts\install-clef.ps1 -Directory D:\BlackjackVisionLab\clef
.\scripts\run-clef.ps1 -Directory D:\BlackjackVisionLab\clef
```

The scripts create a separate environment, use pinned runtime versions and
download the pinned official model. No OpenAI / Typesafe key is requested. The
runtime listens on loopback `127.0.0.1:9051`; keep it open while used. It is optional
and is not included in the Windows installer.

The script checks the official model-head file’s SHA-256 before importing it.
The unchanged head uses an NF4 backbone with float16 computation. Input/output
vocabulary matrices are mapped read-only from the official checkpoint; only
requested input-token and option-token rows move to GPU. The adapter's BF16,
F16 and F32 row-selection self-test compares exact stored values, including
repeated batched indices and out-of-range rejection. This preserves the head’s
row calculation while reducing resident RAM and VRAM use. It is an
experimental configuration, not an upstream performance certification or a
lossless equivalent of full-precision inference.

**Programs & extensions → Check local Clef runtime** checks readiness. **Image &
manual advice → Optional Clef scene check** classifies the supplied image. Its
result remains separate from mathematical advice and card counts. Classifier
confidence is never described as a probability of winning.

An independent test records load time, GPU/VRAM and text/image results:

```powershell
D:\BlackjackVisionLab\clef\venv\Scripts\python.exe scripts\clef-runtime.py `
  --model D:\BlackjackVisionLab\clef\model `
  --test-image path\to\controlled-table.png --evidence work\clef-test.json
```

Add `--serve-after-test` to keep the successfully tested model on port 9051,
avoiding a second load. Processor dependencies are checked before loading weights.
The CUDA environment pins PyTorch 2.11.0 and Torchvision 0.26.0 from the
[official CUDA 12.6 wheel index](https://download.pytorch.org/whl/cu126/torchvision/).
Torchvision is required by the upstream processor even for image-only requests.

Offline/OOM/timeout stays visible and does not disable core strategy or video.
A small smoke test does not establish general card recognition, five-table neural
inference or downstream strategy accuracy. Connecting a new model to arbitrary
artwork tracking requires labeled data and separate false-count, abstention and
latency evaluation. Laya remains deferred; Jev is optional and inactive.

## Measured local run

[CLEF_VERIFICATION.json](CLEF_VERIFICATION.json) records the actual pinned model
on an RTX 2070 SUPER with 8 GB VRAM and 16 GB system RAM. The empty-office text
case selected `other`; the controlled A–7 lab image selected `blackjack`. This
two-case check establishes execution, not general classification accuracy.

Loading took 1,099 seconds during concurrent work. The first text and image
classifications took 137.1 and 35.7 seconds. A subsequent actual HTTP request
through the core bridge classified the same image in 3.8 seconds (8.2 seconds
roundtrip). A subsequent actual browser button test reported 1.2 seconds for
the warm image classification, while mathematical A–7 advice remained Hit.
Peak allocated model VRAM was 4,028 MiB. These are measured examples,
not minimum hardware requirements or latency bounds. This setup is unsuitable
for per-frame real-time neural analysis on five tables.

Earlier full CPU-vocabulary loading was stopped at 97% RAM pressure. The row
adapter then completed backbone loading but encountered the missing Torchvision
dependency. After installing it, an unsupported processor backend option was
removed and the final processor/image/inference path passed. Model loading also
caused substantial system-memory pressure; the preview diagnostic failure is
retained in STATUS.md. The first bridge readiness check exceeded its 3-second
budget; the subsequent warm status and classification request passed.

The two `UNEXPECTED` vocabulary keys in the Transformers report are intentional:
their unchanged rows are supplied by the read-only checkpoint adapter. No other
missing or unexpected model keys were reported. Quantization remains approximate.
