// SmartHealth AI -- NodeMCU v3 (ESP8266), USB cable only. No WiFi.
//
// Wiring (3.3 V only):
//   MPU6050  VCC->3V3  GND->GND  SDA->D2  SCL->D1  AD0->GND
//   MAX30102 VIN->3V3  GND->GND  SDA->D2  SCL->D1  (INT unused)
//   Active buzzer +->D5, -->GND  (use a transistor or module)
//   Push button D6 -> GND        (silences the buzzer)
//
// Arduino IDE setup:
//   Board: "NodeMCU 1.0 (ESP-12E Module)" from the esp8266 package.
//   Libraries: Adafruit MPU6050, Adafruit Unified Sensor,
//              SparkFun MAX3010x Pulse and Proximity Sensor Library.
//
// Usage: upload, CLOSE the Serial Monitor, start the backend, open the
// dashboard, pick this board's port in the top bar and press Connect.
//
// Each sensor is independent. If one is missing or fails, the other keeps
// working. A sensor plugged in later (or unplugged) is noticed within ~1 s.
// Without the MPU6050 there is no motion data, so no activity or fall
// detection, only heart rate and SpO2.
//
// USB protocol, 115200 baud, one message per line:
//   board -> host  D,ax,ay,az,gx,gy,gz,hr,spo2
//                    50 lines/s. m/s^2, rad/s, bpm, %. hr/spo2 = -1 if
//                    unknown.
//                  V,hr,spo2
//                    1 line/s, only while the MPU6050 is missing.
//                  # sensors imu=1 vitals=0
//                    which sensors are alive (on change and every 5 s).
//                  # ...
//                    other log text, ignored by the data parser.
//   host  -> board B
//                    confirmed fall: sound the buzzer.

#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Arduino.h>
#include <MAX30105.h>
#include <Wire.h>
#include <heartRate.h>

// ===================== CONFIG =====================
#define SDA_PIN 4      // D2
#define SCL_PIN 5      // D1
#define BUZZER_PIN 14  // D5
#define BUTTON_PIN 12  // D6 (to GND)

#define MPU_ADDR 0x68  // MPU6050 with AD0 -> GND
#define PPG_ADDR 0x57  // MAX30102

#define SAMPLE_INTERVAL_MS 20  // 50 Hz, must match the ML model
#define BUZZER_ON_MS 3000
#define BUZZER_MUTE_MS 10000  // after a button press, ignore fall commands
// ==================================================

static Adafruit_MPU6050 mpu;
static MAX30105 ppg;

struct ImuSample {
  float ax, ay, az, gx, gy, gz;
  bool valid;
};
struct VitalsSample {
  float hr, spo2;
  bool valid;
};

static unsigned long buzzer_off_at_ms = 0, muted_until_ms = 0;
static bool imu_ok = false, vitals_ok = false;

// ---------- IMU ----------
static bool imu_init() {
  if (!mpu.begin(MPU_ADDR, &Wire))
    return false;
  mpu.setAccelerometerRange(MPU6050_RANGE_16_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  return true;
}

static ImuSample imu_read() {
  ImuSample s{};
  sensors_event_t a, g, t;
  if (!mpu.getEvent(&a, &g, &t))
    return s;  // valid = false
  s = {a.acceleration.x, a.acceleration.y, a.acceleration.z,
       g.gyro.x,         g.gyro.y,         g.gyro.z,
       true};  // m/s^2, rad/s
  return s;
}

// ---------- Heart rate / SpO2 (MAX30102) ----------
// SpO2 is a simplified AC/DC ratio ESTIMATE, not clinical.
static const uint8_t RATE_SIZE = 4;
static float rates[RATE_SIZE];
static uint8_t rate_spot = 0, rate_count = 0;
static unsigned long last_beat = 0, last_beat_ms = 0;
static float current_bpm = -1;
static const uint8_t SPO2_N = 100;  // 2 s at 50 Hz
static uint32_t ir_buf[SPO2_N], red_buf[SPO2_N];
static uint8_t spo2_idx = 0;
static bool spo2_full = false;

static bool vitals_init() {
  if (!ppg.begin(Wire, I2C_SPEED_FAST))
    return false;
  // ~12 mA, avg 4, red+IR, 200 sps / 4 = 50 Hz output, 411 us, 4096 nA
  ppg.setup(60, 4, 2, 200, 411, 4096);
  return true;
}

static float spo2_estimate() {
  if (!spo2_full)
    return -1;
  uint32_t imin = UINT32_MAX, imax = 0, rmin = UINT32_MAX, rmax = 0;
  uint64_t isum = 0, rsum = 0;
  for (uint8_t i = 0; i < SPO2_N; i++) {
    imin = min(imin, ir_buf[i]);
    imax = max(imax, ir_buf[i]);
    rmin = min(rmin, red_buf[i]);
    rmax = max(rmax, red_buf[i]);
    isum += ir_buf[i];
    rsum += red_buf[i];
  }
  float idc = isum / (float)SPO2_N, rdc = rsum / (float)SPO2_N;
  float iac = imax - imin, rac = rmax - rmin;
  if (idc <= 0 || rdc <= 0 || iac <= 0)
    return -1;
  float r = (rac / rdc) / (iac / idc);
  return constrain(110.0f - 25.0f * r, 0.0f, 100.0f);
}

// Call at 50 Hz: beat detection needs a dense PPG stream.
static VitalsSample vitals_read() {
  VitalsSample s{-1, -1, false};
  long ir = ppg.getIR(), red = ppg.getRed();
  if (ir < 5000) {  // no contact: drop state so no stale value is reported
    current_bpm = -1;
    rate_count = 0;
    rate_spot = 0;
    last_beat = 0;
    spo2_idx = 0;
    spo2_full = false;
    return s;
  }
  unsigned long now = millis();
  if (checkForBeat(ir)) {
    if (last_beat != 0) {
      float bpm = 60000.0f / (now - last_beat);
      if (bpm > 30 && bpm < 220) {
        rates[rate_spot++] = bpm;
        rate_spot %= RATE_SIZE;
        if (rate_count < RATE_SIZE)
          rate_count++;
        float sum = 0;
        for (uint8_t i = 0; i < rate_count; i++)
          sum += rates[i];
        current_bpm = sum / rate_count;
        last_beat_ms = now;
      }
    }
    last_beat = now;
  }
  if (current_bpm > 0 && now - last_beat_ms > 5000)
    current_bpm = -1;  // no beat for 5 s
  ir_buf[spo2_idx] = ir;
  red_buf[spo2_idx] = red;
  spo2_idx = (spo2_idx + 1) % SPO2_N;
  if (spo2_idx == 0)
    spo2_full = true;
  s = {current_bpm, spo2_estimate(), true};
  return s;
}

// ---------- Sensor presence (independent, hot-pluggable) ----------
static bool i2c_present(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

// Probe both sensors. Initialise one that appeared, mark a lost one as gone.
static void check_sensors(bool report) {
  bool was_imu = imu_ok, was_vit = vitals_ok;

  bool present = i2c_present(MPU_ADDR);
  if (imu_ok && !present)
    imu_ok = false;
  else if (!imu_ok && present)
    imu_ok = imu_init();

  present = i2c_present(PPG_ADDR);
  if (vitals_ok && !present)
    vitals_ok = false;
  else if (!vitals_ok && present)
    vitals_ok = vitals_init();

  if (was_imu != imu_ok)
    Serial.printf("# MPU6050 %s\n", imu_ok ? "connected" : "LOST");
  if (was_vit != vitals_ok)
    Serial.printf("# MAX30102 %s\n", vitals_ok ? "connected" : "LOST");
  if (report || was_imu != imu_ok || was_vit != vitals_ok)
    Serial.printf("# sensors imu=%d vitals=%d\n", imu_ok, vitals_ok);
}

// ---------- Buzzer ----------
static void set_buzzer(bool on) { digitalWrite(BUZZER_PIN, on ? HIGH : LOW); }

static void trigger_fall(unsigned long now) {
  if ((long)(now - muted_until_ms) >= 0 && buzzer_off_at_ms == 0) {
    Serial.println("# CONFIRMED FALL -- buzzer");
    set_buzzer(true);
    buzzer_off_at_ms = now + BUZZER_ON_MS;
  }
}

// ---------- Arduino ----------
void setup() {
  Serial.begin(115200);
  delay(200);
  pinMode(BUZZER_PIN, OUTPUT);
  set_buzzer(false);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  Wire.begin(SDA_PIN, SCL_PIN);
  check_sensors(true);  // never blocks: a missing sensor is retried in loop()
  if (!imu_ok)
    Serial.println("# MPU6050 not found (D2/D1/3V3/GND, AD0->GND). Retrying.");
  if (!vitals_ok)
    Serial.println("# MAX30102 not found (D2/D1/VIN/GND). Retrying.");
  Serial.println("# Running.");
}

void loop() {
  static unsigned long next_ms = millis();
  static unsigned long last_report_ms = 0, last_check_ms = 0, last_v_ms = 0;
  static float hr = -1, spo2 = -1;
  static bool button_prev = HIGH;

  unsigned long now = millis();
  if ((long)(now - next_ms) < 0)
    return;  // fixed-schedule 50 Hz tick
  next_ms += SAMPLE_INTERVAL_MS;
  if ((long)(now - next_ms) > 100)
    next_ms = now + SAMPLE_INTERVAL_MS;  // far behind: resync

  // Host command: 'B' = confirmed fall.
  while (Serial.available()) {
    if (Serial.read() == 'B')
      trigger_fall(now);
  }

  // Button silences the buzzer and ignores fall commands for a while.
  bool button_now = digitalRead(BUTTON_PIN);
  if (button_prev == HIGH && button_now == LOW) {
    set_buzzer(false);
    buzzer_off_at_ms = 0;
    muted_until_ms = now + BUZZER_MUTE_MS;
  }
  button_prev = button_now;
  if (buzzer_off_at_ms != 0 && (long)(now - buzzer_off_at_ms) >= 0) {
    set_buzzer(false);
    buzzer_off_at_ms = 0;
  }

  if (now - last_check_ms >= 1000) {  // notice sensors appearing / vanishing
    last_check_ms = now;
    check_sensors(false);
  }

  // Vitals are polled at 50 Hz even without the IMU (beat detection).
  hr = spo2 = -1;
  if (vitals_ok) {
    VitalsSample v = vitals_read();
    if (v.valid) {
      hr = v.hr;
      spo2 = v.spo2;
    }
  }

  if (imu_ok) {
    ImuSample imu = imu_read();
    if (imu.valid)
      Serial.printf("D,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.0f,%.0f\n", imu.ax,
                    imu.ay, imu.az, imu.gx, imu.gy, imu.gz, hr, spo2);
  } else if (vitals_ok && now - last_v_ms >= 1000) {
    // Vitals-only mode. Always sent, -1 means no finger on the sensor.
    last_v_ms = now;
    Serial.printf("V,%.0f,%.0f\n", hr, spo2);
  }

  if (now - last_report_ms >= 5000) {
    last_report_ms = now;
    Serial.printf("# sensors imu=%d vitals=%d\n", imu_ok, vitals_ok);
    Serial.printf("# [%lus] hr=%.0f spo2=%.0f heap=%u\n", now / 1000, hr, spo2,
                  ESP.getFreeHeap());
  }
}
