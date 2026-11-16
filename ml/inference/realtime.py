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
from ml.lstm.model import ActivityLSTM
from ml.preprocessing.normalize import ChannelScaler
from ml.segmentation.windowing import EventSegmentBuffer


class ActivityPredictor:
    """Loads one trained model once; call predict_window() per full window.
    which="deployed" -> the CNN, which="comparison" -> the LSTM it is compared against."""

    def __init__(self, models_dir=MODELS_DIR, which: str = "deployed"):
        meta = json.loads((models_dir / "model_meta.json").read_text())[which]
        cfg, self.model_name = meta["config"], meta["arch"]
        if self.model_name == "CNN":
            self.model = ActivityCNN(NUM_CHANNELS, len(CLASSES), filters=tuple(cfg["filters"]),
                                      kernel_size=cfg["kernel_size"], dropout=cfg["dropout"])
        elif self.model_name == "LSTM":
            self.model = ActivityLSTM(NUM_CHANNELS, len(CLASSES), hidden_size=cfg["hidden_size"],
                                       num_layers=cfg["num_layers"], dropout=cfg["dropout"])
        else:
            raise NotImplementedError(f"Unsupported model arch '{self.model_name}' in ml/inference/realtime.py")
        weights = "deployed_model.pt" if which == "deployed" else "comparison_model.pt"
        self.model.load_state_dict(torch.load(models_dir / weights, map_location="cpu"))
        self.model.eval()
        self.scaler = ChannelScaler.load(models_dir / "scaler.json")

    def predict_window(self, window: np.ndarray) -> dict:
        """window: [WINDOW_LENGTH, NUM_CHANNELS] raw IMU units (Ax..Gz)."""
        x = self.scaler.transform(window[np.newaxis, ...].astype(np.float32))
        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(torch.from_numpy(x))
            probs = torch.softmax(logits, dim=1)[0].numpy()
        latency_ms = (time.perf_counter() - t0) * 1000
        pred_idx = int(probs.argmax())
        return {
            "activity": CLASSES[pred_idx],
            "confidence": float(probs[pred_idx]),
            "fall_probability": float(probs[FALL_CLASS_IDX]),
            "tremor_probability": None,  # no tremor class trained in v1, see ml/config.py
            "probabilities": {c: float(p) for c, p in zip(CLASSES, probs)},
            "model_name": self.model_name,
            "latency_ms": latency_ms,
        }


class DeviceInferenceStream:
    """Per-device event-segment buffer + predictor. One instance per connected
    device_id. Uses EventSegmentBuffer (not a naive fixed sliding window) so
    live segmentation matches the whole-trial-resample transform the model
    was trained on -- see ml/segmentation/windowing.py docstring."""

    def __init__(self, predictor: ActivityPredictor, comparison: ActivityPredictor | None = None):
        self.predictor = predictor
        self.comparison = comparison   # optional second model run on the very same window (CNN vs LSTM)
        self.buffer = EventSegmentBuffer()

    def push_sample(self, imu_sample) -> dict | None:
        """imu_sample: sequence [ax, ay, az, gx, gy, gz]. Returns a prediction
        dict once a motion event has been captured and classified, else None."""
        window = self.buffer.push(np.asarray(imu_sample, dtype=np.float32))
        if window is None:
            return None
        result = self.predictor.predict_window(window)
        result["window_raw"] = window
        if self.comparison is not None:
            result["comparison"] = self.comparison.predict_window(window)
        result["inferred_at"] = time.time()
        return result
