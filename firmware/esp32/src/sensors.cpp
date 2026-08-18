#include "sensors.h"
#include "config.h"

#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <MAX30105.h>
#include <heartRate.h>
#include <Wire.h>

static Adafruit_MPU6050 mpu;
static MAX30105 particleSensor;

// --- HR beat-detection state (SparkFun-standard moving-average approach) ---
static const uint8_t RATE_SIZE = 4;
static float rates[RATE_SIZE];
static uint8_t rate_spot = 0;
static long last_beat = 0;
static float current_bpm = -1;

// --- SpO2: simplified AC/DC ratio estimate over a short buffer, NOT the
// full Maxim lookup-table algorithm. Documented as an estimate throughout
// this project (docs/DOCUMENTATION.md, README) -- this keeps that honest
// framing true at the firmware level too, rather than implying clinical-
// grade SpO2 calculation. See docs/DOCUMENTATION.md sec 16 known limitations. ---
static const uint8_t SPO2_BUF_SIZE = 50;
static uint32_t ir_buf[SPO2_BUF_SIZE];
static uint32_t red_buf[SPO2_BUF_SIZE];
static uint8_t spo2_buf_idx = 0;
static bool spo2_buf_full = false;

bool sensors_init_imu() {
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    if (!mpu.begin()) {
        return false;
    }
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    return true;
}

bool sensors_init_vitals() {
    if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
        return false;
    }
    particleSensor.setup();  // default: LED brightness, sample avg, mode, rate, pulse width, ADC range
    particleSensor.setPulseAmplitudeRed(0x0A);
    particleSensor.setPulseAmplitudeGreen(0);
    return true;
}

ImuSample sensors_read_imu() {
    ImuSample s{};
    sensors_event_t a, g, temp;
    if (!mpu.getEvent(&a, &g, &temp)) {
        s.valid = false;
        return s;
    }
    s.ax = a.acceleration.x;
    s.ay = a.acceleration.y;
    s.az = a.acceleration.z;
    s.gx = g.gyro.x;
    s.gy = g.gyro.y;
    s.gz = g.gyro.z;
    s.valid = true;
    return s;
}

static float compute_spo2_estimate() {
    if (!spo2_buf_full) return -1;
    uint32_t ir_min = UINT32_MAX, ir_max = 0, red_min = UINT32_MAX, red_max = 0;
    uint64_t ir_sum = 0, red_sum = 0;
    for (uint8_t i = 0; i < SPO2_BUF_SIZE; i++) {
        ir_min = min(ir_min, ir_buf[i]);
        ir_max = max(ir_max, ir_buf[i]);
        red_min = min(red_min, red_buf[i]);
        red_max = max(red_max, red_buf[i]);
        ir_sum += ir_buf[i];
        red_sum += red_buf[i];
    }
    float ir_dc = ir_sum / (float)SPO2_BUF_SIZE;
    float red_dc = red_sum / (float)SPO2_BUF_SIZE;
    float ir_ac = ir_max - ir_min;
    float red_ac = red_max - red_min;
    if (ir_dc <= 0 || red_dc <= 0 || ir_ac <= 0) return -1;

    float r = (red_ac / red_dc) / (ir_ac / ir_dc);
    float spo2 = 110.0f - 25.0f * r;  // simplified empirical formula, see module comment
    if (spo2 > 100) spo2 = 100;
    if (spo2 < 0) spo2 = 0;
    return spo2;
}

VitalsSample sensors_read_vitals() {
    VitalsSample s{-1, -1, false};

    long ir_value = particleSensor.getIR();
    long red_value = particleSensor.getRed();
    if (ir_value < 5000) {
        // No finger/wrist contact detected; don't report a fabricated reading.
        return s;
    }

    if (checkForBeat(ir_value)) {
        long now = millis();
        float delta = now - last_beat;
        last_beat = now;
        float bpm = 60000.0f / delta;
        if (bpm > 20 && bpm < 255) {
            rates[rate_spot++] = bpm;
            rate_spot %= RATE_SIZE;
            float avg = 0;
            for (uint8_t i = 0; i < RATE_SIZE; i++) avg += rates[i];
            current_bpm = avg / RATE_SIZE;
        }
    }

    ir_buf[spo2_buf_idx] = (uint32_t)ir_value;
    red_buf[spo2_buf_idx] = (uint32_t)red_value;
    spo2_buf_idx = (spo2_buf_idx + 1) % SPO2_BUF_SIZE;
    if (spo2_buf_idx == 0) spo2_buf_full = true;

    s.heart_rate = current_bpm;
    s.spo2 = compute_spo2_estimate();
    s.valid = true;
    return s;
}
