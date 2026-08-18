"""Phase 9 -- end-to-end pipeline test across the demonstration scenarios in
docs/DOCUMENTATION.md sec 19: wearable(simulated) -> ESP32(simulated) ->
Flask -> AI -> decision engine -> dashboard/DB -> alert.

Uses trials from subjects held out of BOTH training and validation (the
subject-wise TEST split from ml/training/train.py), so this is a genuine
held-out demonstration, not a replay of data the model has seen.

Run the Flask server first: python -m backend.app
Usage: python -m tests.e2e_demo
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ml.datasets.bits2_adapter import ADL_LABEL_MAP, DATA_RAW_DIR

BASE_URL = "http://127.0.0.1:5000"

# Held-out TEST subjects from the actual training run (models/training_results.json subject_split.test)
TEST_SUBJECTS = [2, 3, 9, 14, 34, 37]

SCENARIOS = [
    ("Walking", "adl", 1, "Walking Slowly"),
    ("Sitting", "adl", 9, "Slowly sitting on chair"),
    ("Running", "adl", 3, "Jogging"),
    ("Fall", "fall", 4, "Forward Fall"),
]


def get(path):
    with urllib.request.urlopen(BASE_URL + path, timeout=5) as r:
        return json.loads(r.read())


def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE_URL + path, data=data,
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def stream_csv(device_id, csv_path, rate_hz=20.0, pad_seconds=3.0):
    from ml.datasets.bits2_adapter import _parse_sensor_rows
    acc, gyro = _parse_sensor_rows(csv_path)
    n = min(len(acc), len(gyro))
    t = time.time()
    i = 0

    def send(imu):
        nonlocal i, t
        _, body = post("/api/sensor-data", {
            "device_id": device_id, "timestamp": t, "imu": imu,
            "vitals": {"heart_rate": 76 + (i % 6), "spo2": 97},
        })
        i += 1
        t += 1.0 / rate_hz
        return body

    last = None
    for _ in range(int(pad_seconds * rate_hz)):
        send({"ax": 0.1, "ay": -0.1, "az": 9.8, "gx": 0.0, "gy": 0.0, "gz": 0.0})
    for k in range(n):
        body = send({"ax": float(acc[k, 0]), "ay": float(acc[k, 1]), "az": float(acc[k, 2]),
                      "gx": float(gyro[k, 0]), "gy": float(gyro[k, 1]), "gz": float(gyro[k, 2])})
        if body.get("windowed"):
            last = body
    for _ in range(int(pad_seconds * rate_hz)):
        body = send({"ax": 0.1, "ay": -0.1, "az": 9.8, "gx": 0.0, "gy": 0.0, "gz": 0.0})
        if body.get("windowed"):
            last = body
    return last


def find_trial(kind, subject, activity_id):
    return DATA_RAW_DIR / kind / f"user{subject}" / f"user{subject}_{kind}{activity_id}.csv"


if __name__ == "__main__":
    print(f"Backend health: {get('/api/health')}")
    print(f"Using held-out TEST subjects (never seen in training or validation): {TEST_SUBJECTS}\n")

    results = []
    for label, kind, activity_id, activity_name in SCENARIOS:
        subject = TEST_SUBJECTS[len(results) % len(TEST_SUBJECTS)]
        csv_path = find_trial(kind, subject, activity_id)
        device_id = f"e2e_{label.lower()}"
        print(f"=== Scenario: {label} (subject {subject}, '{activity_name}', held-out test data) ===")
        result = stream_csv(device_id, csv_path)
        if result:
            print(f"  activity={result['activity']} confidence={result['confidence']*100:.0f}% "
                  f"fall_probability={result['fall_probability']*100:.0f}% "
                  f"confirmed_fall={result['confirmed_fall']} motion_verified={result['motion_verified']}")
            alerts = get(f"/api/alerts?device_id={device_id}")
            print(f"  alerts stored: {len(alerts)}")
            expected = "Fall" if label == "Fall" else label
            correct = result["activity"] == expected
            print(f"  expected={expected} -> {'PASS' if correct else 'MISMATCH'}")
            results.append((label, correct, result))
        else:
            print("  NO WINDOW PRODUCED (event never closed / trial too short)")
            results.append((label, False, None))
        print()

    print("=== Tremor-like movement scenario ===")
    print("  NOT RUN: no tremor-labeled data in the BITS-2 training set (see ml/config.py, "
          "docs/DOCUMENTATION.md sec 16). Tremor detection is a known v1 limitation, not "
          "silently skipped.")

    print("\n=== Summary ===")
    for label, correct, _ in results:
        print(f"  {label:10s} {'PASS' if correct else 'FAIL'}")
