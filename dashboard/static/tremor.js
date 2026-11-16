// Tremor card: polls /api/tremor (accelerometer spectral analysis on the backend, or the demo engine).
(() => {
  const CFG = window.SMARTHEALTH_CONFIG;
  const led = document.getElementById("tremor-led"), val = document.getElementById("tremor-value");

  function render(t) {
    let text = "No motion data", ledState = "unavailable", tip = "Needs the motion sensor (MPU6050) streaming";
    if (t.state === "warming_up") { text = "Analysing…"; ledState = "idle"; tip = "Collecting the first 3 seconds"; }
    else if (t.state === "none") { text = "Not detected"; ledState = "idle"; tip = ""; }
    else if (t.state === "detected") {
      text = `Detected · ${t.freq_hz.toFixed(1)} Hz`; ledState = "warn";
      tip = `Dominant ${t.freq_hz.toFixed(1)} Hz, amplitude ${t.amplitude.toFixed(2)} m/s² RMS`;
    }
    led.dataset.state = ledState; val.textContent = text; val.title = tip;
  }

  async function poll() {
    try { render(await getJSON("/api/tremor", { device_id: state.deviceId })); }   // getJSON/state come from app.js
    catch { render({ state: "no_data" }); }
  }
  poll();
  setInterval(poll, CFG.POLL_INTERVAL_MS);
})();
