// Phase 2 -- IMU data logger (docs/PLAN.md Phase 2).
//
// Separate entry point from main.cpp (Phase 5+ live streaming firmware):
// this one only needs the MPU6050 and prints a labeled CSV line per sample
// over Serial, no WiFi/backend involved. Capture with e.g.:
//   pio device monitor -e esp32dev_logger | tee walking_01.csv
//
// Send a single character over Serial to set the current label before/while
// recording a trial (matches docs/DOCUMENTATION.md sec 8 activity list):
//   w=Walking  r=Running  s=Sitting  l=Lying  f=Fall  x=unlabeled/idle
//
// STATUS: compiles against the real ESP32 toolchain (see firmware/esp32/README.md);
// not yet run on physical hardware.

#include <Arduino.h>
#include "config.h"
#include "sensors.h"

static char current_label = 'x';
static unsigned long last_imu_ms = 0;

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("timestamp_ms,ax,ay,az,gx,gy,gz,label");

    if (!sensors_init_imu()) {
        Serial.println("# MPU6050 init FAILED -- check wiring/I2C address.");
    }
}

void loop() {
    if (Serial.available()) {
        char c = Serial.read();
        if (strchr("wrslfx", c) != nullptr) {
            current_label = c;
        }
    }

    unsigned long now = millis();
    if (now - last_imu_ms < IMU_SAMPLE_INTERVAL_MS) {
        return;
    }
    last_imu_ms = now;

    ImuSample s = sensors_read_imu();
    if (!s.valid) {
        return;
    }
    Serial.printf("%lu,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%c\n",
                  now, s.ax, s.ay, s.az, s.gx, s.gy, s.gz, current_label);
}
