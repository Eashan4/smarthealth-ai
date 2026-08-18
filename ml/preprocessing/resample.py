"""Shared resampling used by BOTH the offline BITS-2 trial loader (training)
and the real-time event-segment inference path -- must stay one function, not
reimplemented twice (PLAN.md engineering rule #2: preprocessing identical
between training and real-time inference).
"""

from __future__ import annotations

import numpy as np


def resample_to_window(signal: np.ndarray, target_len: int) -> np.ndarray:
    """Linearly resample an [N, C] signal onto a fixed [target_len, C] grid."""
    n = signal.shape[0]
    if n == target_len:
        return signal
    if n < 2:
        return np.repeat(signal, target_len, axis=0)[:target_len]
    src_idx = np.linspace(0.0, 1.0, num=n)
    dst_idx = np.linspace(0.0, 1.0, num=target_len)
    out = np.empty((target_len, signal.shape[1]), dtype=np.float32)
    for c in range(signal.shape[1]):
        out[:, c] = np.interp(dst_idx, src_idx, signal[:, c])
    return out
