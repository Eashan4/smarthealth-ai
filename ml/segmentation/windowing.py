"""Window segmentation for sensor streams.

Two strategies live here:

1. EventSegmentBuffer -- what the v1 deployed model actually needs. The
   BITS-2 training data (ml/datasets/bits2_adapter.py) is built from whole,
   discrete activity/fall TRIALS (each a few seconds long) resampled onto a
   fixed WINDOW_LENGTH grid -- not fixed-duration slices of a continuous
   stream. A naive fixed-length rolling window over a live continuous stream
   is therefore a *different transform* than what the model was trained on,
   which would silently violate PLAN.md engineering rule #2 ("preprocessing
   identical between training and real-time inference"). This was caught by
   running the fake-ESP32 end-to-end test (tests/fake_esp32_sender.py)
   against a real fall trial and seeing the live prediction disagree sharply
   with the offline evaluation on the same data.
   EventSegmentBuffer instead detects a motion event (onset/offset around a
   near-rest acceleration band) in the live stream, then resamples the
   captured raw segment with the exact same ml.preprocessing.resample
   function used at training time -- so both paths do the same transform.

2. sliding_windows() / RollingBuffer -- fixed-duration continuous-stream
   segmentation, matching PLAN.md's original baseline sketch. NOT used by
   the current v1 event-classifier pipeline. Kept for a future model
   version trained on genuinely continuous multi-minute recordings (e.g.
   from Phase 2 custom data collection), at which point it would become the
   correct approach instead of event-triggering. See
   docs/DOCUMENTATION.md sec 15 for this documented deviation.
"""

from __future__ import annotations

import numpy as np

from ml.config import (
    EVENT_MAX_SAMPLES,
    EVENT_MIN_SAMPLES,
    EVENT_OFFSET_HOLD_SAMPLES,
    EVENT_ONSET_ACCEL_DELTA,
    WINDOW_LENGTH,
    WINDOW_OVERLAP,
)
from ml.preprocessing.resample import resample_to_window

_REST_MAGNITUDE = 9.8  # m/s^2, standard gravity -- accelerometer at rest


def sliding_windows(stream: np.ndarray, window_length: int = WINDOW_LENGTH,
                     overlap: float = WINDOW_OVERLAP) -> np.ndarray:
    """Segment a [T, C] continuous stream into overlapping fixed windows.
    See module docstring -- not used by the v1 pipeline."""
    step = max(1, int(round(window_length * (1 - overlap))))
    n_samples = stream.shape[0]
    starts = range(0, n_samples - window_length + 1, step)
    windows = np.stack([stream[s:s + window_length] for s in starts]) if starts else np.empty((0, window_length, stream.shape[1]))
    return windows.astype(np.float32)


class RollingBuffer:
    """Fixed-capacity sliding buffer for sliding_windows()-equivalent live
    segmentation. See module docstring -- not used by the v1 pipeline."""

    def __init__(self, window_length: int = WINDOW_LENGTH, overlap: float = WINDOW_OVERLAP,
                 num_channels: int = 6):
        self.window_length = window_length
        self.step = max(1, int(round(window_length * (1 - overlap))))
        self.num_channels = num_channels
        self._buf: list[np.ndarray] = []

    def push(self, sample: np.ndarray) -> np.ndarray | None:
        self._buf.append(np.asarray(sample, dtype=np.float32))
        if len(self._buf) < self.window_length:
            return None
        if (len(self._buf) - self.window_length) % self.step != 0:
            return None
        window = np.stack(self._buf[-self.window_length:])
        if len(self._buf) > self.window_length + self.step:
            self._buf = self._buf[-(self.window_length + self.step):]
        return window


class EventSegmentBuffer:
    """Onset/offset motion-event segmentation for the live IMU stream,
    matching the BITS-2 whole-trial-resample training transform.

    Feed raw [ax, ay, az, gx, gy, gz] samples at whatever native rate the
    device sends (does not need to be exactly IMU_SAMPLE_RATE). While near
    rest, samples are held in a small lookback buffer (so the emitted
    segment includes a bit of pre-onset context, like a real trial
    recording). Once accel magnitude deviates from rest by more than
    EVENT_ONSET_ACCEL_DELTA, a segment starts accumulating; it closes -- and
    is resampled to WINDOW_LENGTH and returned -- once accel returns near
    rest for EVENT_OFFSET_HOLD_SAMPLES consecutive samples, or after
    EVENT_MAX_SAMPLES (whichever first).

    Onset/offset thresholds are heuristic segmentation triggers, not the
    classification-relevant ACCELERATION_THRESHOLD (that one *is*
    experimentally derived, see ml/evaluation/threshold_analysis.py and
    ml/config.py) -- documented as such, not silently conflated.
    """

    def __init__(self, num_channels: int = 6, lookback: int = 5):
        self.num_channels = num_channels
        self.lookback = lookback
        self._pre_buf: list[np.ndarray] = []
        self._event: list[np.ndarray] | None = None
        self._rest_run = 0

    def _accel_mag(self, sample: np.ndarray) -> float:
        return float(np.linalg.norm(sample[:3]))

    def push(self, sample: np.ndarray) -> np.ndarray | None:
        sample = np.asarray(sample, dtype=np.float32)
        mag = self._accel_mag(sample)
        moving = abs(mag - _REST_MAGNITUDE) > EVENT_ONSET_ACCEL_DELTA

        if self._event is None:
            self._pre_buf.append(sample)
            if len(self._pre_buf) > self.lookback:
                self._pre_buf.pop(0)
            if moving:
                self._event = list(self._pre_buf)
                self._rest_run = 0
            return None

        self._event.append(sample)
        if moving:
            self._rest_run = 0
        else:
            self._rest_run += 1

        should_close = self._rest_run >= EVENT_OFFSET_HOLD_SAMPLES or len(self._event) >= EVENT_MAX_SAMPLES
        if not should_close:
            return None

        segment = np.stack(self._event)
        self._event = None
        self._pre_buf = []
        self._rest_run = 0
        if segment.shape[0] < EVENT_MIN_SAMPLES:
            return None
        return resample_to_window(segment, WINDOW_LENGTH)
