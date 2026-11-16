// Where the dashboard's data comes from. Exactly one of three modes at any time:
//   idle  (default)  nothing is fetched or shown. No simulated data, no old database rows.
//   demo             simulated data from mock.js, clearly labelled. Only when the user presses "Demo".
//   live             REAL hardware only: the backend API, restricted to rows recorded since the USB
//                    session started (?since=...), so earlier runs / simulated rows never show up.
// app.js already routes every API call through window.__mockGetJSON when window.__MOCK_ENABLED is set
// (the hook name is historical); this file installs the router behind that hook.
(() => {
  const CFG = window.SMARTHEALTH_CONFIG;
  const $ = (id) => document.getElementById(id);
  let mode = "idle", since = 0, label = "";

  const EMPTY = {
    "/api/vitals": { heart_rate: null, spo2: null },
    "/api/activity": { activity: null, confidence: null },
    "/api/alerts": [],
    "/api/history": [],
    "/api/latest": { reading: null, prediction: null },
    "/api/tremor": { state: "no_data" },
  };

  window.__MOCK_ENABLED = true;
  window.__mockGetJSON = async (path, params = {}) => {
    if (mode === "demo") return window.__sim.route(path, params);
    if (mode === "idle") return JSON.parse(JSON.stringify(EMPTY[path] ?? {}));
    const res = await fetch(CFG.API_BASE_URL + path + qs({ ...params, since }));   // qs() is defined in app.js
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return res.json();
  };

  const BANNER = {
    idle: () => "Not connected. Plug in the board and press Connect, or press Demo to preview with simulated data.",
    demo: () => "DEMO MODE: simulated data for display, not from hardware.",
    live: () => `LIVE: hardware on ${label}. Showing only data recorded since you connected.`,
  };

  function render() {
    const banner = $("mode-banner"), demoBtn = $("demo-btn");
    banner.dataset.mode = mode;
    banner.textContent = BANNER[mode]();
    demoBtn.textContent = mode === "demo" ? "Exit demo" : "Demo";
    demoBtn.setAttribute("aria-pressed", String(mode === "demo"));
    demoBtn.disabled = mode === "live";        // hardware connected: live data only
    demoBtn.title = mode === "live" ? "Disconnect the hardware to use demo mode" : "Show simulated data for display";
  }

  window.__getMode = () => ({ mode, since });
  window.__setMode = (next, opts = {}) => {
    if (next === "demo" && mode === "live") return;   // never mix simulated data into a live session
    if (mode === "demo" && next !== "demo") window.__sim.stop();
    mode = next; since = opts.since || 0; label = opts.label || "";
    if (mode === "demo") window.__sim.start();
    render();
    if (typeof state !== "undefined") { state.accelTrace = []; state.hrTrace = []; state.spo2Trace = []; }
    if (typeof backfillTraces === "function") backfillTraces().then(refresh);
  };

  $("demo-btn").addEventListener("click", () => window.__setMode(mode === "demo" ? "idle" : "demo"));
  render();
})();
