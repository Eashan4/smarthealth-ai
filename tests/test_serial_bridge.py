"""Hardware-free check of the USB serial path: a pty plays the board, the real Flask routes + bridge
ingest it into a temp DB. Run: python -m tests.test_serial_bridge"""

import os, tempfile, threading, time
from pathlib import Path

from backend.database import db
db.DB_PATH = Path(tempfile.mkdtemp()) / "t.db"   # never touch the real data/smarthealth.db

from backend.app import create_app
from backend.routes import serial_routes as sr
from backend.services import serial_bridge as sb

real_process_sample = sb.process_sample   # test_end_to_end swaps in a fake; later tests restore this


def test_parse_line():
    p = sb.parse_line("D,0.1,0.2,9.8,0.0,0.0,0.0,72,97", "d")
    assert p["imu"]["az"] == 9.8 and p["vitals"] == {"heart_rate": 72.0, "spo2": 97.0}
    assert "vitals" not in sb.parse_line("D,0,0,9.8,0,0,0,-1,-1", "d")
    v = sb.parse_line("V,72,97", "d")
    assert "imu" not in v and v["vitals"] == {"heart_rate": 72.0, "spo2": 97.0}
    assert sb.parse_line("V,-1,-1", "d")["vitals"] == {}          # "no finger" is kept so it can clear the display
    assert sb.parse_line("V,1,2,3", "d") is None
    for bad in ("", "# boot", "D,1,2,3", "D,a,b,c,d,e,f,g,h", "D,nan,0,0,0,0,0,0,0", "X,0,0,0,0,0,0,0,0"):
        assert sb.parse_line(bad, "d") is None, bad


def test_end_to_end():
    master, slave = os.openpty()
    slave_path = os.ttyname(slave)
    fake_ports = lambda: [{"device": slave_path, "description": "pty", "usb": True}]
    sb.list_serial_ports = sr.list_serial_ports = fake_ports
    real_process, calls = sb.process_sample, []
    def fake_process(conn, clean):          # first sample pretends the backend confirmed a fall
        r = real_process(conn, clean); calls.append(1)
        if len(calls) == 5: r["buzzer"] = True
        return r
    sb.process_sample = fake_process

    got, stop = bytearray(), threading.Event()
    def board():                             # 50 Hz like the firmware, plus boot noise and a log line
        os.write(master, b"\xff\xfegarbage at 74880 baud\n# Running.\n")
        i = 0
        while not stop.is_set():
            os.write(master, f"D,0.01,0.02,9.81,0.0,0.0,0.0,{70 + i % 5},97\n".encode()); i += 1
            time.sleep(0.02)
    def host_rx():
        while not stop.is_set():
            try: got.extend(os.read(master, 64))
            except OSError: return

    c = create_app().test_client()
    assert c.post("/api/serial/connect", json={"port": "/dev/nope"}).status_code == 409   # whitelist
    assert c.get("/api/serial/ports").get_json()["ports"][0]["device"] == slave_path
    st = c.post("/api/serial/connect", json={"port": slave_path, "device_id": "usb_test"}).get_json()
    assert st["connected"]
    assert c.post("/api/serial/connect", json={"port": slave_path}).status_code == 409    # already connected
    [threading.Thread(target=f, daemon=True).start() for f in (board, host_rx)]   # board powers up now
    time.sleep(2.0)
    st = c.get("/api/serial/status").get_json()
    assert st["connected"] and st["samples"] > 60 and st["last_sample_age_s"] < 1, st
    assert st["last_message"] == "# Running.", st
    latest = c.get("/api/latest?device_id=usb_test").get_json()["reading"]
    assert latest["az"] == 9.81, latest                                                   # dashboard sees it
    st = c.post("/api/serial/disconnect").get_json()
    assert not st["connected"]
    time.sleep(0.2); stop.set()
    assert b"B\n" in got, "buzzer command missing"
    print(f"OK: {st['samples']} samples ingested over the pty, buzzer command seen by the 'board'")


def _fake_board(lines_by_time, seconds, device_id):
    """Connect the bridge to a pty that emits `lines_by_time` (list of (delay_s, bytes)); returns (client, status)."""
    master, slave = os.openpty()
    slave_path = os.ttyname(slave)
    sb.list_serial_ports = sr.list_serial_ports = lambda: [{"device": slave_path, "description": "pty", "usb": True}]
    sb.process_sample = real_process_sample
    c = create_app().test_client()
    assert c.post("/api/serial/connect", json={"port": slave_path, "device_id": device_id}).get_json()["connected"]
    def board():
        for delay, line in lines_by_time:
            time.sleep(delay); os.write(master, line)
    threading.Thread(target=board, daemon=True).start()
    time.sleep(seconds)
    st = c.get("/api/serial/status").get_json()
    return c, st


def test_vitals_only_when_imu_missing():
    lines = [(0.0, b"# sensors imu=0 vitals=1\n")] + [(0.1, b"V,72,97\n")] * 8
    c, st = _fake_board(lines, 1.5, "vonly")
    assert st["imu_ok"] is False and st["vitals_ok"] is True and st["samples"] >= 5, st
    assert c.get("/api/vitals?device_id=vonly").get_json()["heart_rate"] == 72.0   # dashboard shows HR without IMU
    c.post("/api/serial/disconnect")


def test_vitals_clear_when_finger_removed():
    lines = [(0.0, b"# sensors imu=0 vitals=1\n"), (0.1, b"V,72,97\n"), (0.3, b"V,-1,-1\n")]
    c, st = _fake_board(lines, 1.0, "vclear")
    v = c.get("/api/vitals?device_id=vclear").get_json()
    assert v["heart_rate"] is None and v["spo2"] is None, v
    c.post("/api/serial/disconnect")


def test_imu_only_when_vitals_missing():
    lines = [(0.0, b"# sensors imu=1 vitals=0\n")] + [(0.02, b"D,0.01,0.02,9.81,0,0,0,-1,-1\n")] * 60
    c, st = _fake_board(lines, 2.0, "imuonly")
    assert st["imu_ok"] is True and st["vitals_ok"] is False and st["samples"] >= 50, st
    r = c.get("/api/latest?device_id=imuonly").get_json()["reading"]
    assert r["az"] == 9.81 and r["heart_rate"] is None, r
    assert c.get("/api/vitals?device_id=imuonly").get_json()["heart_rate"] is None
    c.post("/api/serial/disconnect")


def test_no_sensors():
    c, st = _fake_board([(0.0, b"# sensors imu=0 vitals=0\n")], 0.6, "none")
    assert st["imu_ok"] is False and st["vitals_ok"] is False and st["samples"] == 0, st
    c.post("/api/serial/disconnect")


def test_tremor_and_live_only_over_usb():
    import math
    conn = db.get_connection()   # an OLD simulated row for the same device: must never appear in a live session
    db.insert_reading(conn, "tr", 1700000000.0, dict(ax=1, ay=1, az=1, gx=1, gy=1, gz=1), 99, 99)
    db.insert_alert(conn, "tr", 1700000000.0, "fall", "critical", "old fake fall"); conn.close()

    t0 = time.time()
    # 5 Hz hand tremor (0.6 m/s2 peak) on top of gravity, generated against wall-clock time at ~50 Hz
    lines = [(0.02, f"D,0,0,{9.81 + 0.6 * math.sin(2 * math.pi * 5 * (t0 + 0.02 * i)):.4f},0,0,0,-1,-1\n".encode())
             for i in range(400)]
    c, st = _fake_board(lines, 8.5, "tr")
    tr = c.get("/api/tremor?device_id=tr").get_json()
    assert tr["state"] == "detected" and 4.0 <= tr["freq_hz"] <= 6.0, tr
    since = st["connected_at"]
    assert since and since >= t0 - 1, st
    live = c.get(f"/api/latest?device_id=tr&since={since}").get_json()["reading"]
    assert live is not None and live["timestamp"] >= since and live["heart_rate"] is None, live   # not the 99 bpm fake
    assert c.get(f"/api/alerts?device_id=tr&since={since}").get_json() == []                       # old fake fall hidden
    assert c.get("/api/alerts?device_id=tr").get_json()[0]["message"] == "old fake fall"           # still there without since
    assert c.get(f"/api/latest?device_id=tr&since={time.time() + 60}").get_json()["reading"] is None
    c.post("/api/serial/disconnect")
    time.sleep(3.5)
    assert c.get("/api/tremor?device_id=tr").get_json()["state"] == "no_data"                      # stream stopped -> stale


if __name__ == "__main__":
    test_parse_line()
    test_end_to_end()
    test_vitals_only_when_imu_missing()
    test_vitals_clear_when_finger_removed()
    test_imu_only_when_vitals_missing()
    test_no_sensors()
    test_tremor_and_live_only_over_usb()
    print("OK: vitals-only, IMU-only and no-sensor modes behave")
