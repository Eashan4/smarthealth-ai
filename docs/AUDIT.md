# SmartHealth AI — Audit Checklist

Purpose: a living checklist to audit the project against its own stated scope limits, engineering rules, and success criteria. Review and update this file at the end of every phase (see [PLAN.md](PLAN.md)) — do not treat it as a one-time document.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done/verified

## 1. Scope limits (must never be violated)

This project is monitoring/detection/classification only. It must never claim to:

- [ ] Diagnose diseases
- [ ] Replace doctors or provide clinical decisions
- [ ] Provide clinically certified SpO₂ measurements
- [ ] Provide clinically certified fall detection
- [ ] Detect Parkinson's disease specifically (only "tremor-like movement")
- [ ] Provide medication recommendations
- [ ] Measure blood pressure (no hardware for this)
- [ ] Claim any form of medical certification

**Audit action:** grep the README, dashboard copy, and final report for words like "diagnose," "diagnosis," "certified," "clinical," "Parkinson's," and "medical device" before each submission/demo. Flag any hit for rewording to "monitoring / detection / classification / prototype / estimated."

## 2. Data integrity rules

- [ ] No preprocessing statistic (mean/std/scaler) is fit on data outside the training split
- [ ] No recording appears in both train and test sets
- [ ] No sliding window straddles a train/test split boundary
- [ ] Thresholds (`FALL_PROBABILITY_THRESHOLD`, `ACCELERATION_THRESHOLD`, `POST_FALL_INACTIVITY_SECONDS`) were set from an experiment, not guessed, and the experiment is documented in DOCUMENTATION.md §6
- [ ] Train/val/test split is subject-wise where the dataset allows it; if not, the limitation is documented
- [ ] Fall-event windows use the event-centered labeling rule, not majority-label (DOCUMENTATION.md §4)

## 3. Reporting integrity

- [ ] Every metric (accuracy, precision, recall, F1, confusion matrix, inference latency, model size) in the final report traces to an actual logged experiment run
- [ ] No fabricated or placeholder numbers remain in the final report
- [ ] Final model choice is justified by measured results (esp. fall recall), not accuracy alone
- [ ] Known limitations section (DOCUMENTATION.md §16) is filled in, not left as a stub

## 4. Engineering discipline

- [ ] Sampling rate, window size, overlap, and all thresholds are defined in one central config, not scattered as literals
- [ ] Preprocessing code path is shared (not duplicated) between training and real-time inference
- [ ] Hardware/firmware code, backend logic, training code, and inference code are kept in separate layers/directories
- [ ] No Wi-Fi credentials or secrets are committed to the repository
- [ ] Sensor payloads are validated (type/required fields) before use, not trusted blindly

## 5. Safety

- [ ] Fall data collection used safe simulated/controlled events only — no intentional falls onto hard surfaces
- [ ] Custom data collection protocol (per activity class) is documented before collection begins

## 6. Success criteria (from project spec §38)

- [ ] ESP32 collects real MPU6050 data
- [ ] ESP32 collects real MAX30102 readings
- [ ] ESP32 transmits timestamped data over Wi-Fi
- [ ] Backend receives and validates incoming payloads
- [ ] IMU data is segmented into sliding windows (train + inference share logic)
- [ ] 1D CNN performs real-time activity classification
- [ ] LSTM is trained for comparison
- [ ] Model performance is evaluated with accuracy/precision/recall/F1/confusion matrix, subject-wise
- [ ] Fall detection combines AI prediction + rule-based verification
- [ ] Tremor-like movement can be detected
- [ ] HR and estimated SpO₂ are displayed
- [ ] Dashboard updates with live results
- [ ] Confirmed fall alert activates the buzzer
- [ ] Sensor data, predictions, and alerts are stored in the database
- [ ] Full system demonstrated end-to-end (all 4 demo scenarios in DOCUMENTATION.md §15)

## 7. Repository/documentation hygiene

- [ ] README reflects current project state (not aspirational)
- [ ] DOCUMENTATION.md updated at the end of each phase, not just at the end of the project
- [ ] PLAN.md "Current phase" line kept up to date
- [ ] This AUDIT.md reviewed at the end of each phase

## Audit log

| Date | Phase | Reviewer | Notes |
|---|---|---|---|
| 2026-08-19 | Project init | — | Repo scaffolded; no implementation yet, checklist all unchecked by design. |
