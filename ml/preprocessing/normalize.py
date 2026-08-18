"""Per-channel normalization, fit on training data only (no leakage, see
docs/DOCUMENTATION.md sec 10). Shared between training and real-time
inference so the exact same transform is applied in both paths.
"""

from __future__ import annotations

import json

import numpy as np


class ChannelScaler:
    """Standardizes each of the NUM_CHANNELS axes independently."""

    def __init__(self):
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None

    def fit(self, X: np.ndarray) -> "ChannelScaler":
        # X: [N, T, C] -- compute mean/std per channel over all N*T samples.
        flat = X.reshape(-1, X.shape[-1])
        self.mean_ = flat.mean(axis=0)
        self.std_ = flat.std(axis=0)
        self.std_[self.std_ < 1e-8] = 1e-8
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean_ is None:
            raise RuntimeError("ChannelScaler.fit() must be called before transform()")
        return (X - self.mean_) / self.std_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)

    def save(self, path) -> None:
        with open(path, "w") as fh:
            json.dump({"mean": self.mean_.tolist(), "std": self.std_.tolist()}, fh)

    @classmethod
    def load(cls, path) -> "ChannelScaler":
        with open(path) as fh:
            d = json.load(fh)
        s = cls()
        s.mean_ = np.array(d["mean"], dtype=np.float32)
        s.std_ = np.array(d["std"], dtype=np.float32)
        return s
