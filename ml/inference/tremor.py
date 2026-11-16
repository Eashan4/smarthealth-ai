"""Tremor detection from the MPU6050 accelerometer AND gyro (spectral analysis, not a trained model).

Every 0.5 s, on a rolling 3 s window, per sensor (accel m/s^2, gyro rad/s): remove the mean (gravity / posture /
gyro bias), Hann window, FFT, then measure the 3-8 Hz band amplitude (rms), its share of the 2.5-15 Hz energy, how
sharp the peak is (share of band power within +-0.7 Hz of it), slow-motion energy (0.5-2.5 Hz), and whether the peak
is a harmonic of a gait fundamental (stronger peak at F/2 or F/3 in 1-2.8 Hz). Tremor = either sensor passes all gates.
Walking/running are rejected by the harmonic check + the amplitude cap, broadband noise by the peak sharpness,
stillness by the minimum amplitude. A short on/off debounce stops flicker. Thresholds live in ml/config.py.
"""

from __future__ import annotations

import time
from collections import deque

import numpy as np

from ml.config import (
    FS_ACCEPT_RANGE, FS_JITTER_TOLERANCE, IMU_SAMPLE_RATE, TREMOR_BAND_HZ, TREMOR_HARMONIC_FRAC,
    TREMOR_HOP_SECONDS, TREMOR_MAX_GYRO_RMS, TREMOR_MAX_LOW_TO_BAND_RMS, TREMOR_MAX_RMS,
    TREMOR_MIN_BAND_RATIO, TREMOR_MIN_GYRO_RMS, TREMOR_MIN_PEAK_FRAC, TREMOR_MIN_RMS, TREMOR_OFF_EVALS,
    TREMOR_ON_EVALS, TREMOR_PEAK_HALFWIDTH_HZ, TREMOR_STALE_SECONDS, TREMOR_WINDOW_SECONDS,
)

_TOTAL_BAND = (2.5, 15.0)   # excludes slow hand motion so it cannot mask a tremor; >15 Hz is mostly sensor noise (MPU6050 low-pass 21 Hz)
_LOW_BAND = (0.5, 2.5)      # voluntary movement / gait fundamental
_GAIT_BAND = (1.0, 2.8)     # where a gait fundamental (of a harmonic that lands in the tremor band) lives


def effective_fs(ts, nominal: float) -> float:
    """Sample rate over the WHOLE window. Serial lines arrive in bursts so per-sample jitter is meaningless; the
    window average is trusted only if it is clearly off nominal (a real slow stream), else nominal is used."""
    span = ts[-1] - ts[0] if len(ts) > 1 else 0.0
    if span <= 0:
        return nominal
    fs = (len(ts) - 1) / span
    if abs(fs - nominal) <= FS_JITTER_TOLERANCE * nominal:
        return nominal
    return fs if FS_ACCEPT_RANGE[0] * nominal <= fs <= FS_ACCEPT_RANGE[1] * nominal else nominal


def analyze(x: np.ndarray, fs: float) -> dict:
    """x: [N, 3] (accel m/s^2 or gyro rad/s) at rate fs. Returns raw (un-debounced) spectral measurements."""
    x = x - x.mean(axis=0)
    n = len(x)
    w = np.hanning(n)
    spec = np.fft.rfft(x * w[:, None], axis=0)
    freqs = np.fft.rfftfreq(n, 1.0 / fs)
    psd = (np.abs(spec) ** 2).sum(axis=1) / (fs * (w ** 2).sum())   # (unit)^2 / Hz, summed over axes
    psd[1:] *= 2                                                    # one-sided
    df = freqs[1] - freqs[0]

    def rms(lo, hi):
        return float(np.sqrt(psd[(freqs >= lo) & (freqs < hi)].sum() * df))

    band = (freqs >= TREMOR_BAND_HZ[0]) & (freqs < TREMOR_BAND_HZ[1])
    band_rms, total_rms, low_rms = rms(*TREMOR_BAND_HZ), rms(*_TOTAL_BAND), rms(*_LOW_BAND)
    band_psd = np.where(band, psd, 0.0)
    peak_i = int(band_psd.argmax())
    f0 = float(freqs[peak_i])
    near = band & (np.abs(freqs - f0) <= TREMOR_PEAK_HALFWIDTH_HZ)
    peak_frac = float(psd[near].sum() / psd[band].sum()) if psd[band].sum() > 0 else 0.0

    def around(f):   # strongest bin within +-0.3 Hz of f
        m = np.abs(freqs - f) <= 0.3
        return float(psd[m].max()) if m.any() else 0.0

    harmonic = any(_GAIT_BAND[0] <= f0 / k <= _GAIT_BAND[1] and around(f0 / k) >= TREMOR_HARMONIC_FRAC * psd[peak_i]
                   for k in (2, 3))
    return {"freq_hz": f0, "amplitude": band_rms, "band_ratio": (band_rms / total_rms) ** 2 if total_rms else 0.0,
            "peak_frac": peak_frac, "low_rms": low_rms, "harmonic": bool(harmonic)}


def looks_like_tremor(m: dict, lo: float = TREMOR_MIN_RMS, hi: float = TREMOR_MAX_RMS) -> bool:
    return (lo <= m["amplitude"] <= hi
            and m["band_ratio"] >= TREMOR_MIN_BAND_RATIO
            and m["peak_frac"] >= TREMOR_MIN_PEAK_FRAC
            and m["low_rms"] <= TREMOR_MAX_LOW_TO_BAND_RMS * m["amplitude"]
            and not m["harmonic"])


def _score(m: dict, lo: float) -> float:
    """0..1 rhythmic-ness x how far above the noise floor; 0 for gait harmonics."""
    return 0.0 if m["harmonic"] else round(m["peak_frac"] * min(1.0, m["amplitude"] / (2 * lo)), 2)


class TremorDetector:
    """One per device. push() every IMU sample; status() any time."""

    def __init__(self, fs: float = IMU_SAMPLE_RATE):
        self.nominal_fs = fs
        self.win = int(TREMOR_WINDOW_SECONDS * fs)
        self.hop = max(1, int(TREMOR_HOP_SECONDS * fs))
        self._acc: deque = deque(maxlen=self.win)
        self._gyr: deque = deque(maxlen=self.win)
        self._ts: deque = deque(maxlen=self.win)
        self._since_eval = 0
        self._on = self._off = 0
        self.detected = False
        self.last = None        # accel metrics (+ "gyro": gyro metrics, "score")
        self.last_push_at = 0.0

    def push(self, sample, ts: float | None = None) -> None:
        """sample: [ax, ay, az, gx, gy, gz]. ts: arrival time, used only for the window-average rate estimate."""
        self._acc.append(sample[:3])
        self._gyr.append(sample[3:6])
        self._ts.append(time.time() if ts is None else ts)
        self.last_push_at = time.time()
        self._since_eval += 1
        if len(self._acc) == self.win and self._since_eval >= self.hop:
            self._since_eval = 0
            self._evaluate()

    def _evaluate(self) -> None:
        fs = effective_fs(self._ts, self.nominal_fs)
        a = analyze(np.asarray(self._acc, dtype=np.float64), fs)
        g = analyze(np.asarray(self._gyr, dtype=np.float64), fs)
        sa, sg = _score(a, TREMOR_MIN_RMS), _score(g, TREMOR_MIN_GYRO_RMS)
        ok_a, ok_g = looks_like_tremor(a), looks_like_tremor(g, TREMOR_MIN_GYRO_RMS, TREMOR_MAX_GYRO_RMS)
        src = g if sg > sa else a            # report the frequency of the more tremor-like sensor
        self.last = {**a, "freq_hz": src["freq_hz"], "gyro": g, "score": max(sa, sg) if (ok_a or ok_g) else 0.0}
        if ok_a or ok_g:
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
        return {"state": "detected" if self.detected else "none",
                "freq_hz": round(self.last["freq_hz"], 2),
                "amplitude": round(self.last["amplitude"], 3),
                "gyro_amplitude": round(self.last["gyro"]["amplitude"], 3),
                "band_ratio": round(self.last["band_ratio"], 2),
                "score": self.last["score"]}
