# TypeSafe image observer (experiment)

An optional second observer built on TypeSafe's image questions (Noul and Box, Jev 1.14). It is **not** a card reader and
it never chooses an action, a bet or an EV. The local OCR/detector stays the reader; this experiment asks whether an
independent model can cheaply answer scene questions that the lab currently handles with manual calibration:

- is a blackjack table with dealt cards visible (Noul),
- are player action buttons visible (Noul),
- is this a Texas Hold'em table instead (Noul),
- where is the table/video canvas on the screen (Box), which could pre-fill the manual table calibration.

Images and Box are marked "Dreamer-ready" by TypeSafe (not production, format and limits may change), and the vendor
says models perform worse on images than on text. See <https://docs.typesafe.ai/images> and
<https://docs.typesafe.ai/primitives/box>.

## Run

```powershell
python experiments/typesafe_images/run_experiment.py --dry-run          # validates labels and image sizes, no request
$env:TYPESAFE_API_KEY = "<already set securely>"                       # never committed, never printed
python experiments/typesafe_images/run_experiment.py --allow-network --output experiments/typesafe_images/jev-1.14.0-report.json
```

Nothing is sent without `--allow-network` and a key already in the environment. Requests carry the required
`TypeSafe-Danger-Zone-Images: true` header. Each image is referenced once, in the state, because every reference adds
another copy of the image to the input (five references cost about five times as many tokens in a measured test).
Errors are recorded by status or type only, never by message.

This experiment is separate from the cloud ledger and its USD cap described in `AGENTS.md`. It keeps its own usage
numbers inside the report. The ledger, keys and billing settings are untouched.

## Data and limits of the evidence

`labels.json` holds 17 hand labels of the screenshots in `docs/screenshots`, written by looking at each image, with
eyeballed table boxes (about 2% error). The screenshots show the lab's own UI over its synthetic artwork. They are not
real casino footage, not an independent holdout and not enough to certify a threshold. Two false alarms for "action
buttons" (strategy table and mobile view) come from H/S/D legend chips that look like buttons; the labels were not
adjusted to hide that.

## Robustness run (same day, `--variants`)

Each screenshot was also sent blurred, darkened, at half resolution with JPEG quality 30, with the left sidebar cut off
(the box moves accordingly) and with a grey block over 30% of the table: 102 requests, 0 errors, 305,128 input tokens
(about USD 0.013), latency about 0.40 s median and 0.63 s p95. The mean Box IoU stayed between 0.84 and 0.90 in every
variant. Scene questions moved by one or two images per variant (details in `jev-1.14.0-variants-report.json`):
the Hold'em screen was missed after blur and at low resolution, "action buttons" lost one or two true cases at low
resolution and blur, and the dark copies produced two misses for "blackjack table" (plus one false alarm, as did
blur and low resolution). The "action buttons" false alarms on legends appear in all variants (two in four of them, one
in blur and low resolution). These variants are artificial degradations of the same 17 pictures, so they
test sensitivity to image quality, not new tables or new layouts.

## Measured result (2026-10-20, jev-1.14.0, 17 images, one run)

See `jev-1.14.0-report.json` for every number. Headline: Box found the table canvas with a mean IoU of 0.85 against the
hand boxes (11 of 11 at IoU 0.5 or better, 10 of 11 at 0.7). Latency was about 0.44 s median and 0.64 s p95 per image.
All 17 requests used 58,513 input tokens (about USD 0.0025 at the listed price).
