"""Fall decision engine (live demo version).

Primary evidence is the rule-based state machine in ml/inference/motion_rules.py running on the continuous stream
(free-fall dip and/or large impact, then ~1 s of stillness). The event-triggered CNN (trained on BITS-2, a different
sensor placement) is supporting evidence only: its fall probability counts when it is >= FALL_PROBABILITY_THRESHOLD,
fresh (FALL_CNN_EVIDENCE_TTL_SECONDS) AND an impact > FALL_CNN_MIN_IMPACT m/s^2 happened in the last 2 s.

    confirmed_fall = rules confirmed  OR  (CNN prob >= threshold AND recent impact)
    fall_probability (stored) = max(CNN prob, rule score 0..1)

Heuristics tuned on synthetic data, not clinically validated. Tremor is handled separately (ml/inference/tremor.py).
"""

from __future__ import annotations

import time

from ml.config import FALL_CNN_EVIDENCE_TTL_SECONDS, FALL_CNN_MIN_IMPACT, FALL_PROBABILITY_THRESHOLD


class DecisionEngine:
    def __init__(self):
        self._cnn: dict[str, tuple[float, float]] = {}   # device -> (fall probability, time seen)

    def note_cnn(self, device_id: str, prediction: dict, now: float | None = None) -> None:
        self._cnn[device_id] = (prediction["fall_probability"], time.time() if now is None else now)

    def evaluate(self, device_id: str, motion: dict, now: float | None = None) -> dict:
        """motion: result dict from MotionClassifier. Returns the decision for this 1 Hz tick."""
        now = time.time() if now is None else now
        p, at = self._cnn.get(device_id, (0.0, 0.0))
        cnn_p = p if now - at <= FALL_CNN_EVIDENCE_TTL_SECONDS else 0.0
        impact = motion["features"]["peak_accel_2s"] >= FALL_CNN_MIN_IMPACT
        rules = motion["fall_state"] == "confirmed"
        cnn_candidate = cnn_p >= FALL_PROBABILITY_THRESHOLD
        confirmed = rules or (cnn_candidate and impact)
        return {
            "device_id": device_id,
            "confirmed_fall": confirmed,
            "fall_active": confirmed,                    # False -> ingest re-arms the alert
            "by_rules": rules,
            "ai_fall_candidate": cnn_candidate,
            "motion_verified": impact or rules,
            "cnn_fall_probability": cnn_p,
            "fall_probability": max(cnn_p, motion["fall_score"], 1.0 if confirmed else 0.0),
            "activity": "Fall" if confirmed else motion["activity"],
        }

    def reset(self, device_id: str) -> None:
        self._cnn.pop(device_id, None)
