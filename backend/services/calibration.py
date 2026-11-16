"""Per-device gyro-bias / rest-gravity calibration. Fed raw samples from ingest.process_sample.
Only the gyro offset is removed by apply(); accel is untouched (gravity must stay).
Persisted to data/calibration.json (atomic write) so it survives restarts."""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

CAL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "calibration.json"
SAMPLE_HZ = 50          # firmware rate; collection length in samples = seconds * SAMPLE_HZ
NO_DATA_S = 5.0         # no sample at all within this long after start -> fail
TIMEOUT_S = 8.0         # collection hard cap, never stay 'collecting'
MAX_GYRO_STD = 0.05     # rad/s per axis
MAX_ACCEL_STD = 0.6     # m/s^2 on |a|

_lock = threading.Lock()
_cache: dict | None = None      # device_id -> {bias, gravity, still_std, at}; None = not loaded yet
_runs: dict[str, dict] = {}     # device_id -> {state, t0, n, rows, message}


def _load() -> dict:                                  # call with _lock held
    global _cache
    if _cache is None:
        try:
            data = json.loads(Path(CAL_PATH).read_text())
            _cache = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _cache = {}
    return _cache


def _save(cache: dict):                               # call with _lock held
    try:
        p = Path(CAL_PATH)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(cache, f)
        os.replace(tmp, p)
    except OSError:
        pass  # still calibrated in memory for this run


def _expire(dev: str, run: dict, now: float):         # call with _lock held
    if run["state"] != "collecting":
        return
    if not run["rows"] and now - run["t0"] > NO_DATA_S:
        run.update(state="failed", message="No data: connect the board first")
    elif now - run["t0"] > TIMEOUT_S:
        run.update(state="failed", message="Calibration timed out: keep the board still and retry")


def start(dev: str, seconds: float = 2.0) -> bool:
    """Begin collecting; False if a collection is already running."""
    now = time.time()
    with _lock:
        run = _runs.get(dev)
        if run:
            _expire(dev, run, now)
            if run["state"] == "collecting":
                return False
        _runs[dev] = {"state": "collecting", "t0": now, "n": max(2, int(seconds * SAMPLE_HZ)),
                      "rows": [], "message": "Keep the board still"}
        return True


def feed(dev: str, imu: dict):
    """Offer one RAW sample to a running collection (cheap no-op otherwise)."""
    run = _runs.get(dev)
    if not run or run["state"] != "collecting":
        return
    now = time.time()
    with _lock:
        if run["state"] != "collecting":
            return
        run["rows"].append([imu[k] for k in ("ax", "ay", "az", "gx", "gy", "gz")])
        _expire(dev, run, now)
        if run["state"] != "collecting" or len(run["rows"]) < run["n"]:
            return
        a = np.array(run["rows"], dtype=float)
        gstd, astd = float(a[:, 3:].std(axis=0).max()), float(np.linalg.norm(a[:, :3], axis=1).std())
        if not (gstd <= MAX_GYRO_STD and astd <= MAX_ACCEL_STD):   # also rejects NaN
            run.update(state="failed", message="Keep the board still", rows=[])
            return
        m = a.mean(axis=0)
        cache = _load()
        cache[dev] = {"bias": m[3:].tolist(), "gravity": m[:3].tolist(),
                      "still_std": {"gyro": gstd, "accel": astd}, "at": now}
        _save(cache)
        run.update(state="done", message="Calibrated", rows=[])


def apply(dev: str, imu: dict) -> dict:
    """Copy of imu with the gyro bias removed (unchanged copy if uncalibrated)."""
    with _lock:
        c = _load().get(dev)
    out = dict(imu)
    if c:
        for k, b in zip(("gx", "gy", "gz"), c["bias"]):
            out[k] = imu[k] - b
    return out


def is_calibrated(dev: str) -> bool:
    with _lock:
        return dev in _load()


def reset(dev: str):
    with _lock:
        _runs.pop(dev, None)
        cache = _load()
        if cache.pop(dev, None) is not None:
            _save(cache)


def status(dev: str) -> dict:
    now = time.time()
    with _lock:
        run, c = _runs.get(dev), _load().get(dev)
        if run:
            _expire(dev, run, now)
        state = run["state"] if run else ("done" if c else "idle")
        progress = (min(1.0, len(run["rows"]) / run["n"]) if state == "collecting"
                    else 1.0 if state == "done" else 0.0)
        msg = run["message"] if run else ("Calibrated" if c else "Not calibrated")
        if state == "collecting" and not run["rows"] and now - run["t0"] > 1:
            msg = "Waiting for data..."
        d = {"state": state, "progress": round(progress, 3), "calibrated": c is not None,
             "bias": None, "bias_deg_s": None, "gravity": None, "still_std": None, "at": None,
             "message": msg}
        if c:
            d.update(bias=dict(zip(("gx", "gy", "gz"), c["bias"])),
                     bias_deg_s={k: math.degrees(v) for k, v in zip(("gx", "gy", "gz"), c["bias"])},
                     gravity=dict(zip("xyz", c["gravity"])), still_std=c["still_std"], at=c["at"])
        return d
