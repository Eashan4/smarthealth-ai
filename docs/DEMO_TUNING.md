# Demo tuning: Walking / Running / Fall / Tremor

Live detection is rule-based (`ml/inference/motion_rules.py`, `ml/inference/tremor.py`) with the old BITS-2 CNN kept
only as supporting fall evidence. **These are heuristics tuned on synthetic signals (50 Hz, MPU6050-like noise), not
validated on real subjects and not clinically validated.** Expect to nudge the numbers below on the real board.
All values live in `ml/config.py`; the backend auto-reloads on save. Check what the classifier sees at
`GET /api/motion?device_id=...` (`features.accel_std`, `dom_freq_hz`, `peak_frac`, `gyro_rms`, `peak_accel_2s`,
`fall_state`) and `GET /api/tremor`.

Units: accel m/s^2, gyro rad/s (calibrated bias removed), 50 Hz.

## Walking / Running / Sitting
Window is `MOTION_WINDOW_SECONDS` (2.5 s), result every `MOTION_HOP_SECONDS` (1 s), label needs `MOTION_SWITCH_EVALS` (2) wins to change.

| Constant | Meaning | If it under-detects | If it over-detects |
|---|---|---|---|
| `MOTION_STILL_STD` (0.6) / `MOTION_STILL_GYRO` (0.35) | below both = still -> Sitting/Lying | raise if a held-still board shows "Standing" | lower if slow walking reads Sitting |
| `WALK_MIN_STD` (1.0) | min std of &#124;accel&#124; to call it walking | lower if gentle walking reads Standing | raise if hand fidgeting reads Walking |
| `WALK_FREQ_HZ` (1.2-2.6) | step cadence band | widen if your gait cadence is outside it | narrow |
| `RUN_MIN_STD` (2.5) | energy needed for Running when cadence > 2.6 Hz | lower if jogging reads Standing | raise if fast walking reads Running |
| `RUN_ANY_CADENCE_STD` (9.0) | this much energy is Running at any cadence | lower if hard running at ~2 Hz reads Walking | raise if hard arm-swing walking reads Running |
| `RUN_MAX_CADENCE_HZ` (4.0) | dominant freq above this is never locomotion (shake/vibration) | raise only if sprint cadence is cut off | lower to 3.5 if hand shaking is read as Running |
| `LOCO_MIN_PEAK_FRAC` (0.25) | rhythmic share of band power at cadence+harmonics | lower for irregular gait (wrist, pocket) | raise if random movement reads Walking |
| `SUBHARMONIC_FRAC` (0.2) | halves a 3-5.2 Hz dominant freq when a half-frequency peak exists (2nd-harmonic-dominated gait) | lower if walking reads Running/Standing at ~3.8 Hz | raise if 4-5 Hz shaking reads Walking |
| `TILT_UPRIGHT_MAX_DEG` (30) / `TILT_LYING_MIN_DEG` (60) | still + tilt of gravity vs the calibrated rest gravity: Sitting / Standing / Lying | - | - |

Sitting/Lying/Standing is orientation-dependent: with no calibration every still state is "Resting" shown as Sitting.
With calibration (`rest gravity`), calibrate in the pose you want to call Sitting; rotating the board >= 60 deg reads Lying.
"Standing" also means "active but not walking" (fidgeting, shaking, tremor).

## Fall
State machine on the live stream: `freefall -> impact -> confirming -> confirmed`, exposed as `fall_state`.

| Constant | Meaning | If a real fall is missed | If false alarms |
|---|---|---|---|
| `FREEFALL_MAG` (3.5) | &#124;accel&#124; below this = weightless | raise (4-5) | lower |
| `FREEFALL_MIN_SECONDS` (0.10) | dip must last this long (~5 cm drop) | lower to 0.06 | raise (a table put-down also dips briefly) |
| `FALL_IMPACT_AFTER_FREEFALL_MAG` (18) | spike that completes a dip | lower (12-15) for soft landings | raise |
| `FALL_IMPACT_ONLY_MAG` (28) | spike with no dip seen (wrist strap) | lower (22-25) | raise; running peaks reach ~25-30 |
| `FALL_STILL_STD` (0.8) / `FALL_STILL_SECONDS` (1.0) | std/duration of stillness after impact | raise std, shorten seconds | lower std, lengthen seconds |
| `FALL_STILL_DEADLINE_SECONDS` (2.0) | stillness must begin within this after impact | raise | lower |
| `FALL_SETTLE_SECONDS` (0.3) | bounce ignored right after impact | - | raise if the bounce prevents stillness |
| `FALL_REARM_STD` (2.0), `FALL_HOLD_SECONDS` (8) | confirmed ends on resumed motion or after the hold (label "Fall" + buzzer) | - | - |
| `FALL_PROBABILITY_THRESHOLD` (0.466), `FALL_CNN_MIN_IMPACT` (20), `FALL_CNN_EVIDENCE_TTL_SECONDS` (3) | CNN path: prob over threshold AND an impact > 20 within 2 s, within 3 s of the CNN event | lower threshold | raise threshold (the CNN was trained on another placement; if it false-alarms, set the threshold to 1.01 to disable it) |

Known limits: "shake hard, then hold perfectly still" looks like a fall to a rule on |accel| alone; so does a hard drop onto
a table that is not caught by the free-fall dip gate.

## Tremor
Accel and gyro (mean-removed) are analysed in the 3-8 Hz band every 0.5 s over 3 s; either sensor passing all gates counts.
Debounce: on after `TREMOR_ON_EVALS` (3), off after `TREMOR_OFF_EVALS` (4).

| Constant | Meaning | If missed | If false alarms |
|---|---|---|---|
| `TREMOR_MIN_RMS` (0.12 m/s^2), `TREMOR_MIN_GYRO_RMS` (0.04 rad/s) | band amplitude floor (sensor noise is ~0.04 / ~0.01) | lower toward 0.08 / 0.025 | raise |
| `TREMOR_MAX_RMS` (3.0), `TREMOR_MAX_GYRO_RMS` (2.5) | above this it is gait/violent motion | raise if a hard shake is rejected | lower |
| `TREMOR_MIN_PEAK_FRAC` (0.45) | sharpness: share of 3-8 Hz power within +-0.7 Hz of the peak | lower (0.35) for a ragged shake | raise (broadband vibration) |
| `TREMOR_MIN_BAND_RATIO` (0.5) | band share of 2.5-15 Hz power | lower | raise |
| `TREMOR_MAX_LOW_TO_BAND_RMS` (6) | slow-motion rms may be this x tremor rms | raise if big slow arm motion blocks it | lower |
| `TREMOR_HARMONIC_FRAC` (0.15) | reject a peak when F/2 or F/3 (1-2.8 Hz) is this strong (gait harmonics) | raise if tremor with slow arm motion at ~2 Hz is rejected | lower if walking triggers tremor |
| `FS_JITTER_TOLERANCE` (0.10), `FS_ACCEPT_RANGE` | the 50 Hz nominal rate is used unless the whole-window rate is clearly off | - | - |
