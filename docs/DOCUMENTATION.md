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

**Pin configuration:** to be documented here once firmware wiring is finalized in Phase 1.

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

Activity classes: `Walking, Standing, Sitting, Running, Lying, Fall, Tremor` (adjust to match the chosen public dataset's label set; document the dataset→app label mapping here once selected).

- **Ordinary activities:** majority-label per window (e.g. 60% Walking / 40% Standing → Walking).
- **Fall:** event-centered labeling, not majority-label — a window containing a meaningful fall event must not be relabeled as a normal activity just because most of the window is pre/post-fall movement. Document the exact rule used once implemented. Do not silently mix the majority-label and event-centered strategies.
- **Tremor:** treated as a repetitive temporal pattern learned by the model over the window, not a simple acceleration threshold. Classes: `Normal movement`, `Tremor-like movement` (an optional future split into `Mild` / `Strong` tremor-like movement may be added later, but not until the baseline works). Never label, log, or report as "Parkinson's disease" — only "tremor-like movement pattern." This wording matters for scientific accuracy, not just UI copy.

## 6. Models

### 6.1 Primary — 1D CNN
Input: `150 × 6`. Baseline block: `Conv1D → BatchNorm → ReLU → MaxPool → Conv1D → BatchNorm → ReLU → MaxPool → GlobalPool/Flatten → Dense → Dropout → Softmax`. Filter counts, kernel sizes, and depth are tuned experimentally — the first architecture is a baseline, not a claimed optimum. Output: per-class probabilities across the 7 classes, e.g.:

```
Walking: 0.94   Standing: 0.02   Sitting: 0.01
Running: 0.01   Lying: 0.00      Fall: 0.01   Tremor: 0.01
```

### 6.2 Comparison — LSTM
Same segmented input, used purely for sequence-learning comparison against the CNN.

### 6.3 Model selection experiment
Compare CNN vs. LSTM, optionally across window sizes (2s / 3s / 5s), recording for each run:

```
Accuracy   Precision   Recall   F1-score   Inference time   Model size
```

Example result table shape (fill with real numbers once run — never fabricate):

```
Model   Window   Accuracy   Precision   Recall   F1
CNN     2 sec    ...
CNN     3 sec    ...
CNN     5 sec    ...
LSTM    2 sec    ...
LSTM    3 sec    ...
LSTM    5 sec    ...
```

For fall detection specifically, weight **fall recall and false negatives** over raw accuracy — a model is not acceptable just because overall accuracy is high if fall recall is poor. The final deployed model is selected from these measured results, with the rationale recorded here.

## 7. Fall detection (two-stage)

1. **AI stage:** model outputs `P(Fall)`.
2. **Rule verification stage:** sudden acceleration + abnormal angular velocity + post-fall inactivity.

```
AI predicts FALL + sudden motion pattern + post-fall inactivity → Confirmed Fall Event
```

Thresholds (`FALL_PROBABILITY_THRESHOLD`, `POST_FALL_INACTIVITY_SECONDS`, `ACCELERATION_THRESHOLD`) must be set from experiments on collected data, not guessed, and recorded here with the experiment that produced them. This is not a clinical-grade fall detector — do not present it as one.

## 8. Datasets & custom data collection

- **Public dataset(s):** selection pending — chosen based on availability, labels, sensor type, sampling rate, activity classes, fall examples, and structural compatibility with our `150×6` input. If structure doesn't match, build an explicit adaptation layer rather than force-merging incompatible datasets.
- **Custom ESP32 dataset:** collected from our own hardware, used for testing, validating real-world behavior, demonstrating hardware-to-AI integration, and identifying domain mismatch between the public dataset and our sensor. Do not assume a model trained purely on the public dataset transfers perfectly — measure the gap.
- **Activities to collect:** Walking, Standing, Sitting, Running, Lying, Tremor-like motion, Fall-like events.
- **Fall data collection safety:** simulated/controlled fall-like events only. Never require anyone to intentionally fall onto hard surfaces — safety takes priority over data realism. Document the exact safe protocol used (e.g. falling onto a mattress/mat, slow-motion simulated falls) once designed.

## 9. Train / validation / test split

Prefer **subject-wise** splitting: training subjects, validation subjects, and testing subjects are disjoint, with the test subject never seen during training. If the chosen dataset doesn't support this (e.g. too few subjects), document the limitation explicitly here rather than silently random-splitting.

Random splitting of highly overlapping sliding windows from the same person across train and test is not acceptable — it leaks information and produces unrealistically optimistic evaluation results (see §10).

## 10. Data pipeline & leakage prevention

Correct order (adapt only with documented justification):

```
Raw data → split subjects/recordings → fit preprocessing on training data only
→ apply to val/test → window segmentation → train → evaluate
```

Rules:
- Never normalize/scale using statistics from the full dataset before splitting.
- Never let the same recording appear in both train and test.
- Never create overlapping windows that straddle the train/test boundary.
- Never tune thresholds (fall, tremor, or otherwise) on the final test set.
- Prefer subject-wise splits (§9). If the dataset can't support this, document the limitation explicitly here.

## 11. Backend (Flask)

Responsibilities: receive → validate → store raw → preprocess → build inference window → run model → run decision engine → store prediction → respond.

Planned endpoints (adjust during implementation, document actual final set here):

```
POST /api/sensor-data
GET  /api/latest
GET  /api/activity
GET  /api/vitals
GET  /api/alerts
GET  /api/history
GET  /api/health
```

Never trust a sensor payload blindly — validate required fields/types before use, and return clear errors on malformed/missing data rather than silently accepting it.

## 12. ESP32 firmware

Firmware responsibilities, in order:

1. Initialize MPU6050
2. Initialize MAX30102
3. Initialize Wi-Fi
4. Read sensors at configured intervals
5. Attach timestamps
6. Build a structured JSON payload
7. Send data to Flask
8. Receive response where needed
9. Trigger buzzer when instructed by the backend/decision engine
10. Handle network failures gracefully
11. Continue local acquisition as much as possible if the network temporarily fails

Design notes:
- Avoid blocking code wherever practical (non-blocking sensor reads / network calls) so sampling stays close to the configured rate.
- Configurable constants (not hard-coded literals): Wi-Fi credentials, backend URL, sampling frequency, send interval, device ID.
- **Never commit Wi-Fi credentials or other secrets into source that gets pushed to the repo** — use a local, gitignored config/secrets file for firmware credentials.

## 13. Device → server payload format

JSON, versioned if the schema needs to change later. This example is illustrative, not final — finalize and document the real schema during Phase 5:

```json
{
  "device_id": "wearable_01",
  "timestamp": 1750000000,
  "imu": { "ax": 0.12, "ay": 0.45, "az": 0.98, "gx": 2.1, "gy": 1.3, "gz": 0.4 },
  "vitals": { "heart_rate": 78, "spo2": 97 }
}
```

## 14. Database schema (SQLite, initial)

**sensor_readings**: `id, timestamp, ax, ay, az, gx, gy, gz, heart_rate, spo2`
**predictions**: `id, timestamp, activity, confidence, fall_probability, tremor_probability, model_name`
**alerts**: `id, timestamp, alert_type, severity, status, message`

Keep normalized and simple; document schema changes here as they happen. Move to MySQL only if a concrete requirement emerges — don't add complexity speculatively.

## 15. Real-time inference

```
Continuous stream → rolling buffer → latest 3s window (once full) → preprocess (identical to training)
→ CNN inference → prediction → decision engine → dashboard update
```

At 50% overlap and a 3s window, a new inference is available roughly every 1.5s. Interval is configurable. Keep this inference code path separate from training code — same preprocessing logic, different entry point.

## 16. Dashboard

Cards: Heart Rate, SpO₂, Current Activity, Fall Status, Tremor Status.
Graphs: HR vs time, SpO₂ vs time, acceleration vs time, angular velocity vs time, activity timeline.
AI display: per-class probability breakdown (e.g. `Walking 94%, Standing 2%, Sitting 1%, Fall 2%, Tremor 1%`).
Alerts section: `No active alerts`, or e.g. `FALL DETECTED — Time: 09:15:32 — Confidence: 91%`.
History section: activity history, vital history, alert history.

## 17. Alert logic

- Fall alert: only on a *confirmed* fall event (AI + rule verification), not a single noisy prediction.
- Tremor alert: on sustained tremor-like probability, not a single window.
- Debouncing: require the prediction to remain abnormal for N consecutive inference windows before alerting, to reduce transient false positives. N is a configurable value, determined experimentally and documented here once set — not invented arbitrarily.

## 18. Testing strategy

Test each layer individually before end-to-end testing.

**Hardware tests:** MPU6050 readings, MAX30102 readings, Wi-Fi reliability, buzzer, button.

**Backend tests:** valid payload, invalid payload, missing fields, network interruption, database failure.

**ML tests:** class-wise precision, class-wise recall, confusion matrix, unseen-subject testing, inference latency.

**System tests (end-to-end):** `Wearable → ESP32 → Flask → AI → Dashboard → Alert`, across multiple complete scenarios (see §19).

## 19. Demonstration scenarios

1. **Walking** — Activity: Walking, confidence ~94%, HR/SpO₂ shown, no fall/tremor.
2. **Sitting** — Activity: Sitting, high confidence (~96%).
3. **Tremor-like movement** — tremor-like movement notification shown.
4. **Safe simulated fall** — fall probability ~91% → motion verification passed → post-fall inactivity detected → confirmed fall → buzzer + dashboard alert.

## 20. Reporting metrics

The final report must include, for the selected model: Accuracy, Precision, Recall, F1-score, Confusion Matrix. For fall detection specifically, additionally: Sensitivity/Recall, False Positive Rate, False Negative Count. Also record inference latency and model size where practical. Every number must come from an actual experiment — never generate fictional values (see AUDIT.md §3).

## 21. Known limitations

To be filled in as they're discovered during implementation (dataset domain mismatch, threshold sensitivity, sensor noise, battery/runtime constraints, etc.) — do not leave this section empty at submission time.

## 22. Documentation maintenance checklist

Keep the following up to date here as each phase lands, not all at once at the end: architecture, hardware connections/pin configuration, sensor protocol, API design, database schema, dataset source, dataset preprocessing, segmentation method, labeling method, CNN architecture, LSTM architecture, training configuration, evaluation results, known limitations, testing results.
