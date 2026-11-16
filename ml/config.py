"""Central configuration for SmartHealth AI ML pipeline.

Single source of truth for sampling/window parameters, class labels, thresholds,
and file paths. Never hard-code these values elsewhere (see PLAN.md engineering
rule #5). Threshold values start as placeholders and are set from experiments
(see DOCUMENTATION.md, Fall Detection / Model Selection sections) once measured.
"""

from pathlib import Path

# --- Hardware / sampling contract (fixed baseline, PLAN.md sec 3) ---
IMU_SAMPLE_RATE = 50          # Hz, target rate for the live ESP32 -> Flask stream
WINDOW_SIZE_SECONDS = 3
WINDOW_OVERLAP = 0.5          # 50%, used for continuous real-time inference windowing
WINDOW_LENGTH = int(IMU_SAMPLE_RATE * WINDOW_SIZE_SECONDS)  # 150 timesteps
NUM_CHANNELS = 6              # Ax, Ay, Az, Gx, Gy, Gz
CHANNEL_NAMES = ["ax", "ay", "az", "gx", "gy", "gz"]

# --- Class labels ---
# Trained on the BITS-2 dataset (Zenodo 10.5281/zenodo.10013090), the only class
# subset with real recorded data for this label set. Standing and Tremor are NOT
# present in BITS-2's 16 ADL / 8 fall trial types and are therefore excluded from
# the v1 trained model rather than approximated or fabricated. See
# docs/DOCUMENTATION.md sec 5 (Labels and classes) and sec 16 (Known limitations).
CLASSES = ["Walking", "Running", "Sitting", "Lying", "Fall"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}
IDX_TO_CLASS = {i: c for c, i in CLASS_TO_IDX.items()}
FALL_CLASS_IDX = CLASS_TO_IDX["Fall"]

# --- Fall / tremor decision thresholds (Phase 8) ---
# Set from ml/evaluation/threshold_analysis.py (real experiment on BITS-2 held-out
# val set / raw trials), see docs/DOCUMENTATION.md sec 7 and models/threshold_experiment.json.
FALL_PROBABILITY_THRESHOLD = 0.466   # precision=1.00, recall=0.917 on val set at this cut
ACCELERATION_THRESHOLD = 45.94       # m/s^2, 95th-percentile peak accel magnitude across non-fall ADL trials
# PROVISIONAL -- BITS-2 trials are trimmed to ~1-3s around the event and do not
# contain a genuine multi-second post-fall settling period, so this could not be
# measured from real continuous data (see threshold_analysis.py note). Literature-
# informed placeholder; must be re-validated against continuous Phase 2 ESP32
# recordings before being treated as final (DOCUMENTATION.md sec 16).
POST_FALL_INACTIVITY_SECONDS = 1.5
ALERT_DEBOUNCE_WINDOWS = 2           # consecutive abnormal inference windows required before alerting

# --- Live event-segmentation triggers (ml/segmentation/windowing.py) ---
# Heuristic onset/offset triggers for the live EventSegmentBuffer, distinct
# from the experimentally-derived ACCELERATION_THRESHOLD above (that one
# gates fall-verification; these just decide when to start/stop capturing a
# segment to classify). See ml/segmentation/windowing.py docstring.
EVENT_ONSET_ACCEL_DELTA = 2.0     # m/s^2 deviation from rest (9.8) that starts an event
EVENT_OFFSET_HOLD_SAMPLES = 10    # consecutive near-rest raw samples that end an event
EVENT_MAX_SAMPLES = 200           # hard cap on raw samples captured per event
EVENT_MIN_SAMPLES = 4             # minimum captured samples to bother classifying

# --- Tremor detection (ml/inference/tremor.py) ---
# Signal-processing detector on the MPU6050 accelerometer AND gyro, NOT a trained model (BITS-2 has no tremor class).
# Rest/postural tremor is a rhythmic 3-8 Hz oscillation (Parkinsonian rest tremor ~4-6 Hz). The gyro (rad/s) is far
# more sensitive to hand tremor than the accelerometer. Walking/running also put energy in this band through
# harmonics, so a candidate peak is rejected if a stronger peak sits at 1/2 or 1/3 of its frequency (gait
# fundamental) or if the amplitude is gait-sized. Heuristic thresholds tuned on synthetic signals, not clinically
# validated: verify by deliberately shaking the board at ~5 Hz and adjust here, never inside the detector.
TREMOR_BAND_HZ = (3.0, 8.0)
TREMOR_WINDOW_SECONDS = 3.0
TREMOR_HOP_SECONDS = 0.5              # re-evaluate this often once the window is full
TREMOR_MIN_RMS = 0.12                 # m/s^2, accel band rms below this is sensor noise (MPU6050 noise in band ~0.04)
TREMOR_MAX_RMS = 3.0                  # m/s^2, accel band rms above this is gait / violent motion, not tremor
TREMOR_MIN_GYRO_RMS = 0.04            # rad/s, gyro band rms below this is noise (noise in band ~0.01)
TREMOR_MAX_GYRO_RMS = 2.5             # rad/s, above this it is gait / deliberate large rotation
TREMOR_MIN_BAND_RATIO = 0.5           # tremor-band power / 2.5-15 Hz power (slow hand drift is excluded from the denominator)
TREMOR_MIN_PEAK_FRAC = 0.45           # share of 3-8 Hz power within +-TREMOR_PEAK_HALFWIDTH_HZ of the peak: rhythmic, not broadband
TREMOR_PEAK_HALFWIDTH_HZ = 0.7
TREMOR_MAX_LOW_TO_BAND_RMS = 6.0      # slow voluntary motion (0.5-2.5 Hz) rms may be at most this x the tremor rms
TREMOR_HARMONIC_FRAC = 0.15           # peak at F rejected if power at F/2 or F/3 (gait range) >= this x power at F
TREMOR_ON_EVALS = 3                   # consecutive positive evaluations to declare "detected" (1.5 s)
TREMOR_OFF_EVALS = 4                  # consecutive negatives to clear it (2 s)
TREMOR_STALE_SECONDS = 3.0            # no motion samples for this long -> "no_data"
FS_JITTER_TOLERANCE = 0.10            # window-average rate within +-10% of nominal -> use nominal (serial bursts)
FS_ACCEPT_RANGE = (0.4, 1.6)          # estimated/nominal ratio outside this is a timestamp glitch -> use nominal

# --- Continuous activity rules (ml/inference/motion_rules.py) ---
# Orientation-independent rolling-window classifier for the live demo (board in hand / on wrist or waist).
# Heuristics tuned on synthetic signals, not validated on a labelled dataset. See docs/DEMO_TUNING.md.
MOTION_WINDOW_SECONDS = 2.5           # rolling window for features
MOTION_HOP_SECONDS = 1.0              # emit a result this often (1 Hz)
MOTION_MIN_SECONDS = 1.5              # no result until this much data exists
MOTION_FREQ_BAND_HZ = (0.8, 8.0)      # search band for the dominant frequency of |accel|
MOTION_STILL_STD = 0.6                # m/s^2, |accel| std below this (and gyro below MOTION_STILL_GYRO) = still
MOTION_STILL_GYRO = 0.35              # rad/s, mean |gyro| below this = still
WALK_FREQ_HZ = (1.2, 2.6)             # step cadence of walking
RUN_MAX_CADENCE_HZ = 4.0              # dominant freq above this is shaking/vibration, never locomotion
WALK_MIN_STD = 1.0                    # m/s^2, |accel| std needed for walking
RUN_MIN_STD = 2.5                     # m/s^2, |accel| std needed for running when cadence > WALK_FREQ_HZ[1]
RUN_ANY_CADENCE_STD = 9.0             # m/s^2, this much |accel| std at a gait cadence is running
LOCO_MIN_PEAK_FRAC = 0.25             # share of band power at the dominant freq: gait is rhythmic
SUBHARMONIC_FRAC = 0.2                # dominant freq in 3-5.2 Hz is halved if power at half freq >= this x peak (2nd-harmonic dominated gait)
MOTION_SWITCH_EVALS = 2               # a new label must win this many consecutive 1 Hz evaluations (hysteresis)
TILT_UPRIGHT_MAX_DEG = 30.0           # still, gravity within this of the calibrated rest gravity -> Sitting
TILT_LYING_MIN_DEG = 60.0             # still, gravity at least this far from rest gravity -> Lying (between -> Standing)

# --- Fall state machine on the continuous stream (ml/inference/motion_rules.py) ---
# idle -> freefall (|a| dip) -> impact (spike) -> confirming (waiting for stillness) -> confirmed. Impact alone
# (no dip) needs the larger FALL_IMPACT_ONLY_MAG. Running/shaking never confirms: it needs post-impact stillness.
FREEFALL_MAG = 3.5                    # m/s^2, |accel| below this = weightless
FREEFALL_MIN_SECONDS = 0.10           # dip must last this long (5 samples ~ 5 cm drop)
FREEFALL_MAX_SECONDS = 1.0            # longer than this is a sensor glitch, abandon
FREEFALL_TO_IMPACT_SECONDS = 0.5      # impact must follow the dip within this
FALL_IMPACT_AFTER_FREEFALL_MAG = 18.0 # m/s^2, spike that completes a freefall dip
FALL_IMPACT_ONLY_MAG = 28.0           # m/s^2, spike alone (no dip seen), e.g. sensor in a wrist strap
FALL_SETTLE_SECONDS = 0.3             # ignore the bounce right after impact
FALL_STILL_SECONDS = 1.0              # stillness must last this long
FALL_STILL_DEADLINE_SECONDS = 2.0     # stillness must start within this after impact
FALL_STILL_STD = 0.8                  # m/s^2, |accel| std below this over FALL_STILL_SECONDS = still
FALL_REARM_STD = 2.0                  # confirmed state ends when |accel| std over 0.5 s exceeds this (motion resumed)
FALL_HOLD_SECONDS = 8.0               # a confirmed fall is held (label + buzzer) at most this long
FALL_STATE_SCORE = {"idle": 0.0, "freefall": 0.3, "impact": 0.5, "confirming": 0.6, "confirmed": 1.0}
FALL_CNN_MIN_IMPACT = 20.0            # m/s^2, CNN fall prob alone needs an impact this big in the last 2 s
FALL_CNN_IMPACT_LOOKBACK_SECONDS = 2.0
FALL_CNN_EVIDENCE_TTL_SECONDS = 3.0   # a CNN fall probability counts for this long after its event closed

# --- Paths ---
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = REPO_ROOT / "data" / "raw" / "bits2" / "Dataset"
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MODELS_DIR = REPO_ROOT / "models"
