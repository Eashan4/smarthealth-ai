"""Phase 5 -- POST /api/sensor-data: receive -> validate -> store raw ->
preprocess -> windowed inference -> decision engine -> store -> respond.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.database import db
from backend.services import live_state
from backend.services.validation import PayloadValidationError, validate_sensor_payload

sensor_bp = Blueprint("sensor", __name__)


@sensor_bp.route("/api/sensor-data", methods=["POST"])
def receive_sensor_data():
    payload = request.get_json(silent=True)
    try:
        clean = validate_sensor_payload(payload)
    except PayloadValidationError as e:
        return jsonify({"error": e.message}), 400

    conn = db.get_connection()
    try:
        db.insert_reading(conn, clean["device_id"], clean["timestamp"], clean["imu"],
                           clean["heart_rate"], clean["spo2"])

        stream = live_state.get_stream(clean["device_id"])
        sample = [clean["imu"][f] for f in ("ax", "ay", "az", "gx", "gy", "gz")]
        prediction = stream.push_sample(sample)

        response = {"status": "ok", "windowed": prediction is not None}

        if prediction is not None:
            db.insert_prediction(
                conn, clean["device_id"], clean["timestamp"], prediction["activity"],
                prediction["confidence"], prediction["fall_probability"],
                prediction["tremor_probability"], prediction["model_name"],
            )

            engine = live_state.get_decision_engine()
            decision = engine.evaluate(clean["device_id"], prediction, prediction["window_raw"])

            if decision["confirmed_fall"] and not live_state.alert_already_active(clean["device_id"]):
                db.insert_alert(
                    conn, clean["device_id"], clean["timestamp"], "fall", "critical",
                    f"FALL DETECTED - confidence {prediction['fall_probability']*100:.0f}% "
                    f"(motion_verified={decision['motion_verified']})",
                )
                live_state.set_alert_active(clean["device_id"], True)
            elif not decision["ai_fall_candidate"]:
                live_state.set_alert_active(clean["device_id"], False)

            response.update({
                "activity": prediction["activity"],
                "confidence": prediction["confidence"],
                "fall_probability": prediction["fall_probability"],
                "confirmed_fall": decision["confirmed_fall"],
                "motion_verified": decision["motion_verified"],
                "buzzer": decision["confirmed_fall"],
            })

        return jsonify(response), 201
    finally:
        conn.close()
