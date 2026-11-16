# SmartHealth AI — 10-Slide Presentation Script

Speaker script for the 10-slide deck (`SmartHealth AI — Project Presentation`). Written for a
2-person team, ~11–13 minutes of talking across 10 slides, plus an optional 5-minute live demo
cue on slide 7 and Q&A. Every number here is traceable to an actual run — see the file/section
references so you can defend each claim. This is the companion script to the deck; for the
longer 20-minute version with a full live-demo walkthrough, see `docs/PRESENTATION.md`.

- **Total time (no live demo):** ~12 min talk + Q&A
- **Total time (with live demo on slide 7):** ~17 min talk + demo + Q&A
- **Have open:** the deck, a browser tab on `http://localhost:5000` if demoing, and this file.
- Each slide below also carries its own short speaker notes inside the deck itself (visible in
  presenter/speaker-notes view) — this document is the fuller version to rehearse from.

---

## Slide 1 — Cover (~30 sec)

**Say:**

> "SmartHealth AI is a wearable we built for our Healthcare Analytics course that watches how
> someone moves and how their vitals trend, and flags a fall the moment one happens. Everything
> you'll see today is a real trained model running against real backend code — not mockups."

Point at the dashboard screenshot on the slide. State the scope line out loud: **2-person
team, fixed low-cost hardware, and up front — this is a monitoring and classification
prototype, not a certified medical device.**

---

## Slide 2 — Problem Definition & Objectives (~75 sec)

**Say:**

> "Falls are a leading cause of injury for older adults, and the real danger is often lying
> undetected afterward. Commercial fall-alert pendants exist, but they're expensive,
> single-purpose, and reactive rather than continuous."

Walk the five objectives on the right as a checklist of what the project set out to build:
continuous activity recognition, automatic fall detection with a local buzzer + dashboard
alert, deep learning on time-series IMU/PPG data (CNN benchmarked against an LSTM), live
heart-rate/SpO₂ monitoring, and a documented decision engine.

Close by reading the disclaimer box: it's in the README and on the dashboard itself, tracked
in `docs/AUDIT.md` as a hard rule.

---

## Slide 3 — System Architecture (~90 sec)

**Say, tracing the numbered pipeline top row then bottom row:**

> "The wearable is an ESP32 with an MPU6050 for motion and a MAX30102 for pulse-ox, plus a
> buzzer. It posts timestamped JSON to a Flask backend over Wi-Fi, which validates every
> payload — malformed data gets a 400, not a silent accept. The backend segments the motion
> stream into a 3-second, 150-by-6 tensor — exactly what the CNN was trained on — and feeds it
> to the model."

> "The CNN's output goes to a decision engine that combines AI probability with rule checks —
> peak acceleration, post-fall stillness. Everything lands in SQLite, and a dashboard polls
> every two seconds. A confirmed fall flips the dashboard to an alert and tells the ESP32 to
> buzz."

End on the bottom line: **the ML preprocessing is the same code in training and in live
inference — not equivalent, the same functions.** Flag that this mattered in practice (the
segmentation-bug story is in `docs/PRESENTATION.md` §4 if you have time for it).

---

## Slide 4 — Dataset, Split & Training Discipline (~75 sec)

**Say:**

> "41 subjects, recorded with the exact same sensor pair as our hardware — that's why we chose
> BITS-2 over a generic phone-based dataset. 775 labeled windows total, split by subject so no
> person ever appears in more than one of train, validation, or test."

> "5 of 7 planned classes are actually trained. Standing and Tremor aren't — there's no
> matching data in BITS-2, so we report them as unavailable instead of faking a number."

Point at the dataset card: 205 trials that didn't map cleanly (jumping, hand-swinging,
transitions) were **dropped, not force-labeled** — a data-integrity choice. Then the three
principle cards on the right — train/inference parity, no leakage, event-triggered
segmentation — as the discipline that makes the next slide's numbers trustworthy.

---

## Slide 5 — Quality of Work & Innovation (~90 sec)

Pick **two** cards to tell as short stories rather than reading all six.

**Best story — the parity bug:**

> "Our first live design used a fixed rolling window. It looked reasonable, but a real fall
> trial that scored over 80% fall probability offline scored 14% live. The cause was a silent
> transform mismatch — a fixed-length window over a continuous stream is a different transform
> than the model ever saw in training. We fixed it with event-triggered segmentation, and
> after that, live and offline agreed."

**Second — the decision-engine deviation:**

> "We measured that gating fall confirmation on the acceleration rule would catch only 54% of
> real falls, since soft falls onto a bed don't spike the accelerometer. So we confirm on AI
> probability alone and log the rule signals for explainability instead of letting them veto a
> detection."

Gesture at the remaining four cards: "the same discipline — sensor-matched data, a fair model
sweep, a leakage-proof pipeline, honest reporting — runs through everything else here."

---

## Slide 6 — Results: Model Performance (~90 sec)

**Say, pointing at the left table:**

> "The CNN beats the LSTM on accuracy, macro-F1, and fall recall, and it's 17 times faster with
> a quarter of the parameters — about 11.8 thousand versus 52 thousand. The LSTM underperforms
> here because BITS-2 is small and its windows are whole resampled trials, not long natural
> sequences — that favors the CNN's local-pattern bias."

**Pointing at the right table:**

> "Per class, Fall has the strongest numbers by far — 95.6% precision, 89.6% recall, 0.925 F1 —
> and that's the class that matters most for safety. Fall recall was weighted first in model
> selection; the CNN wins that too, so this wasn't a precision/recall tradeoff, it was a clean
> win."

Be upfront: Running and Lying have only 6 test windows each. Read "85.1% accuracy" as "this
model, on this specific 6-subject held-out set," not a universal claim.

---

## Slide 7 — Results: Live Dashboard Demo (~90 sec, or ~5 min with a live demo)

**If running the live demo here:** switch to the terminal and run:

```bash
python -m tests.e2e_demo
```

Say while it runs: "This runs four scenarios through the full pipeline — backend, segmentation,
CNN, decision engine, database — using trials from held-out test subjects the model never saw."

**Narrating the screenshots (with or without the live run):**

> "Left is the calm state — the waveform you see is the actual acceleration signal being
> classified, not decoration. Middle is a confirmed fall: the dashboard flips to a red alert,
> and the API response carries `buzzer: true`, which on real hardware fires the ESP32's
> buzzer. Right is the mobile layout — config-driven, no code changes."

Point at the Running chip: "this one has an asterisk — during testing, a short ambiguous burst
right as the subject started moving crossed the fall threshold at 52% confidence. We kept that
in the record instead of quietly patching it." End on Tremor: "not run — no trained class, and
the dashboard says so honestly instead of faking a result."

---

## Slide 8 — Tutorial Unit 1: Healthcare Data Analytics & EHR (~75 sec)

**Say:**

> "SmartHealth AI itself uses wearable sensor data, not EHR — so for this unit's coursework we
> built our own realistic, synthetic EHR dataset: 410 records, deliberately messy, so the
> cleaning tutorials had real problems to fix."

Point at the two charts: left is T1's diagnosis-code breakdown across real ICD-10 codes (I10
hypertension, E11.9 type 2 diabetes, J45.909 asthma); right is T3's before/after — missingness
dropped from up to 15% down to exactly zero, combining listwise deletion for the truly
unsalvageable rows with KNN/median/mode imputation for the rest.

Mention T2 in passing: standardizing gender and date formats, and catching 42 rows where a
temperature had silently been recorded in the wrong unit (°F instead of °C).

---

## Slide 9 — Tutorial Unit 2: Biomedical Image Analysis (~75 sec)

**Say:**

> "There's no imaging pipeline in the main project, so this unit uses scikit-image's biomedical
> microscopy sample image as a realistic stand-in — documented honestly in the README."

Walk the four tiles: "top-left is the raw microscopy image, top-right after CLAHE contrast
enhancement — that's T4. Bottom-left is RANSAC: we warped a copy of the image by a known
12-degree rotation, detected SIFT keypoints in both images, and RANSAC recovered an
11.9-degree estimate while rejecting the mismatched pairs as outliers — that's T5. Bottom-right
is T6's segmentation overlay, the boundary Otsu thresholding found, drawn back on the original
image."

Mention verbally (not pictured): denoising restoration recovered PSNR from about 20 dB to 25
dB, JPEG compression at quality 10 vs. 90 shows the classic size-vs-quality tradeoff, and a
tiny torch CNN trained on synthetic image patches with monotonically decreasing loss —
demonstrating the full forward/backward training pipeline end to end.

---

## Slide 10 — Closing: Limitations, Roadmap & Thank You (~75 sec)

**Say:**

> "The single biggest open item is hardware: the firmware compiles against the real Espressif
> toolchain, but we've never flashed a physical board, because we don't have one in this
> environment. Everything else on the roadmap follows from that."

Read limitation #1 (no hardware run) and #5 (the real measured false positive) if short on
time; the rest — sensor domain gap, untrained classes, provisional threshold — can be trimmed
verbally to "documented in full in `docs/DOCUMENTATION.md` §21."

Walk the roadmap briefly, in order: flash firmware → collect own data → add Standing/Tremor →
re-derive the inactivity threshold from continuous recordings.

Close with the bookend line: **"A low-cost wearable that classifies activity and detects falls
in real time, trained and measured on a real geriatric-fall dataset, with an honest account of
what it does and doesn't do."** Then take questions.

---

## Timing cheat-sheet

| Slide | Target | Cut first if short on time |
|---|---|---|
| 1. Cover | 0:30 | — |
| 2. Problem & objectives | 1:15 | trim to 3 objectives |
| 3. Architecture | 1:30 | drop the parity-code closing line |
| 4. Dataset & training | 1:15 | drop the 205-trials detail |
| 5. Quality & innovation | 1:30 | tell only the parity-bug story |
| 6. Results — model | 1:30 | drop the per-class table, keep the headline table |
| 7. Results — demo | 1:30 (5:00 with live demo) | skip the live run, narrate screenshots only |
| 8. Tutorial Unit 1 | 1:15 | mention T2 in one sentence, skip detail |
| 9. Tutorial Unit 2 | 1:15 | skip the unpictured T4 metrics |
| 10. Closing | 1:15 | keep limitation #1 and #5 only |
| **Talk total** | **~12:15** (~17:45 with live demo) | |
| Q&A | 3:00 | — |

---

## Q&A prep

Reuse the full Q&A bank in `docs/PRESENTATION.md` §9 — it covers the CNN-vs-LSTM choice, the
85% accuracy question, overfitting/leakage, hardware status, the buzzer, the
`motion_verified=False` confirmed fall, tremor/Parkinson's, SpO₂ accuracy, and train/inference
parity. All answers there still apply to this deck unchanged.
