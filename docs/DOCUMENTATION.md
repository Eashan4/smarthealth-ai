# SmartHealth AI — Technical Documentation

Living document. Update each section as the corresponding phase (see [PLAN.md](PLAN.md)) is implemented — do not wait until the end to fill this in. Scope limits and success criteria are tracked separately in [AUDIT.md](AUDIT.md); the phase order lives in [PLAN.md](PLAN.md). This file is the technical reference: architecture, hardware, data, models, backend, firmware, and testing detail.

## 0. Technical identity

A deep-learning-based wearable healthcare analytics system that performs time-series classification of inertial sensor data for human activity recognition, fall detection, and tremor-like movement detection, while simultaneously monitoring heart rate and estimated SpO₂ using a low-cost ESP32-based wearable platform.

- **ML research component:** time-series segmentation → 1D CNN + LSTM comparison → activity/fall/tremor classification.
- **Hardware component:** ESP32 + MPU6050 + MAX30102.
- **Application component:** Flask API + database + real-time web dashboard + alert system.

**Not an image/object-detection project.** Even though the course brief mentions deep learning and object detection generally, this project's deep-learning problem is `sensor time series → temporal feature learning → activity/fall/tremor classification`. Do not introduce YOLO or image-based object detection into the core architecture. If the professor later requires an object-detection component, treat it as an optional add-on, not a redesign of this baseline.

## 1. System layers

| # | Layer | Responsibility |
|---|---|---|
| 1 | Hardware | ESP32, MPU6050, MAX30102, buzzer, push button, battery + charging circuit |
| 2 | Sensor acquisition | ESP32 reads `Ax, Ay, Az, Gx, Gy, Gz, HR, SpO2` + timestamp |
| 3 | Data transmission | ESP32 → HTTP/REST → Flask, configurable sampling/send interval |
| 4 | Data preprocessing | Missing-value handling, noise filtering, normalization, timestamp alignment, sliding-window segmentation, tensor preparation |
| 5 | Deep learning | 1D CNN (primary) + LSTM (comparison) on time-series IMU windows |
| 6 | Decision engine | Combines AI output with rule-based safety checks for activity/fall/tremor/alert state |
| 7 | Database | SQLite: sensor readings, predictions, fall/tremor/alert events |
| 8 | Dashboard | Live vitals, activity, fall/tremor status, graphs, alert + history views |

## 2. Architecture

```
MPU6050 ── Ax,Ay,Az,Gx,Gy,Gz ──┐
                                 ├─→ ESP32 (timestamp) ─→ Wi-Fi/HTTP ─→ Flask Backend
MAX30102 ── HR, SpO2 ───────────┘                                          │
                                                                            ▼
                                                          Filtering / Normalization
                                                                            │
                                                                            ▼
                                                    Sliding Window (3s × 50Hz → 150×6)
                                                                            │
                                                              ┌─────────────┴─────────────┐
                                                              ▼                           ▼
                                                           1D CNN                       LSTM
                                                              │                           │
                                                              └─────────────┬─────────────┘
                                                                            ▼
                                                                    Classification
                                                              (Activity / Fall / Tremor)
                                                                            │
                                                                    Decision Engine
                                                              (AI + rule verification)
                                                                            │
                                                                     Alert Logic
                                                              ┌─────────────┴─────────────┐
                                                              ▼                           ▼
                                                          Buzzer                  Web Dashboard
                                                                                          ▲
                                                                                          │
                                                                                     SQLite DB
```

This is the fixed baseline. Evaluate any change against it rather than adding features ad hoc.

## 3. Hardware

| Component | Role | Notes |
|---|---|---|
| ESP32 | MCU, Wi-Fi, orchestration | Reads both sensors, timestamps, posts JSON, drives buzzer |
| MPU6050 | 6-axis IMU (accel + gyro) | I2C, ~50 Hz sampling |
| MAX30102 | PPG (heart rate, SpO₂ estimate) | I2C, separate stream from IMU, not medical-grade |
| Buzzer | Local fall alert | Triggered by decision engine via ESP32 |
| Push button | Manual ack / test trigger | TBD exact use during Phase 1 |
| Battery + charging circuit | Power | TBD capacity/runtime budget |

**Pin configuration:** default assumption for a standard ESP32 DevKit board (`firmware/esp32/src/config.h`), **not yet physically verified** -- no hardware available in this environment. Confirm against the real board during Phase 1 bring-up.

| Signal | Pin |
|---|---|
| I2C SDA (MPU6050 + MAX30102, shared bus) | GPIO21 |
| I2C SCL | GPIO22 |
| Buzzer | GPIO25 |
| Push button (active-low, internal pull-up) | GPIO26 |

Push button use: silences an active buzzer (see `firmware/esp32/src/main.cpp`).

## 4. Sensor data & configuration

Raw IMU sample: `[Ax, Ay, Az, Gx, Gy, Gz]`.

Config values (must live in one central config, never hard-coded inline):

```
IMU_SAMPLE_RATE = 50          # Hz
WINDOW_SIZE_SECONDS = 3
WINDOW_OVERLAP = 0.5          # 50%
```

Window length in timesteps: `3s × 50Hz = 150`. Model input shape: `150 × 6`. Dataset shape for N windows: `N × 150 × 6`.

Baseline model uses the raw six-axis IMU data only. Derived features (acceleration magnitude, angular velocity magnitude) may be evaluated later but are not part of the baseline.

Sliding window with 50% overlap:
```
Window 1: 0.0–3.0s   Window 2: 1.5–4.5s   Window 3: 3.0–6.0s   Window 4: 4.5–7.5s ...
```
This segmentation logic must be shared code between training and real-time inference — not reimplemented twice.

HR/SpO₂ are a separate, lower-rate stream, synchronized to IMU windows by timestamp — not resampled into the 50Hz IMU stream. Example synchronized reading:

```
Timestamp: 09:15:10
Activity: Walking          Activity confidence: 94%
Heart Rate: 82 BPM         Estimated SpO2: 97%
Fall: No                   Tremor: No
```

## 5. Labels and classes

**v1 trained classes: `Walking, Running, Sitting, Lying, Fall`** (5 classes). `Standing` and `Tremor` from the original 7-class plan are **not trained in v1** -- see "Dataset → app label mapping" below and sec 16 (Known limitations) for why, rather than approximating or fabricating labels for them.

### Dataset → app label mapping (BITS-2, see sec 8)

BITS-2's 16 ADL types + 8 fall types are mapped in `ml/datasets/bits2_adapter.py::ADL_LABEL_MAP`:

| BITS-2 ADL activity | -> Class |
|---|---|
| Walking Slowly, Walking Quickly, Climbing up/down (slowly/normally) x4 | Walking |
| Jogging | Running |
| Slowly/Rapidly sitting, Nearly sitting+getting up | Sitting |
| Lying on Bed | Lying |
| Jumping, Swinging Hands, the 3 lying-transition activities | **excluded** (no honest match) |
| All 8 fall types | Fall |

Excluded-trial counts (real, from the actual data load): Jumping=41, Swinging Hands=41, and each of the 3 lying-transition types=41 (one per subject) -- 205 trials excluded out of 980 total files seen.

Resulting dataset: **775 usable windows** across 41 subjects -- Walking=246, Sitting=123, Lying=41, Running=41, Fall=324.

- **Ordinary activities:** each BITS-2 trial file is a single homogeneous activity recording (whole-trial label), not a majority-vote over a mixed window -- there's no mixed-activity content to majority-vote over in this dataset.
- **Fall:** every fall-type trial is labeled Fall in full (event-centered by construction -- BITS-2 fall trials are trimmed to the fall event itself, not embedded in a longer mixed recording).
- **Standing:** BITS-2 has no static "standing still" activity among its 16 ADL types -- excluded rather than approximated from partial/idle segments of other trials.
- **Tremor:** BITS-2 has no tremor-like class at all -- excluded. Detecting tremor-like movement requires a dedicated dataset (e.g. a Parkinsonian-tremor accelerometer dataset) or custom data collection (Phase 2); until then, the dashboard reports Tremor status as "Not available" rather than a fabricated probability. Never label, log, or report as "Parkinson's disease" if/when tremor detection is added -- only "tremor-like movement pattern."

## 6. Models

### 6.1 Primary — 1D CNN
Input: `150 × 6`. Block (`ml/cnn/model.py`): `Conv1D → BatchNorm → ReLU → MaxPool → Conv1D → BatchNorm → ReLU → MaxPool → GlobalAvgPool → Dropout → Dense(Softmax)`. **Deployed config** (selected by the experiment in 6.3): `filters=(32,64), kernel_size=5, dropout=0.3` -- 11,813 parameters, 52.9 KB on disk.

### 6.2 Comparison — LSTM
`ml/lstm/model.py`: single/multi-layer LSTM -> dropout -> Dense(Softmax) on the same `150×6` input. Best comparison config: `hidden_size=64, num_layers=2, dropout=0.4` -- 52,037 parameters.

### 6.3 Model selection experiment (real results, `ml/training/train.py`)

Trained on the BITS-2 dataset (sec 8), subject-wise split (sec 9), per-channel z-score normalization fit on train only, jitter+scale augmentation (2 extra copies, real recorded windows perturbed, not synthetic content) applied to the training set only. 6 CNN configs and 4 LSTM configs were trained (60-80 epochs each, early-stopped on validation macro-F1, Adam + ReduceLROnPlateau); the table below reports each architecture's best config, evaluated once on the held-out TEST split (subjects 2,3,9,14,34,37 -- never seen during training or model selection):

| Model | Config | Test Accuracy | Test Macro-F1 | Test Fall Recall | Inference latency (CPU) | Params | Size |
|---|---|---|---|---|---|---|---|
| **CNN (deployed)** | filters=(32,64), k=5, dropout=0.3 | **85.1%** | **0.805** | **89.6%** | 0.123 ms/window | 11,813 | 52.9 KB |
| LSTM (comparison) | hidden=64, layers=2, dropout=0.4 | 81.6% | 0.755 | 87.5% | 2.111 ms/window | 52,037 | ~209 KB |

CNN per-class (test set, n=114: Walking=36, Running=6, Sitting=18, Lying=6, Fall=48):

| Class | Precision | Recall | F1 |
|---|---|---|---|
| Walking | 0.964 | 0.750 | 0.844 |
| Running | 0.714 | 0.833 | 0.769 |
| Sitting | 0.654 | 0.944 | 0.773 |
| Lying | 0.625 | 0.833 | 0.714 |
| Fall | 0.956 | 0.896 | 0.925 |

Confusion matrix (rows=true, cols=pred, order = Walking, Running, Sitting, Lying, Fall):

```
Walking  [27, 2, 6, 0, 1]
Running  [1, 5, 0, 0, 0]
Sitting  [0, 0, 17, 0, 1]
Lying    [0, 0, 1, 5, 0]
Fall     [0, 0, 2, 3, 43]
```

**Selection rationale:** CNN beats LSTM on every measured axis on this dataset -- higher accuracy, higher macro-F1, higher fall recall, ~17x faster inference, ~4.4x fewer parameters. The LSTM underperforms here primarily because the training set is small (547 base / 1641 augmented windows) and BITS-2 windows are whole resampled trials rather than long natural sequences, which favors the CNN's local-pattern inductive bias over the LSTM's need for more sequence data. Per sec 6.3's own priority rule, fall recall was weighted first in selection (CNN's 89.6% vs LSTM's 87.5%), with macro-F1 as tiebreaker -- CNN wins both, so the choice isn't a precision/recall tradeoff call, it's a clean win.

**Caveat on the numbers themselves:** the test set is only 114 windows from 6 subjects (Fall=48, Running=6, Lying=6) -- small enough that these percentages carry wide confidence intervals, especially for Running/Lying. Treat "85.1% accuracy" as "this model, on this specific 6-subject held-out set," not a general claim.

Full run log (all 10 configs' validation numbers) is in `models/training_results.json` (gitignored -- large/regeneratable; re-run `python -m ml.training.train` to reproduce).

## 7. Fall detection (two-stage, with a documented deviation from the original design)

1. **AI stage:** CNN outputs `P(Fall)` for a captured motion-event segment (sec 15).
2. **Rule verification stage:** peak acceleration magnitude vs. `ACCELERATION_THRESHOLD`, and post-event low-motion check vs. `POST_FALL_INACTIVITY_SECONDS`.

**Deviation, with evidence:** the original sketch was `AI FALL AND rule verification -> Confirmed Fall`. `ml/evaluation/threshold_analysis.py` measured that only 54% of real BITS-2 fall trials exceed the rule-based acceleration threshold (many real "falls" here, e.g. controlled falls onto a bed, never produce a big peak) -- requiring rule-AND-gating would roughly halve measured fall recall for no precision gain the data supports (the tuned AI threshold alone already hits precision=1.00 on validation). So `backend/services/decision_engine.py` confirms on **AI probability alone**; `motion_verified` and `post_fall_inactivity_detected` are still computed and attached to every alert for explainability/audit, not used to suppress a confirmed AI detection. This is a deliberate, recall-over-precision choice consistent with sec 6.3's stated priority -- see sec 16 for the real false-positive this produced during Phase 9 testing.

**Thresholds (real experiment, `ml/evaluation/threshold_analysis.py` -> `models/threshold_experiment.json`):**

| Threshold | Value | How derived |
|---|---|---|
| `FALL_PROBABILITY_THRESHOLD` | 0.466 | Precision-recall sweep on held-out validation set; highest-precision point with recall ≥ 0.90 -> precision=1.00, recall=0.917 |
| `ACCELERATION_THRESHOLD` | 45.94 m/s² | 95th percentile of peak acceleration magnitude across non-fall BITS-2 ADL trials. Only corroborates 54% of real fall trials (see above) -- logged, not gating. |
| `POST_FALL_INACTIVITY_SECONDS` | 1.5s | **Provisional, not experimentally derived.** BITS-2 trials are trimmed to ~1-3s around the event and don't contain a genuine multi-second post-fall settling period (measured within-trial low-motion run: mean 0.01s -- unusable). Literature-informed placeholder; must be re-validated against continuous Phase 2 recordings. |

This is not a clinical-grade fall detector -- see AUDIT.md sec 1.

## 8. Datasets & custom data collection

- **Public dataset: BITS-2** (Zenodo [10.5281/zenodo.10013090](https://doi.org/10.5281/zenodo.10013090), "Inertial Measurement and Heart-Rate sensor-based dataset for Geriatric fall detection using custom built wrist-worn device," BITS Pilani K.K. Birla Goa Campus). Selected because it was collected with an **MPU6500 (accel+gyro) + MAX30102 (HR/SpO2) wrist device -- the same sensor pair as this project's hardware** -- rather than a phone-based or different-sensor dataset. 41 subjects, 16 ADL types + 8 fall types, 5 trials/activity nominally, ~20 Hz motion sensor sampling, 1 Hz HR. Full adapter + mapping: `ml/datasets/bits2_adapter.py`.
  - **Structural mismatches vs. our fixed baseline, and how each was handled** (see that module's docstring for full detail): (1) ~20 Hz native rate vs. our 50 Hz target -> each trial resampled onto the fixed `WINDOW_LENGTH=150` grid, not merged at native rate. (2) Raw CSV timestamps are truncated to 3 significant figures (e.g. `"1.23E+12"`), unusable for sub-sample alignment -- accel/gyro rows aligned by acquisition order (row index) within each trial instead. (3) Each CSV is one short discrete trial, not a continuous stream -- trials are resampled to one canonical window each, not sliding-windowed (sec 15 covers what this means for real-time inference).
- **Custom ESP32 dataset:** not yet collected -- Phase 2 firmware (`firmware/esp32/src/logger_main.cpp`) is written and compiles against the real toolchain, but no physical hardware is available in this environment to record real trials or measure the BITS-2-vs-our-sensor domain gap. Treat the trained model's real-world transfer to our actual MPU6050/MAX30102 units as unverified until this happens.
- **Activities to collect (once hardware exists):** the excluded classes above all -- Standing, Tremor-like motion -- plus more Walking/Running/Fall examples on our own hardware to measure and correct any BITS-2-vs-our-sensor domain gap.
- **Fall data collection safety:** simulated/controlled fall-like events only (e.g. falling onto a mattress/mat, slow-motion simulated falls) -- exact protocol to be written before Phase 2 custom collection begins; not yet needed since no custom collection has happened.

## 9. Train / validation / test split

**Subject-wise split, actually used** (`ml/training/train.py::subject_wise_split`, seed=42, 70/15/15 by subject count over BITS-2's 41 subjects):

- Train (29 subjects): 1, 4, 5, 6, 7, 8, 10, 11, 12, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 36, 38, 39, 41
- Validation (6 subjects): 13, 15, 16, 18, 35, 40
- Test (6 subjects): 2, 3, 9, 14, 34, 37

No subject appears in more than one split; no BITS-2 recording (each trial file belongs to exactly one subject) crosses a split boundary. Sizes: train=547 windows, val=114, test=114 -- the split is small enough (6 test subjects) that per-class test metrics for the rarer classes (Running=6, Lying=6 test windows) should be read as indicative, not precise (sec 6.3 caveat).

## 10. Data pipeline & leakage prevention

Correct order (adapt only with documented justification):

```
Raw data → split subjects/recordings → fit preprocessing on training data only
→ apply to val/test → window segmentation → train → evaluate
```

Rules followed: no preprocessing statistic fit outside train (ChannelScaler fit on train only, `ml/training/train.py`); no BITS-2 subject appears in more than one split; thresholds (sec 7) were tuned on validation, never on test; subject-wise split used throughout (sec 9).

## 11. Backend (Flask)

Implemented (`backend/app.py`, `backend/routes/`, `backend/services/`, `backend/database/db.py`). Responsibilities: receive → validate → store raw → push through the live per-device event-segmentation buffer (sec 15) → run model → run decision engine → store prediction/alert → respond.

Final endpoint set (matches the original plan exactly):

```
POST /api/sensor-data   -- validate + ingest + inference + decision engine
GET  /api/latest         -- latest reading + prediction for a device
GET  /api/activity        -- latest activity/confidence/fall_probability
GET  /api/vitals          -- latest heart_rate/spo2
GET  /api/alerts          -- recent alerts (?device_id=&limit=)
GET  /api/history         -- recent rows from sensor_readings/predictions/alerts
GET  /api/health          -- liveness check
```

Payload validation (`backend/services/validation.py`) rejects, with a specific error message and HTTP 400: missing `device_id`, missing/wrong-typed `imu.*` fields, non-object bodies, and non-JSON bodies -- verified with real requests during Phase 5/9 testing (see sec 18).

## 12. ESP32 firmware

Written (`firmware/esp32/src/`) and **compiles successfully against the real ESP32 Arduino toolchain** (`pio run`, verified in this environment: 73.2% flash / 14.6% RAM for the live-streaming build, 22.7% flash / 6.7% RAM for the Phase 2 logger build). **Not run on physical hardware** -- no board is available in this environment, so Phase 1's actual exit criteria ("raw IMU and PPG values print reliably over serial") is not yet met. Two PlatformIO environments in one `platformio.ini`:

- `esp32dev` (`src/main.cpp`): the full pipeline below.
- `esp32dev_logger` (`src/logger_main.cpp`): Phase 2 CSV logger, IMU-only, no WiFi.

Firmware responsibilities, in order (all implemented in `main.cpp`):

1. Initialize MPU6050 (`sensors_init_imu`, `src/sensors.cpp`)
2. Initialize MAX30102 (`sensors_init_vitals`)
3. Initialize Wi-Fi (`connect_wifi`, blocking only in `setup()`)
4. Read sensors at configured intervals (`IMU_SAMPLE_RATE_HZ=50`, HR at 1 Hz) via non-blocking `millis()` timing in `loop()`
5. Attach timestamps (currently `millis()/1000.0` -- seconds since boot, not wall-clock; add NTP sync before a real demo if wall-clock alert timestamps matter)
6. Build a structured JSON payload (ArduinoJson, matches sec 13 schema)
7. Send data to Flask (`HTTPClient`, `BACKEND_URL` from `secrets.h`)
8. Receive response, check `"buzzer"` field
9. Trigger buzzer when instructed (3s sound; push button silences it early)
10. Handle network failures gracefully (non-blocking reconnect with backoff, `WIFI_RECONNECT_BACKOFF_MS`)
11. Continue local acquisition if the network is down (falls back to Serial-printing readings instead of blocking on a failed POST)

**Never commit Wi-Fi credentials:** real values go in `firmware/esp32/src/secrets.h`, gitignored; `secrets.h.example` is the committed template.

**SpO2 caveat:** `sensors.cpp::compute_spo2_estimate()` uses a simplified AC/DC ratio formula (`SpO2 = 110 - 25*R`), not the full Maxim reference lookup-table algorithm -- consistent with this project's "estimated, not clinical" framing (AUDIT.md sec 1).

## 13. Device → server payload format

Implemented as designed, no changes needed from the original sketch:

```json
{
  "device_id": "wearable_01",
  "timestamp": 1750000000,
  "imu": { "ax": 0.12, "ay": 0.45, "az": 0.98, "gx": 2.1, "gy": 1.3, "gz": 0.4 },
  "vitals": { "heart_rate": 78, "spo2": 97 }
}
```

`vitals` is optional; `imu.*` fields are required and type-checked (sec 11).

## 14. Database schema (SQLite, implemented as designed)

**sensor_readings**: `id, device_id, timestamp, ax, ay, az, gx, gy, gz, heart_rate, spo2`
**predictions**: `id, device_id, timestamp, activity, confidence, fall_probability, tremor_probability, model_name`
**alerts**: `id, device_id, timestamp, alert_type, severity, status, message`

Only addition vs. the original sketch: `device_id` on every table (needed once the API supports more than one device), plus indexes on `(device_id, timestamp)`. `tremor_probability` is always `NULL` in v1 (sec 5). See `backend/database/db.py`.

## 15. Real-time inference (redesigned from the original sketch, with evidence)

**What actually ships (`ml/segmentation/windowing.py::EventSegmentBuffer`, `ml/inference/realtime.py`):**

```
Continuous raw stream → onset detection (|accel_mag - 9.8| > 2.0 m/s^2 starts capture)
→ accumulate raw samples → offset detection (10 consecutive near-rest samples, or 200-sample cap)
→ resample captured segment to 150x6 (SAME function used at training time)
→ normalize (SAME ChannelScaler fit at training time) → CNN inference → decision engine → dashboard update
```

**Why this differs from the original "3s rolling window, 50% overlap" sketch:** BITS-2 training data is built from whole discrete trials resampled onto the fixed grid (sec 8), not fixed-duration slices of a continuous stream -- a naive fixed-length rolling window over the live stream would silently apply a *different transform* than the model was trained on, breaking PLAN.md's "identical preprocessing" rule. This was caught empirically, not by inspection: running `tests/fake_esp32_sender.py` with a naive `RollingBuffer` against a real fall trial produced `Lying` at 14% fall probability live, while the SAME trial evaluated offline (whole-trial resample) gave `Fall` at 80%+. Switching to event-triggered segmentation (calling the identical `ml.preprocessing.resample.resample_to_window` used in training) fixed the discrepancy -- re-verified in sec 18/19.

`sliding_windows()` / `RollingBuffer` are kept in the same module for a possible future model trained on genuinely continuous recordings (e.g. once Phase 2 custom data collection produces long streams), but are **not used by the v1 pipeline**.

A second consequence: **debouncing is per-event, not per-consecutive-window** (sec 17) -- there's no longer a stream of overlapping windows over the same physical event to require agreement across.

## 16. Dashboard

Implemented (`dashboard/index.html`, `dashboard/static/{style.css,app.js}`), served by Flask (`backend/app.py`). Cards: Heart Rate, SpO₂, Current Activity, Fall Status, Tremor Status ("Not available" -- sec 5). Charts (Chart.js via CDN): HR vs time, SpO₂ vs time, acceleration magnitude vs time, activity timeline. Per-class probability bars: only Fall-probability + winning-class-confidence are shown for **historical** data, because the `predictions` table (sec 14) stores only the winning class + its confidence + fall_probability, not the full 5-class vector for past windows -- a real constraint of the fixed schema, not an oversight (see `dashboard/static/app.js` comment). Alerts section and activity history poll `/api/alerts` and `/api/history` every 2s.

**Verification note:** headless-browser screenshot tooling was not available in this environment, so the dashboard was verified via direct HTTP checks instead -- confirmed `index.html`/`app.js`/`style.css` serve with 200 (initially 404 due to a Flask default-static-folder route conflict, fixed -- sec 18), and confirmed every API response shape the JS consumes matches what it expects, using real data produced by the Phase 9 e2e run. Not a substitute for an actual visual check; do one before a live demo.

## 17. Alert logic (debounce redesigned, with reasoning)

- Fall alert: fires on a single captured motion event when `fall_probability >= FALL_PROBABILITY_THRESHOLD` (sec 7) -- **not** N-consecutive-windows, because `EventSegmentBuffer` (sec 15) produces exactly one classification per physical motion event, not a stream of overlapping windows over the same event to require agreement across. `motion_verified` / `post_fall_inactivity_detected` are attached to the alert for explainability but don't gate it (sec 7).
- Once an alert is active for a device, a new critical alert isn't re-inserted until that device's AI stops flagging a fall candidate (`backend/services/live_state.py` alert-active tracking) -- a cooldown, not a debounce-by-repetition.
- Tremor alert: not implemented in v1 -- no trained tremor class (sec 5).

## 18. Testing strategy -- what was actually run

**Hardware tests:** not run -- no physical ESP32/MPU6050/MAX30102 available in this environment. Firmware instead verified by compiling against the real ESP32 toolchain (sec 12) -- catches API/syntax errors, not wiring/electrical issues.

**Backend tests (`tests/fake_esp32_sender.py`, `tests/e2e_demo.py`, manual curl):** valid payload accepted (201); missing `device_id` rejected (400, specific message); missing `imu.gz` rejected (400); wrong-typed field (`imu.ax: "x"`) rejected (400); non-JSON body rejected (400). Two real bugs were found and fixed this way, not by inspection: (1) `KeyError: 'tremor_probability'` -- the live prediction dict never set this key even though the route read it (fixed in `ml/inference/realtime.py`); (2) dashboard static assets 404'd because Flask's default static route (pointing at a nonexistent `backend/static/`) shadowed the custom one (fixed with `static_folder=None` in `backend/app.py`).

**ML tests:** class-wise precision/recall/F1/confusion matrix, subject-wise held-out test set, inference latency -- all real, see sec 6.3.

**System tests (end-to-end, `tests/e2e_demo.py`):** see sec 19 -- run against BITS-2 test-split subjects (2,3,9,14,34,37), genuinely unseen during training/validation.

## 19. Demonstration scenarios -- real results (`tests/e2e_demo.py`, held-out test subjects)

1. **Walking** (subject 2, "Walking Slowly") -- predicted Walking, confidence 89%, fall_probability 9%. PASS.
2. **Sitting** (subject 3, "Slowly sitting on chair") -- predicted Sitting, confidence 82%, fall_probability 5%. PASS.
3. **Running** (subject 9, "Jogging") -- predicted Running, confidence 100% on the steady-state segment. PASS, **but** see sec 16/21: an earlier short onset-transition segment in the same stream was misclassified as Fall at 52% confidence and fired a (real, measured) false alert -- documented in Known Limitations, not hidden.
4. **Safe simulated fall** (subject 14, "Forward Fall") -- predicted Fall, confidence 50%, `confirmed_fall=True`, `motion_verified=False` (this specific fall trial has a low acceleration peak -- consistent with the sec 7 finding that not all real falls in this dataset spike hard). Buzzer-trigger flag (`"buzzer": true`) returned to the caller. PASS.
5. **Tremor-like movement** -- **not run**. No tremor-labeled training data exists (sec 5); the dashboard correctly shows "Not available" rather than a fabricated result.

All 4 runnable scenarios pass on subjects the model never saw during training or threshold tuning.

## 20. Reporting metrics

See sec 6.3 for the full accuracy/precision/recall/F1/confusion-matrix table (CNN vs LSTM, held-out test set) and sec 7 for fall-specific sensitivity/threshold numbers. Inference latency and model size are in the same table. Every number above traces to an actual run (`ml/training/train.py`, `ml/evaluation/threshold_analysis.py`, `tests/e2e_demo.py`) -- see AUDIT.md sec 3.

## 21. Known limitations (real, discovered during implementation)

1. **No physical hardware validated.** Firmware compiles against the real toolchain (sec 12) but has never run on an actual ESP32/MPU6050/MAX30102/buzzer/button. Phase 1 exit criteria is open.
2. **Small dataset, small test set.** 775 total windows, 114 in the held-out test split, from only 6 test subjects (Running/Lying have just 6 test windows each). Reported percentages (sec 6.3) have wide confidence intervals; don't over-read small differences.
3. **Standing and Tremor are not trained classes.** BITS-2 has neither (sec 5). The dashboard reports Tremor as "Not available" rather than fabricating a value.
4. **Sensor domain gap unmeasured.** The model is trained entirely on BITS-2's MPU6500/MAX30102 device, not our actual MPU6050/MAX30102 wearable. These are different chips; real-world transfer has not been measured (would require Phase 2 custom data collection with real hardware).
5. **POST_FALL_INACTIVITY_SECONDS is not experimentally derived** (sec 7) -- BITS-2 trials are too short to measure genuine post-fall settling time. Literature-informed placeholder pending real continuous recordings.
6. **Rule-based acceleration verification only corroborates 54% of real fall trials** (sec 7) -- it's informative but was deliberately not used as a hard confirmation gate, which is why fall confirmation relies on the AI threshold alone.
7. **Real measured false positive on activity-transition onset** (sec 19, Running scenario): the automatic event-segmentation boundary occasionally captures a short, ambiguous burst right as a person starts moving (rather than a full trial-length recording like training data), and such short bursts can cross the fall-probability threshold (measured: 52% confidence, `motion_verified=False`). This is a direct consequence of the recall-over-precision priority (sec 6.3, sec 7) combined with event segmentation being algorithmic rather than human-curated like the training trials. Mitigation ideas for future work: collect enough labeled transition-onset examples (via Phase 2) to teach the model to distinguish them, or require a secondary corroborating signal specifically for borderline-probability detections -- not yet implemented because it would need proper re-validation against the full dataset, not an ad hoc threshold tweak.
8. **SpO2 is a simplified estimate**, not the clinical Maxim algorithm (sec 12).
9. **Battery/runtime budget** not yet measured -- no hardware.

## 22. Documentation maintenance checklist

Keep the following up to date here as each phase lands, not all at once at the end: architecture, hardware connections/pin configuration, sensor protocol, API design, database schema, dataset source, dataset preprocessing, segmentation method, labeling method, CNN architecture, LSTM architecture, training configuration, evaluation results, known limitations, testing results.
