const POLL_MS = 2000;
const MAX_POINTS = 30;

const deviceInput = document.getElementById("device-id");

function deviceId() {
  return deviceInput.value.trim() || undefined;
}

function qs(params) {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined));
  const s = new URLSearchParams(clean).toString();
  return s ? `?${s}` : "";
}

async function getJSON(path, params = {}) {
  const res = await fetch(path + qs(params));
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function makeLineChart(ctx, label, color) {
  return new Chart(ctx, {
    type: "line",
    data: { labels: [], datasets: [{ label, data: [], borderColor: color, backgroundColor: color, tension: 0.25, pointRadius: 0 }] },
    options: {
      animation: false,
      responsive: true,
      scales: {
        x: { ticks: { color: "#93a0b8" }, grid: { color: "#2a3349" } },
        y: { ticks: { color: "#93a0b8" }, grid: { color: "#2a3349" } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

const hrChart = makeLineChart(document.getElementById("hr-chart"), "HR", "#4fd1c5");
const spo2Chart = makeLineChart(document.getElementById("spo2-chart"), "SpO2", "#f5b942");
const accelChart = makeLineChart(document.getElementById("accel-chart"), "Accel magnitude", "#8b8cf0");
const activityChart = new Chart(document.getElementById("activity-chart"), {
  type: "line",
  data: { labels: [], datasets: [{ label: "Activity", data: [], borderColor: "#4fd1c5", stepped: true, pointRadius: 2 }] },
  options: {
    animation: false,
    scales: {
      x: { ticks: { color: "#93a0b8" }, grid: { color: "#2a3349" } },
      y: { ticks: { color: "#93a0b8" }, grid: { color: "#2a3349" } },
    },
    plugins: { legend: { display: false } },
  },
});

function pushPoint(chart, label, value) {
  chart.data.labels.push(label);
  chart.data.datasets[0].data.push(value);
  if (chart.data.labels.length > MAX_POINTS) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update();
}

function timeLabel(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleTimeString();
}

function renderProbabilities(prediction) {
  const box = document.getElementById("prob-bars");
  box.innerHTML = "";
  if (!prediction || !prediction.probabilities) return;
  Object.entries(prediction.probabilities).forEach(([cls, p]) => {
    const row = document.createElement("div");
    row.className = "prob-row" + (cls === "Fall" ? " is-fall" : "");
    row.innerHTML = `
      <span class="label">${cls}</span>
      <span class="bar-bg"><span class="bar-fill" style="width:${(p * 100).toFixed(0)}%"></span></span>
      <span class="pct">${(p * 100).toFixed(0)}%</span>`;
    box.appendChild(row);
  });
}

async function refresh() {
  const id = deviceId();
  try {
    const [vitals, activityData, alerts, history] = await Promise.all([
      getJSON("/api/vitals", { device_id: id }),
      getJSON("/api/activity", { device_id: id }),
      getJSON("/api/alerts", { device_id: id, limit: 10 }),
      getJSON("/api/history", { device_id: id, table: "predictions", limit: 20 }),
    ]);

    document.getElementById("hr-value").textContent = vitals.heart_rate ?? "--";
    document.getElementById("spo2-value").textContent = vitals.spo2 ?? "--";
    if (vitals.heart_rate != null) pushPoint(hrChart, timeLabel(vitals.timestamp), vitals.heart_rate);
    if (vitals.spo2 != null) pushPoint(spo2Chart, timeLabel(vitals.timestamp), vitals.spo2);

    document.getElementById("activity-value").textContent = activityData.activity ?? "--";
    document.getElementById("activity-confidence").textContent = activityData.confidence != null
      ? `confidence ${(activityData.confidence * 100).toFixed(0)}%` : "";

    const fallStatusEl = document.getElementById("fall-status");
    const fallDetailEl = document.getElementById("fall-detail");
    const activeCritical = alerts.find(a => a.alert_type === "fall" && a.status === "active");
    if (activeCritical) {
      fallStatusEl.textContent = "FALL DETECTED";
      fallStatusEl.classList.add("fall-active");
      fallDetailEl.textContent = activeCritical.message;
    } else {
      fallStatusEl.textContent = "No fall";
      fallStatusEl.classList.remove("fall-active");
      fallDetailEl.textContent = activityData.fall_probability != null
        ? `fall probability ${(activityData.fall_probability * 100).toFixed(0)}%` : "";
    }

    const banner = document.getElementById("alert-banner");
    const bannerText = document.getElementById("alert-text");
    if (activeCritical) {
      banner.classList.remove("hidden");
      bannerText.textContent = `${activeCritical.message} — Time: ${timeLabel(activeCritical.timestamp)}`;
    } else {
      banner.classList.add("hidden");
    }

    const alertsList = document.getElementById("alerts-list");
    alertsList.innerHTML = "";
    if (alerts.length === 0) {
      alertsList.innerHTML = '<li class="empty">No active alerts</li>';
    } else {
      alerts.forEach(a => {
        const li = document.createElement("li");
        li.className = a.severity === "critical" ? "alert-critical" : "";
        li.textContent = `[${timeLabel(a.timestamp)}] ${a.message}`;
        alertsList.appendChild(li);
      });
    }

    const historyList = document.getElementById("history-list");
    historyList.innerHTML = "";
    history.forEach(p => {
      const li = document.createElement("li");
      li.textContent = `[${timeLabel(p.timestamp)}] ${p.activity} (${(p.confidence * 100).toFixed(0)}%)`;
      historyList.appendChild(li);
    });

    if (activityData.activity) {
      pushPoint(activityChart, timeLabel(activityData.timestamp), activityData.activity);
    }

    const latest = await getJSON("/api/latest", { device_id: id });
    if (latest.reading) {
      const mag = Math.sqrt(latest.reading.ax ** 2 + latest.reading.ay ** 2 + latest.reading.az ** 2);
      pushPoint(accelChart, timeLabel(latest.reading.timestamp), mag);
    }
    // predictions table (docs/DOCUMENTATION.md sec 14 fixed schema) stores only the
    // winning class + its confidence + fall_probability, not the full per-class
    // vector -- so history/dashboard can only reconstruct these two bars, not a
    // full breakdown across all 5 classes for past windows.
    if (latest.prediction) {
      renderProbabilities({
        probabilities: {
          [latest.prediction.activity]: latest.prediction.confidence,
          Fall: latest.prediction.fall_probability,
        },
      });
    }
  } catch (err) {
    console.error("dashboard refresh failed:", err);
  }
}

refresh();
setInterval(refresh, POLL_MS);
deviceInput.addEventListener("change", refresh);
