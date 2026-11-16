"""In-process live state: one predictor loaded once, one rolling-window
inference stream + decision engine state per connected device. Simple
module-level singletons are fine for a single-process Flask dev server
(this project's scope, see README tech stack); would need a shared store
(e.g. Redis) behind a multi-worker/multi-process deployment.
"""

from __future__ import annotations

from ml.inference.motion_rules import MotionClassifier
from ml.inference.realtime import ActivityPredictor, DeviceInferenceStream
from ml.inference.tremor import TremorDetector

from .decision_engine import DecisionEngine

_predictor: ActivityPredictor | None = None
_streams: dict[str, DeviceInferenceStream] = {}
_decision_engine = DecisionEngine()
_alert_active: dict[str, bool] = {}
_tremor: dict[str, TremorDetector] = {}
_motion: dict[str, MotionClassifier] = {}


def get_predictor() -> ActivityPredictor:
    global _predictor
    if _predictor is None:
        _predictor = ActivityPredictor()
    return _predictor


def get_stream(device_id: str) -> DeviceInferenceStream:
    if device_id not in _streams:
        _streams[device_id] = DeviceInferenceStream(get_predictor())
    return _streams[device_id]


def get_tremor(device_id: str) -> TremorDetector:
    if device_id not in _tremor:
        _tremor[device_id] = TremorDetector()
    return _tremor[device_id]


def get_motion_classifier(device_id: str) -> MotionClassifier:
    if device_id not in _motion:
        _motion[device_id] = MotionClassifier()
    return _motion[device_id]


def get_motion(device_id: str) -> dict:
    """Latest rule-classifier result + tremor status (in memory, so inherently live). {"activity": None} if none yet."""
    last = _motion[device_id].status() if device_id in _motion else None
    if last is None:
        return {"activity": None}
    return {"activity": last["activity"], "confidence": last["confidence"], "features": last["features"],
            "fall_state": _motion[device_id].fall_state, "tremor": get_tremor(device_id).status()}


def get_decision_engine() -> DecisionEngine:
    return _decision_engine


def alert_already_active(device_id: str) -> bool:
    return _alert_active.get(device_id, False)


def set_alert_active(device_id: str, active: bool) -> None:
    _alert_active[device_id] = active


def reset_device(device_id: str) -> None:
    _streams.pop(device_id, None)
    _tremor.pop(device_id, None)
    _motion.pop(device_id, None)
    _decision_engine.reset(device_id)
    _alert_active[device_id] = False
