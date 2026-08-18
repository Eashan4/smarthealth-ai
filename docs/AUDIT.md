# SmartHealth AI — Audit Checklist

Purpose: a living checklist to audit the project against its own stated scope limits, engineering rules, and success criteria. Review and update this file at the end of every phase (see [PLAN.md](PLAN.md)) — do not treat it as a one-time document.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done/verified

## 1. Scope limits (must never be violated)

This project is monitoring/detection/classification only. It must never claim to:

- [x] Diagnose diseases -- not claimed anywhere in README/dashboard/docs
- [x] Replace doctors or provide clinical decisions -- not claimed
- [x] Provide clinically certified SpO₂ measurements -- firmware explicitly documents its SpO2 as a simplified estimate, not the clinical algorithm (docs/DOCUMENTATION.md sec 12)
- [x] Provide clinically certified fall detection -- explicitly documented as not clinical-grade (docs/DOCUMENTATION.md sec 7)
- [x] Detect Parkinson's disease specifically -- N/A, no tremor detection is trained at all in v1 (docs/DOCUMENTATION.md sec 5)
- [x] Provide medication recommendations -- not present anywhere
- [x] Measure blood pressure -- not present anywhere
- [x] Claim any form of medical certification -- not claimed

**Audit action (run 2026-08-19):** `grep -rniE "diagnos|certifi|clinical|parkinson|medical device" README.md dashboard/ backend/ ml/ firmware/esp32/src/` -- every hit is the intended honest-framing disclaimer (README.md:5, dashboard/index.html:13, firmware/esp32/src/sensors.cpp:23); no violations found. Re-run this grep before each submission/demo, since new copy could reintroduce a violation.

## 2. Data integrity rules

- [x] No preprocessing statistic (mean/std/scaler) is fit on data outside the training split -- `ChannelScaler` fit on `X_train` only (`ml/training/train.py`)
- [x] No recording appears in both train and test sets -- subject-wise split, BITS-2 subjects are disjoint per split (39 subjects into 29/6/6, listed in DOCUMENTATION.md sec 9)
- [x] No sliding window straddles a train/test split boundary -- N/A in the literal sliding-window sense (each BITS-2 trial belongs to exactly one subject/split, no cross-trial windows are formed for training); the live event-segmentation path (Phase 6) operates only at inference time, not on train/test data
- [~] Thresholds (`FALL_PROBABILITY_THRESHOLD`, `ACCELERATION_THRESHOLD`, `POST_FALL_INACTIVITY_SECONDS`) were set from an experiment, not guessed, and the experiment is documented in DOCUMENTATION.md §7 -- **2 of 3 are**; `POST_FALL_INACTIVITY_SECONDS` could not be experimentally derived from BITS-2's short trials and is an explicitly-flagged literature-informed placeholder (DOCUMENTATION.md sec 7/16 item 5), not silently presented as measured
- [x] Train/val/test split is subject-wise where the dataset allows it; if not, the limitation is documented -- subject-wise, all 41 BITS-2 subjects used
- [x] Fall-event windows use the event-centered labeling rule, not majority-label (DOCUMENTATION.md §5) -- every fall-type trial is Fall in full; N/A majority-vote concern since trials are single-activity by construction

## 3. Reporting integrity

- [x] Every metric (accuracy, precision, recall, F1, confusion matrix, inference latency, model size) in the final report traces to an actual logged experiment run -- `ml/training/train.py`, `ml/evaluation/threshold_analysis.py`, `tests/e2e_demo.py` output, recorded in DOCUMENTATION.md sec 6.3/7/19
- [x] No fabricated or placeholder numbers remain in the final report -- the one placeholder value (`POST_FALL_INACTIVITY_SECONDS`) is explicitly labeled PROVISIONAL everywhere it appears, not presented as measured
- [x] Final model choice is justified by measured results (esp. fall recall), not accuracy alone -- CNN beats LSTM on fall recall (89.6% vs 87.5%) and every other axis, DOCUMENTATION.md sec 6.3
- [x] Known limitations section (DOCUMENTATION.md §21) is filled in, not left as a stub -- 9 concrete, evidence-backed items

## 4. Engineering discipline

- [x] Sampling rate, window size, overlap, and all thresholds are defined in one central config, not scattered as literals -- `ml/config.py` (Python side), `firmware/esp32/src/config.h` (firmware side)
- [x] Preprocessing code path is shared (not duplicated) between training and real-time inference -- `ml/preprocessing/resample.py::resample_to_window` and `ml/preprocessing/normalize.py::ChannelScaler` are both imported by training (`ml/datasets/bits2_adapter.py`) and live inference (`ml/segmentation/windowing.py`, `ml/inference/realtime.py`); this exact gap was caught and fixed once already during Phase 9 testing (see DOCUMENTATION.md sec 15)
- [x] Hardware/firmware code, backend logic, training code, and inference code are kept in separate layers/directories -- `firmware/`, `backend/`, `ml/training+ml/datasets`, `ml/inference` respectively
- [x] No Wi-Fi credentials or secrets are committed to the repository -- `firmware/esp32/src/secrets.h` is gitignored; only `secrets.h.example` (placeholder values) is committed
- [x] Sensor payloads are validated (type/required fields) before use, not trusted blindly -- `backend/services/validation.py`, tested with real malformed requests (DOCUMENTATION.md sec 18)

## 5. Safety

- [ ] Fall data collection used safe simulated/controlled events only -- N/A to this project's own work yet: v1 training uses the pre-existing third-party BITS-2 dataset, whose own collection protocol (controlled/simulated falls by consenting volunteers) is documented in its published paper, not something this project performed. No custom fall data has been collected here.
- [ ] Custom data collection protocol (per activity class) is documented before collection begins -- not yet needed; will be required before any Phase 2 custom collection using real hardware

## 6. Success criteria (from project spec §38)

- [ ] ESP32 collects real MPU6050 data -- code complete (`sensors_read_imu`), hardware-unverified (no board)
- [ ] ESP32 collects real MAX30102 readings -- code complete (`sensors_read_vitals`), hardware-unverified
- [ ] ESP32 transmits timestamped data over Wi-Fi -- code complete (`main.cpp`), hardware-unverified; wire protocol itself verified via simulated sender (`tests/fake_esp32_sender.py`)
- [x] Backend receives and validates incoming payloads -- tested with real requests, DOCUMENTATION.md sec 18
- [x] IMU data is segmented into sliding windows (train + inference share logic) -- via `EventSegmentBuffer` + shared `resample_to_window` (redesigned from a naive rolling window after a real train/inference mismatch was caught, see DOCUMENTATION.md sec 15)
- [x] 1D CNN performs real-time activity classification -- verified end-to-end, `tests/e2e_demo.py`
- [x] LSTM is trained for comparison -- DOCUMENTATION.md sec 6.3
- [x] Model performance is evaluated with accuracy/precision/recall/F1/confusion matrix, subject-wise -- DOCUMENTATION.md sec 6.3
- [x] Fall detection combines AI prediction + rule-based verification -- `backend/services/decision_engine.py`, with a documented, evidence-based deviation on how the two combine (DOCUMENTATION.md sec 7)
- [ ] Tremor-like movement can be detected -- **not implemented in v1**, no tremor-labeled training data exists (BITS-2 has none); dashboard honestly shows "Not available" rather than fabricating a result
- [x] HR and estimated SpO₂ are displayed -- dashboard cards + charts; firmware-side values are hardware-unverified, but the full display pipeline was verified with real data from `tests/e2e_demo.py`
- [x] Dashboard updates with live results -- 2s polling, verified via direct API checks (no browser screenshot tool available in this environment)
- [~] Confirmed fall alert activates the buzzer -- backend correctly returns `"buzzer": true` on a confirmed fall (verified) and firmware code drives `BUZZER_PIN` on that flag (compiles, but never run on a physical buzzer)
- [x] Sensor data, predictions, and alerts are stored in the database -- `backend/database/db.py`, verified via `tests/e2e_demo.py`
- [~] Full system demonstrated end-to-end (all 4 demo scenarios in DOCUMENTATION.md §19) -- 3 of 4 pass on held-out data (Walking, Sitting/Running, Fall); Tremor scenario not applicable (no trained class), not silently skipped -- documented

## 7. Repository/documentation hygiene

- [x] README reflects current project state (not aspirational) -- updated 2026-08-19
- [x] DOCUMENTATION.md updated at the end of each phase, not just at the end of the project -- updated 2026-08-19 with real results through Phase 9
- [x] PLAN.md "Current phase" line kept up to date -- updated 2026-08-19
- [x] This AUDIT.md reviewed at the end of each phase -- this review

## Audit log

| Date | Phase | Reviewer | Notes |
|---|---|---|---|
| 2026-08-19 | Project init | — | Repo scaffolded; no implementation yet, checklist all unchecked by design. |
| 2026-08-19 | Phases 1-9 (software) | Claude (autonomous build session) | Full software stack implemented and tested against real data (BITS-2 dataset, real CNN/LSTM training, real Flask backend, real dashboard, real ESP32 firmware compiled against the toolchain). Genuine gap: no physical hardware available in this environment, so Phases 1/2 and the ESP32 side of Phase 5/8 remain hardware-unverified. Three real bugs were found and fixed via testing (not inspection): a missing `tremor_probability` key causing a 500 error, a Flask static-route conflict causing dashboard 404s, and a train/inference preprocessing mismatch (naive rolling window vs. the model's actual whole-trial-resample training transform) that silently produced wrong live predictions until redesigned into event-triggered segmentation. See docs/DOCUMENTATION.md for full detail on every deviation from the original plan and why. |
