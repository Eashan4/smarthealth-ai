"""Tremor detection from the MPU6050 accelerometer (spectral analysis, not a trained model).

How it works: keep a rolling ~3 s window of accelerometer samples; every 0.5 s remove the mean (gravity /
posture), apply a Hann window, FFT, and measure
  - amplitude of the 3-8 Hz tremor band (RMS in m/s^2),
  - how much of the total (0.5-15 Hz) energy sits in that band,
  - whether there is a sharp spectral peak in the band (rhythmic) vs broadband noise,
  - how large slow voluntary motion (0.5-2.5 Hz) is compared with the tremor.
Walking/running are rejected because their large low-frequency motion dominates; plain stillness is
rejected by the minimum amplitude. A short on/off debounce stops flicker.
Thresholds live in ml/config.py.
"""

from __future__ import annotations

import time
from collections import deque

import numpy as np

from ml.config import (
    IMU_SAMPLE_RATE,
    TREMOR_BAND_HZ,
    TREMOR_HOP_SECONDS,
    TREMOR_MAX_LOW_TO_BAND_RMS,
    TREMOR_MIN_BAND_RATIO,
    TREMOR_MIN_PEAK_RATIO,
    TREMOR_MIN_RMS,
    TREMOR_OFF_EVALS,
    TREMOR_ON_EVALS,
    TREMOR_STALE_SECONDS,
    TREMOR_WINDOW_SECONDS,
)

_TOTAL_BAND = (0.5, 15.0)   # above ~15 Hz is mostly sensor noise (the MPU6050 low-pass is 21 Hz)
_LOW_BAND = (0.5, 2.5)      # voluntary movement / gait fundamental


def analyze(accel: np.ndarray, fs: float) -> dict:
    """accel: [N, 3] m/s^2 at sample rate fs. Returns the raw (un-debounced) spectral measurements."""
    x = accel - accel.mean(axis=0)                       # remove gravity / constant posture
    n = len(x)
    w = np.hanning(n)
    spec = np.fft.rfft(x * w[:, None], axis=0)
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    psd = (np.abs(spec) ** 2).sum(axis=1) / (fs * (w ** 2).sum())   # (m/s^2)^2 / Hz, summed over axes
    psd[1:] *= 2                                                    # one-sided
    df = freqs[1] - freqs[0]

    def rms(lo, hi):
        m = (freqs >= lo) & (freqs < hi)
        return float(np.sqrt(psd[m].sum() * df)), m

    band_rms, band_mask = rms(*TREMOR_BAND_HZ)
    total_rms, total_mask = rms(*_TOTAL_BAND)
    low_rms, _ = rms(*_LOW_BAND)
    band_ratio = (band_rms / total_rms) ** 2 if total_rms > 0 else 0.0

    band_psd = np.where(band_mask, psd, 0.0)
    peak_i = int(band_psd.argmax())
    median = float(np.median(psd[total_mask])) or 1e-12
    peak_ratio = float(psd[peak_i] / median)
    return {
        "freq_hz": float(freqs[peak_i]),
        "amplitude": band_rms,
        "band_ratio": band_ratio,
        "peak_ratio": peak_ratio,
        "low_rms": low_rms,
    }


def looks_like_tremor(m: dict) -> bool:
    return (
        m["amplitude"] >= TREMOR_MIN_RMS
        and m["band_ratio"] >= TREMOR_MIN_BAND_RATIO
        and m["peak_ratio"] >= TREMOR_MIN_PEAK_RATIO
        and m["low_rms"] <= TREMOR_MAX_LOW_TO_BAND_RMS * m["amplitude"]
    )


class TremorDetector:
    """One per device. push() every IMU sample; status() any time."""

    def __init__(self, fs: float = IMU_SAMPLE_RATE):
        self.nominal_fs = fs
        self.win = int(TREMOR_WINDOW_SECONDS * fs)
        self.hop = max(1, int(TREMOR_HOP_SECONDS * fs))
        self._acc: deque = deque(maxlen=self.win)
        self._ts: deque = deque(maxlen=self.win)
        self._since_eval = 0
        self._on = self._off = 0
        self.detected = False
        self.last = None
        self.last_push_at = 0.0

    def push(self, sample, ts: float | None = None) -> None:
        """sample: [ax, ay, az, gx, gy, gz] (only the accelerometer is used). ts: arrival time, used only to
        measure the real sample rate so the reported frequency stays right if the stream runs slow."""
        self._acc.append(sample[:3])
        self._ts.append(time.time() if ts is None else ts)
        self.last_push_at = time.time()
        self._since_eval += 1
        if len(self._acc) == self.win and self._since_eval >= self.hop:
            self._since_eval = 0
            self._evaluate()

    def _fs(self) -> float:
        span = self._ts[-1] - self._ts[0]
        fs = (len(self._ts) - 1) / span if span > 0 else self.nominal_fs
        return fs if 0.6 * self.nominal_fs <= fs <= 1.4 * self.nominal_fs else self.nominal_fs

    def _evaluate(self) -> None:
        m = analyze(np.asarray(self._acc, dtype=np.float64), self._fs())
        self.last = m
        if looks_like_tremor(m):
            self._on, self._off = self._on + 1, 0
            if self._on >= TREMOR_ON_EVALS:
                self.detected = True
        else:
            self._off, self._on = self._off + 1, 0
            if self._off >= TREMOR_OFF_EVALS:
                self.detected = False

    def status(self) -> dict:
        if time.time() - self.last_push_at > TREMOR_STALE_SECONDS:
            return {"state": "no_data"}
        if self.last is None:
            return {"state": "warming_up"}
        out = {"state": "detected" if self.detected else "none",
               "freq_hz": round(self.last["freq_hz"], 2),
               "amplitude": round(self.last["amplitude"], 3),
               "band_ratio": round(self.last["band_ratio"], 2)}
        return out
