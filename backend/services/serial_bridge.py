"""USB-serial transport: reads sample lines from the board over a COM/tty port and feeds the SAME
pipeline as the WiFi path (services/ingest.py), so the dashboard works identically either way.

Wire protocol (115200 baud, newline-terminated), see firmware/esp8266_ino:
  board -> host   D,ax,ay,az,gx,gy,gz,hr,spo2     one line per 50 Hz sample (hr/spo2 = -1 if unknown)
                  V,hr,spo2                        1 Hz, only while the IMU is missing (vitals-only)
                  # sensors imu=1 vitals=0         which sensors are alive
                  anything else                    human-readable log text, shown in the UI status
  host  -> board  B   confirmed fall -> sound the buzzer
The board streams continuously; opening the port resets most NodeMCU boards (DTR/RTS auto-reset),
so data starts ~2-3 s after Connect.
"""

from __future__ import annotations

import math
import re
import threading
import time

import serial
from serial.tools import list_ports

from backend.database import db
from backend.services import live_state
from backend.services.ingest import process_sample
from backend.services.validation import PayloadValidationError, validate_sensor_payload

BAUD = 115200
IMU_FIELDS = ("ax", "ay", "az", "gx", "gy", "gz")


SENSORS_RE = re.compile(r"^#\s*sensors\s+imu=([01])\s+vitals=([01])\s*$")


def parse_line(line: str, device_id: str):
    """'D,...' -> full sample payload (with "imu"); 'V,hr,spo2' -> vitals-only payload (no "imu");
    None if it isn't a valid data line. Unknown vitals (-1) are simply left out."""
    parts = line.strip().split(",")
    if parts[0] == "D" and len(parts) == 9:
        n_imu = 6
    elif parts[0] == "V" and len(parts) == 3:
        n_imu = 0
    else:
        return None
    try:
        v = [float(x) for x in parts[1:]]
    except ValueError:
        return None
    if not all(math.isfinite(x) for x in v):
        return None
    payload = {"device_id": device_id, "timestamp": time.time()}
    if n_imu:
        payload["imu"] = dict(zip(IMU_FIELDS, v[:6]))
    vitals = {}
    if v[n_imu] > 0:
        vitals["heart_rate"] = v[n_imu]
    if v[n_imu + 1] > 0:
        vitals["spo2"] = v[n_imu + 1]
    if vitals or not n_imu:       # vitals-only lines are kept even when empty: "no finger" must clear the display
        payload["vitals"] = vitals
    return payload


def list_serial_ports() -> list[dict]:
    """USB devices first. On macOS each port shows up as /dev/cu.* and /dev/tty.*; keep only cu.*."""
    out = []
    for p in list_ports.comports():
        if p.device.startswith("/dev/tty.") and any(q.device == p.device.replace("/dev/tty.", "/dev/cu.", 1)
                                                    for q in list_ports.comports()):
            continue
        out.append({"device": p.device, "description": p.description or p.device, "usb": p.vid is not None})
    return sorted(out, key=lambda d: (not d["usb"], d["device"]))


class BridgeError(Exception):
    pass


class SerialBridge:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._reset_status()

    def _reset_status(self):
        self.port = self.device_id = self.error = self.last_message = None
        self.samples = 0
        self.last_sample_at = 0.0
        self.connected_at = None
        self.imu_ok = self.vitals_ok = None   # None until the board reports "# sensors ..."

    def status(self) -> dict:
        alive = self._thread is not None and self._thread.is_alive()
        return {
            "connected": alive,
            "port": self.port if alive else None,
            "device_id": self.device_id if alive else None,
            "connected_at": self.connected_at if alive else None,   # epoch s; dashboard live mode shows data since then
            "samples": self.samples,
            "imu_ok": self.imu_ok,
            "vitals_ok": self.vitals_ok,
            "last_sample_age_s": round(time.time() - self.last_sample_at, 1) if self.last_sample_at else None,
            "last_message": self.last_message,
            "error": self.error,
        }

    def connect(self, port: str, device_id: str):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise BridgeError(f"already connected to {self.port}")
            if port not in {p["device"] for p in list_serial_ports()}:
                raise BridgeError(f"unknown serial port: {port}")
            try:
                ser = serial.Serial(port, BAUD, timeout=0.2)
            except (serial.SerialException, OSError) as e:
                raise BridgeError(f"cannot open {port}: {e}") from e
            self._reset_status()
            self.port, self.device_id = port, device_id
            self.connected_at = time.time()
            live_state.reset_device(device_id)  # drop any stale rolling window
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, args=(ser, device_id), daemon=True)
            self._thread.start()

    def disconnect(self):
        with self._lock:
            t = self._thread
            if t is None:
                return
            self._stop.set()
        t.join(timeout=3)

    def _run(self, ser: serial.Serial, device_id: str):
        conn = db.get_connection()
        buf = b""
        last_buzz = 0.0
        try:
            while not self._stop.is_set():
                buf += ser.read(max(1, ser.in_waiting))
                if len(buf) > 4096 and b"\n" not in buf:  # garbage with no newline (wrong baud): don't grow forever
                    buf = b""
                *lines, buf = buf.split(b"\n")
                for raw in lines:
                    text = raw.decode("ascii", errors="replace").strip()
                    if not text:
                        continue
                    payload = parse_line(text, device_id)
                    if payload is None:
                        m = SENSORS_RE.match(text)
                        if m:
                            self.imu_ok, self.vitals_ok = m.group(1) == "1", m.group(2) == "1"
                        else:
                            self.last_message = text[:200]
                        continue
                    if "imu" not in payload:   # vitals-only (IMU missing): store, no inference possible
                        v = payload["vitals"]
                        db.insert_vitals(conn, device_id, payload["timestamp"], v.get("heart_rate"), v.get("spo2"))
                        self.samples += 1
                        self.last_sample_at = time.time()
                        continue
                    try:
                        resp = process_sample(conn, validate_sensor_payload(payload))
                    except PayloadValidationError:
                        continue
                    except Exception as e:  # keep streaming; surface it in the UI
                        self.error = f"{type(e).__name__}: {e}"
                        continue
                    self.samples += 1
                    self.last_sample_at = time.time()
                    if resp.get("buzzer") and time.time() - last_buzz > 1.0:
                        ser.write(b"B\n")
                        last_buzz = time.time()
        except (serial.SerialException, OSError) as e:  # cable pulled, board reset by someone else, ...
            self.error = f"serial lost: {e}"
        finally:
            ser.close()
            conn.close()


bridge = SerialBridge()
