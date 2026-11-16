// SmartHealth AI dashboard configuration. Edit here; nothing below is hard-coded elsewhere.
window.SMARTHEALTH_CONFIG = {
  DEFAULT_DEVICE_ID: "wearable_01",
  API_BASE_URL: "",              // "" = same origin as the Flask app

  POLL_INTERVAL_MS: 1000,        // vitals, activity, alerts, tremor, motion
  STALE_AFTER_MS: 15000,         // no successful poll for this long = connection LED idle
  SPARK_POINTS: 60,              // points kept in the heart rate / SpO2 sparklines
  EVENTS_SHOWN: 10,              // rows in the events list

  // Tremor & motion panel (static/gyro.js)
  IMU_POLL_INTERVAL_MS: 250,     // /api/imu, only while a data source is active
  IMU_WINDOW_SAMPLES: 200,       // samples drawn across each trace (4 s at 50 Hz)
  IMU_MIN_RANGE_DPS: 25,         // smallest +/- scale of the gyro strips
  IMU_STALE_AFTER_S: 2,          // no new samples for this long = stale
  CALIB_POLL_MS: 250,            // /api/calibration while collecting
  CALIB_IDLE_POLL_MS: 3000,      // ... and otherwise

  // Model comparison (static/models.js)
  LIVE_MODELS_POLL_MS: 2000,     // /api/models/live
};
