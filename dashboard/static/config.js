// SmartHealth AI dashboard configuration.
// Edit this file to change dashboard behavior -- nothing below should be
// hard-coded anywhere else in dashboard/static/app.js.
window.SMARTHEALTH_CONFIG = {
  // Which device to show on load. The device chip in the status bar can
  // switch devices at runtime without editing this file.
  DEFAULT_DEVICE_ID: "wearable_01",

  // How often the dashboard polls the backend, in milliseconds. Lower =
  // more live-feeling, higher server load. 2000 matches the ~1.5-3s cadence
  // a real device is expected to produce inference results at (see
  // docs/DOCUMENTATION.md sec 15).
  POLL_INTERVAL_MS: 2000,

  // How many recent points to keep in the on-screen HR/SpO2/waveform traces
  // and the activity history strip.
  TRACE_HISTORY_LENGTH: 40,
  ACTIVITY_LOG_LENGTH: 12,

  // Base URL for the backend API. Empty string = same origin (default,
  // works when the dashboard is served by the same Flask app). Set to a
  // full origin (e.g. "http://192.168.1.50:5000") to point the dashboard at
  // a backend running elsewhere.
  API_BASE_URL: "",

  // Milliseconds of silence from the backend before the status bar shows
  // the device as disconnected.
  STALE_AFTER_MS: 15000,
};
