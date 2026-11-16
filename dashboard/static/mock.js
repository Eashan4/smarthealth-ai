/**
 * SmartHealth AI — DEMO data engine
 * ----------------------------------
 * Simulated data for presentations ONLY. It does nothing until the user presses the Demo button
 * (datasource.js calls window.__sim.start()), and is never used while real hardware is connected.
 */

(function () {
  "use strict";

  const ACTIVITIES = ["Walking", "Sitting", "Running", "Lying", "Standing"];
  const ACTIVITY_WEIGHTS = [0.35, 0.25, 0.15, 0.15, 0.10];

  const VITAL_PROFILES = {
    Walking:  { hrBase: 92,  hrVar: 10, spo2Base: 97.5, spo2Var: 0.8 },
    Sitting:  { hrBase: 68,  hrVar: 6,  spo2Base: 98.2, spo2Var: 0.5 },
    Running:  { hrBase: 148, hrVar: 18, spo2Base: 96.5, spo2Var: 1.2 },
    Lying:    { hrBase: 58,  hrVar: 5,  spo2Base: 98.8, spo2Var: 0.4 },
    Standing: { hrBase: 75,  hrVar: 7,  spo2Base: 98.0, spo2Var: 0.6 },
    Fall:     { hrBase: 120, hrVar: 25, spo2Base: 95.0, spo2Var: 2.0 },
  };

  const sim = {
    activity: "Walking",
    confidence: 0.88,
    hr: 90,
    spo2: 97.5,
    fallProb: 0.02,
    alerts: [],
    history: [],
    readings: [],
    tick: 0,
    activityChangeCooldown: 0,
    fallActive: false,
    fallClearAt: 0,
    tremorTicks: 0,
    tremorFreq: 5,
    tremorAmp: 0.5,
  };

  function rand(min, max) { return min + Math.random() * (max - min); }
  function randn() { return (Math.random() + Math.random() + Math.random() - 1.5) / 1.5; }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function weightedRandom(items, weights) {
    let r = Math.random(), cumul = 0;
    for (let i = 0; i < items.length; i++) {
      cumul += weights[i];
      if (r <= cumul) return items[i];
    }
    return items[items.length - 1];
  }
  function nowTs() { return Math.floor(Date.now() / 1000); }

  function simStep() {
    sim.tick++;
    const now = nowTs();

    if (sim.activityChangeCooldown > 0) {
      sim.activityChangeCooldown--;
    } else if (Math.random() < 0.08) {
      sim.activity = weightedRandom(ACTIVITIES, ACTIVITY_WEIGHTS);
      sim.confidence = clamp(rand(0.72, 0.98), 0, 1);
      sim.activityChangeCooldown = (rand(8, 25) | 0);
      sim.history.unshift({ activity: sim.activity, confidence: sim.confidence, timestamp: now });
      if (sim.history.length > 50) sim.history.pop();
    } else {
      sim.confidence = clamp(sim.confidence + randn() * 0.02, 0.55, 0.99);
    }

    if (!sim.fallActive && Math.random() < 0.003) {
      sim.fallActive = true;
      sim.fallClearAt = now + 20;
      sim.alerts.unshift({
        alert_type: "fall", severity: "critical", status: "active",
        message: "Fall detected — check on patient immediately",
        timestamp: now, id: "fall_" + now,
      });
    }
    if (sim.fallActive && now >= sim.fallClearAt) {
      sim.fallActive = false;
      sim.alerts = sim.alerts.map(function(a) {
        return a.alert_type === "fall" ? Object.assign({}, a, { status: "resolved" }) : a;
      });
    }

    // Occasional simulated tremor episode (5-10 s), only while sitting/lying/standing still.
    if (sim.tremorTicks > 0) sim.tremorTicks--;
    else if (["Sitting", "Lying", "Standing"].indexOf(sim.activity) >= 0 && Math.random() < 0.02) {
      sim.tremorTicks = 10 + (Math.random() * 10 | 0);
      sim.tremorFreq = rand(4.2, 6.2);
      sim.tremorAmp = rand(0.3, 1.1);
    }

    const profile = sim.fallActive ? VITAL_PROFILES.Fall : (VITAL_PROFILES[sim.activity] || VITAL_PROFILES.Walking);

    sim.hr   = clamp(sim.hr   * 0.92 + profile.hrBase   * 0.08 + randn() * profile.hrVar   * 0.3, 40, 200);
    sim.spo2 = clamp(sim.spo2 * 0.94 + profile.spo2Base * 0.06 + randn() * profile.spo2Var * 0.4, 88, 100);
    sim.fallProb = sim.fallActive ? rand(0.75, 0.99) : clamp(rand(0, 0.08), 0, 1);

    if (sim.hr > 160 && !sim.alerts.find(function(a) { return a.alert_type === "hr_high" && a.status === "active"; })) {
      sim.alerts.unshift({
        alert_type: "hr_high", severity: "warn", status: "active",
        message: "Tachycardia — HR " + Math.round(sim.hr) + " bpm",
        timestamp: now, id: "hr_" + now,
      });
    } else if (sim.hr < 155) {
      sim.alerts = sim.alerts.map(function(a) {
        return a.alert_type === "hr_high" ? Object.assign({}, a, { status: "resolved" }) : a;
      });
    }

    if (sim.spo2 < 93 && !sim.alerts.find(function(a) { return a.alert_type === "spo2_low" && a.status === "active"; })) {
      sim.alerts.unshift({
        alert_type: "spo2_low", severity: "critical", status: "active",
        message: "Low SpO2 — " + sim.spo2.toFixed(1) + "%",
        timestamp: now, id: "spo2_" + now,
      });
    } else if (sim.spo2 >= 94) {
      sim.alerts = sim.alerts.map(function(a) {
        return a.alert_type === "spo2_low" ? Object.assign({}, a, { status: "resolved" }) : a;
      });
    }

    sim.alerts = sim.alerts.slice(0, 20);

    const motionScale = { Walking: 0.4, Running: 1.2, Sitting: 0.05, Lying: 0.03, Standing: 0.08, Fall: 2.5 };
    const scale = sim.fallActive ? 2.5 : (motionScale[sim.activity] || 0.3);
    const g = 9.8;
    const reading = {
      ax: randn() * scale * g,
      ay: g + randn() * scale * g * 0.3,
      az: randn() * scale * g * 0.6,
      heart_rate: sim.hr,
      spo2: sim.spo2,
      timestamp: now,
      device_id: "wearable_01",
    };
    sim.readings.unshift(reading);
    if (sim.readings.length > 200) sim.readings.pop();
  }

  var timer = null;

  function apiVitals()    { return { heart_rate: sim.hr, spo2: sim.spo2, timestamp: nowTs() }; }
  function apiActivity()  {
    return { activity: sim.activity, confidence: sim.confidence, fall_probability: sim.fallProb, timestamp: nowTs() };
  }
  function apiAlerts(limit)  {
    limit = limit || 10;
    return sim.alerts.filter(function(a) { return a.status === "active"; }).slice(0, limit);
  }
  function apiHistory(table, limit) {
    limit = limit || 12;
    if (table === "predictions") return sim.history.slice(0, limit);
    return sim.readings.slice(0, limit);
  }
  function apiLatest() {
    var r = sim.readings[0] || null;
    return {
      reading: r,
      prediction: r ? { activity: sim.activity, confidence: sim.confidence, fall_probability: sim.fallProb } : null,
    };
  }

  var ROUTES = {
    "/api/vitals":   function(p) { return apiVitals(); },
    "/api/activity": function(p) { return apiActivity(); },
    "/api/alerts":   function(p) { return apiAlerts(p.limit); },
    "/api/history":  function(p) { return apiHistory(p.table, p.limit); },
    "/api/latest":   function(p) { return apiLatest(); },
  };

  function apiTremor() {
    if (sim.tremorTicks > 0) {
      return { state: "detected", freq_hz: +sim.tremorFreq.toFixed(1), amplitude: +sim.tremorAmp.toFixed(2), band_ratio: 0.9 };
    }
    return { state: "none", freq_hz: 0, amplitude: 0.02, band_ratio: 0.1 };
  }
  ROUTES["/api/tremor"] = function() { return apiTremor(); };

  function reset() {
    sim.alerts = []; sim.history = []; sim.readings = []; sim.tick = 0;
    sim.fallActive = false; sim.tremorTicks = 0; sim.activityChangeCooldown = 0;
  }

  window.__sim = {
    start: function () { if (timer) return; reset(); simStep(); timer = setInterval(simStep, 500); },
    stop: function () { if (timer) clearInterval(timer); timer = null; },
    route: function (path, params) {
      var handler = ROUTES[path];
      if (!handler) { console.warn("[demo] unknown route:", path); return {}; }
      return handler(params || {});
    },
  };
})();
