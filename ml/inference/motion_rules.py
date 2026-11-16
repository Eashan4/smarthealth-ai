"""Continuous, orientation-independent rule-based activity + fall detection for the live demo.

Replaces "classify only after a motion event closes" (CNN, trained on another sensor placement) with a rolling
2.5 s window evaluated at 1 Hz. Only |accel| (m/s^2), |gyro| (rad/s) and the dominant frequency of |accel| are used,
so the board can be held / strapped in any orientation.

  Still (|a| std and gyro small) -> Sitting. If a calibrated rest gravity is supplied, the tilt of the current
        gravity vs it picks Sitting (<30 deg) / Standing (30-60) / Lying (>=60). Without calibration the board's
        orientation is unknown, so every still state is "Resting" reported as Sitting. Heuristic, not validated.
  Walking  -> dominant |a| frequency 1.2-2.6 Hz (step cadence), enough energy, rhythmic.
  Running  -> cadence > 2.6 Hz (up to 4 Hz) with high energy, or huge energy at any gait cadence.
  Moving but not rhythmic / shaking / tremor flag -> "Standing" (active, not locomotion). A 4-6 Hz hand shake is
        above the 4 Hz cadence cap, and the tremor flag vetoes Walking/Running outright.
  Fall -> per-sample state machine idle -> freefall -> impact -> confirming -> confirmed (see ml/config.py).
        Needs a free-fall dip + impact (or a very large impact) followed by ~1 s of stillness, so a vigorous shake
        or running (no stillness) and a drop that keeps moving never confirm.
Labels are debounced (a new label must win MOTION_SWITCH_EVALS consecutive evaluations); Fall is immediate.
All thresholds are in ml/config.py (see docs/DEMO_TUNING.md).
"""

from __future__ import annotations

import time
from collections import deque

import numpy as np

from ml.config import *  # noqa: F403  (thresholds only)
from ml.inference.tremor import effective_fs

GRAVITY = 9.81


class MotionClassifier:
    """One per device. push() every sample; it returns a result dict about once a second (and at once when a
    fall is confirmed), else None. status() returns the last result."""

    def __init__(self, fs: float = IMU_SAMPLE_RATE):
        self.nominal_fs = self.fs = fs
        n = int(MOTION_WINDOW_SECONDS * fs)
        self._acc, self._gyr, self._ts = deque(maxlen=n), deque(maxlen=n), deque(maxlen=n)
        self._mag = deque(maxlen=int(3 * fs))
        self._since_eval = 0
        self._n = 0                            # samples seen (the fall clock)
        self.rest_gravity = None               # calibrated gravity vector (board axes), optional
        self.tremor = False                    # set by the caller from the tremor detector
        self.fall_state = "idle"
        self._ff_run = 0
        self._t_ff = self._t_imp = self._t_conf = 0
        self._label, self._cand, self._cand_n, self._conf = None, None, 0, 0.0
        self.last = None

    # ---- fall state machine (per sample, on |accel|) ----
    def _sec(self, s: float) -> int:
        return max(1, int(s * self.fs))

    def _std_last(self, seconds: float) -> float | None:
        k = self._sec(seconds)
        return float(np.std(list(self._mag)[-k:])) if len(self._mag) >= k else None

    def _fall_step(self, m: float) -> None:
        n, st = self._n, self.fall_state
        self._ff_run = self._ff_run + 1 if m < FREEFALL_MAG else 0
        if st == "idle":
            if self._ff_run >= self._sec(FREEFALL_MIN_SECONDS):
                self.fall_state, self._t_ff, st = "freefall", n, "freefall"
            elif m >= FALL_IMPACT_ONLY_MAG:
                self.fall_state, self._t_imp = "impact", n
        if st == "freefall":
            if m < FREEFALL_MAG:
                self._t_ff = n
                if self._ff_run >= self._sec(FREEFALL_MAX_SECONDS):
                    self.fall_state = "idle"
            elif m >= FALL_IMPACT_AFTER_FREEFALL_MAG:
                self.fall_state, self._t_imp = "impact", n
            elif n - self._t_ff > self._sec(FREEFALL_TO_IMPACT_SECONDS):
                self.fall_state = "idle"
        elif st in ("impact", "confirming"):
            t = n - self._t_imp
            self.fall_state = "impact" if t < self._sec(FALL_SETTLE_SECONDS) else "confirming"
            if t >= self._sec(FALL_SETTLE_SECONDS + FALL_STILL_SECONDS):
                s = self._std_last(FALL_STILL_SECONDS)
                if s is not None and s < FALL_STILL_STD:
                    self.fall_state, self._t_conf = "confirmed", n
                elif t > self._sec(FALL_STILL_DEADLINE_SECONDS + FALL_STILL_SECONDS):
                    self.fall_state = "idle"
        elif st == "confirmed":
            t = n - self._t_conf
            s = self._std_last(0.5)
            if t > self._sec(FALL_HOLD_SECONDS) or (t > self._sec(1.0) and s is not None and s > FALL_REARM_STD):
                self.fall_state, self._ff_run = "idle", 0

    # ---- features -> label ----
    def _dom_freq(self, mag: np.ndarray) -> tuple[float, float]:
        x = (mag - mag.mean()) * np.hanning(len(mag))
        nfft = 512
        p = np.abs(np.fft.rfft(x, nfft)) ** 2
        f = np.fft.rfftfreq(nfft, 1.0 / self.fs)
        band = (f >= MOTION_FREQ_BAND_HZ[0]) & (f <= MOTION_FREQ_BAND_HZ[1])
        if p[band].sum() <= 1e-9:
            return 0.0, 0.0
        i = int(np.where(band, p, 0).argmax())
        f0 = float(f[i])
        if 3.0 <= f0 <= 5.2:                   # step impacts can make the 2nd harmonic dominate: use the fundamental
            h = np.abs(f - f0 / 2) <= 0.3
            if p[h].max() >= SUBHARMONIC_FRAC * p[i]:
                j = int(np.where(h, p, 0).argmax())
                f0, i = float(f[j]), j
        near = band & (np.min([np.abs(f - k * f0) for k in (1, 2, 3)], axis=0) <= 0.5)   # fundamental + harmonics
        frac = float(p[near].sum() / p[band].sum())
        return f0, frac

    def _tilt(self, acc: np.ndarray) -> float | None:
        if self.rest_gravity is None:
            return None
        g, r = acc.mean(axis=0), np.asarray(self.rest_gravity, dtype=float)
        d = np.linalg.norm(g) * np.linalg.norm(r)
        return float(np.degrees(np.arccos(np.clip(g @ r / d, -1, 1)))) if d > 0 else None

    def _classify(self, std, gyro, f, frac, tilt) -> tuple[str, float]:
        if std < MOTION_STILL_STD and gyro < MOTION_STILL_GYRO:
            sure = 0.9 if std < MOTION_STILL_STD / 2 else 0.75
            if tilt is None:
                return "Sitting", sure * 0.7                        # "Resting": orientation unknown
            return ("Sitting" if tilt < TILT_UPRIGHT_MAX_DEG else "Lying" if tilt >= TILT_LYING_MIN_DEG
                    else "Standing"), sure
        gait = (not self.tremor and f <= RUN_MAX_CADENCE_HZ and frac >= LOCO_MIN_PEAK_FRAC
                and f >= WALK_FREQ_HZ[0] and std >= WALK_MIN_STD)
        conf = min(1.0, 0.5 + 0.5 * frac / 0.6)
        if gait and (std >= RUN_ANY_CADENCE_STD or (f > WALK_FREQ_HZ[1] and std >= RUN_MIN_STD)):
            return "Running", conf
        if gait and f <= WALK_FREQ_HZ[1]:
            return "Walking", conf
        return "Standing", 0.6                                      # active but not locomotion (fidget, shake, tremor)

    def _evaluate(self) -> dict:
        acc, gyr = np.asarray(self._acc, float), np.asarray(self._gyr, float)
        self.fs = effective_fs(self._ts, self.nominal_fs)
        mag, gmag = np.linalg.norm(acc, axis=1), np.linalg.norm(gyr, axis=1)
        std, tilt = float(mag.std()), self._tilt(acc)
        f, frac = self._dom_freq(mag)
        gyro = float(np.sqrt((gmag ** 2).mean()))
        raw, conf = self._classify(std, gyro, f, frac, tilt)
        if self.fall_state == "confirmed":
            label, self._conf, self._cand, self._cand_n = "Fall", 0.95, None, 0
        elif self._label in (None, "Fall"):
            label, self._conf = raw, conf
        elif raw == self._label:
            label, self._conf, self._cand, self._cand_n = raw, conf, None, 0
        else:
            self._cand_n = self._cand_n + 1 if raw == self._cand else 1
            self._cand = raw
            label = self._label
            if self._cand_n >= MOTION_SWITCH_EVALS:
                label, self._conf, self._cand, self._cand_n = raw, conf, None, 0
        self._label = label
        k = self._sec(FALL_CNN_IMPACT_LOOKBACK_SECONDS)
        feats = {"accel_mean": round(float(mag.mean()), 2), "accel_std": round(std, 2),
                 "dom_freq_hz": round(f, 2), "peak_frac": round(frac, 2), "gyro_rms": round(gyro, 3),
                 "peak_accel_2s": round(float(max(list(self._mag)[-k:])), 1),
                 "tilt_deg": None if tilt is None else round(tilt, 1), "tremor": self.tremor,
                 "fall_state": self.fall_state, "fs_hz": round(self.fs, 1)}
        self.last = {"activity": label, "confidence": round(self._conf, 2), "features": feats,
                     "fall_state": self.fall_state, "fall_score": FALL_STATE_SCORE[self.fall_state]}
        return self.last

    def push(self, sample, ts: float | None = None) -> dict | None:
        """sample: [ax, ay, az, gx, gy, gz] (calibrated). ts: arrival time (window-average rate only)."""
        self._acc.append(sample[:3])
        self._gyr.append(sample[3:6])
        self._ts.append(time.time() if ts is None else ts)
        m = float(np.linalg.norm(sample[:3]))
        self._mag.append(m)
        self._n += 1
        self._since_eval += 1
        before = self.fall_state
        self._fall_step(m)
        just_confirmed = self.fall_state == "confirmed" and before != "confirmed"
        if len(self._acc) >= self._sec(MOTION_MIN_SECONDS) and (
                self._since_eval >= self._sec(MOTION_HOP_SECONDS) or just_confirmed):
            self._since_eval = 0
            return self._evaluate()
        return None

    def status(self) -> dict | None:
        return self.last
