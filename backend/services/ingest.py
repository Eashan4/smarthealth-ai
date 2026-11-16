"""Shared ingest pipeline: store raw -> windowed inference -> decision engine -> store -> response.
Used by both transports: WiFi HTTP (routes/sensor_routes.py) and USB serial (services/serial_bridge.py)."""

from __future__ import annotations

from backend.database import db
from backend.services import calibration, imu_live, live_state


def process_sample(conn, clean: dict) -> dict:
    """Store + infer + decide for one validated sample; returns the response dict."""
    raw = clean["imu"]
    calibration.feed(clean["device_id"], raw)                         # raw sample -> running calibration
    clean["imu"] = calibration.apply(clean["device_id"], raw)         # everything below sees calibrated gyro
    imu_live.push(clean["device_id"], clean["imu"], raw)
    db.insert_reading(conn, clean["device_id"], clean["timestamp"], clean["imu"],
                       clean["heart_rate"], clean["spo2"])

    dev = clean["device_id"]
    sample = [clean["imu"][f] for f in ("ax", "ay", "az", "gx", "gy", "gz")]
    tremor = live_state.get_tremor(dev)
    tremor.push(sample)                                     # continuous spectral tremor (accel + gyro)
    motion, engine = live_state.get_motion_classifier(dev), live_state.get_decision_engine()
    motion.tremor = tremor.detected                         # a shaking hand must not read as Walking/Running
    cnn = live_state.get_stream(dev).push_sample(sample)    # event-triggered CNN: supporting fall evidence only
    if cnn is not None:
        engine.note_cnn(dev, cnn)
        live_state.set_last_models(dev, cnn)
    result = motion.push(sample)                            # continuous rules: result ~1 Hz (at once on a fall)

    response = {"status": "ok", "windowed": result is not None}
    if result is None:
        return response

    g = calibration.status(dev).get("gravity")              # calibrated rest gravity -> Sitting/Standing/Lying tilt
    motion.rest_gravity = [g["x"], g["y"], g["z"]] if g else None
    decision = engine.evaluate(dev, result)
    db.insert_prediction(conn, dev, clean["timestamp"], decision["activity"], result["confidence"],
                         decision["fall_probability"], None, "rules+CNN")

    if decision["confirmed_fall"] and not live_state.alert_already_active(dev):
        db.insert_alert(
            conn, dev, clean["timestamp"], "fall", "critical",
            f"FALL DETECTED - confidence {decision['fall_probability']*100:.0f}% "
            f"(by_rules={decision['by_rules']}, motion_verified={decision['motion_verified']})",
        )
        live_state.set_alert_active(dev, True)
    elif not decision["fall_active"]:
        live_state.set_alert_active(dev, False)             # re-arm once the fall state clears

    response.update({
        "activity": decision["activity"],
        "confidence": result["confidence"],
        "fall_probability": decision["fall_probability"],
        "confirmed_fall": decision["confirmed_fall"],
        "motion_verified": decision["motion_verified"],
        "buzzer": decision["confirmed_fall"],
    })
    return response
