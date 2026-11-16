// Where the dashboard's data comes from. Exactly one of three modes at any time:
//   idle  (default)  nothing is fetched or shown (offline model results excepted: see below).
//   demo             simulated data from mock.js, clearly labelled. Only when the user presses "Demo".
//   live             REAL hardware only: backend API, restricted to rows recorded since the USB session
//                    started (?since=...), so earlier runs / simulated rows never show up.
// app.js routes every API call through window.__mockGetJSON (the hook name is historical).
(() => {
  const CFG = window.SMARTHEALTH_CONFIG;
  const $ = (id) => document.getElementById(id);
  let mode = "idle", since = 0, label = "";

  const EMPTY = {
    "/api/vitals": { heart_rate: null, spo2: null },
    "/api/activity": { activity: null, confidence: null },
    "/api/alerts": [],
    "/api/history": [],
    "/api/tremor": { state: "no_data" },
    "/api/motion": {},
    "/api/imu": { samples: [], latest: null, rate_hz: 0, calibrated: false, age_s: null },
    "/api/calibration": { state: "idle", progress: 0, calibrated: false, bias_deg_s: null, message: "" },
    "/api/models/live": { at: null, age_s: null, cnn: null, lstm: null, agree: null },
  };
  // Per-device in-memory or offline data: never filtered by the USB session start.
  const NO_SINCE = new Set(["/api/imu", "/api/calibration", "/api/models", "/api/models/live"]);
  // Offline evaluation results are real in every mode (demo included).
  const ALWAYS_REAL = new Set(["/api/models"]);

  async function real(path, params) {
    const p = { ...params };
    if (!NO_SINCE.has(path)) p.since = since;
    const res = await fetch(CFG.API_BASE_URL + path + qs(p));   // qs() is defined in app.js
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return res.json();
  }

  window.__MOCK_ENABLED = true;
  window.__mockGetJSON = async (path, params = {}) => {
    if (ALWAYS_REAL.has(path)) return real(path, params);
    if (mode === "demo") return window.__sim.route(path, params);
    if (mode === "idle") return JSON.parse(JSON.stringify(EMPTY[path] ?? {}));
    return real(path, params);
  };

  const BANNER = {
    idle: () => "Not connected. Plug in the board and press Connect, or press Demo to preview with simulated data.",
    demo: () => "DEMO: simulated data for display, not from hardware.",
    live: () => `LIVE: hardware on ${label}. Showing only data recorded since you connected.`,
  };

  function render() {
    const banner = $("mode-banner"), demoBtn = $("demo-btn");
    banner.dataset.mode = mode;
    banner.textContent = BANNER[mode]();
    demoBtn.textContent = mode === "demo" ? "Exit demo" : "Demo";
    demoBtn.setAttribute("aria-pressed", String(mode === "demo"));
    demoBtn.disabled = mode === "live";
    demoBtn.title = mode === "live" ? "Disconnect the hardware to use demo mode" : "Show simulated data for display";
  }

  window.__getMode = () => ({ mode, since });
  window.__setMode = (next, opts = {}) => {
    if (next === "demo" && mode === "live") return;   // never mix simulated data into a live session
    if (mode === "demo" && next !== "demo") window.__sim.stop();
    mode = next; since = opts.since || 0; label = opts.label || "";
    if (mode === "demo") window.__sim.start();
    render();
    window.dispatchEvent(new CustomEvent("sh:mode", { detail: { mode } }));   // every panel resets and re-polls
  };

  $("demo-btn").addEventListener("click", () => window.__setMode(mode === "demo" ? "idle" : "demo"));
  render();
})();
