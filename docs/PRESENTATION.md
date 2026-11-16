# SmartHealth AI — Presentation Script

A speaker script for presenting this project (course review / demo day). Written for a
2-person team, ~12 minutes talk + ~5 minutes live demo + Q&A. Every number here is
traceable to an actual run — see the file/section references so you can defend each claim.

- **Total time:** ~20 min (12 talk / 5 demo / 3 Q&A)
- **What to have open before you start:** two terminals in the repo root, `venv` activated,
  a browser tab on `http://localhost:5000`, this file, and `docs/DOCUMENTATION.md`.
- **Pre-flight (run once, silently, before the audience is watching):** see [§8](#8-pre-flight-checklist).

---

## 0. One-line summary (say this if you only get one sentence)

> "We built a low-cost wearable that streams motion and pulse data to a server, and a
> 1D CNN classifies the wearer's activity and detects falls in real time — trained and
> measured on a real geriatric-fall dataset, with an honest account of what it does and
> doesn't do."

---

## 1. Opening — the problem (1 min)

**Say:**

"Falls are the leading cause of injury for older adults, and the danger isn't just the
fall — it's lying undetected afterwards. Commercial fall-alert pendants exist but they're
expensive and single-purpose.

Our project, SmartHealth AI, is a student prototype of a wrist wearable that does two
things at once: continuous activity monitoring — walking, running, sitting, lying — and
automatic fall detection, with a live dashboard and a local buzzer alert.

Up front, the honest framing: this is a monitoring and classification prototype for a
Healthcare Analytics course. It is **not** a certified medical device, it does not
diagnose anything, and our SpO2 is an estimate, not a clinical reading. That disclaimer
is in the README and on the dashboard itself — `docs/AUDIT.md` tracks it as a hard rule."

**Why lead with the disclaimer:** it's a healthcare course. Showing you know the scope
limits is worth more than one extra feature.

---

## 2. What it is — the architecture (2 min)

**Show:** the architecture diagram in `README.md` (or `docs/DOCUMENTATION.md` §2).

**Say, tracing the diagram top to bottom:**

"The wearable is an **ESP32** microcontroller with two sensors: an **MPU6050** — a 6-axis
accelerometer and gyroscope — and a **MAX30102** pulse-oximetry sensor for heart rate and
estimated SpO2. Plus a buzzer for the local alert.

The ESP32 samples the motion sensor, timestamps it, packs it into JSON, and POSTs it over
Wi-Fi to a **Flask backend**. The backend validates every payload — malformed data is
rejected with a 400, not silently accepted.

The backend feeds the motion stream into a **segmentation buffer** that watches for a
motion event, captures it, and resamples it to a fixed 150-timestep by 6-channel tensor —
the exact same shape and transform the model was trained on.

That tensor goes to the **1D CNN**, our deployed model. It outputs an activity class and a
fall probability. A **decision engine** then applies rule-based checks — peak acceleration,
post-event stillness — and decides whether to confirm a fall.

Everything lands in **SQLite**, and a **web dashboard** polls the backend every 2 seconds
to show live vitals, the activity, the acceleration waveform, and any alerts. A confirmed
fall flips the dashboard into an alert state and tells the ESP32 to sound the buzzer.

One design principle we enforced everywhere: the ML preprocessing is **the same code**
in training and in live inference. Not equivalent — the same functions. That mattered,
and I'll come back to why."

---

## 3. The ML — what we actually did (3 min)

**Show:** `docs/DOCUMENTATION.md` §6.3 (the results table).

**Say:**

"The academic core is **time-series deep learning**, not image detection. The input is a
3-second window of 6-axis IMU data — 150 samples by 6 channels.

**Dataset.** We trained on **BITS-2**, a public dataset from BITS Pilani Goa — a
geriatric-fall study collected with a wrist device using the *same sensor pair* as ours:
an MPU-series IMU plus a MAX30102. 41 subjects, 16 daily-activity types, 8 fall types.
We chose it specifically because the sensors match — not a phone-based dataset.

**Honest mapping.** BITS-2's activities don't map perfectly to our target classes. We
mapped what mapped cleanly — walking variants, jogging, sitting, lying, all falls — and
**excluded** what didn't: jumping, hand-swinging, and lying-transition trials, 205 trials
dropped rather than force-labeled. Two classes from our original plan — *Standing* and
*Tremor* — have no matching data in BITS-2 at all, so **we did not train them**. The
dashboard shows Tremor as 'Not available' rather than inventing a number. That's a
deliberate choice, documented in `docs/DOCUMENTATION.md` §5.

**Split.** Subject-wise: 29 subjects train, 6 validation, 6 test. No subject in more than
one split, no preprocessing statistic fit on anything but the training set. The test
subjects — 2, 3, 9, 14, 34, 37 — were never seen during training or threshold tuning.

**Models.** We trained a **1D CNN** and an **LSTM** for comparison — 6 CNN configs, 4 LSTM
configs, early-stopped on validation macro-F1. Results on the held-out test set:

| Model | Test accuracy | Macro-F1 | Fall recall | Inference (CPU) | Params |
|---|---|---|---|---|---|
| **CNN (deployed)** | **85.1%** | **0.805** | **89.6%** | 0.12 ms/window | 11,813 |
| LSTM (comparison) | 81.6% | 0.755 | 87.5% | 2.1 ms/window | 52,037 |

The CNN wins on **every axis** — accuracy, F1, fall recall, 17x faster, 4x smaller. The
LSTM underperforms because the dataset is small and the windows are whole resampled trials,
not long natural sequences — that favors the CNN's local-pattern bias. We weighted **fall
recall** first in the choice, because a missed fall is the dangerous error.

**The caveat we say out loud:** the test set is 114 windows from 6 subjects. 'Fall' has 48,
'Running' and 'Lying' only 6 each. Treat '85%' as 'this model on this specific held-out
set,' not a universal claim. That's in §6.3."

---

## 4. The engineering story — one bug worth telling (1.5 min)

**Say:**

"The most instructive thing that happened wasn't in training — it was in live inference.

Our first real-time design used a naive fixed 3-second rolling window over the live
stream. It looked reasonable. But when we replayed a real fall trial through it, the live
model said 'Lying, 14% fall probability' — while the *same trial* evaluated offline said
'Fall, 80-plus percent.'

The cause: BITS-2 trials are short discrete recordings that we resample to a fixed grid
for training. A fixed-length rolling window over a continuous stream is a **different
transform** than the model ever saw. We were silently feeding it out-of-distribution data.

The fix was **event-triggered segmentation** — detect motion onset, capture the event,
detect offset, then resample that segment with the *identical* function used in training.
That's `ml/segmentation/windowing.py`. After the switch, live and offline agreed.

We found two other bugs the same way — by testing, not by reading code: a missing
dictionary key that 500'd the API, and a Flask route conflict that 404'd the dashboard
assets. All three are in the audit log in `docs/AUDIT.md`."

**Why tell this:** it shows real debugging and the train/inference-parity principle in
action. Examiners like a project that found its own bug.

---

## 5. Live demo (5 min)

> Two terminals, both in repo root with `venv` active. Backend already running from
> pre-flight. Browser on `http://localhost:5000`.

### 5a. Show the model works end-to-end on unseen data (~1 min)

**Terminal 2:**
```bash
python -m tests.e2e_demo
```

**Say while it runs:**

"This runs four scenarios through the full pipeline — backend, segmentation, CNN, decision
engine, database — using trials from the **held-out test subjects** the model never saw.
Walking, Sitting, Running, Fall."

**Point at the output:**

- `Walking ... PASS`, `Sitting ... PASS`, `Running ... PASS`, `Fall ... PASS`
- On the Fall line: `confirmed_fall=True`, and note `motion_verified=False` —
  "this particular fall is a soft landing that never spikes the accelerometer hard.
  Our decision engine still confirms it, because we confirm on the AI probability and
  *attach* the rule checks for the log rather than letting them veto a detection. Real
  falls don't all look the same — 46% of the fall trials in this dataset never cross the
  acceleration threshold."
- The Tremor line: "explicitly **not run** — no trained class. Reported, not skipped."

### 5b. Live dashboard — a full activity arc with a fall (~3.5 min)

**Terminal 2:**
```bash
python -m tests.demo_5min
```
(Use `--fast` if you're short on time — it sends the whole arc in a few seconds. Real-time
is more convincing if you have the minutes.)

**Say while it streams, switching to the browser:**

"This replays a realistic ~5-minute arc from real test-subject data: resting, walking,
jogging, cooldown, sitting, lying down, then a fall, then post-fall stillness. Heart rate
and SpO2 follow a plausible trajectory for each phase.

Watch the dashboard — it polls every 2 seconds, no refresh."

**Point out, as each happens:**

- The **hero waveform** is the live acceleration-magnitude signal — the actual input the
  model classifies, not decoration.
- The **Current Activity** card changing as the arc progresses; the confidence bar.
- **Heart rate / SpO2** cards and their sparklines moving with the phase.
- When the fall hits: the dashboard flips to a **FALL DETECTED** alert banner, the status
  LED goes red, the alert is written to the **activity log**, and the API response carries
  `"buzzer": true` — on real hardware that's the ESP32 sounding the buzzer.
- Post-fall: the alert stays active (it's a latched critical alert, cooldown not
  repetition-debounce).

**If asked "is this real data?":** "The motion is real BITS-2 trials from held-out subject
2. The idle gaps between events and the vitals arc are synthetic — BITS-2 trials are too
short to carry a 5-minute vitals story — and we label that clearly in the script's
docstring."

### 5c. Config-driven, briefly (~30 sec)

**Show:** `dashboard/static/config.js`.

"Poll rate, trace length, which device, backend URL — all here, one file, no code changes.
Same discipline on the ML side: every rate and threshold lives in `ml/config.py`."

---

## 6. Honest limitations (1.5 min)

**Show:** `docs/DOCUMENTATION.md` §21.

**Say:**

"What we're not claiming:

1. **No physical hardware run yet.** The ESP32 firmware is written and **compiles against
   the real Espressif toolchain** — we can show `pio run` succeeding — but we had no
   physical board, sensors, or buzzer in this environment. Phases 1 and 2 are code-complete,
   hardware-unverified. That's the one open gap.
2. **Sensor domain gap.** The model learned BITS-2's hardware, not our exact chips. Transfer
   to our MPU6050 is unmeasured until we collect data on our own board.
3. **Standing and Tremor aren't trained** — no data.
4. **One threshold is provisional** — post-fall inactivity time. BITS-2 trials are too
   short to measure it; it's a literature-informed placeholder, flagged everywhere it
   appears, not presented as measured.
5. **A real false positive we found and kept in the docs:** the event-segmenter can catch
   a short ambiguous burst right as someone starts moving, and that can cross the fall
   threshold — we measured it at 52% confidence during testing. It's a direct consequence
   of prioritizing recall. We wrote up mitigation ideas rather than patch it with an ad hoc
   tweak that we couldn't re-validate.

Every metric in our report traces to a logged run. There are no placeholder numbers
presented as real — `docs/AUDIT.md` §3 is our own checklist for that."

---

## 7. Close + roadmap (30 sec)

**Say:**

"So: a full software stack — firmware, backend, ML, dashboard, decision engine — built in
nine phases, tested against real data, with the deviations and bugs documented as we went.

Next steps, in order: flash the firmware to a real board and close Phase 1, collect our own
data to measure and correct the sensor gap, then add Standing and Tremor as trained
classes. Everything software-side is ready for that.

Questions?"

---

## 8. Pre-flight checklist

Run this **before** the audience is in the room. ~2 min if the dataset is already in place,
~5 min if you need to train.

```bash
cd /path/to/Healthcare
source venv/bin/activate

# 1. Dataset present? (needed for the demos)
ls data/raw/bits2/Dataset/adl/user2/user2_adl1.csv   # should exist

# 2. Models present? (skip training if these exist and you trust them)
ls models/deployed_model.pt models/scaler.json models/model_meta.json

#    ...or regenerate from scratch (~2-8 min on CPU):
python -m ml.training.train
python -m ml.evaluation.threshold_analysis

# 3. Start the backend (leave running in Terminal 1):
python -m backend.app                                 # http://localhost:5000

# 4. Smoke-test in Terminal 2:
curl -s http://localhost:5000/api/health              # {"status":"ok"}
python -m tests.e2e_demo                               # Walking/Sitting/Running/Fall PASS

# 5. Open the dashboard, confirm it renders with no console errors.
open http://localhost:5000

# 6. Optional: pre-seed one fall so the dashboard isn't empty on first load:
python -m tests.fake_esp32_sender \
  --trial data/raw/bits2/Dataset/adl/user2/user2_adl1.csv --device-id wearable_01
```

**If the demo machine has no dataset and no internet:** run `tests/e2e_demo.py` is not
possible without BITS-2. Fall back to: the pre-recorded screenshots in `docs/screenshots/`,
the `docs/DOCUMENTATION.md` §6.3 numbers, and a walkthrough of the code. Say clearly that
the live demo needs the dataset.

**Firmware compile demo (optional, impressive, needs PlatformIO):**
```bash
pip install platformio
cd firmware/esp32
cp src/secrets.h.example src/secrets.h
pio run                        # live-streaming build
pio run -e esp32dev_logger     # Phase 2 logger build
```
Both compile clean (~73% flash / 15% RAM for the streaming build). Nothing runs on a board.

---

## 9. Q&A prep — likely questions and honest answers

**"Why a CNN and not an LSTM for time series?"**
We tried both. On this dataset the CNN beat the LSTM on every metric including fall recall,
and it's 17x faster. LSTMs need more sequence data than 547 short windows to pay off.
Details in `docs/DOCUMENTATION.md` §6.3.

**"85% accuracy isn't very high for a medical application."**
Agreed, and we don't call it medical. Two things: fall *recall* is 89.6%, which is the
metric that matters for safety, and the test set is tiny (6 subjects) so the number has a
wide confidence interval. A deployed version needs far more data — that's limitation #2.

**"How do you know it's not overfitting / leaking?"**
Subject-wise split, scaler fit on train only, thresholds tuned on validation and never on
test, test subjects fixed and disclosed. `docs/AUDIT.md` §2 is our data-integrity
checklist.

**"Does it actually run on the ESP32?"**
The firmware compiles against the real Espressif toolchain — we can show that. It has never
run on a physical board because we didn't have one. That's the single biggest open item and
it's stated plainly in the README status badge and `docs/PLAN.md`.

**"What about the buzzer / hardware alert?"**
Backend returns `"buzzer": true` on a confirmed fall — verified. Firmware reads that flag
and drives the buzzer pin — compiles, never physically tested.

**"Why is the fall confirmed even when motion_verified is False?"**
Deliberate. We measured that requiring the acceleration rule as a hard gate would catch
only 54% of real falls in this dataset — soft falls onto a bed don't spike. So we confirm
on the AI probability (precision 1.00 on validation at our threshold) and log the rule
signals for explainability. `docs/DOCUMENTATION.md` §7.

**"Can it detect tremor / Parkinson's?"**
No. No tremor data in BITS-2, so no trained class. The dashboard says 'Not available.' If
we ever add it, it would be labeled 'tremor-like movement,' never a disease name.

**"What's the SpO2 accuracy?"**
It's a simplified AC/DC-ratio estimate, not the Maxim clinical algorithm. Framed as
'estimated' everywhere. We would not report it as a clinical measurement.

**"How is real-time inference kept consistent with training?"**
The same preprocessing functions are imported by both paths — `resample_to_window` and
`ChannelScaler`. We learned this the hard way: a naive rolling window silently used a
different transform and produced wrong live predictions until we redesigned it into
event-triggered segmentation. `docs/DOCUMENTATION.md` §15.

**"How long did this take / who did what?"**
2-person team, 9 phases, built in dependency order (hardware contract → ML → backend →
inference → dashboard → decision engine → end-to-end). `docs/PLAN.md` has the phase list.

---

## 10. Timing cheat-sheet

| Segment | Target | Cut first if short on time |
|---|---|---|
| Problem + disclaimer | 1:00 | — |
| Architecture | 2:00 | trim to the diagram + 3 sentences |
| ML / dataset / results | 3:00 | drop the LSTM detail, keep the table |
| The bug story | 1:30 | **cut entirely** if needed |
| Live demo | 5:00 | use `demo_5min --fast`, skip 5c |
| Limitations | 1:30 | keep #1 and #5, drop the rest |
| Close | 0:30 | — |
| Q&A | 3:00 | — |
