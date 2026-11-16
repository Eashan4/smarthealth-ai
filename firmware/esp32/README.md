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

## NodeMCU v3 (ESP8266) -- USB cable only, open the .ino in the Arduino IDE

Sketch: `firmware/esp8266_ino/SmartHealth_ESP8266/SmartHealth_ESP8266.ino`. No WiFi. It streams 50 lines/s over USB;
the backend reads them when you pick the port in the dashboard and press Connect (close the Serial Monitor first).
Libraries: Adafruit MPU6050, Adafruit Unified Sensor, SparkFun MAX3010x.

| Part pin | NodeMCU pin (GPIO) |
|---|---|
| MPU6050 VCC / MAX30102 VIN | 3V3 |
| MPU6050 GND / MAX30102 GND | GND |
| MPU6050 SDA + MAX30102 SDA | D2 (GPIO4) |
| MPU6050 SCL + MAX30102 SCL | D1 (GPIO5) |
| MPU6050 AD0 | GND |
| Buzzer + (active) | D5 (GPIO14) |
| Buzzer - | GND |
| Button | D6 (GPIO12) to GND |

## Wiring (ESP32 DevKit, all sensors 3.3 V)

| Part pin | ESP32 pin | Notes |
|---|---|---|
| MPU6050 VCC | 3V3 | |
| MPU6050 GND | GND | |
| MPU6050 SDA | GPIO21 | shared I2C bus |
| MPU6050 SCL | GPIO22 | shared I2C bus |
| MPU6050 AD0 | GND | address 0x68 (do not leave floating) |
| MAX30102 VIN | 3V3 | |
| MAX30102 GND | GND | |
| MAX30102 SDA | GPIO21 | shared (address 0x57) |
| MAX30102 SCL | GPIO22 | shared |
| MAX30102 INT | -- | unused |
| Active buzzer + (or module S/IN) | GPIO25 | active-HIGH; module with transistor preferred |
| Active buzzer - (GND) | GND | |
| Push button | GPIO26 -- GND | internal pull-up, active-low |

Pins live in `src/config.h`. Avoid GPIO 0/2/12/15 (boot straps) and 6-11 (flash).

## Architecture

Core 1 `loop()` samples IMU + MAX30102 at a fixed 50 Hz into a queue; core 0
`net_task` does WiFi/NTP/HTTP POSTs. Slow or dead network never slows sampling
(new samples are dropped and counted: see `dropped=` in the 5 s serial status line).

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

- Not yet run on hardware. One blocking POST per sample means the achievable rate
  depends on WiFi RTT (~15-30 ms typical); watch `dropped=`. A batch endpoint is the fix if it climbs.

- SpO2 uses a simplified AC/DC ratio formula (`compute_spo2_estimate()` in
  `src/sensors.cpp`), not the full Maxim reference lookup-table algorithm --
  consistent with this project's "estimated, not clinical" framing.
- `timestamp` is currently `millis()/1000.0` (seconds since boot), not wall-clock
  time -- add NTP sync (`configTime()`) before Phase 9 demos if wall-clock
  alert timestamps matter for the writeup.
