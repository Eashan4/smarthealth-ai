"""Read-only dashboard/API endpoints (docs/DOCUMENTATION.md sec 11)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.database import db

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/api/latest", methods=["GET"])
def latest():
    device_id = request.args.get("device_id")
    conn = db.get_connection()
    try:
        reading = db.latest_reading(conn, device_id)
        prediction = db.latest_prediction(conn, device_id)
        return jsonify({"reading": reading, "prediction": prediction})
    finally:
        conn.close()


@api_bp.route("/api/activity", methods=["GET"])
def activity():
    device_id = request.args.get("device_id")
    conn = db.get_connection()
    try:
        prediction = db.latest_prediction(conn, device_id)
        if prediction is None:
            return jsonify({"activity": None, "confidence": None})
        return jsonify({
            "activity": prediction["activity"],
            "confidence": prediction["confidence"],
            "fall_probability": prediction["fall_probability"],
            "tremor_probability": prediction["tremor_probability"],
            "timestamp": prediction["timestamp"],
        })
    finally:
        conn.close()


@api_bp.route("/api/vitals", methods=["GET"])
def vitals():
    device_id = request.args.get("device_id")
    conn = db.get_connection()
    try:
        reading = db.latest_reading(conn, device_id)
        if reading is None:
            return jsonify({"heart_rate": None, "spo2": None})
        return jsonify({
            "heart_rate": reading["heart_rate"],
            "spo2": reading["spo2"],
            "timestamp": reading["timestamp"],
        })
    finally:
        conn.close()


@api_bp.route("/api/alerts", methods=["GET"])
def alerts():
    device_id = request.args.get("device_id")
    limit = int(request.args.get("limit", 50))
    conn = db.get_connection()
    try:
        return jsonify(db.recent_alerts(conn, limit=limit, device_id=device_id))
    finally:
        conn.close()


@api_bp.route("/api/history", methods=["GET"])
def history():
    device_id = request.args.get("device_id")
    table = request.args.get("table", "predictions")
    limit = int(request.args.get("limit", 100))
    if table not in ("sensor_readings", "predictions", "alerts"):
        return jsonify({"error": "table must be one of sensor_readings, predictions, alerts"}), 400
    conn = db.get_connection()
    try:
        return jsonify(db.history(conn, table, limit=limit, device_id=device_id))
    finally:
        conn.close()
