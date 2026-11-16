"""Phase 5 -- POST /api/sensor-data: receive -> validate -> store raw ->
preprocess -> windowed inference -> decision engine -> store -> respond.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.database import db
from backend.services.ingest import process_sample
from backend.services.validation import PayloadValidationError, validate_sensor_payload

sensor_bp = Blueprint("sensor", __name__)


@sensor_bp.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    try:
        clean = validate_sensor_payload(request.get_json(silent=True))
    except PayloadValidationError as e:
        return jsonify({"error": e.message}), 400
    conn = db.get_connection()
    try:
        return jsonify(process_sample(conn, clean)), 201
    finally:
        conn.close()
