"""Sensor payload validation, per docs/DOCUMENTATION.md sec 11/13: never
trust a payload blindly -- validate required fields/types before use."""

from __future__ import annotations

REQUIRED_IMU_FIELDS = ("ax", "ay", "az", "gx", "gy", "gz")


class PayloadValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _require_type(value, types, field_name):
    if not isinstance(value, types) or isinstance(value, bool):
        raise PayloadValidationError(f"Field '{field_name}' must be a number, got {type(value).__name__}")


def validate_sensor_payload(payload) -> dict:
    if not isinstance(payload, dict):
        raise PayloadValidationError("Request body must be a JSON object")

    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise PayloadValidationError("Field 'device_id' is required and must be a non-empty string")

    timestamp = payload.get("timestamp")
    _require_type(timestamp, (int, float), "timestamp")

    imu = payload.get("imu")
    if not isinstance(imu, dict):
        raise PayloadValidationError("Field 'imu' is required and must be an object")
    for f in REQUIRED_IMU_FIELDS:
        if f not in imu:
            raise PayloadValidationError(f"Field 'imu.{f}' is required")
        _require_type(imu[f], (int, float), f"imu.{f}")

    heart_rate = spo2 = None
    vitals = payload.get("vitals")
    if vitals is not None:
        if not isinstance(vitals, dict):
            raise PayloadValidationError("Field 'vitals' must be an object if present")
        if "heart_rate" in vitals and vitals["heart_rate"] is not None:
            _require_type(vitals["heart_rate"], (int, float), "vitals.heart_rate")
            heart_rate = float(vitals["heart_rate"])
        if "spo2" in vitals and vitals["spo2"] is not None:
            _require_type(vitals["spo2"], (int, float), "vitals.spo2")
            spo2 = float(vitals["spo2"])

    return {
        "device_id": device_id,
        "timestamp": float(timestamp),
        "imu": {f: float(imu[f]) for f in REQUIRED_IMU_FIELDS},
        "heart_rate": heart_rate,
        "spo2": spo2,
    }
