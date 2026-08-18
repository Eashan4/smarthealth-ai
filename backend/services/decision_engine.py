"""Phase 8 -- fall decision engine: AI probability + rule verification +
debouncing -> confirmed fall event.

Design note (deviation from the naive "AI AND rule" baseline sketch in
docs/PLAN.md, evaluated and documented per that plan's own rule that changes
must be justified against measured results, not made ad hoc):

ml/evaluation/threshold_analysis.py measured, on real BITS-2 trials, that the
tuned AI fall-probability threshold (0.466) already reaches precision=1.00 /
recall=0.917 on the held-out validation set by itself, while requiring the
rule-based acceleration check (95th-percentile ADL peak) as a hard AND-gate
would only catch 54% of true fall trials (many real falls in this dataset --
e.g. a controlled fall onto a bed -- never exceed that peak). Gating
confirmation on AI-AND-rule would therefore roughly halve measured fall
recall for no precision gain the data supports.

So here: CONFIRMED fall = AI probability over threshold, sustained for
ALERT_DEBOUNCE_WINDOWS consecutive windows (debounce). The rule-based
acceleration/inactivity checks are still computed and attached to every
result as `motion_verified` / `post_fall_inactivity_detected` -- surfaced on
the dashboard and logged with the alert for explainability/audit, not used
to suppress a confirmed AI detection. Revisit this balance once Phase 2
custom hardware data is available (see docs/DOCUMENTATION.md sec 16).

Tremor: BITS-2 has no tremor-like class (see ml/config.py CLASSES), so
tremor detection is not implemented in v1 -- `tremor_probability` is always
reported as None. Documented as a known limitation, not silently omitted.

Debouncing note (second deviation from the PLAN.md baseline sketch, also
forced by the event-triggered redesign in ml/segmentation/windowing.py):
the original sketch debounces across N *consecutive overlapping windows* of
a continuous stream. With EventSegmentBuffer, one real motion event yields
exactly one captured segment and one classification -- there are no
overlapping windows of the same event to require agreement across. So
confirmation here is per-event (single-event AI threshold + attached rule
signals), not cross-event-consecutive. ALERT_DEBOUNCE_WINDOWS is kept as a
lightweight cooldown instead: it suppresses re-firing a *new* alert for a
device that already has one active, rather than requiring repeated events.
"""

from __future__ import annotations

import numpy as np

from ml.config import (
    ACCELERATION_THRESHOLD,
    FALL_PROBABILITY_THRESHOLD,
    IMU_SAMPLE_RATE,
    POST_FALL_INACTIVITY_SECONDS,
)

_INACTIVITY_STD_THRESHOLD = 2.0  # m/s^2, "low motion" band width around rest


class DecisionEngine:
    def evaluate(self, device_id: str, prediction: dict, raw_window: np.ndarray) -> dict:
        accel_mag = np.linalg.norm(raw_window[:, :3], axis=1)
        peak_accel = float(accel_mag.max())
        motion_verified = peak_accel >= ACCELERATION_THRESHOLD

        tail_len = max(1, int(POST_FALL_INACTIVITY_SECONDS * IMU_SAMPLE_RATE))
        tail = accel_mag[-tail_len:]
        post_fall_inactivity_detected = bool(tail.std() < _INACTIVITY_STD_THRESHOLD)

        ai_candidate = prediction["fall_probability"] >= FALL_PROBABILITY_THRESHOLD

        return {
            "device_id": device_id,
            "ai_fall_candidate": ai_candidate,
            "motion_verified": motion_verified,
            "peak_acceleration": peak_accel,
            "post_fall_inactivity_detected": post_fall_inactivity_detected,
            "confirmed_fall": ai_candidate,
            "tremor_probability": None,  # not trained in v1, see module docstring
        }

    def reset(self, device_id: str) -> None:
        pass
