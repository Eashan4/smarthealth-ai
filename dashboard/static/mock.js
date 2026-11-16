/**
 * SmartHealth AI - DEMO data engine
 * Simulated data for presentations ONLY. Does nothing until the Demo button is pressed
 * (datasource.js calls window.__sim.start()) and is never used while real hardware is connected.
 * A simple loop: Sitting -> Walking -> Sitting with tremor -> Fall -> back to Sitting.
 * Simulated: vitals, activity, tremor, IMU, motion, calibration, /api/models/live.
 * (/api/models is the real offline evaluation and is always fetched from the backend.)
 */

(function () {
  "use strict";

  var G = 9.81, HZ = 50, D2R = Math.PI / 180, R2D = 180 / Math.PI;
  var BIAS = { gx: 0.035, gy: -0.021, gz: 0.012 };   // rad/s: the gyro offset that calibration removes
  var CAL_MS = 2200;

  var VITAL_PROFILES = {
    Walking:  { hrBase: 92,  hrVar: 10, spo2Base: 97.5, spo2Var: 0.8 },
    Sitting:  { hrBase: 68,  hrVar: 6,  spo2Base: 98.2, spo2Var: 0.5 },
    Lying:    { hrBase: 58,  hrVar: 5,  spo2Base: 98.8, spo2Var: 0.4 },
        Fall:     { hrBase: 120, hrVar: 25, spo2Base: 95.0, spo2Var: 2.0 },
  };

  // kind drives the signal shape; label/next are shown in the demo-script panel.
  var SCRIPT = [
    { kind: "still",  act: "Sitting", dur: 10, label: "Sitting still" },
    { kind: "walk",   act: "Walking", dur: 12, label: "Walking" },
    { kind: "tremor", act: "Sitting", dur: 12, label: "Sitting with hand tremor at 5 Hz" },
    { kind: "fall",   act: "Fall",    dur: 12, label: "A fall (lift, drop, lie still)" },
  ];
  var CYCLE = SCRIPT.reduce(function (a, p) { return a + p.dur; }, 0);

  var sim = {
    t0: 0, activity: "Sitting", confidence: 0.9, hr: 70, spo2: 98, fallProb: 0.02, fallState: "idle",
    alerts: [], history: [], readings: [], lastPhase: -1, fallAlerted: -1, tremor: { state: "none", freq_hz: 0, amplitude: 0.02 },
  };
  var imu = { buf: [], seq: 0, genT: 0 };
  var cal = { state: "idle", start: 0, calibrated: false, at: null, message: "" };

  function rand(min, max) { return min + Math.random() * (max - min); }
  function randn() { return (Math.random() + Math.random() + Math.random() - 1.5) / 1.5; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function nowTs() { return Math.floor(Date.now() / 1000); }
  function elapsed() { return (Date.now() - sim.t0) / 1000; }

  // Where we are in the script at time t (seconds since start).
  function phaseAt(t) {
    var cycle = Math.floor(t / CYCLE), u = t - cycle * CYCLE;
    for (var i = 0; i < SCRIPT.length; i++) {
      if (u < SCRIPT[i].dur) return { i: i, p: SCRIPT[i], u: u, n: cycle * SCRIPT.length + i };
      u -= SCRIPT[i].dur;
    }
    return { i: 0, p: SCRIPT[0], u: 0, n: 0 };
  }
  // Fall sub-state from seconds into the fall phase: lift, free-fall, impact, still, confirmed.
  function fallStateAt(u) {
    return u < 1.0 ? "idle" : u < 1.4 ? "freefall" : u < 1.5 ? "impact" : u < 3.5 ? "confirming" : "confirmed";
  }

  // Ideal (noise-free) pose at time t: tilt in degrees, motion added on top of gravity (m/s^2), true gyro in deg/s.
  function pose(t) {
    var ph = phaseAt(t), u = ph.u, o = { roll: 3, pitch: -5, gscale: 1, d: [0, 0, 0], g: [0, 0, 0], hz: 0 };
    var w, k = ph.p.kind;
    if (k === "still") {
      o.roll += 0.6 * Math.sin(t * 0.7); o.pitch += 0.4 * Math.sin(t * 0.5);
    } else if (k === "walk") {
      w = 2 * Math.PI * 1.9 * t; o.hz = 1.9;
      o.g = [60 * Math.sin(w), 35 * Math.sin(w + 1.1), 22 * Math.sin(w / 2 + 0.4)];
      o.d = [1.2 * Math.sin(w + 0.5), 1.8 * Math.sin(w + 0.8), 3.2 * Math.sin(w)];
      o.roll += 14 * Math.sin(w + 0.5); o.pitch += 10 * Math.sin(w);
    } else if (k === "tremor") {
      w = 2 * Math.PI * (5 + 0.25 * Math.sin(t * 0.5)) * t; o.hz = 5;
      var amp = u < 1.5 ? u / 1.5 : u > ph.p.dur - 1 ? Math.max(0, ph.p.dur - u) : 1;   // ramp in/out
      o.g = [15 * amp * Math.sin(w), 10 * amp * Math.sin(w + 0.9), 4 * amp * Math.sin(w + 2)];
      o.d = [0.5 * amp * Math.sin(w), 0.6 * amp * Math.sin(w + 0.6), 0.9 * amp * Math.sin(w + 1.2)];
      o.roll = 18 + 2 * amp * Math.sin(w); o.pitch = -22;
    } else {   // fall
      if (u < 1.0) {                                   // lifting the board
        o.roll = 3 + 20 * u; o.pitch = -5 + 12 * u; o.g = [30 * u, 10 * u, 0]; o.d = [0, 0, 2.5 * Math.sin(u * Math.PI)];
      } else if (u < 1.4) {                            // free-fall: weightless, tumbling
        o.gscale = 0.06; o.roll = 23 + 300 * (u - 1); o.pitch = 7 + 120 * (u - 1); o.g = [160, 90, 40];
      } else if (u < 1.5) {                            // impact
        o.d = [18, -12, 42]; o.g = [320, -240, 120]; o.roll = 70; o.pitch = 15;
      } else {                                         // lying still on the pillow
        var decay = Math.exp(-(u - 1.5) * 4);
        o.roll = 82; o.pitch = 12; o.d = [3 * decay * Math.sin(u * 30), 2 * decay * Math.sin(u * 27), 4 * decay * Math.sin(u * 24)];
        o.g = [40 * decay * Math.sin(u * 30), 20 * decay * Math.sin(u * 26), 10 * decay];
      }
    }
    return o;
  }

  function synth(t) {
    var o = pose(t), r = o.roll * D2R, q = o.pitch * D2R, gs = G * o.gscale;
    var calibrated = cal.calibrated;
    var s = {
      ax: -gs * Math.sin(q) + o.d[0] + randn() * 0.05,
      ay: gs * Math.sin(r) * Math.cos(q) + o.d[1] + randn() * 0.05,
      az: gs * Math.cos(r) * Math.cos(q) + o.d[2] + randn() * 0.05,
    };
    ["gx", "gy", "gz"].forEach(function (k, i) {
      var raw = (o.g[i] + randn() * 0.5) * D2R + BIAS[k];   // what the chip really reports
      s["raw_" + k] = raw;
      s[k] = raw - (calibrated ? BIAS[k] : 0);              // what the backend serves (calibrated when it has run)
    });
    return s;
  }

  // Generate 50 Hz samples up to "now" (on demand, so a hidden tab doesn't pile up work).
  function imuCatchUp() {
    var t = elapsed();
    if (t - imu.genT > 8) imu.genT = t - 8;
    while (imu.genT + 1 / HZ <= t) {
      imu.genT += 1 / HZ;
      var s = synth(imu.genT);
      s.seq = ++imu.seq; s.t = sim.t0 / 1000 + imu.genT;
      imu.buf.push(s);
    }
    if (imu.buf.length > 400) imu.buf.splice(0, imu.buf.length - 400);
  }

  function deg(s, k) { return +(s[k] * R2D).toFixed(2); }
  function apiImu(p) {
    imuCatchUp();
    var n = Math.min(+p.n || 100, imu.buf.length), samples = imu.buf.slice(imu.buf.length - n);
    var l = imu.buf[imu.buf.length - 1], latest = null;
    if (l) {
      latest = {
        ax: l.ax, ay: l.ay, az: l.az, gx: l.gx, gy: l.gy, gz: l.gz,
        gx_dps: deg(l, "gx"), gy_dps: deg(l, "gy"), gz_dps: deg(l, "gz"),
        roll_deg: +(Math.atan2(l.ay, l.az) * R2D).toFixed(1),
        pitch_deg: +(Math.atan2(-l.ax, Math.hypot(l.ay, l.az)) * R2D).toFixed(1),
        raw_gx: l.raw_gx, raw_gy: l.raw_gy, raw_gz: l.raw_gz,
      };
    }
    return { device_id: p.device_id, samples: samples, latest: latest, rate_hz: HZ, calibrated: cal.calibrated, age_s: 0.0 };
  }

  function apiCalibration() {
    if (cal.state === "collecting") {
      var pr = (Date.now() - cal.start) / CAL_MS;
      if (pr >= 1) {
        cal.state = "done"; cal.calibrated = true; cal.at = nowTs();
        cal.message = "Gyro offset measured and removed.";
      } else return calBody(pr);
    }
    return calBody(cal.state === "done" ? 1 : 0);
  }
  function calBody(progress) {
    var k = cal.calibrated;
    return {
      state: cal.state, progress: progress, calibrated: k,
      bias: k ? { gx: BIAS.gx, gy: BIAS.gy, gz: BIAS.gz } : null,
      bias_deg_s: k ? { gx: BIAS.gx * R2D, gy: BIAS.gy * R2D, gz: BIAS.gz * R2D } : null,
      gravity: k ? G : null, still_std: k ? 0.4 : null, at: cal.at, message: cal.message,
    };
  }

  function apiMotion() {
    imuCatchUp();
    var recent = imu.buf.slice(-100), mags = recent.map(function (s) { return Math.hypot(s.ax, s.ay, s.az); });
    var mean = mags.reduce(function (a, v) { return a + v; }, 0) / (mags.length || 1);
    var std = Math.sqrt(mags.reduce(function (a, v) { return a + (v - mean) * (v - mean); }, 0) / (mags.length || 1));
    var g50 = imu.buf.slice(-50), rms = Math.sqrt(g50.reduce(function (a, s) {
      return a + (s.gx * s.gx + s.gy * s.gy + s.gz * s.gz) * R2D * R2D;
    }, 0) / (g50.length || 1));
    return {
      activity: sim.activity, confidence: sim.confidence,
      features: { accel_std: +std.toFixed(3), dom_freq_hz: pose(elapsed()).hz, gyro_rms: +rms.toFixed(1) },
      fall_state: sim.fallState, tremor: apiTremor(),
    };
  }

  function apiTremor() { return sim.tremor.state === "detected" ? Object.assign({ band_ratio: 0.9 }, sim.tremor) : Object.assign({ band_ratio: 0.1 }, sim.tremor); }

  // ---- 2 Hz "classifier" step: derives activity / vitals / alerts from the script ----
  function simStep() {
    var now = nowTs(), ph = phaseAt(elapsed());
    var fs = ph.p.kind === "fall" ? fallStateAt(ph.u) : "idle";
    var activity = ph.p.kind === "fall" ? (fs === "confirmed" ? "Fall" : "Sitting") : ph.p.act;
    sim.fallState = fs;
    if (activity !== sim.activity || sim.lastPhase < 0) {
      sim.activity = activity; sim.confidence = clamp(rand(0.84, 0.97), 0, 1);
      sim.history.unshift({ activity: activity, confidence: sim.confidence, timestamp: now });
      modelEventStep(activity);
      if (sim.history.length > 50) sim.history.pop();
    } else sim.confidence = clamp(sim.confidence + randn() * 0.02, 0.6, 0.99);
    sim.lastPhase = ph.n;

    var fallActive = fs === "confirmed";
    if (fallActive && sim.fallAlerted !== ph.n) {
      sim.fallAlerted = ph.n;
      sim.alerts.unshift({ alert_type: "fall", severity: "critical", status: "active",
        message: "Fall detected — check on patient immediately", timestamp: now, id: "fall_" + now });
    }
    if (!fallActive) sim.alerts = sim.alerts.map(function (a) { return a.alert_type === "fall" ? Object.assign({}, a, { status: "resolved" }) : a; });

    if (ph.p.kind === "tremor") {
      sim.tremor = ph.u < 3 ? { state: "warming_up", freq_hz: 0, amplitude: 0 }
        : { state: "detected", freq_hz: +(5 + rand(-0.2, 0.2)).toFixed(1), amplitude: +(0.45 + rand(-0.08, 0.08)).toFixed(2) };
    } else sim.tremor = { state: "none", freq_hz: 0, amplitude: 0.02 };

    var profile = fallActive ? VITAL_PROFILES.Fall : (VITAL_PROFILES[activity] || VITAL_PROFILES.Sitting);
    sim.hr = clamp(sim.hr * 0.92 + profile.hrBase * 0.08 + randn() * profile.hrVar * 0.3, 40, 200);
    sim.spo2 = clamp(sim.spo2 * 0.94 + profile.spo2Base * 0.06 + randn() * profile.spo2Var * 0.4, 88, 100);
    sim.fallProb = fallActive ? rand(0.75, 0.99) : fs !== "idle" ? rand(0.3, 0.6) : clamp(rand(0, 0.08), 0, 1);
    sim.alerts = sim.alerts.slice(0, 20);

    var s = imu.buf[imu.buf.length - 1] || synth(elapsed());
    sim.readings.unshift({ ax: s.ax, ay: s.ay, az: s.az, heart_rate: sim.hr, spo2: sim.spo2, timestamp: now, device_id: "wearable_01" });
    if (sim.readings.length > 200) sim.readings.pop();
  }

  // Both models classify the same window; every other event the LSTM disagrees with the CNN.
  var CONFUSED = { Sitting: "Lying", Lying: "Sitting", Walking: "Running", Running: "Walking", Fall: "Lying" };
  function apiModelsLive() {
    var ev = sim.modelEvent;
    if (!ev) return { at: null, age_s: null, cnn: null, lstm: null, agree: null };
    return { at: ev.at, age_s: +(nowTs() - ev.at).toFixed(1), cnn: ev.cnn, lstm: ev.lstm, agree: ev.cnn.activity === ev.lstm.activity };
  }
  function modelEventStep(activity) {
    var n = (sim.modelN = (sim.modelN || 0) + 1), agree = n % 2 === 1;
    var c = clamp(rand(0.82, 0.97), 0, 1), l = clamp(agree ? c - rand(0.02, 0.1) : rand(0.5, 0.7), 0, 1);
    sim.modelEvent = {
      at: nowTs(),
      cnn:  { activity: activity, confidence: +c.toFixed(2), fall_probability: activity === "Fall" ? 0.96 : 0.03, latency_ms: +rand(0.11, 0.17).toFixed(2) },
      lstm: { activity: agree ? activity : (CONFUSED[activity] || "Sitting"), confidence: +l.toFixed(2), fall_probability: activity === "Fall" ? 0.9 : 0.05, latency_ms: +rand(1.9, 2.4).toFixed(2) },
    };
  }

  var timer = null;

  var ROUTES = {
    "/api/vitals":   function () { return { heart_rate: sim.hr, spo2: sim.spo2, timestamp: nowTs() }; },
    "/api/activity": function () { return { activity: sim.activity, confidence: sim.confidence, fall_probability: sim.fallProb, timestamp: nowTs() }; },
    "/api/alerts":   function (p) { return sim.alerts.filter(function (a) { return a.status === "active"; }).slice(0, p.limit || 10); },
    "/api/history":  function (p) { return (p.table === "predictions" ? sim.history : sim.readings).slice(0, p.limit || 12); },
    "/api/tremor":      function () { return apiTremor(); },
    "/api/imu":         apiImu,
    "/api/calibration": apiCalibration,
    "/api/motion":      apiMotion,
    "/api/models/live": apiModelsLive,
  };

  function fail(message, status) { return Object.assign(new Error(message), { status: status }); }

  window.__sim = {
    start: function () {
      if (timer) return;
      sim.alerts = []; sim.history = []; sim.readings = []; sim.lastPhase = -1; sim.fallAlerted = -1; sim.fallState = "idle"; sim.modelEvent = null; sim.modelN = 0;
      sim.t0 = Date.now(); imu.buf = []; imu.seq = 0; imu.genT = 0;
      cal = { state: "idle", start: 0, calibrated: false, at: null, message: "" };
      simStep(); timer = setInterval(simStep, 500);
    },
    stop: function () { if (timer) clearInterval(timer); timer = null; },
    route: function (path, params) {
      var handler = ROUTES[path];
      if (!handler) { console.warn("[demo] unknown route:", path); return {}; }
      return handler(params || {});
    },
    // POST endpoints used by the dashboard (app.js postJSON routes here in demo mode).
    post: function (path) {
      return new Promise(function (resolve, reject) {
        if (path === "/api/calibrate/gyro") {
          apiCalibration();
          if (cal.state === "collecting") return reject(fail("already calibrating", 409));
          cal.state = "collecting"; cal.start = Date.now(); cal.message = "";
          return resolve(calBody(0));
        }
        if (path === "/api/calibrate/reset") {
          cal = { state: "idle", start: 0, calibrated: false, at: null, message: "" };
          return resolve(calBody(0));
        }
        reject(fail("unknown demo route " + path, 404));
      });
    },
  };
})();
