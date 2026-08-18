# SmartHealth AI — Technical Documentation

Living document. Update each section as the corresponding phase (see [PLAN.md](PLAN.md)) is implemented — do not wait until the end to fill this in.

## 1. Architecture

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

## 2. Hardware

| Component | Role | Notes |
|---|---|---|
| ESP32 | MCU, Wi-Fi, orchestration | Reads both sensors, timestamps, posts JSON, drives buzzer |
| MPU6050 | 6-axis IMU (accel + gyro) | I2C, ~50 Hz sampling |
| MAX30102 | PPG (heart rate, SpO₂ estimate) | I2C, separate stream from IMU, not medical-grade |
| Buzzer | Local fall alert | Triggered by decision engine via ESP32 |
| Push button | Manual ack / test trigger | TBD exact use during Phase 1 |
| Battery + charging circuit | Power | TBD capacity/runtime budget |

**Pin configuration:** to be documented here once firmware wiring is finalized in Phase 1.

## 3. Sensor data & configuration

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
Window 1: 0.0–3.0s   Window 2: 1.5–4.5s   Window 3: 3.0–6.0s ...
```
This segmentation logic must be shared code between training and real-time inference — not reimplemented twice.

HR/SpO₂ are a separate, lower-rate stream, synchronized to IMU windows by timestamp — not resampled into the 50Hz IMU stream.

## 4. Labels and classes

Activity classes: `Walking, Standing, Sitting, Running, Lying, Fall, Tremor` (adjust to match the chosen public dataset's label set; document the dataset→app label mapping here once selected).

- **Ordinary activities:** majority-label per window (e.g. 60% Walking / 40% Standing → Walking).
- **Fall:** event-centered labeling, not majority-label — a window containing a meaningful fall event must not be relabeled as a normal activity just because most of the window is pre/post-fall movement. Document the exact rule used once implemented.
- **Tremor:** treated as a repetitive temporal pattern learned by the model, not a simple acceleration threshold. Classes: `Normal movement`, `Tremor-like movement` (do not add "mild/strong" sub-classes until the baseline works). Never label or report as "Parkinson's disease" — only "tremor-like movement pattern."

## 5. Models

### 5.1 Primary — 1D CNN
Input: `150 × 6`. Baseline block: `Conv1D → BatchNorm → ReLU → MaxPool → Conv1D → BatchNorm → ReLU → MaxPool → GlobalPool/Flatten → Dense → Dropout → Softmax`. Filter counts, kernel sizes, and depth are tuned experimentally — the first architecture is a baseline, not a claimed optimum. Output: per-class probabilities across the 7 classes.

### 5.2 Comparison — LSTM
Same segmented input, used purely for sequence-learning comparison against the CNN.

### 5.3 Model selection experiment
Compare CNN vs. LSTM, optionally across window sizes (2s / 3s / 5s), on: accuracy, precision, recall, F1, inference time, model size. For fall detection specifically, weight **fall recall and false negatives** — a model is not acceptable just because overall accuracy is high if fall recall is poor. Record actual results in a table here once run; never fabricate values.

## 6. Fall detection (two-stage)

1. **AI stage:** model outputs `P(Fall)`.
2. **Rule verification stage:** sudden acceleration + abnormal angular velocity + post-fall inactivity.

```
AI predicts FALL + sudden motion pattern + post-fall inactivity → Confirmed Fall Event
```

Thresholds (`FALL_PROBABILITY_THRESHOLD`, `POST_FALL_INACTIVITY_SECONDS`, `ACCELERATION_THRESHOLD`) must be set from experiments on collected data, not guessed, and recorded here with the experiment that produced them. This is not a clinical-grade fall detector.

## 7. Data pipeline & leakage prevention

Correct order (adapt only with documented justification):

```
Raw data → split subjects/recordings → fit preprocessing on training data only
→ apply to val/test → window segmentation → train → evaluate
```

Rules:
- Never normalize using the full dataset before splitting.
- Never let the same recording appear in both train and test.
- Never create overlapping windows across the train/test boundary.
- Never tune thresholds on the final test set.
- Prefer subject-wise splits (train/val/test subjects disjoint). If the dataset can't support this, document the limitation explicitly here.

## 8. Datasets

- **Public dataset(s):** selection pending — chosen based on availability, labels, sensor type, sampling rate, activity classes, fall examples, and structural compatibility with our `150×6` input. If structure doesn't match, build an explicit adaptation layer rather than force-merging.
- **Custom ESP32 dataset:** collected from our own hardware for validation, domain-mismatch measurement, and hardware-to-AI integration demonstration. Do not assume a model trained purely on the public dataset transfers perfectly — measure the gap.
- **Fall data collection safety:** simulated/controlled fall-like events only. Never require intentional falls onto hard surfaces.

## 9. Backend (Flask)

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

Never trust a sensor payload blindly — validate required fields/types before use.

## 10. Device → server payload format

JSON, versioned if the schema needs to change later:

```json
{
  "device_id": "wearable_01",
  "timestamp": 1750000000,
  "imu": { "ax": 0.12, "ay": 0.45, "az": 0.98, "gx": 2.1, "gy": 1.3, "gz": 0.4 },
  "vitals": { "heart_rate": 78, "spo2": 97 }
}
```

## 11. Database schema (SQLite, initial)

**sensor_readings**: `id, timestamp, ax, ay, az, gx, gy, gz, heart_rate, spo2`
**predictions**: `id, timestamp, activity, confidence, fall_probability, tremor_probability, model_name`
**alerts**: `id, timestamp, alert_type, severity, status, message`

Keep normalized and simple; document schema changes here as they happen.

## 12. Real-time inference

```
Continuous stream → rolling buffer → latest 3s window (once full) → preprocess (identical to training)
→ CNN inference → prediction → decision engine → dashboard update
```

At 50% overlap and a 3s window, a new inference is available roughly every 1.5s. Interval is configurable.

## 13. Dashboard

Cards: Heart Rate, SpO₂, Current Activity, Fall Status, Tremor Status. Graphs: HR vs time, SpO₂ vs time, acceleration vs time, angular velocity vs time, activity timeline. Alert section shows active alerts or "No active alerts." History section: activity/vitals/alerts.

## 14. Alert logic

- Fall alert: only on a *confirmed* fall event (AI + rule verification), not a single noisy prediction.
- Tremor alert: on sustained tremor-like probability.
- Debouncing: require N consecutive abnormal inference windows before alerting; N determined experimentally, documented here once set.

## 15. Demonstration scenarios

1. **Walking** — Activity: Walking, confidence ~94%, HR/SpO₂ shown, no fall/tremor.
2. **Sitting** — Activity: Sitting, high confidence.
3. **Tremor-like movement** — tremor notification shown.
4. **Safe simulated fall** — fall probability high → motion verification passed → post-fall inactivity detected → confirmed fall → buzzer + dashboard alert.

## 16. Known limitations

To be filled in as they're discovered during implementation (dataset domain mismatch, threshold sensitivity, sensor noise, etc.) — do not leave this section empty at submission time.
