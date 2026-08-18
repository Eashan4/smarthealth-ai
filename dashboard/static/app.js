const CFG = window.SMARTHEALTH_CONFIG;

const CLASS_COLOR = {
  Walking: "#46e0c4",
  Running: "#9c8cfb",
  Sitting: "#f5b84a",
  Lying: "#5a86d9",
  Fall: "#ff5c74",
};

const state = {
  deviceId: localStorage.getItem("smarthealth_device_id") || CFG.DEFAULT_DEVICE_ID,
  lastSuccessAt: 0,
  accelTrace: [],
  hrTrace: [],
  spo2Trace: [],
};

const el = (id) => document.getElementById(id);
const deviceInput = el("device-input");
deviceInput.value = state.deviceId;
deviceInput.addEventListener("change", () => {
  const v = deviceInput.value.trim() || CFG.DEFAULT_DEVICE_ID;
  state.deviceId = v;
  localStorage.setItem("smarthealth_device_id", v);
  state.accelTrace = []; state.hrTrace = []; state.spo2Trace = [];
  backfillTraces().then(refresh);
});

function qs(params) {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ""));
  const s = new URLSearchParams(clean).toString();
  return s ? `?${s}` : "";
}

async function getJSON(path, params = {}) {
  const res = await fetch(CFG.API_BASE_URL + path + qs(params));
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function timeLabel(ts) {
  if (!ts) return "--";
  return new Date(ts * 1000).toLocaleTimeString([], { hour12: false });
}

function pushTrace(arr, value) {
  if (value == null) return;
  arr.push(value);
  if (arr.length > CFG.TRACE_HISTORY_LENGTH) arr.shift();
}

// ---------- Canvas drawing ----------

function fitCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width * dpr));
  const h = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: rect.width, h: rect.height };
}

function drawWave(canvas, values, color) {
  const { ctx, w, h } = fitCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  if (values.length < 2) return;

  const min = Math.min(...values), max = Math.max(...values);
  const range = Math.max(max - min, 0.5);
  const stepX = w / (CFG.TRACE_HISTORY_LENGTH - 1);
  const offset = CFG.TRACE_HISTORY_LENGTH - values.length;

  const points = values.map((v, i) => {
    const x = (offset + i) * stepX;
    const y = h - 10 - ((v - min) / range) * (h - 20);
    return [x, y];
  });

  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + "55");
  grad.addColorStop(1, color + "00");
  ctx.beginPath();
  ctx.moveTo(points[0][0], h);
  points.forEach(([x, y]) => ctx.lineTo(x, y));
  ctx.lineTo(points[points.length - 1][0], h);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  points.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.75;
  ctx.lineJoin = "round";
  ctx.stroke();

  const [lx, ly] = points[points.length - 1];
  ctx.beginPath();
  ctx.arc(lx, ly, 3, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

// ---------- Rendering ----------

function setLed(id, state_) {
  el(id).dataset.state = state_;
}

function renderConnection() {
  const stale = Date.now() - state.lastSuccessAt > CFG.STALE_AFTER_MS;
  setLed("conn-led", state.lastSuccessAt === 0 ? "idle" : stale ? "idle" : "live");
}

function renderClock() {
  el("clock").textContent = new Date().toLocaleTimeString([], { hour12: false });
}

function renderActivity(activityData) {
  el("activity-word").textContent = activityData.activity || "—";
  el("activity-confidence").textContent = activityData.confidence != null
    ? `${(activityData.confidence * 100).toFixed(0)}%` : "--";
}

function renderMeters(prediction) {
  const box = el("prob-meters");
  box.innerHTML = "";
  if (!prediction) {
    box.innerHTML = '<p class="dim small">No prediction yet</p>';
    return;
  }
  const rows = [[prediction.activity, prediction.confidence]];
  if (prediction.activity !== "Fall") rows.push(["Fall", prediction.fall_probability]);
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "meter-row" + (label === "Fall" ? " is-fall" : "");
    const pct = Math.round((value ?? 0) * 100);
    row.innerHTML = `
      <span class="meter-label">${label}</span>
      <span class="meter-track"><span class="meter-fill" style="width:${pct}%"></span></span>
      <span class="meter-pct mono">${pct}%</span>`;
    box.appendChild(row);
  });
}

function renderFallStatus(activityData, alerts) {
  const active = alerts.find((a) => a.alert_type === "fall" && a.status === "active");
  if (active) {
    setLed("fall-led", "critical");
    el("fall-value").textContent = "DETECTED";
    el("alert-rail").classList.remove("hidden");
    el("alert-rail-text").textContent = `${active.message} — ${timeLabel(active.timestamp)}`;
  } else {
    const p = activityData.fall_probability ?? 0;
    setLed("fall-led", p > 0.25 ? "warn" : "idle");
    el("fall-value").textContent = "Clear";
    el("alert-rail").classList.add("hidden");
  }
}

function renderAlerts(alerts) {
  const list = el("alerts-list");
  list.innerHTML = "";
  if (alerts.length === 0) {
    list.innerHTML = '<li class="log-empty">No active alerts</li>';
    return;
  }
  alerts.forEach((a) => {
    const li = document.createElement("li");
    if (a.severity === "critical") li.classList.add("log-critical");
    li.innerHTML = `<span class="log-time mono">${timeLabel(a.timestamp)}</span><span>${a.message}</span>`;
    list.appendChild(li);
  });
}

function renderHistory(history) {
  const list = el("history-list");
  list.innerHTML = "";
  history.slice(0, CFG.ACTIVITY_LOG_LENGTH).forEach((p) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="log-time">${timeLabel(p.timestamp)}</span><span>${p.activity} ${(p.confidence * 100).toFixed(0)}%</span>`;
    list.appendChild(li);
  });

  const timeline = el("timeline");
  timeline.innerHTML = "";
  const recent = history.slice(0, CFG.ACTIVITY_LOG_LENGTH).reverse();
  if (recent.length === 0) {
    timeline.innerHTML = '<span class="timeline-empty">No activity recorded yet</span>';
    return;
  }
  recent.forEach((p) => {
    const tick = document.createElement("span");
    tick.className = "tick";
    tick.style.background = CLASS_COLOR[p.activity] || "#3a4a6a";
    tick.title = `${p.activity} — ${timeLabel(p.timestamp)}`;
    timeline.appendChild(tick);
  });
}

function renderVitals(vitals) {
  el("hr-value").textContent = vitals.heart_rate != null ? Math.round(vitals.heart_rate) : "--";
  el("spo2-value").textContent = vitals.spo2 != null ? Math.round(vitals.spo2) : "--";
  setLed("hr-led", vitals.heart_rate != null ? "ok" : "idle");
  setLed("spo2-led", vitals.spo2 != null ? "ok" : "idle");
  pushTrace(state.hrTrace, vitals.heart_rate);
  pushTrace(state.spo2Trace, vitals.spo2);
  drawWave(el("hr-spark"), state.hrTrace, CLASS_COLOR.Walking);
  drawWave(el("spo2-spark"), state.spo2Trace, "#5a86d9");
}

// ---------- Poll loop ----------

async function backfillTraces() {
  try {
    const rows = await getJSON("/api/history", {
      device_id: state.deviceId, table: "sensor_readings", limit: CFG.TRACE_HISTORY_LENGTH,
    });
    rows.reverse().forEach((r) => {
      pushTrace(state.accelTrace, Math.sqrt(r.ax ** 2 + r.ay ** 2 + r.az ** 2));
      pushTrace(state.hrTrace, r.heart_rate);
      pushTrace(state.spo2Trace, r.spo2);
    });
  } catch (err) {
    console.error("trace backfill failed:", err);
  }
}

async function refresh() {
  try {
    const [vitals, activityData, alerts, history, latest] = await Promise.all([
      getJSON("/api/vitals", { device_id: state.deviceId }),
      getJSON("/api/activity", { device_id: state.deviceId }),
      getJSON("/api/alerts", { device_id: state.deviceId, limit: 10 }),
      getJSON("/api/history", { device_id: state.deviceId, table: "predictions", limit: CFG.ACTIVITY_LOG_LENGTH }),
      getJSON("/api/latest", { device_id: state.deviceId }),
    ]);

    state.lastSuccessAt = Date.now();
    renderConnection();
    renderVitals(vitals);
    renderActivity(activityData);
    renderMeters(latest.prediction);
    renderFallStatus(activityData, alerts);
    renderAlerts(alerts);
    renderHistory(history);

    if (latest.reading) {
      const mag = Math.sqrt(latest.reading.ax ** 2 + latest.reading.ay ** 2 + latest.reading.az ** 2);
      pushTrace(state.accelTrace, mag);
    }
    const waveColor = el("fall-led").dataset.state === "critical" ? CLASS_COLOR.Fall : CLASS_COLOR.Walking;
    drawWave(el("wave-canvas"), state.accelTrace, waveColor);
  } catch (err) {
    console.error("dashboard refresh failed:", err);
    renderConnection();
  }
}

setInterval(renderClock, 1000);
setInterval(renderConnection, 1000);
renderClock();
backfillTraces().then(refresh);
setInterval(refresh, CFG.POLL_INTERVAL_MS);
window.addEventListener("resize", () => {
  drawWave(el("wave-canvas"), state.accelTrace, CLASS_COLOR.Walking);
  drawWave(el("hr-spark"), state.hrTrace, CLASS_COLOR.Walking);
  drawWave(el("spo2-spark"), state.spo2Trace, "#5a86d9");
});
