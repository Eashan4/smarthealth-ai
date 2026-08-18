"""SQLite storage, per docs/DOCUMENTATION.md sec 14 schema."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "smarthealth.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    ax REAL NOT NULL, ay REAL NOT NULL, az REAL NOT NULL,
    gx REAL NOT NULL, gy REAL NOT NULL, gz REAL NOT NULL,
    heart_rate REAL,
    spo2 REAL
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    activity TEXT NOT NULL,
    confidence REAL NOT NULL,
    fall_probability REAL NOT NULL,
    tremor_probability REAL,
    model_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_readings_device_ts ON sensor_readings(device_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_predictions_device_ts ON predictions(device_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_device_ts ON alerts(device_id, timestamp);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_reading(conn, device_id, timestamp, imu, heart_rate=None, spo2=None) -> int:
    cur = conn.execute(
        "INSERT INTO sensor_readings (device_id, timestamp, ax, ay, az, gx, gy, gz, heart_rate, spo2) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (device_id, timestamp, imu["ax"], imu["ay"], imu["az"], imu["gx"], imu["gy"], imu["gz"],
         heart_rate, spo2),
    )
    conn.commit()
    return cur.lastrowid


def insert_prediction(conn, device_id, timestamp, activity, confidence, fall_probability,
                       tremor_probability, model_name) -> int:
    cur = conn.execute(
        "INSERT INTO predictions (device_id, timestamp, activity, confidence, fall_probability, "
        "tremor_probability, model_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (device_id, timestamp, activity, confidence, fall_probability, tremor_probability, model_name),
    )
    conn.commit()
    return cur.lastrowid


def insert_alert(conn, device_id, timestamp, alert_type, severity, message, status="active") -> int:
    cur = conn.execute(
        "INSERT INTO alerts (device_id, timestamp, alert_type, severity, status, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (device_id, timestamp, alert_type, severity, status, message),
    )
    conn.commit()
    return cur.lastrowid


def latest_reading(conn, device_id=None):
    q = "SELECT * FROM sensor_readings"
    args = ()
    if device_id:
        q += " WHERE device_id = ?"
        args = (device_id,)
    q += " ORDER BY timestamp DESC LIMIT 1"
    row = conn.execute(q, args).fetchone()
    return dict(row) if row else None


def latest_prediction(conn, device_id=None):
    q = "SELECT * FROM predictions"
    args = ()
    if device_id:
        q += " WHERE device_id = ?"
        args = (device_id,)
    q += " ORDER BY timestamp DESC LIMIT 1"
    row = conn.execute(q, args).fetchone()
    return dict(row) if row else None


def recent_alerts(conn, limit=50, device_id=None):
    q = "SELECT * FROM alerts"
    args = ()
    if device_id:
        q += " WHERE device_id = ?"
        args = (device_id,)
    q += " ORDER BY timestamp DESC LIMIT ?"
    rows = conn.execute(q, args + (limit,)).fetchall()
    return [dict(r) for r in rows]


def history(conn, table, limit=100, device_id=None):
    assert table in ("sensor_readings", "predictions", "alerts")
    q = f"SELECT * FROM {table}"
    args = ()
    if device_id:
        q += " WHERE device_id = ?"
        args = (device_id,)
    q += " ORDER BY timestamp DESC LIMIT ?"
    rows = conn.execute(q, args + (limit,)).fetchall()
    return [dict(r) for r in rows]
