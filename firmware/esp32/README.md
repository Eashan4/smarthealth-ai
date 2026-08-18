# ESP32 firmware

Status: **compiles cleanly against the real ESP32 toolchain** (`pio run`,
verified in this environment -- 73% flash / 15% RAM on a standard esp32dev
target) but **not yet flashed or run on physical hardware**. Phase 1 exit
criteria (docs/PLAN.md: "raw IMU and PPG values print reliably over serial")
is therefore still open. Treat this as code-complete-pending-hardware.

## Build

```bash
pip install platformio
cp src/secrets.h.example src/secrets.h   # fill in real WiFi/backend values
cd firmware/esp32
pio run                 # compile
pio run -t upload       # flash (once a board is connected)
pio device monitor       # serial monitor, 115200 baud
```

`secrets.h` is gitignored -- never commit real WiFi credentials (see
docs/AUDIT.md sec 4).

## Wiring (default assumption, unverified -- confirm during Phase 1)

Standard ESP32 DevKit I2C bus, shared by both sensors:

| Signal | ESP32 pin |
|---|---|
| SDA (MPU6050 + MAX30102) | GPIO21 |
| SCL (MPU6050 + MAX30102) | GPIO22 |
| Buzzer (+) | GPIO25 |
| Push button | GPIO26 (internal pull-up, active-low) |

See `src/config.h` for the single source of truth on pins/rates -- update
there (and docs/DOCUMENTATION.md sec 3) once the real board wiring is
confirmed, not scattered across files.

## What it does

1. Init MPU6050 (accel+gyro) and MAX30102 (HR/SpO2 -- see `src/sensors.cpp`
   for the simplified, non-clinical SpO2 estimate formula used).
2. Connect to WiFi.
3. Read IMU at `IMU_SAMPLE_RATE_HZ` (50 Hz) and vitals at 1 Hz, non-blocking.
4. POST each IMU sample + latest known vitals as JSON to `BACKEND_URL`
   (docs/DOCUMENTATION.md sec 13 payload schema).
5. If the backend response has `"buzzer": true` (a confirmed fall, see
   backend/services/decision_engine.py), sound the buzzer for 3s. The push
   button silences an active buzzer early.
6. If WiFi is down, keeps sampling and prints readings to Serial instead of
   blocking or crashing (docs/DOCUMENTATION.md sec 12, responsibility #11).

## Known limitations

- SpO2 uses a simplified AC/DC ratio formula (`compute_spo2_estimate()` in
  `src/sensors.cpp`), not the full Maxim reference lookup-table algorithm --
  consistent with this project's "estimated, not clinical" framing.
- `timestamp` is currently `millis()/1000.0` (seconds since boot), not wall-clock
  time -- add NTP sync (`configTime()`) before Phase 9 demos if wall-clock
  alert timestamps matter for the writeup.
