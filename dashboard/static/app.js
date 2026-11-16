// Core of the dashboard: shared helpers, the 1 s poll loop, vitals, status tiles and the events list.
// gyro.js (motion panel) and models.js (model comparison) build on getJSON / postJSON / fitCanvas below.
const CFG = window.SMARTHEALTH_CONFIG;

const CLASS_COLOR = {
  Walking: "#46e0c4", Running: "#9c8cfb", Sitting: "#f5b84a", Lying: "#5a86d9", Fall: "#ff5c74",
};
const COLOR_HR = "#46e0c4", COLOR_SPO2 = "#7aa7ff";

const store = {   // localStorage can throw (private mode / blocked): never let it break the page
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
};

const state = { deviceId: store.get("smarthealth_device_id") || CFG.DEFAULT_DEVICE_ID, lastSuccessAt: 0 };
const SH = { motion: null };   // shared observations for the other scripts

const el = (id) => document.getElementById(id);
const mode = () => window.__getMode().mode;
const setText = (id, t) => { const e = el(id); if (e.textContent !== t) e.textContent = t; };

function qs(params) {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ""));
  const s = new URLSearchParams(clean).toString();
  return s ? `?${s}` : "";
}

// Every call goes through datasource.js, which decides between idle / demo / live.
function getJSON(path, params = {}) { return window.__mockGetJSON(path, params); }

async function postJSON(path, body = {}) {
  const m = mode();
  if (m === "demo") return window.__sim.post(path, body);
  if (m === "idle") throw new Error("Connect the board or press Demo first");
  const res = await fetch(CFG.API_BASE_URL + path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || data.message || `${path} -> ${res.status}`), { status: res.status });
  return data;
}

function timeLabel(ts) {
  return ts ? new Date(ts * 1000).toLocaleTimeString([], { hour12: false }) : "--";
}

// ---------- Canvas ----------

function fitCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width * dpr)), h = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: rect.width, h: rect.height };
}

// Filled line chart of the newest `max` values, scaled to their own range (at least `minRange` tall).
function drawSpark(canvas, values, color, max, minRange) {
  const { ctx, w, h } = fitCanvas(canvas);
  ctx.clearRect(0, 0, w, h);
  if (values.length < 2) return;
  const lo = Math.min(...values), hi = Math.max(...values), mid = (lo + hi) / 2;
  const range = Math.max(hi - lo, minRange), min = mid - range / 2;
  const stepX = w / (max - 1), offset = max - values.length;
  const pts = values.map((v, i) => [(offset + i) * stepX, h - 6 - ((v - min) / range) * (h - 12)]);
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + "40"); grad.addColorStop(1, color + "00");
  ctx.beginPath(); ctx.moveTo(pts[0][0], h);
  pts.forEach(([x, y]) => ctx.lineTo(x, y));
  ctx.lineTo(pts[pts.length - 1][0], h); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();
  ctx.beginPath();
  pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
  ctx.strokeStyle = color; ctx.lineWidth = 1.75; ctx.lineJoin = "round"; ctx.stroke();
  const [lx, ly] = pts[pts.length - 1];
  ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
}

// ---------- Header ----------

const deviceInput = el("device-input");
deviceInput.value = state.deviceId;
deviceInput.addEventListener("change", () => {
  state.deviceId = deviceInput.value.trim() || CFG.DEFAULT_DEVICE_ID;
  store.set("smarthealth_device_id", state.deviceId);
  resetSession();
  window.dispatchEvent(new Event("sh:reset"));
});

function renderConnection() {
  const stale = Date.now() - state.lastSuccessAt > CFG.STALE_AFTER_MS;
  // Teal only when a data source is active (hardware or demo); idle means nothing is feeding the page.
  const on = mode() !== "idle" && state.lastSuccessAt && !stale;
  el("conn-led").dataset.state = on ? "live" : "idle";
  el("conn-led").setAttribute("aria-label", on ? "Data connection: receiving" : "Data connection: no data");
}

// ---------- Vitals ----------

const vit = {
  hr:   { trace: [], min: null, max: null, sum: 0, n: 0, color: COLOR_HR, minRange: 10 },
  spo2: { trace: [], min: null, max: null, sum: 0, n: 0, color: COLOR_SPO2, minRange: 4 },
};
function resetSession() {
  Object.values(vit).forEach((v) => Object.assign(v, { trace: [], min: null, max: null, sum: 0, n: 0 }));
  SH.motion = null;
}

// Chip tone: ok / warn / crit / none. The icon shape differs per tone so state is never colour-only.
function setChip(id, tone, text) {
  el(id).dataset.tone = tone;
  setText(id + "-text", text);
}

function hrStatus(v) {
  if (v == null) return mode() === "idle" ? ["none", "Not connected"] : ["warn", "No finger detected"];
  return v < 60 ? ["warn", "Low"] : v > 100 ? ["warn", "High"] : ["ok", "Normal"];
}
function spo2Status(v) {
  if (v == null) return mode() === "idle" ? ["none", "Not connected"] : ["warn", "No finger detected"];
  return v >= 95 ? ["ok", "Normal"] : v >= 90 ? ["warn", "Low"] : ["crit", "Critical"];
}

function renderVital(key, value, statusFn) {
  const v = vit[key];
  if (value != null) {
    v.trace.push(value); if (v.trace.length > CFG.SPARK_POINTS) v.trace.shift();
    v.min = v.min == null ? value : Math.min(v.min, value);
    v.max = v.max == null ? value : Math.max(v.max, value);
    v.sum += value; v.n++;
  }
  const r = (x) => (x == null ? "--" : String(Math.round(x)));
  setText(key + "-value", r(value));
  setText(key + "-min", r(v.min)); setText(key + "-max", r(v.max)); setText(key + "-avg", v.n ? r(v.sum / v.n) : "--");
  const [tone, text] = statusFn(value);
  setChip(key + "-chip", tone, text);
  drawVitals(key);
}
function drawVitals(key) { drawSpark(el(key + "-spark"), vit[key].trace, vit[key].color, CFG.SPARK_POINTS, vit[key].minRange); }

// ---------- Status tiles ----------

function setTile(id, tone, val, sub) {
  el("tile-" + id).dataset.tone = tone;
  setText(({ activity: "act", tremor: "tremor", fall: "fall", signal: "sig" })[id] + "-val", val);
  setText(({ activity: "act", tremor: "tremor", fall: "fall", signal: "sig" })[id] + "-sub", sub);
}

function renderActivity(a) {
  if (!a.activity) return setTile("activity", "none", "--", mode() === "idle" ? "Not connected" : "No data");
  const pct = a.confidence != null ? `${Math.round(a.confidence * 100)}% confidence` : "";
  setTile("activity", a.activity === "Fall" ? "crit" : "ok", a.activity, pct);
  el("tile-activity").style.setProperty("--act", CLASS_COLOR[a.activity] || "var(--text-dim)");
}

function renderTremor(t) {
  if (t.state === "detected") setTile("tremor", "warn", "Detected", `${t.freq_hz.toFixed(1)} Hz, ${t.amplitude.toFixed(2)} m/s²`);
  else if (t.state === "none") setTile("tremor", "ok", "Not detected", "Motion within normal range");
  else if (t.state === "warming_up") setTile("tremor", "none", "Analysing", "Collecting the first seconds");
  else setTile("tremor", "none", "--", mode() === "idle" ? "Not connected" : "No motion data");
}

function renderFall(motion, alerts) {
  const active = alerts.find((a) => a.alert_type === "fall" && a.status === "active");
  const fs = motion.fall_state;
  const rail = el("alert-rail");
  if (active || fs === "confirmed") {
    setTile("fall", "crit", "DETECTED", active ? timeLabel(active.timestamp) : "Confirmed by motion rules");
    rail.classList.remove("hidden");
    setText("alert-rail-text", active ? `${active.message} (${timeLabel(active.timestamp)})` : "Fall detected");
  } else {
    rail.classList.add("hidden");
    if (["freefall", "impact", "confirming"].includes(fs)) setTile("fall", "warn", "Checking", "Possible fall, confirming");
    else if (mode() === "idle") setTile("fall", "none", "--", "Not connected");
    else setTile("fall", "ok", "Clear", "No fall detected");
  }
}

// ---------- Events ----------

function renderEvents(alerts, history) {
  const tl = el("timeline");
  tl.replaceChildren();
  history.slice(0, 40).reverse().forEach((p) => {
    const tick = document.createElement("span");
    tick.className = "tick"; tick.style.background = CLASS_COLOR[p.activity] || "#3a4a6a";
    tick.title = `${p.activity}, ${timeLabel(p.timestamp)}`;
    tl.appendChild(tick);
  });

  // Prediction rows repeat every second: keep only the moments the activity changed.
  const changes = [];
  [...history].reverse().forEach((p, i, a) => { if (i === 0 || p.activity !== a[i - 1].activity) changes.push(p); });
  const rows = [
    ...alerts.map((a) => ({ ts: a.timestamp, kind: a.severity === "critical" ? "alert" : "notice", text: a.message })),
    ...changes.map((p) => ({ ts: p.timestamp, kind: "activity", text: `${p.activity} (${Math.round(p.confidence * 100)}%)` })),
  ].sort((a, b) => b.ts - a.ts).slice(0, CFG.EVENTS_SHOWN);

  const list = el("events-list");
  list.replaceChildren();
  if (!rows.length) {
    const li = document.createElement("li"); li.className = "events-empty";
    li.textContent = mode() === "idle" ? "Connect the board or press Demo to see events." : "Nothing recorded yet";
    list.appendChild(li);
    return;
  }
  rows.forEach((r) => {
    const li = document.createElement("li"); li.dataset.kind = r.kind;
    const t = document.createElement("time"); t.className = "mono"; t.textContent = timeLabel(r.ts);
    const k = document.createElement("span"); k.className = "ev-kind"; k.textContent = r.kind === "activity" ? "Activity" : r.kind === "alert" ? "Alert" : "Notice";
    const m = document.createElement("span"); m.className = "ev-text"; m.textContent = r.text;
    li.append(t, k, m);
    list.appendChild(li);
  });
}

// ---------- Poll loop ----------

async function refresh() {
  const q = { device_id: state.deviceId };
  try {
    const [vitals, activity, alerts, history, tremor, motion] = await Promise.all([
      getJSON("/api/vitals", q), getJSON("/api/activity", q),
      getJSON("/api/alerts", { ...q, limit: 10 }),
      getJSON("/api/history", { ...q, table: "predictions", limit: 60 }),
      getJSON("/api/tremor", q), getJSON("/api/motion", q),
    ]);
    state.lastSuccessAt = Date.now();
    SH.motion = motion;
    renderVital("hr", vitals.heart_rate, hrStatus);
    renderVital("spo2", vitals.spo2, spo2Status);
    renderActivity(activity);
    renderTremor(tremor);
    renderFall(motion, alerts);
    renderEvents(alerts, history);
  } catch (err) {
    console.error("dashboard refresh failed:", err);
  }
  renderConnection();
}

window.addEventListener("sh:mode", () => { resetSession(); refresh(); });
window.addEventListener("resize", () => { drawVitals("hr"); drawVitals("spo2"); });

setInterval(() => { el("clock").textContent = new Date().toLocaleTimeString([], { hour12: false }); }, 1000);
el("clock").textContent = new Date().toLocaleTimeString([], { hour12: false });
setInterval(renderConnection, 1000);
refresh();
setInterval(refresh, CFG.POLL_INTERVAL_MS);
