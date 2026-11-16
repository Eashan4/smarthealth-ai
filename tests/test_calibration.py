"""Gyro calibration + live IMU feed, Flask test_client + process_sample, temp DB/calibration file.
Run: python -m tests.test_calibration"""

import json, sys, tempfile, time, traceback
from pathlib import Path

import numpy as np

tmp = Path(tempfile.mkdtemp())
from backend.database import db
db.DB_PATH = tmp / "t.db"                       # never touch the real data/smarthealth.db
from backend.services import calibration as cal, imu_live
cal.CAL_PATH = tmp / "cal.json"                  # nor the real calibration file

from backend.app import create_app
from backend.services.ingest import process_sample

BIAS = np.array([0.03, -0.02, 0.015])
rng = np.random.default_rng(1)
c = create_app().test_client()
conn = db.get_connection()


def feed(dev, n, bias=BIAS, noise=0.005, gnoise=None, accel_noise=0.02):
    for _ in range(n):
        g = bias + rng.normal(0, gnoise if gnoise is not None else noise, 3)
        a = np.array([0.1, 0.2, 9.8]) + rng.normal(0, accel_noise, 3)
        imu = dict(zip(("ax", "ay", "az", "gx", "gy", "gz"), (*a, *g)))
        process_sample(conn, {"device_id": dev, "timestamp": time.time(), "imu": imu, "heart_rate": None, "spo2": None})


def fresh():
    cal._cache = None; cal._runs.clear()


def t_recover_bias():
    fresh()
    assert c.get("/api/calibration?device_id=a").get_json()["state"] == "idle"
    r = c.post("/api/calibrate/gyro", json={"device_id": "a"})
    assert r.status_code == 202 and r.get_json()["state"] == "collecting"
    assert c.post("/api/calibrate/gyro", json={"device_id": "a"}).status_code == 409
    feed("a", 100)
    s = c.get("/api/calibration?device_id=a").get_json()
    assert s["state"] == "done" and s["calibrated"] and s["progress"] == 1.0, s
    assert np.allclose([s["bias"][k] for k in ("gx", "gy", "gz")], BIAS, atol=0.003), s["bias"]
    assert abs(s["gravity"]["z"] - 9.8) < 0.05 and abs(s["bias_deg_s"]["gx"] - np.degrees(s["bias"]["gx"])) < 1e-9
    feed("a", 200)                                # after calibration the gyro mean is ~0, accel untouched
    smp = c.get("/api/imu?device_id=a&n=200").get_json()
    g = np.array([[x["gx"], x["gy"], x["gz"]] for x in smp["samples"]])
    assert np.abs(g.mean(axis=0)).max() < 0.002, g.mean(axis=0)
    assert abs(np.mean([x["az"] for x in smp["samples"]]) - 9.8) < 0.01
    raw = np.array([[x["raw_gx"], x["raw_gy"], x["raw_gz"]] for x in smp["samples"]]).mean(axis=0)
    assert np.allclose(raw, BIAS, atol=0.003) and smp["calibrated"] and len(smp["samples"]) == 200


def t_moving_fails():
    fresh()
    c.post("/api/calibrate/gyro", json={"device_id": "m"})
    feed("m", 100, gnoise=0.5)
    s = c.get("/api/calibration?device_id=m").get_json()
    assert s["state"] == "failed" and s["message"] == "Keep the board still" and not s["calibrated"], s
    assert c.post("/api/calibrate/gyro", json={"device_id": "m"}).status_code == 202   # can retry after failure


def t_no_data_and_timeout():
    fresh(); old = cal.NO_DATA_S, cal.TIMEOUT_S
    try:
        cal.NO_DATA_S, cal.TIMEOUT_S = 0.2, 0.5
        c.post("/api/calibrate/gyro", json={"device_id": "n"})
        time.sleep(0.3)
        s = c.get("/api/calibration?device_id=n").get_json()
        assert s["state"] == "failed" and s["message"].startswith("No data"), s
        c.post("/api/calibrate/gyro", json={"device_id": "t"})
        feed("t", 5); time.sleep(0.6)             # trickle then stall -> hard timeout, never stuck collecting
        s = c.get("/api/calibration?device_id=t").get_json()
        assert s["state"] == "failed" and "timed out" in s["message"], s
    finally:
        cal.NO_DATA_S, cal.TIMEOUT_S = old


def t_reset_and_persist():
    fresh()
    c.post("/api/calibrate/gyro", json={"device_id": "p", "seconds": 1}); feed("p", 50)
    assert c.get("/api/calibration?device_id=p").get_json()["state"] == "done"
    assert "p" in json.loads(cal.CAL_PATH.read_text())
    fresh()                                       # simulated restart
    s = c.get("/api/calibration?device_id=p").get_json()
    assert s["calibrated"] and abs(s["bias"]["gx"] - BIAS[0]) < 0.003, s
    cal._cache = None; cal.CAL_PATH.write_text("{corrupt")
    assert not c.get("/api/calibration?device_id=p").get_json()["calibrated"]   # corrupt file tolerated
    cal.CAL_PATH.unlink()
    assert c.post("/api/calibrate/reset", json={"device_id": "a"}).get_json()["state"] == "idle"
    fresh(); c.post("/api/calibrate/gyro", json={"device_id": "p", "seconds": 1}); feed("p", 50)
    r = c.post("/api/calibrate/reset", json={"device_id": "p"}).get_json()
    assert r["state"] == "idle" and not r["calibrated"] and r["bias"] is None, r
    fresh(); assert not c.get("/api/calibration?device_id=p").get_json()["calibrated"]   # removed on disk too


def t_imu_and_validation():
    imu_live.reset("e")
    r = c.get("/api/imu?device_id=e").get_json()
    assert r == {"device_id": "e", "samples": [], "latest": None, "rate_hz": 0.0, "calibrated": False, "age_s": None}, r
    for _ in range(300):
        feed("e", 1); time.sleep(0.002)
    r = c.get("/api/imu?device_id=e&n=250").get_json()
    L = r["latest"]
    assert len(r["samples"]) == 250 and L["seq"] == 300 and r["age_s"] < 1 and r["rate_hz"] > 10, r["rate_hz"]
    assert abs(L["roll_deg"] - np.degrees(np.arctan2(L["ay"], L["az"]))) < 1e-9
    assert abs(L["pitch_deg"] + np.degrees(np.arctan2(L["ax"], np.hypot(L["ay"], L["az"])))) < 1e-9
    assert abs(L["gx_dps"] - np.degrees(L["gx"])) < 1e-9
    assert len(c.get("/api/imu?device_id=e&n=5").get_json()["samples"]) == 5
    for url in ("/api/imu?n=0", "/api/imu?n=251", "/api/imu?n=x", "/api/imu?device_id="):
        assert c.get(url).status_code == 400, url
    for body in ({"seconds": 0}, {"seconds": 6}, {"seconds": "2"}, {"seconds": True}, {"device_id": 5}, {"device_id": " "}):
        assert c.post("/api/calibrate/gyro", json=body).status_code == 400, body
    assert c.post("/api/calibrate/gyro", data="{bad", content_type="application/json").status_code == 400
    assert c.post("/api/calibrate/gyro", json=[1]).status_code == 400
    assert c.post("/api/calibrate/reset", json={}).get_json()["state"] in ("idle", "done")   # default device


if __name__ == "__main__":
    bad = 0
    for name, fn in [(n, f) for n, f in sorted(globals().items()) if n.startswith("t_")]:
        try:
            fn(); print("PASS", name)
        except Exception:
            bad += 1; print("FAIL", name); traceback.print_exc()
    sys.exit(1 if bad else 0)
