"""5-minute live demo stream: a full activity arc (rest -> walk -> jog ->
cooldown -> sit -> rest -> lie down -> fall -> recovery) sent to a running
backend in real time, so the dashboard visibly updates for ~5 minutes.

Motion (accel+gyro) comes from real BITS-2 trials for subject 2 -- a held-out
test subject, same as tests/e2e_demo.py -- chained with synthetic near-rest
idle segments to fill out the gaps between events. Heart rate and SpO2 are
synthetic (BITS-2 trials are too short to carry a meaningful vitals arc) but
follow a physiologically plausible trajectory for each phase, interpolated
sample-by-sample with noise, not held at a fixed value the way
fake_esp32_sender's HR does.

Usage:
  python -m tests.demo_5min                 # real-time, ~5 minutes
  python -m tests.demo_5min --fast          # no pacing, sends as fast as possible
  python -m tests.demo_5min --device-id demo_watch_01
"""

from __future__ import annotations

import argparse
import random
import time

from ml.datasets.bits2_adapter import _parse_sensor_rows
from tests.fake_esp32_sender import post

RATE_HZ = 20.0
SUBJECT = 2  # held-out test subject, matches tests/e2e_demo.py
ADL_DIR = "data/raw/bits2/Dataset/adl/user2"
FALL_DIR = "data/raw/bits2/Dataset/fall/user2"


def _idle_imu():
    return {
        "ax": random.uniform(-0.3, 0.3), "ay": random.uniform(-0.3, 0.3),
        "az": 9.8 + random.uniform(-0.3, 0.3),
        "gx": random.uniform(-0.1, 0.1), "gy": random.uniform(-0.1, 0.1),
        "gz": random.uniform(-0.1, 0.1),
    }


def _vitals_at(frac, hr_range, spo2_range, hr_noise=1.5, spo2_noise=0.3):
    hr = hr_range[0] + (hr_range[1] - hr_range[0]) * frac + random.uniform(-hr_noise, hr_noise)
    spo2 = spo2_range[0] + (spo2_range[1] - spo2_range[0]) * frac + random.uniform(-spo2_noise, spo2_noise)
    return round(max(40.0, hr), 1), round(min(100.0, max(70.0, spo2)), 1)


# (kind, label, source, duration_s-or-None, hr_range, spo2_range)
PHASES = [
    ("idle", "Resting (sitting, baseline)", None, 35, (66, 70), (97, 99)),
    ("trial", "Walking Slowly (real trial)", f"{ADL_DIR}/user2_adl1.csv", None, (71, 88), (96, 98)),
    ("idle", "Warming up (walk -> jog transition)", None, 20, (88, 102), (95, 97)),
    ("trial", "Running / Jogging (real trial)", f"{ADL_DIR}/user2_adl3.csv", None, (102, 140), (94, 96)),
    ("idle", "Cooldown after run", None, 40, (140, 92), (95, 97)),
    ("trial", "Sitting down (real trial)", f"{ADL_DIR}/user2_adl9.csv", None, (92, 80), (96, 98)),
    ("idle", "Resting (sitting)", None, 35, (80, 68), (97, 99)),
    ("trial", "Lying down (real trial)", f"{ADL_DIR}/user2_adl13.csv", None, (68, 61), (97, 99)),
    ("idle", "Resting (lying, calm)", None, 35, (61, 64), (97, 98)),
    ("trial", "FALL (real trial)", f"{FALL_DIR}/user2_fall4.csv", None, (64, 112), (97, 91)),
    ("idle", "Post-fall recovery (lying still)", None, 51, (112, 75), (91, 96)),
]


def run(url, device_id, real_time):
    total_samples = 0
    for kind, label, source, duration, hr_range, spo2_range in PHASES:
        if kind == "trial":
            acc, gyro = _parse_sensor_rows(source)
            n = min(len(acc), len(gyro))
        else:
            n = int(duration * RATE_HZ)
        total_samples += n

    print(f"5-min demo: {len(PHASES)} phases, {total_samples} samples "
          f"({total_samples / RATE_HZ:.0f}s of simulated time) at {RATE_HZ:.0f} Hz "
          f"-> device_id={device_id}")
    print(f"{'real-time pacing' if real_time else 'fast (no pacing)'}. "
          f"Open http://localhost:5000 and set the device ID to watch it live.\n")

    t = time.time()
    i = 0
    period = 1.0 / RATE_HZ
    for kind, label, source, duration, hr_range, spo2_range in PHASES:
        if kind == "trial":
            acc, gyro = _parse_sensor_rows(source)
            n = min(len(acc), len(gyro))
        else:
            n = int(duration * RATE_HZ)

        print(f"--- {label} ({n / RATE_HZ:.1f}s, {n} samples) ---")
        for k in range(n):
            frac = k / max(1, n - 1)
            hr, spo2 = _vitals_at(frac, hr_range, spo2_range)
            imu = _idle_imu() if kind == "idle" else {
                "ax": float(acc[k, 0]), "ay": float(acc[k, 1]), "az": float(acc[k, 2]),
                "gx": float(gyro[k, 0]), "gy": float(gyro[k, 1]), "gz": float(gyro[k, 2]),
            }
            payload = {
                "device_id": device_id, "timestamp": t, "imu": imu,
                "vitals": {"heart_rate": hr, "spo2": spo2},
            }
            send_start = time.time()
            status, body = post(url, payload)
            if body.get("windowed"):
                print(f"  sample {i:4d} -> {status} activity={body.get('activity')} "
                      f"fall_prob={body.get('fall_probability', 0):.3f} "
                      f"confirmed_fall={body.get('confirmed_fall')} "
                      f"hr={hr} spo2={spo2}")
            i += 1
            t += period
            if real_time:
                elapsed = time.time() - send_start
                time.sleep(max(0.0, period - elapsed))

    print(f"\nDone: {i} samples sent over "
          f"{'~' + str(round(total_samples / RATE_HZ)) + 's real time' if real_time else 'fast mode'}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5000/api/sensor-data")
    parser.add_argument("--device-id", default="wearable_01")
    parser.add_argument("--fast", action="store_true", help="send as fast as possible, no real-time pacing")
    args = parser.parse_args()
    run(args.url, args.device_id, real_time=not args.fast)
