// Sensor read wrappers -- kept separate from main.cpp's networking/orchestration
// logic (PLAN.md engineering rule #6: hardware code, backend logic, training
// code, and inference code in separate layers).
#pragma once

#include <Arduino.h>

struct ImuSample {
    float ax, ay, az;  // m/s^2
    float gx, gy, gz;  // rad/s
    bool valid;
};

struct VitalsSample {
    float heart_rate;  // bpm, -1 if not available
    float spo2;        // %, -1 if not available
    bool valid;
};

bool sensors_init_imu();
bool sensors_init_vitals();
ImuSample sensors_read_imu();
VitalsSample sensors_read_vitals();
