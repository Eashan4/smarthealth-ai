// SmartHealth AI -- ESP32 firmware (live streaming).
//
// Architecture (two cores, one queue):
//   core 1  loop()      fixed 50 Hz: read MPU6050 + MAX30102 -> queue; button; buzzer
//   core 0  net_task()  pop queue -> HTTP POST (docs/DOCUMENTATION.md sec 13 schema)
//                       -> if response has "buzzer": true, raise fall_alert
// The network can be slow or down without ever delaying sampling (sec 12 #11):
// if it falls behind the queue fills and NEW samples are dropped (counted).
//
// Copy secrets.h.example -> secrets.h and fill in real values (gitignored).

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <sys/time.h>

#include "config.h"
#include "secrets.h"
#include "sensors.h"

struct Packet {
    double ts;  // epoch seconds if NTP synced, else seconds since boot
    ImuSample imu;
    float hr, spo2;
};

static QueueHandle_t q;
static volatile bool fall_alert = false;     // set by net task, consumed by loop()
static volatile uint32_t dropped = 0;
static unsigned long buzzer_off_at_ms = 0;
static unsigned long muted_until_ms = 0;
static bool vitals_ok = false;

static double now_seconds() {
    struct timeval tv;
    gettimeofday(&tv, nullptr);
    if (tv.tv_sec > 1700000000L) return tv.tv_sec + tv.tv_usec / 1e6;  // NTP synced
    return millis() / 1000.0;
}

static void post_packet(const Packet &p) {
    JsonDocument doc;
    doc["device_id"] = DEVICE_ID;
    doc["timestamp"] = p.ts;
    JsonObject imu = doc["imu"].to<JsonObject>();
    imu["ax"] = p.imu.ax; imu["ay"] = p.imu.ay; imu["az"] = p.imu.az;
    imu["gx"] = p.imu.gx; imu["gy"] = p.imu.gy; imu["gz"] = p.imu.gz;
    if (p.hr > 0 || p.spo2 > 0) {
        JsonObject v = doc["vitals"].to<JsonObject>();
        if (p.hr > 0) v["heart_rate"] = p.hr;
        if (p.spo2 > 0) v["spo2"] = p.spo2;
    }
    String body;
    serializeJson(doc, body);

    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.begin(BACKEND_URL);
    http.addHeader("Content-Type", "application/json");
    int status = http.POST(body);
    if (status > 0) {
        JsonDocument resp;
        if (deserializeJson(resp, http.getString()) == DeserializationError::Ok &&
            resp["buzzer"].as<bool>()) {
            fall_alert = true;
        }
    } else {
        Serial.printf("POST failed: %s\n", http.errorToString(status).c_str());
    }
    http.end();
}

static void net_task(void *) {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    bool ntp_started = false;
    Packet p;
    for (;;) {
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[wifi] not connected, dropping samples");
            xQueueReset(q);  // don't replay stale data when it comes back
            vTaskDelay(pdMS_TO_TICKS(WIFI_RECONNECT_BACKOFF_MS));
            continue;
        }
        if (!ntp_started) {
            Serial.printf("[wifi] connected, IP %s\n", WiFi.localIP().toString().c_str());
            configTime(0, 0, "pool.ntp.org", "time.google.com");  // best effort; falls back to uptime
            ntp_started = true;
        }
        if (xQueueReceive(q, &p, pdMS_TO_TICKS(100)) == pdTRUE) post_packet(p);
    }
}

static void set_buzzer(bool on) { digitalWrite(BUZZER_PIN, on ? HIGH : LOW); }

void setup() {
    Serial.begin(115200);
    delay(200);
    pinMode(BUZZER_PIN, OUTPUT);
    set_buzzer(false);
    pinMode(BUTTON_PIN, INPUT_PULLUP);

    // No IMU = no fall detection: wait for it rather than stream garbage.
    while (!sensors_init_imu()) {
        Serial.println("MPU6050 init FAILED -- check SDA/SCL/3V3/GND and AD0->GND (addr 0x68). Retrying...");
        delay(2000);
    }
    vitals_ok = sensors_init_vitals();
    if (!vitals_ok) Serial.println("MAX30102 init FAILED (addr 0x57) -- continuing IMU-only.");

    q = xQueueCreate(NET_QUEUE_LEN, sizeof(Packet));
    xTaskCreatePinnedToCore(net_task, "net", 8192, nullptr, 1, nullptr, 0);
    Serial.println("Running.");
}

void loop() {
    static unsigned long next_ms = millis();
    static float hr = -1, spo2 = -1;
    static unsigned long last_report_ms = 0;
    static bool button_prev = HIGH;

    // Fixed-schedule 50 Hz tick (no drift from variable work time).
    long wait = (long)(next_ms - millis());
    if (wait > 0) { delay(wait); }
    next_ms += IMU_SAMPLE_INTERVAL_MS;
    unsigned long now = millis();

    // Button: silence now and ignore re-triggers for a while (a confirmed fall keeps returning buzzer=true).
    bool button_now = digitalRead(BUTTON_PIN);
    if (button_prev == HIGH && button_now == LOW) {
        set_buzzer(false);
        buzzer_off_at_ms = 0;
        fall_alert = false;
        muted_until_ms = now + BUZZER_MUTE_MS;
    }
    button_prev = button_now;

    if (fall_alert) {
        fall_alert = false;
        if (now >= muted_until_ms && buzzer_off_at_ms == 0) {
            Serial.println("!!! CONFIRMED FALL -- buzzer !!!");
            set_buzzer(true);
            buzzer_off_at_ms = now + BUZZER_ON_MS;
        }
    }
    if (buzzer_off_at_ms != 0 && now >= buzzer_off_at_ms) {
        set_buzzer(false);
        buzzer_off_at_ms = 0;
    }

    // Vitals are polled at the same 50 Hz as the IMU (beat detection needs a dense PPG stream).
    if (vitals_ok) {
        VitalsSample v = sensors_read_vitals();
        hr = v.valid ? v.heart_rate : -1;      // -1 = no contact / no beat yet; never a stale value
        spo2 = v.valid ? v.spo2 : -1;
    }

    ImuSample imu = sensors_read_imu();
    if (!imu.valid) return;
    Packet p{now_seconds(), imu, hr, spo2};
    if (xQueueSend(q, &p, 0) != pdTRUE) dropped++;

    if (now - last_report_ms >= 5000) {
        last_report_ms = now;
        Serial.printf("[%lus] ax=%.2f ay=%.2f az=%.2f hr=%.0f spo2=%.0f queue=%u dropped=%u wifi=%s\n",
                      now / 1000, imu.ax, imu.ay, imu.az, hr, spo2,
                      (unsigned)uxQueueMessagesWaiting(q), (unsigned)dropped,
                      WiFi.status() == WL_CONNECTED ? "ok" : "down");
    }
}
