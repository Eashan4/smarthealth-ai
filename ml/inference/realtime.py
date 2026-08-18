"""Phase 6 -- real-time rolling-window inference.

Uses the exact same segmentation (ml.segmentation.windowing.RollingBuffer)
and normalization (ml.preprocessing.normalize.ChannelScaler) code paths as
training, per PLAN.md engineering rule #2 (preprocessing must be identical
between training and real-time inference).
"""

from __future__ import annotations

import json
import time

import numpy as np
import torch

from ml.cnn.model import ActivityCNN
from ml.config import CLASSES, FALL_CLASS_IDX, MODELS_DIR, NUM_CHANNELS
from ml.preprocessing.normalize import ChannelScaler
from ml.segmentation.windowing import EventSegmentBuffer


class ActivityPredictor:
    """Loads the deployed model once; call predict_window() per full window."""

    def __init__(self, models_dir=MODELS_DIR):
        meta = json.loads((models_dir / "model_meta.json").read_text())
        cfg = meta["deployed"]["config"]
        arch = meta["deployed"]["arch"]
        if arch != "CNN":
            raise NotImplementedError(
                f"Deployed model arch is '{arch}'; only CNN inference is wired up in "
                "ml/inference/realtime.py. Re-run training or extend this loader."
            )
        self.model = ActivityCNN(NUM_CHANNELS, len(CLASSES), filters=tuple(cfg["filters"]),
                                  kernel_size=cfg["kernel_size"], dropout=cfg["dropout"])
        self.model.load_state_dict(torch.load(models_dir / "deployed_model.pt", map_location="cpu"))
        self.model.eval()
        self.scaler = ChannelScaler.load(models_dir / "scaler.json")

    def predict_window(self, window: np.ndarray) -> dict:
        """window: [WINDOW_LENGTH, NUM_CHANNELS] raw IMU units (Ax..Gz)."""
        x = self.scaler.transform(window[np.newaxis, ...].astype(np.float32))
        with torch.no_grad():
            logits = self.model(torch.from_numpy(x))
            probs = torch.softmax(logits, dim=1)[0].numpy()
        pred_idx = int(probs.argmax())
        return {
            "activity": CLASSES[pred_idx],
            "confidence": float(probs[pred_idx]),
            "fall_probability": float(probs[FALL_CLASS_IDX]),
            "tremor_probability": None,  # no tremor class trained in v1, see ml/config.py
            "probabilities": {c: float(p) for c, p in zip(CLASSES, probs)},
            "model_name": "CNN",
        }


class DeviceInferenceStream:
    """Per-device event-segment buffer + predictor. One instance per connected
    device_id. Uses EventSegmentBuffer (not a naive fixed sliding window) so
    live segmentation matches the whole-trial-resample transform the model
    was trained on -- see ml/segmentation/windowing.py docstring."""

    def __init__(self, predictor: ActivityPredictor):
        self.predictor = predictor
        self.buffer = EventSegmentBuffer()

    def push_sample(self, imu_sample) -> dict | None:
        """imu_sample: sequence [ax, ay, az, gx, gy, gz]. Returns a prediction
        dict once a motion event has been captured and classified, else None."""
        window = self.buffer.push(np.asarray(imu_sample, dtype=np.float32))
        if window is None:
            return None
        result = self.predictor.predict_window(window)
        result["window_raw"] = window
        result["inferred_at"] = time.time()
        return result
