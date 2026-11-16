"""USB-serial control endpoints used by the dashboard's port selector."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.services.serial_bridge import BridgeError, bridge, list_serial_ports

serial_bp = Blueprint("serial", __name__)


@serial_bp.route("/api/serial/ports", methods=["GET"])
def ports():
    return jsonify({"ports": list_serial_ports()})


@serial_bp.route("/api/serial/status", methods=["GET"])
def status():
    return jsonify(bridge.status())


@serial_bp.route("/api/serial/connect", methods=["POST"])
def connect():
    body = request.get_json(silent=True) or {}
    port, device_id = body.get("port"), (body.get("device_id") or "wearable_01")
    if not isinstance(port, str) or not isinstance(device_id, str) or not device_id.strip():
        return jsonify({"error": "'port' and 'device_id' must be strings"}), 400
    try:
        bridge.connect(port, device_id.strip())
    except BridgeError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify(bridge.status())


@serial_bp.route("/api/serial/disconnect", methods=["POST"])
def disconnect():
    bridge.disconnect()
    return jsonify(bridge.status())
