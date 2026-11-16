"""In-memory ring of the latest CALIBRATED IMU samples per device, for the dashboard's live feed."""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from backend.services import calibration

RING = 250
_lock = threading.Lock()
_rings: dict[str, deque] = {}
_seq: dict[str, int] = {}


def push(dev: str, imu: dict, raw: dict):
    """imu = calibrated sample, raw = same sample before calibration."""
    ax, ay, az = imu["ax"], imu["ay"], imu["az"]
    s = {"t": time.time(), **{k: imu[k] for k in ("ax", "ay", "az", "gx", "gy", "gz")},
         **{f"{k}_dps": math.degrees(imu[k]) for k in ("gx", "gy", "gz")},
         "roll_deg": math.degrees(math.atan2(ay, az)),
         "pitch_deg": math.degrees(math.atan2(-ax, math.hypot(ay, az))),
         "raw_gx": raw["gx"], "raw_gy": raw["gy"], "raw_gz": raw["gz"]}
    with _lock:
        _seq[dev] = s["seq"] = _seq.get(dev, 0) + 1
        _rings.setdefault(dev, deque(maxlen=RING)).append(s)


def reset(dev: str):
    with _lock:
        _rings.pop(dev, None)


def snapshot(dev: str, n: int = 100) -> dict:
    now = time.time()
    with _lock:
        ring = list(_rings.get(dev, ()))
    recent = [s["t"] for s in ring if now - s["t"] <= 2.0]
    rate = (len(recent) - 1) / (recent[-1] - recent[0]) if len(recent) > 1 and recent[-1] > recent[0] else 0.0
    return {"device_id": dev, "samples": ring[-n:], "latest": ring[-1] if ring else None,
            "rate_hz": round(rate, 1), "calibrated": calibration.is_calibrated(dev),
            "age_s": round(now - ring[-1]["t"], 3) if ring else None}
