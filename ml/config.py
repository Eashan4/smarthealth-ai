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

# --- Paths ---
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = REPO_ROOT / "data" / "raw" / "bits2" / "Dataset"
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
MODELS_DIR = REPO_ROOT / "models"
