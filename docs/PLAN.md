# SmartHealth AI — Project Plan

## 1. Objective

Develop a low-cost AI-powered wearable system that uses inertial sensor data and physiological signals to perform human activity recognition, fall detection, tremor-like movement detection, and heart-rate/estimated-SpO₂ monitoring, with real-time visualization and alerts through a web dashboard.

Primary academic component: **deep learning on time-series healthcare sensor data** (1D CNN, compared against LSTM) — not image-based object detection.

## 2. Team constraints

- 2-member student team, limited budget.
- Hardware fixed to: ESP32, MPU6050, MAX30102, buzzer, push button, rechargeable battery.
- No scope creep into certified/medical-grade hardware or claims (see [AUDIT.md](AUDIT.md)).

## 3. Fixed baseline architecture

See [DOCUMENTATION.md](DOCUMENTATION.md) for full architecture, data flow, model, API, and schema detail. Any change to the baseline must be evaluated against it, not added casually.

Key fixed parameters (must stay centrally configured, never hard-coded inline):

| Config key                    | Initial value |
|--------------------------------|---------------|
| `IMU_SAMPLE_RATE`              | 50 Hz         |
| `WINDOW_SIZE_SECONDS`          | 3 s           |
| `WINDOW_OVERLAP`                | 50%           |
| `FALL_PROBABILITY_THRESHOLD`   | TBD (validate experimentally) |
| `POST_FALL_INACTIVITY_SECONDS`| TBD (validate experimentally) |
| `ACCELERATION_THRESHOLD`       | TBD (validate experimentally) |

Model input shape: `150 × 6` (150 timesteps × [Ax, Ay, Az, Gx, Gy, Gz]).

## 4. Development phases

Build strictly in this order. Do not parallelize phases that depend on each other's output.

### Phase 1 — Hardware validation
Verify ESP32, MPU6050, MAX30102 independently; print raw values.
**Exit criteria:** raw IMU and PPG values print reliably over serial.

### Phase 2 — Data collection (logger)
Build a clean IMU data logger: `timestamp, Ax, Ay, Az, Gx, Gy, Gz, label`.
**Exit criteria:** logger produces labeled CSV files for each activity class.

### Phase 3 — Offline ML (1D CNN baseline)
Preprocessing → sliding-window segmentation → dataset loader → 1D CNN → evaluation.
**Exit criteria:** trained CNN with documented accuracy/precision/recall/F1/confusion matrix on a held-out (subject-wise) test split.

### Phase 4 — LSTM comparison
Train LSTM on the same segmented data; compare against CNN (see Model Selection Experiment in DOCUMENTATION.md).
**Exit criteria:** comparison table (accuracy, precision, recall, F1, inference time, model size) across window sizes; documented model choice with rationale, weighted toward fall recall over raw accuracy.

### Phase 5 — ESP32 → Flask transmission
Implement the JSON payload contract and REST endpoint; validate on the wire.
**Exit criteria:** ESP32 reliably posts timestamped sensor data to Flask; malformed/missing-field payloads are rejected, not silently accepted.

### Phase 6 — Real-time AI inference
Rolling buffer → windowed inference → prediction, using preprocessing identical to training.
**Exit criteria:** live predictions update at the configured inference interval (~1.5s at 50% overlap) with correct label mapping.

### Phase 7 — Dashboard
Activity, HR, SpO₂, fall/tremor status, graphs, alert and activity history.
**Exit criteria:** dashboard reflects live backend state without manual refresh.

### Phase 8 — Fall decision engine
Combine AI fall probability + motion verification + post-fall inactivity into a confirmed fall event; add debouncing for tremor/activity flicker.
**Exit criteria:** simulated fall (safe) triggers buzzer + dashboard alert; thresholds documented with the experiment that produced them.

### Phase 9 — End-to-end testing
Full pipeline test: wearable → ESP32 → Flask → AI → dashboard → alert, across all demo scenarios in DOCUMENTATION.md §Demonstration Scenarios.
**Exit criteria:** all scenarios in the success criteria checklist (AUDIT.md §Success Criteria) pass.

## 5. Out of scope for the core build (optional future extensions)

Do not implement until the core system (Phases 1–9) is stable and demoed:

- BLE instead of Wi-Fi
- Mobile application
- Cloud deployment
- SMS/email notification
- GPS
- TinyML / on-device inference
- Personalized activity model
- Additional sensors

## 6. Engineering rules for every phase

1. Understand existing structure and reuse working code before rewriting.
2. Keep ML preprocessing byte-for-byte identical between training and real-time inference.
3. No data leakage: split subjects/recordings before fitting any preprocessing statistic (see DOCUMENTATION.md §Data Leakage Prevention).
4. Never fabricate hardware readings or ML metrics — every number in a report must come from an actual run.
5. All thresholds and rates are configuration, not literals scattered through code.
6. Keep hardware code, backend logic, training code, and inference code in separate layers.
7. Use "monitoring / detection / classification / prototype" language — never "diagnosis" or "clinical" claims.

## 7. Current phase

**Phase 1 — Hardware validation** (not started). Update this section as phases complete.
