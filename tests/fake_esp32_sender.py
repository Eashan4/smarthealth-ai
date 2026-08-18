"""Simulated ESP32 sender for Phase 9 end-to-end testing without physical
hardware. Streams raw accel+gyro samples (a real BITS-2 trial, bracketed by
synthetic near-rest padding, or pure synthetic idle data) as a sequence of
POST /api/sensor-data requests -- standing in for the real device until
Phase 1 hardware validation is done. Sends RAW samples at native rate; the
backend's EventSegmentBuffer (ml/segmentation/windowing.py) does its own
onset/offset detection and resampling, exactly like it would for a real
device stream.

Usage:
  python -m tests.fake_esp32_sender --trial data/raw/bits2/Dataset/fall/user2/user2_fall1.csv
  python -m tests.fake_esp32_sender --idle 20
"""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request

from ml.datasets.bits2_adapter import _parse_sensor_rows

REST_SAMPLE = {"ax": 0.0, "ay": 0.0, "az": 9.8, "gx": 0.0, "gy": 0.0, "gz": 0.0}


def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw_body": body.decode(errors="replace")}


def _jitter(base, spread):
    return base + random.uniform(-spread, spread)


def _send(url, device_id, t, imu, i):
    payload = {
        "device_id": device_id,
        "timestamp": t,
        "imu": imu,
        "vitals": {"heart_rate": 78 + (i % 5), "spo2": 97},
    }
    status, body = post(url, payload)
    if body.get("windowed"):
        print(f"  sample {i:4d} -> {status} activity={body.get('activity')} "
              f"fall_prob={body.get('fall_probability', 0):.3f} "
              f"confirmed_fall={body.get('confirmed_fall')} "
              f"motion_verified={body.get('motion_verified')}")
    return status, body


def stream_trial(url, csv_path, device_id, rate_hz, pad_seconds=3.0):
    acc, gyro = _parse_sensor_rows(csv_path)
    n = min(len(acc), len(gyro))
    print(f"Replaying {csv_path}: {pad_seconds}s idle -> {n} raw event samples -> {pad_seconds}s idle, at {rate_hz} Hz")
    t = time.time()
    i = 0
    for _ in range(int(pad_seconds * rate_hz)):
        imu = {"ax": _jitter(0, 0.3), "ay": _jitter(0, 0.3), "az": _jitter(9.8, 0.3),
               "gx": _jitter(0, 0.1), "gy": _jitter(0, 0.1), "gz": _jitter(0, 0.1)}
        _send(url, device_id, t, imu, i); i += 1; t += 1.0 / rate_hz
    for k in range(n):
        imu = {"ax": float(acc[k, 0]), "ay": float(acc[k, 1]), "az": float(acc[k, 2]),
               "gx": float(gyro[k, 0]), "gy": float(gyro[k, 1]), "gz": float(gyro[k, 2])}
        _send(url, device_id, t, imu, i); i += 1; t += 1.0 / rate_hz
    for _ in range(int(pad_seconds * rate_hz)):
        imu = {"ax": _jitter(0, 0.3), "ay": _jitter(0, 0.3), "az": _jitter(9.8, 0.3),
               "gx": _jitter(0, 0.1), "gy": _jitter(0, 0.1), "gz": _jitter(0, 0.1)}
        _send(url, device_id, t, imu, i); i += 1; t += 1.0 / rate_hz


def stream_idle(url, device_id, seconds, rate_hz):
    n = int(seconds * rate_hz)
    print(f"Replaying {n} synthetic near-rest samples at {rate_hz} Hz")
    t = time.time()
    for i in range(n):
        imu = {"ax": _jitter(0, 0.3), "ay": _jitter(0, 0.3), "az": _jitter(9.8, 0.3),
               "gx": _jitter(0, 0.1), "gy": _jitter(0, 0.1), "gz": _jitter(0, 0.1)}
        _send(url, device_id, t, imu, i)
        t += 1.0 / rate_hz


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5000/api/sensor-data")
    parser.add_argument("--device-id", default="wearable_01")
    parser.add_argument("--trial", help="path to a BITS-2 trial CSV to replay")
    parser.add_argument("--idle", type=float, help="seconds of synthetic near-rest data to send instead")
    parser.add_argument("--rate", type=float, default=20.0, help="native send rate, Hz")
    args = parser.parse_args()

    if args.trial:
        stream_trial(args.url, args.trial, args.device_id, args.rate)
    elif args.idle:
        stream_idle(args.url, args.device_id, args.idle, args.rate)
    else:
        parser.error("pass --trial <csv> or --idle <seconds>")
