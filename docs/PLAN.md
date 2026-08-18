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
| `FALL_PROBABILITY_THRESHOLD`   | 0.466 (validated, see DOCUMENTATION.md sec 7) |
| `POST_FALL_INACTIVITY_SECONDS`| 1.5s (provisional -- not fully derivable from BITS-2's short trials, see DOCUMENTATION.md sec 7/16) |
| `ACCELERATION_THRESHOLD`       | 45.94 m/s² (validated, see DOCUMENTATION.md sec 7) |

Model input shape: `150 × 6` (150 timesteps × [Ax, Ay, Az, Gx, Gy, Gz]).

## 4. Development phases

Build strictly in this order. Do not parallelize phases that depend on each other's output.

### Phase 1 — Hardware validation — CODE COMPLETE, HARDWARE-UNVERIFIED
Verify ESP32, MPU6050, MAX30102 independently; print raw values.
**Exit criteria:** raw IMU and PPG values print reliably over serial. **NOT MET** -- no physical ESP32/MPU6050/MAX30102 available in this environment. Firmware (`firmware/esp32/src/main.cpp`, `sensors.cpp`) is written and **compiles successfully against the real ESP32 toolchain** (`pio run`, verified), but has never run on a board. See docs/DOCUMENTATION.md sec 12.

### Phase 2 — Data collection (logger) — CODE COMPLETE, HARDWARE-UNVERIFIED
Build a clean IMU data logger: `timestamp, Ax, Ay, Az, Gx, Gy, Gz, label`.
**Exit criteria:** logger produces labeled CSV files for each activity class. **NOT MET** (same hardware gap as Phase 1). Logger firmware (`firmware/esp32/src/logger_main.cpp`, PlatformIO env `esp32dev_logger`) compiles against the real toolchain; the training dataset itself (Phase 3) uses the public BITS-2 dataset instead of custom-collected data, since no hardware exists to collect from yet.

### Phase 3 — Offline ML (1D CNN baseline) — DONE
Preprocessing → sliding-window segmentation → dataset loader → 1D CNN → evaluation.
**Exit criteria:** trained CNN with documented accuracy/precision/recall/F1/confusion matrix on a held-out (subject-wise) test split. **MET.** Trained on BITS-2 (5 classes: Walking, Running, Sitting, Lying, Fall -- Standing/Tremor excluded, see DOCUMENTATION.md sec 5). Test accuracy 85.1%, macro-F1 0.805, fall recall 89.6%. See DOCUMENTATION.md sec 6.3.

### Phase 4 — LSTM comparison — DONE
Train LSTM on the same segmented data; compare against CNN (see Model Selection Experiment in DOCUMENTATION.md).
**Exit criteria:** comparison table (accuracy, precision, recall, F1, inference time, model size); documented model choice with rationale, weighted toward fall recall over raw accuracy. **MET.** CNN selected -- beats LSTM on every measured axis (accuracy, macro-F1, fall recall, latency, size) on this dataset. Full table: DOCUMENTATION.md sec 6.3.

### Phase 5 — ESP32 → Flask transmission — DONE (backend), CODE COMPLETE (firmware, hardware-unverified)
Implement the JSON payload contract and REST endpoint; validate on the wire.
**Exit criteria:** ESP32 reliably posts timestamped sensor data to Flask; malformed/missing-field payloads are rejected, not silently accepted. **MET for the backend + payload contract** -- tested with real requests (missing fields, wrong types, non-JSON bodies all correctly rejected with 400; valid payloads processed end-to-end). The ESP32 side of the wire is simulated (`tests/fake_esp32_sender.py`) since no hardware exists to send from yet.

### Phase 6 — Real-time AI inference — DONE (redesigned)
Rolling buffer → windowed inference → prediction, using preprocessing identical to training.
**Exit criteria:** live predictions update with correct label mapping, using preprocessing identical to training. **MET, but the mechanism changed**: a naive fixed-duration rolling window was replaced with event-triggered segmentation (`ml/segmentation/windowing.py::EventSegmentBuffer`) after live testing showed it silently used a different transform than training. See docs/DOCUMENTATION.md sec 15 for why and the concrete before/after evidence.

### Phase 7 — Dashboard — DONE
Activity, HR, SpO₂, fall/tremor status, graphs, alert and activity history.
**Exit criteria:** dashboard reflects live backend state without manual refresh. **MET** (2s polling). Visual browser verification wasn't available in this environment -- verified via direct HTTP checks of assets and API response shapes instead; do a real visual check before a live demo. See DOCUMENTATION.md sec 16.

### Phase 8 — Fall decision engine — DONE
Combine AI fall probability + motion verification + post-fall inactivity into a confirmed fall event; add debouncing for tremor/activity flicker.
**Exit criteria:** simulated fall (safe) triggers buzzer + dashboard alert; thresholds documented with the experiment that produced them. **MET**, with one documented deviation: confirmation gates on AI probability alone rather than AI-AND-rule-verification, because measured data showed rule-gating would nearly halve fall recall for no supported precision gain. See DOCUMENTATION.md sec 7.

### Phase 9 — End-to-end testing — DONE (3 of 4 scenarios; tremor not applicable)
Full pipeline test: wearable → ESP32 → Flask → AI → dashboard → alert, across all demo scenarios in DOCUMENTATION.md §Demonstration Scenarios.
**Exit criteria:** all scenarios in the success criteria checklist (AUDIT.md §Success Criteria) pass. **Walking/Sitting/Running/Fall scenarios pass on genuinely held-out test subjects** (`tests/e2e_demo.py`); Tremor scenario not applicable (no trained tremor class). A real false-positive was found and documented (not silently fixed) during this testing -- see DOCUMENTATION.md sec 19/21 item 7.

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

**All 9 phases have code-complete implementations** (2026-08-19). Phases 3, 4, 5 (backend), 6, 7, 8, and 9 (non-hardware scenarios) are done and verified by real test runs (see per-phase notes in sec 4 and docs/DOCUMENTATION.md). Phases 1, 2, and the ESP32 side of Phase 5 are **code-complete but hardware-unverified** -- firmware compiles against the real ESP32 toolchain but has never been flashed to a physical board, since no ESP32/MPU6050/MAX30102/buzzer/button hardware is available in this environment. That remains the single blocking item before a live hardware demo; everything software-side is ready for it. See docs/AUDIT.md for the full checked-item audit.
