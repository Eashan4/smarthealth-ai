"""Synthetic-signal check of the continuous rule classifier + fall state machine.
Run: python -m tests.test_motion_rules   (50 Hz, accel m/s^2, gyro rad/s; prints PASS/FAIL, exits non-zero on failure)"""

import sys

import numpy as np

from ml.inference.motion_rules import MotionClassifier

FS = 50
rng = np.random.default_rng(1)
G = 9.81


def seg(seconds, comps=(), axis=2, gyro_amp=0.0, gyro_f=1.0, base=(0.0, 0.0, G)):
    """comps [(hz, amp)] added on one accel axis over a gravity vector `base`; MPU6050-like noise."""
    t = np.arange(int(seconds * FS)) / FS
    a = rng.normal(0, 0.05, (len(t), 3)) + np.asarray(base)
    for f, amp in comps:
        a[:, axis] += amp * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    g = rng.normal(0, 0.01, (len(t), 3))
    g[:, 0] += gyro_amp * np.sin(2 * np.pi * gyro_f * t)
    return np.hstack([a, g])


def fall_seg(freefall=0.25, impact=40.0, bounce=True):
    """standing -> free-fall dip (|a|~1) -> impact spike -> small bounce."""
    ff = np.zeros((int(freefall * FS), 6)); ff[:, 2] = 1.0
    imp = np.zeros((3, 6)); imp[:, 2] = [impact, impact * 0.6, impact * 0.3]
    out = [ff, imp]
    if bounce:
        b = np.zeros((10, 6)); b[:, 2] = G + 3 * np.sin(np.arange(10) * 1.2)
        out.append(b)
    return np.vstack(out)


def run(samples, tremor=False):
    """returns (list of results, set of fall states seen)"""
    c = MotionClassifier(FS); c.tremor = tremor
    res, states = [], set()
    for i, s in enumerate(samples):
        r = c.push(list(s), ts=i / FS)
        states.add(c.fall_state)
        if r: res.append(r)
    return res, states, c


STILL, WALK = seg(8), None
CASES = []


def case(fn):
    CASES.append(fn); return fn


def tail_label(res, n=3):
    labels = [r["activity"] for r in res[-n:]]
    return max(set(labels), key=labels.count)


@case
def still_is_sitting():
    res, st, _ = run(seg(8))
    assert tail_label(res) == "Sitting" and "confirmed" not in st, res[-1]


@case
def walking_1_9hz():
    res, st, _ = run(seg(12, [(1.9, 3.5), (3.8, 1.2)], gyro_amp=0.8, gyro_f=0.95))
    assert tail_label(res) == "Walking" and "confirmed" not in st, res[-1]
    assert abs(res[-1]["features"]["dom_freq_hz"] - 1.9) < 0.3, res[-1]["features"]


@case
def walking_second_harmonic_dominant():
    res, st, _ = run(seg(12, [(1.9, 1.5), (3.8, 3.0)], gyro_amp=0.8, gyro_f=0.95))
    assert tail_label(res) == "Walking", res[-1]["features"]


@case
def running_2_8hz():
    res, st, _ = run(seg(12, [(2.8, 9.0), (5.6, 3.0)], gyro_amp=2.0, gyro_f=1.4))
    assert tail_label(res) == "Running" and "confirmed" not in st, res[-1]["features"]


@case
def running_with_big_peaks_is_not_fall():
    res, st, _ = run(seg(15, [(2.8, 22.0)]))      # peaks > FALL_IMPACT_ONLY_MAG, but never still
    assert "confirmed" not in st and tail_label(res) == "Running", (st, res[-1]["features"])


@case
def hand_shake_5hz_not_walking_or_running():
    res, st, _ = run(seg(10, [(5.0, 3.0)], gyro_amp=1.0, gyro_f=5.0), tremor=True)
    assert tail_label(res) not in ("Walking", "Running", "Fall") and "confirmed" not in st, res[-1]
    res, st, _ = run(seg(10, [(5.0, 3.0)], gyro_amp=1.0, gyro_f=5.0))          # even without the tremor flag
    assert tail_label(res) not in ("Walking", "Running", "Fall"), res[-1]["features"]


@case
def fall_freefall_impact_stillness():
    res, st, c = run(np.vstack([seg(6, [(1.9, 3.5)]), fall_seg(), seg(5)]))
    assert {"freefall", "impact", "confirming", "confirmed"} <= st, st
    assert any(r["activity"] == "Fall" and r["fall_score"] == 1.0 for r in res), [r["fall_state"] for r in res]


@case
def fall_impact_only_then_stillness():
    res, st, _ = run(np.vstack([seg(5), fall_seg(freefall=0, impact=45.0, bounce=False), seg(5)]))
    assert "confirmed" in st, st


@case
def fall_rearms_after_motion():
    c = MotionClassifier(FS)
    seq = np.vstack([seg(5), fall_seg(), seg(3), seg(5, [(1.9, 3.5)]), seg(3), fall_seg(), seg(4)])
    n_conf, was = 0, False
    for i, s in enumerate(seq):
        c.push(list(s), ts=i / FS)
        now = c.fall_state == "confirmed"
        n_conf += now and not was; was = now
    assert n_conf == 2, n_conf


@case
def shake_without_stillness_not_fall():
    shake = seg(8, [(4.5, 20.0)], axis=0)           # vigorous, |a| peaks > 28 m/s^2
    res, st, _ = run(np.vstack([seg(3), shake]))
    assert "confirmed" not in st, st


@case
def drop_and_keep_moving_not_fall():
    res, st, _ = run(np.vstack([seg(5), fall_seg(), seg(8, [(1.9, 3.5)], gyro_amp=0.8)]))
    assert "impact" in st and "confirmed" not in st, st


@case
def lying_with_rest_gravity():
    c = MotionClassifier(FS); c.rest_gravity = [0, 0, G]
    out = None
    for i, s in enumerate(seg(8, base=(G, 0, 0))):      # board rotated 90 deg from the calibrated pose
        out = c.push(list(s), ts=i / FS) or out
    assert out["activity"] == "Lying" and abs(out["features"]["tilt_deg"] - 90) < 5, out


@case
def stable_label_no_flicker():
    res, _, _ = run(np.vstack([seg(8, [(1.9, 3.5), (3.8, 1.2)], gyro_amp=0.8, gyro_f=0.95),
                               seg(1, [(1.9, 0.9)]), seg(8, [(1.9, 3.5), (3.8, 1.2)], gyro_amp=0.8, gyro_f=0.95)]))
    labels = [r["activity"] for r in res[4:]]                   # one marginal second must not flip the label
    flips = sum(a != b for a, b in zip(labels, labels[1:]))
    assert flips <= 2, labels


@case
def ingest_end_to_end():
    """process_sample on a temp DB: 1 Hz prediction rows, exactly one alert per fall, buzzer, re-arm, /api/motion."""
    import tempfile
    from pathlib import Path
    from backend.database import db
    db.DB_PATH = Path(tempfile.mkdtemp()) / "t.db"
    from backend.app import create_app
    from backend.services import live_state
    from backend.services.ingest import process_sample
    client = create_app().test_client()
    assert client.get("/api/motion?device_id=e2e").get_json() == {"activity": None}
    live_state.reset_device("e2e")
    conn, buzz = db.get_connection(), 0
    seq = np.vstack([seg(8, [(1.9, 3.5)]), fall_seg(), seg(5), seg(5, [(1.9, 3.5)]), fall_seg(), seg(4)])
    for i, r in enumerate(seq):
        imu = dict(zip(("ax", "ay", "az", "gx", "gy", "gz"), map(float, r)))
        resp = process_sample(conn, {"device_id": "e2e", "timestamp": 1000 + i / FS, "imu": imu,
                                     "heart_rate": None, "spo2": None})
        buzz += bool(resp.get("buzzer"))
    preds = db.history(conn, "predictions", limit=200, device_id="e2e")
    alerts = db.recent_alerts(conn, limit=10, device_id="e2e")
    acts = {p["activity"] for p in preds}
    assert acts <= {"Walking", "Running", "Sitting", "Lying", "Standing", "Fall"} and "Fall" in acts, acts
    assert 20 <= len(preds) <= 35, len(preds)
    assert len(alerts) == 2 and buzz >= 2, (len(alerts), buzz)
    j = client.get("/api/motion?device_id=e2e").get_json()
    assert j["activity"] and "accel_std" in j["features"] and "fall_state" in j and "state" in j["tremor"], j


if __name__ == "__main__":
    bad = 0
    for fn in CASES:
        try:
            fn(); print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            bad += 1; print(f"FAIL  {fn.__name__}: {e}")
    print("OK: motion rules" if not bad else f"{bad} FAILED")
    sys.exit(1 if bad else 0)
