// Central firmware configuration -- mirrors the philosophy of ml/config.py
// (PLAN.md engineering rule #5: never scatter rates/pins as literals).
//
// Pin assignments are the standard default I2C/GPIO pins for a generic
// ESP32 DevKit board and have NOT been physically verified (Phase 1 exit
// criteria, docs/PLAN.md, is not yet met -- no hardware available in this
// environment). Confirm/adjust against the actual board during Phase 1
// bring-up and update docs/DOCUMENTATION.md sec 3 with the final wiring.
#pragma once

#if defined(ESP8266)
// NodeMCU v3 (ESP-12E). Arduino pin numbers are GPIO numbers: D2=GPIO4, D1=GPIO5, D5=GPIO14, D6=GPIO12.
// Avoid D3/GPIO0, D4/GPIO2, D8/GPIO15 (boot straps) and D0/GPIO16 (no pull-up).
#define I2C_SDA_PIN 4    // D2
#define I2C_SCL_PIN 5    // D1
#define BUZZER_PIN 14    // D5
#define BUTTON_PIN 12    // D6, active-low, internal pullup
#define BATCH_SIZE 10    // samples per POST (200 ms): one HTTP round trip per 10 samples, not per sample
#else
// --- I2C (shared bus: MPU6050 + MAX30102) ---
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22

// --- Digital I/O ---
#define BUZZER_PIN 25
#define BUTTON_PIN 26  // active-low, internal pullup
#endif

// --- Sampling (must match ml/config.py IMU_SAMPLE_RATE) ---
#define IMU_SAMPLE_RATE_HZ 50
#define IMU_SAMPLE_INTERVAL_MS (1000 / IMU_SAMPLE_RATE_HZ)
#define HR_SAMPLE_INTERVAL_MS 1000  // 1 Hz, separate lower-rate stream (DOCUMENTATION.md sec 4)

// --- Networking ---
#define WIFI_CONNECT_TIMEOUT_MS 15000
#define HTTP_TIMEOUT_MS 3000
#define WIFI_RECONNECT_BACKOFF_MS 5000

// --- Alerts / queue ---
#define BUZZER_ON_MS 3000
#define BUZZER_MUTE_MS 10000  // after the button is pressed, ignore fall re-triggers this long
#define NET_QUEUE_LEN 150     // 3 s of samples between sensing core and network core
