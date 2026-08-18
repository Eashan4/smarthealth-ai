"""Adapter for the BITS-2 geriatric fall-detection dataset.

Source: Zenodo 10.5281/zenodo.10013090 ("Inertial Measurement and Heart-Rate
sensor-based dataset for Geriatric fall detection using custom built
wrist-worn device"). Collected with an MPU6500 (accel+gyro) and MAX30102
(HR/SpO2) wrist device -- the same sensor pair as this project's hardware
(MPU6050 + MAX30102), which is why it was selected over alternatives (see
docs/DOCUMENTATION.md sec 8).

Known structural mismatches vs. our fixed baseline, and how each is handled
(see docs/DOCUMENTATION.md sec 8-10 for the documented rationale):

1. Sampling rate: BITS-2 motion sensors are ~20 Hz nominal; our hardware
   target is 50 Hz. Each trial is resampled (linear interpolation) onto the
   fixed WINDOW_LENGTH grid rather than merged at native rate.
2. Timestamps in the raw CSVs are truncated to 3 significant figures
   (e.g. "1.23E+12"), making them useless for sub-sample alignment. Instead,
   accelerometer and gyroscope rows are aligned by acquisition order (row
   index) within each trial file, then both independently resampled to the
   same fixed length. This is a documented approximation, not fabricated
   data -- every value used is a real recorded reading.
3. Each CSV file is one short discrete trial (a few seconds), not a
   continuous stream. Trials are therefore resampled/padded to exactly one
   canonical WINDOW_LENGTH-sample window each, rather than sliding-windowed.
   Sliding-window segmentation (ml/segmentation) is reserved for the
   continuous live inference stream (Phase 6), not this offline trial data.
4. Label coverage: BITS-2's 16 ADL types and 8 fall types do not include a
   "Standing" (static) class or a "Tremor-like movement" class. Trials with
   no honest mapping are excluded rather than mislabeled -- see
   ADL_LABEL_MAP below and docs/DOCUMENTATION.md sec 16 (Known limitations).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field

import numpy as np

from ml.config import CLASS_TO_IDX, DATA_RAW_DIR, NUM_CHANNELS, WINDOW_LENGTH
from ml.preprocessing.resample import resample_to_window

# ADL activity id (1-16) -> project class name, or None to exclude the trial.
# Source of activity names: dataset paper (PMC10709028), see adapter docstring.
ADL_LABEL_MAP = {
    1: "Walking",   # Walking Slowly
    2: "Walking",   # Walking Quickly
    3: "Running",   # Jogging
    4: None,        # Jumping -- no honest match in our class set
    5: "Walking",   # Climbing up slowly
    6: "Walking",   # Climbing down slowly
    7: "Walking",   # Climbing up normally
    8: "Walking",   # Climbing down normally
    9: "Sitting",   # Slowly sitting on chair
    10: "Sitting",  # Rapidly sitting on chair
    11: "Sitting",  # Nearly sitting on chair and getting up
    12: None,       # Swinging Hands -- not tremor, not a clean class match
    13: "Lying",    # Lying on Bed
    14: None,       # Lying on back and getting up slowly (transition)
    15: None,       # Lying on back and getting up normally (transition)
    16: None,       # Transition from sideways to back while lying (transition)
}
# All 8 fall types map to the single Fall class (event-centered, not activity-specific).
FALL_LABEL = "Fall"

_FILENAME_RE = re.compile(r"user(\d+)_(adl|fall)(\d+)\.csv$")


@dataclass
class RawTrial:
    subject: int
    kind: str            # "adl" or "fall"
    activity_id: int
    label: str            # mapped project class name
    path: str


@dataclass
class LoadSummary:
    included: dict = field(default_factory=dict)   # label -> count
    excluded_adl: dict = field(default_factory=dict)  # activity_id -> count
    skipped_short: int = 0
    total_files_seen: int = 0


def _parse_sensor_rows(csv_path) -> tuple[np.ndarray, np.ndarray]:
    """Return (acc[N,3], gyro[M,3]) in file row order for one trial CSV."""
    acc, gyro = [], []
    with open(csv_path, encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 6:
                continue
            sensor_type = row[5].strip()
            try:
                x, y, z = float(row[1]), float(row[2]), float(row[3])
            except ValueError:
                continue
            if sensor_type == "acc":
                acc.append((x, y, z))
            elif sensor_type == "gyro":
                gyro.append((x, y, z))
    return np.array(acc, dtype=np.float32), np.array(gyro, dtype=np.float32)


def _discover_trials() -> list[RawTrial]:
    trials: list[RawTrial] = []
    for kind, label_map in (("adl", ADL_LABEL_MAP), ("fall", None)):
        base = DATA_RAW_DIR / kind
        for csv_path in sorted(base.glob("user*/*.csv")):
            m = _FILENAME_RE.search(csv_path.name)
            if not m:
                continue
            subject = int(m.group(1))
            activity_id = int(m.group(3))
            if kind == "adl":
                label = ADL_LABEL_MAP.get(activity_id)
            else:
                label = FALL_LABEL
            trials.append(RawTrial(subject, kind, activity_id, label, str(csv_path)))
    return trials


def load_dataset(min_raw_samples: int = 4):
    """Load and resample every usable BITS-2 trial.

    Returns (X, y, subjects, summary):
      X: float32 array [N, WINDOW_LENGTH, NUM_CHANNELS]
      y: int64 array [N] of class indices (ml.config.CLASS_TO_IDX)
      subjects: int array [N] subject id, for subject-wise splitting
      summary: LoadSummary with inclusion/exclusion counts for documentation
    """
    trials = _discover_trials()
    X, y, subjects = [], [], []
    summary = LoadSummary(total_files_seen=len(trials))

    for t in trials:
        if t.label is None:
            summary.excluded_adl[t.activity_id] = summary.excluded_adl.get(t.activity_id, 0) + 1
            continue
        acc, gyro = _parse_sensor_rows(t.path)
        if len(acc) < min_raw_samples or len(gyro) < min_raw_samples:
            summary.skipped_short += 1
            continue
        acc_r = resample_to_window(acc, WINDOW_LENGTH)
        gyro_r = resample_to_window(gyro, WINDOW_LENGTH)
        window = np.concatenate([acc_r, gyro_r], axis=1)  # [WINDOW_LENGTH, 6]
        assert window.shape == (WINDOW_LENGTH, NUM_CHANNELS)
        X.append(window)
        y.append(CLASS_TO_IDX[t.label])
        subjects.append(t.subject)
        summary.included[t.label] = summary.included.get(t.label, 0) + 1

    return (
        np.stack(X).astype(np.float32),
        np.array(y, dtype=np.int64),
        np.array(subjects, dtype=np.int64),
        summary,
    )


if __name__ == "__main__":
    X, y, subjects, summary = load_dataset()
    print(f"Total trial files seen: {summary.total_files_seen}")
    print(f"Skipped (too short): {summary.skipped_short}")
    print(f"Excluded ADL activity ids -> counts: {summary.excluded_adl}")
    print(f"Included per class: {summary.included}")
    print(f"X shape: {X.shape}, y shape: {y.shape}, subjects: {np.unique(subjects).size} unique")
