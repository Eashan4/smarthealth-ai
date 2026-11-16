"""Gyro calibration + live IMU feed endpoints."""

from __future__ import annotations

import math

from flask import Blueprint, jsonify, request

from backend.services import calibration, imu_live

calibration_bp = Blueprint("calibration", __name__)


def _device(src):
    d = src.get("device_id")
    if d is None:
        return "wearable_01"
    return d.strip() if isinstance(d, str) and d.strip() else None


def _body():
    b = request.get_json(silent=True)
    return {} if b is None and not request.data else b


def _bad(msg):
    return jsonify({"error": msg}), 400


@calibration_bp.route("/api/calibrate/gyro", methods=["POST"])
def calibrate_gyro():
    b = _body()
    if not isinstance(b, dict):
        return _bad("JSON object body expected")
    dev, secs = _device(b), b.get("seconds", 2.0)
    if dev is None:
        return _bad("'device_id' must be a non-empty string")
    if isinstance(secs, bool) or not isinstance(secs, (int, float)) or not (1 <= secs <= 5) or math.isnan(secs):
        return _bad("'seconds' must be a number between 1 and 5")
    if not calibration.start(dev, secs):
        return jsonify({**calibration.status(dev), "error": "calibration already running"}), 409
    return jsonify(calibration.status(dev)), 202


@calibration_bp.route("/api/calibration", methods=["GET"])
def get_calibration():
    dev = _device(request.args)
    return jsonify(calibration.status(dev)) if dev else _bad("'device_id' must be a non-empty string")


@calibration_bp.route("/api/calibrate/reset", methods=["POST"])
def reset_calibration():
    b = _body()
    dev = _device(b) if isinstance(b, dict) else None
    if dev is None:
        return _bad("JSON body with a non-empty string 'device_id' expected")
    calibration.reset(dev)
    return jsonify(calibration.status(dev))


@calibration_bp.route("/api/imu", methods=["GET"])
def get_imu():
    dev = _device(request.args)
    try:
        n = int(request.args.get("n", 100))
    except ValueError:
        n = 0
    if dev is None or not 1 <= n <= 250:
        return _bad("'device_id' must be a non-empty string and 'n' an integer 1..250")
    return jsonify(imu_live.snapshot(dev, n))
