"""Shared ingest pipeline: store raw -> windowed inference -> decision engine -> store -> response.
Used by both transports: WiFi HTTP (routes/sensor_routes.py) and USB serial (services/serial_bridge.py)."""

from __future__ import annotations

from backend.database import db
from backend.services import live_state


def process_sample(conn, clean: dict) -> dict:
    """Store + infer + decide for one validated sample; returns the response dict."""
    db.insert_reading(conn, clean["device_id"], clean["timestamp"], clean["imu"],
                       clean["heart_rate"], clean["spo2"])

    stream = live_state.get_stream(clean["device_id"])
    sample = [clean["imu"][f] for f in ("ax", "ay", "az", "gx", "gy", "gz")]
    live_state.get_tremor(clean["device_id"]).push(sample)  # continuous, independent of event segmentation
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

    return response
