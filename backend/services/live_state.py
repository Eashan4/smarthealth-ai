"""In-process live state: one predictor loaded once, one rolling-window
inference stream + decision engine state per connected device. Simple
module-level singletons are fine for a single-process Flask dev server
(this project's scope, see README tech stack); would need a shared store
(e.g. Redis) behind a multi-worker/multi-process deployment.
"""

from __future__ import annotations

from ml.inference.realtime import ActivityPredictor, DeviceInferenceStream

from .decision_engine import DecisionEngine

_predictor: ActivityPredictor | None = None
_streams: dict[str, DeviceInferenceStream] = {}
_decision_engine = DecisionEngine()
_alert_active: dict[str, bool] = {}


def get_predictor() -> ActivityPredictor:
    global _predictor
    if _predictor is None:
        _predictor = ActivityPredictor()
    return _predictor


def get_stream(device_id: str) -> DeviceInferenceStream:
    if device_id not in _streams:
        _streams[device_id] = DeviceInferenceStream(get_predictor())
    return _streams[device_id]


def get_decision_engine() -> DecisionEngine:
    return _decision_engine


def alert_already_active(device_id: str) -> bool:
    return _alert_active.get(device_id, False)


def set_alert_active(device_id: str, active: bool) -> None:
    _alert_active[device_id] = active


def reset_device(device_id: str) -> None:
    _streams.pop(device_id, None)
    _decision_engine.reset(device_id)
    _alert_active[device_id] = False
