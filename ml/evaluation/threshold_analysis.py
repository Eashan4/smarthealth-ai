"""Experiment: derive Phase 8 decision-engine thresholds from real data,
per docs/DOCUMENTATION.md sec 7 and AUDIT.md sec 2 ("thresholds set from an
experiment, not guessed"). Run after ml/training/train.py has produced
models/deployed_model.pt and models/scaler.json.

Usage: python -m ml.evaluation.threshold_analysis
"""

from __future__ import annotations

import json

import numpy as np
import torch
from sklearn.metrics import precision_recall_curve

from ml.cnn.model import ActivityCNN
from ml.config import CLASSES, FALL_CLASS_IDX, MODELS_DIR, NUM_CHANNELS
from ml.datasets.bits2_adapter import FALL_LABEL, _discover_trials, _parse_sensor_rows
from ml.preprocessing.normalize import ChannelScaler
from ml.training.train import split_masks, subject_wise_split
from ml.datasets.bits2_adapter import load_dataset


def acceleration_peak_analysis():
    """Compare raw (non-resampled) acceleration-magnitude peaks between Fall
    and ADL trials to pick ACCELERATION_THRESHOLD, and estimate post-fall
    low-motion duration to inform POST_FALL_INACTIVITY_SECONDS."""
    trials = _discover_trials()
    fall_peaks, adl_peaks = [], []
    post_fall_durations = []

    for t in trials:
        if t.kind == "fall":
            acc, _ = _parse_sensor_rows(t.path)
            if len(acc) < 4:
                continue
            mag = np.linalg.norm(acc, axis=1)
            peak = float(mag.max())
            fall_peaks.append(peak)
            peak_idx = int(mag.argmax())
            tail = mag[peak_idx + 1:]
            if len(tail) >= 2:
                # "low motion" = magnitude within 2 units of gravity-rest band (~9.8),
                # i.e. |mag - 9.8| < 3, a standard near-rest accel-magnitude band.
                low_motion = np.abs(tail - 9.8) < 3.0
                # duration of the low-motion run starting right after the peak
                run = 0
                for v in low_motion:
                    if v:
                        run += 1
                    else:
                        break
                # ~20 Hz nominal sample rate in this raw (non-resampled) data
                post_fall_durations.append(run / 20.0)
        elif t.kind == "adl" and t.activity_id not in (4, 12, 14, 15, 16):
            acc, _ = _parse_sensor_rows(t.path)
            if len(acc) < 4:
                continue
            mag = np.linalg.norm(acc, axis=1)
            adl_peaks.append(float(mag.max()))

    fall_peaks = np.array(fall_peaks)
    adl_peaks = np.array(adl_peaks)
    print(f"Fall trials: n={len(fall_peaks)} peak_accel_magnitude "
          f"mean={fall_peaks.mean():.2f} min={fall_peaks.min():.2f} max={fall_peaks.max():.2f} "
          f"p10={np.percentile(fall_peaks,10):.2f}")
    print(f"ADL (non-fall) trials: n={len(adl_peaks)} peak_accel_magnitude "
          f"mean={adl_peaks.mean():.2f} max={adl_peaks.max():.2f} p95={np.percentile(adl_peaks,95):.2f} "
          f"p99={np.percentile(adl_peaks,99):.2f}")

    # Threshold = ADL p95 peak, i.e. a sudden-acceleration cutoff that most
    # ordinary daily activity in this dataset stays under.
    acceleration_threshold = float(np.percentile(adl_peaks, 95))
    fall_recall_at_threshold = float((fall_peaks > acceleration_threshold).mean())
    print(f"-> Candidate ACCELERATION_THRESHOLD (ADL p95 peak) = {acceleration_threshold:.2f}: "
          f"{fall_recall_at_threshold*100:.1f}% of fall trials exceed it")

    durations = np.array(post_fall_durations)
    print(f"Post-fall low-motion run length within trial (n={len(durations)}): "
          f"mean={durations.mean():.2f}s median={np.median(durations):.2f}s max={durations.max():.2f}s")
    print("NOTE: BITS-2 trials are trimmed to the activity itself and are only "
          "~1-3s long, so this measures low-motion duration WITHIN the short trial "
          "window, not a full post-fall settling period from a continuous stream. "
          "Treat POST_FALL_INACTIVITY_SECONDS derived from this as a lower-bound "
          "estimate to be re-validated once continuous ESP32 recordings (Phase 2) "
          "are available -- documented explicitly, not presented as final.")

    return acceleration_threshold, float(durations.mean()) if len(durations) else None


def fall_probability_threshold_analysis():
    """Precision-recall sweep for FALL_PROBABILITY_THRESHOLD using the
    deployed CNN's softmax fall-class probability on the held-out val set."""
    meta = json.loads((MODELS_DIR / "model_meta.json").read_text())
    cfg = meta["deployed"]["config"]
    model = ActivityCNN(NUM_CHANNELS, len(CLASSES), filters=tuple(cfg["filters"]),
                         kernel_size=cfg["kernel_size"], dropout=cfg["dropout"])
    model.load_state_dict(torch.load(MODELS_DIR / "deployed_model.pt"))
    model.eval()
    scaler = ChannelScaler.load(MODELS_DIR / "scaler.json")

    X, y, subjects, _ = load_dataset()
    train_subj, val_subj, test_subj = subject_wise_split(subjects)
    _, val_mask, _ = split_masks(subjects, train_subj, val_subj, test_subj)
    X_val_n = scaler.transform(X[val_mask])
    y_val = y[val_mask]
    y_val_binary = (y_val == FALL_CLASS_IDX).astype(int)

    with torch.no_grad():
        probs = torch.softmax(model(torch.from_numpy(X_val_n)), dim=1)[:, FALL_CLASS_IDX].numpy()

    precision, recall, thresholds = precision_recall_curve(y_val_binary, probs)
    # Pick the highest threshold that still achieves >=0.90 recall (fall recall
    # is weighted over precision per DOCUMENTATION.md sec 6.3 / sec 7).
    candidates = [(t, p, r) for p, r, t in zip(precision[:-1], recall[:-1], thresholds) if r >= 0.90]
    if candidates:
        chosen = max(candidates, key=lambda c: c[0])  # highest precision among >=90% recall
    else:
        chosen = (float(thresholds[np.argmax(recall[:-1])]), 0.0, float(recall.max()))
    print(f"Fall-probability threshold sweep (val set, n={len(y_val_binary)}, "
          f"{int(y_val_binary.sum())} true fall windows):")
    for t, p, r in list(zip(thresholds, precision[:-1], recall[:-1]))[::max(1, len(thresholds)//10)]:
        print(f"  threshold={t:.3f} precision={p:.3f} recall={r:.3f}")
    print(f"-> Candidate FALL_PROBABILITY_THRESHOLD = {chosen[0]:.3f} "
          f"(precision={chosen[1]:.3f}, recall={chosen[2]:.3f})")
    return float(chosen[0])


if __name__ == "__main__":
    print("=== Acceleration threshold + post-fall inactivity analysis ===")
    accel_threshold, post_fall_secs = acceleration_peak_analysis()
    print("\n=== Fall-probability threshold analysis ===")
    fall_prob_threshold = fall_probability_threshold_analysis()

    result = {
        "ACCELERATION_THRESHOLD": accel_threshold,
        "ACCELERATION_THRESHOLD_UNIT": "m/s^2 (raw accel-magnitude, sensor units as recorded)",
        "ACCELERATION_THRESHOLD_METHOD": "95th percentile of peak acceleration magnitude across non-fall BITS-2 ADL trials",
        "POST_FALL_INACTIVITY_SECONDS_ESTIMATE": post_fall_secs,
        "POST_FALL_INACTIVITY_SECONDS_CAVEAT": "Lower-bound estimate from short trimmed trials; re-validate with continuous Phase 2 recordings before treating as final.",
        "FALL_PROBABILITY_THRESHOLD": fall_prob_threshold,
        "FALL_PROBABILITY_THRESHOLD_METHOD": "precision-recall sweep on held-out validation set, highest-precision point with recall >= 0.90",
    }
    with open(MODELS_DIR / "threshold_experiment.json", "w") as fh:
        json.dump(result, fh, indent=2)
    print("\nSaved models/threshold_experiment.json")
