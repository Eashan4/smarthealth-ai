// SmartHealth AI -- ESP32 firmware.
//
// Implements docs/DOCUMENTATION.md sec 12 responsibilities 1-11: init
// sensors -> init WiFi -> read at configured rate -> timestamp -> build JSON
// (sec 13 schema) -> POST to Flask -> act on response (buzzer) -> handle
// network failures without blocking local acquisition.
//
// STATUS: written against the Adafruit MPU6050 / SparkFun MAX3010x /
// ArduinoJson APIs but NOT flashed or run on physical hardware -- no ESP32
// board is available in this environment. Phase 1 (docs/PLAN.md) exit
// criteria ("raw IMU and PPG values print reliably over serial") is
// therefore NOT met yet. Treat this as code-complete-pending-hardware, not
// hardware-validated; verify pin assignments (config.h) and library
// versions (platformio.ini) against the real board before trusting it.
//
// Copy secrets.h.example -> secrets.h and fill in real WiFi/backend values
// before building (secrets.h is gitignored, never commit it).

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include "config.h"
#include "secrets.h"
#include "sensors.h"

static unsigned long last_imu_ms = 0;
static unsigned long last_hr_ms = 0;
static unsigned long last_wifi_attempt_ms = 0;
static unsigned long buzzer_off_at_ms = 0;

static float last_hr = -1;
static float last_spo2 = -1;

static void connect_wifi() {
    Serial.printf("Connecting to WiFi '%s'...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_CONNECT_TIMEOUT_MS) {
        delay(250);  // setup()-time only; fine to block briefly here
        Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\nWiFi connected, IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\nWiFi connect timed out; will retry in background loop.");
    }
}

static void set_buzzer(bool on, unsigned long duration_ms = 0) {
    digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
    if (on && duration_ms > 0) {
        buzzer_off_at_ms = millis() + duration_ms;
    }
}

static void send_reading(const ImuSample &imu) {
    if (WiFi.status() != WL_CONNECTED) {
        // Responsibility #11: keep acquiring locally, just skip the send.
        Serial.printf("[offline] ax=%.2f ay=%.2f az=%.2f gx=%.2f gy=%.2f gz=%.2f hr=%.0f spo2=%.0f\n",
                      imu.ax, imu.ay, imu.az, imu.gx, imu.gy, imu.gz, last_hr, last_spo2);
        return;
    }

    JsonDocument doc;
    doc["device_id"] = DEVICE_ID;
    doc["timestamp"] = (double)millis() / 1000.0;  // seconds; replace with NTP epoch if available
    JsonObject imu_obj = doc["imu"].to<JsonObject>();
    imu_obj["ax"] = imu.ax; imu_obj["ay"] = imu.ay; imu_obj["az"] = imu.az;
    imu_obj["gx"] = imu.gx; imu_obj["gy"] = imu.gy; imu_obj["gz"] = imu.gz;
    if (last_hr > 0 || last_spo2 > 0) {
        JsonObject vitals_obj = doc["vitals"].to<JsonObject>();
        if (last_hr > 0) vitals_obj["heart_rate"] = last_hr;
        if (last_spo2 > 0) vitals_obj["spo2"] = last_spo2;
    }

    String body;
    serializeJson(doc, body);

    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.begin(BACKEND_URL);
    http.addHeader("Content-Type", "application/json");
    int status = http.POST(body);

    if (status > 0) {
        String response_body = http.getString();
        JsonDocument resp;
        if (deserializeJson(resp, response_body) == DeserializationError::Ok) {
            if (resp["buzzer"].is<bool>() && resp["buzzer"].as<bool>()) {
                Serial.println("!!! CONFIRMED FALL -- sounding buzzer !!!");
                set_buzzer(true, 3000);
            }
        }
    } else {
        Serial.printf("POST failed: %s\n", http.errorToString(status).c_str());
    }
    http.end();
}

void setup() {
    Serial.begin(115200);
    delay(200);

    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
    pinMode(BUTTON_PIN, INPUT_PULLUP);

    Serial.println("Initializing MPU6050...");
    if (!sensors_init_imu()) {
        Serial.println("MPU6050 init FAILED -- check wiring/I2C address.");
    }

    Serial.println("Initializing MAX30102...");
    if (!sensors_init_vitals()) {
        Serial.println("MAX30102 init FAILED -- check wiring/I2C address.");
    }

    connect_wifi();
}

void loop() {
    unsigned long now = millis();

    // Non-blocking WiFi reconnect with backoff (responsibility #10).
    if (WiFi.status() != WL_CONNECTED && now - last_wifi_attempt_ms > WIFI_RECONNECT_BACKOFF_MS) {
        last_wifi_attempt_ms = now;
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }

    // Silence an active buzzer on button press (debounced by edge + cooldown).
    static bool button_prev = HIGH;
    bool button_now = digitalRead(BUTTON_PIN);
    if (button_prev == HIGH && button_now == LOW) {
        set_buzzer(false);
        buzzer_off_at_ms = 0;
    }
    button_prev = button_now;

    if (buzzer_off_at_ms != 0 && now >= buzzer_off_at_ms) {
        set_buzzer(false);
        buzzer_off_at_ms = 0;
    }

    if (now - last_hr_ms >= HR_SAMPLE_INTERVAL_MS) {
        last_hr_ms = now;
        VitalsSample v = sensors_read_vitals();
        if (v.valid) {
            if (v.heart_rate > 0) last_hr = v.heart_rate;
            if (v.spo2 > 0) last_spo2 = v.spo2;
        }
    }

    if (now - last_imu_ms >= IMU_SAMPLE_INTERVAL_MS) {
        last_imu_ms = now;
        ImuSample imu = sensors_read_imu();
        if (imu.valid) {
            send_reading(imu);
        } else {
            Serial.println("IMU read failed, skipping sample.");
        }
    }
}
