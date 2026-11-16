// Tremor and motion panel: acceleration magnitude trace, three gyroscope strips, signal tile, gyro calibration.
// Uses helpers from app.js (getJSON, postJSON, fitCanvas, drawSpark, setTile, state, mode, el, setText).
// IMU and calibration are per-device live buffers on the backend, so they are polled whenever a source is active.
(() => {
  "use strict";
  const W = CFG.IMU_WINDOW_SAMPLES, R2D = 180 / Math.PI;
  const AXES = [["gx", "#ff8a65"], ["gy", "#46e0c4"], ["gz", "#7aa7ff"]];
  const ACCEL_COLOR = "#f5b84a";
  const fmt = (v, d = 1) => (v == null || isNaN(v) ? "--" : (v < 0 ? "-" : "+") + Math.abs(v).toFixed(d));

  let buf = [], lastSeq = -1, rxAt = 0, rate = 0, dirty = true, gen = 0, imuTimer = 0, calTimer = 0, cal = null;
  const scaleNote = document.querySelector(".m-gyro .unit-note");

  // ---------- IMU ----------

  function ingest(d) {
    const s = d.samples || [];
    if (s.length) {
      if (s[0].seq == null) buf = s.slice();
      else {
        if (s[s.length - 1].seq < lastSeq) { buf = []; lastSeq = -1; }   // device restarted
        const fresh = s.filter((x) => x.seq > lastSeq);
        if (fresh.length) { buf.push(...fresh); lastSeq = fresh[fresh.length - 1].seq; }
      }
      if (buf.length > W) buf.splice(0, buf.length - W);
    }
    // age_s is measured by the backend; rxAt anchors it to this browser's clock.
    if (d.age_s != null && d.age_s < CFG.IMU_STALE_AFTER_S) rxAt = Date.now() - d.age_s * 1000;
    rate = d.rate_hz || 0;
    dirty = true;
    renderStatus();
  }

  const isLive = () => mode() !== "idle" && Date.now() - rxAt < CFG.IMU_STALE_AFTER_S * 1000;

  function renderStatus() {
    const live = isLive();
    if (mode() === "idle") setTile("signal", "none", "--", "Not connected");
    else if (!rxAt) setTile("signal", "warn", "No data", "Waiting for motion samples");
    else setTile("signal", live ? "ok" : "warn", live ? "Live" : "Stale", live ? `${Math.round(rate)} Hz sample rate` : "No new samples");
    const last = buf[buf.length - 1];
    if (live && last) {
      AXES.forEach(([k]) => setText(`gyro-${k}-val`, fmt(last[`${k}_dps`] ?? last[k] * R2D)));
      const m = Math.hypot(last.ax, last.ay, last.az);
      setText("accel-val", m < 3 ? `${m.toFixed(2)} g` : `${m.toFixed(1)} m/s²`);
    } else {
      AXES.forEach(([k]) => setText(`gyro-${k}-val`, "--"));
      setText("accel-val", "--");
    }
  }

  async function pollImu(g) {
    try {
      const d = await getJSON("/api/imu", { device_id: state.deviceId, n: buf.length ? 60 : W });
      if (g !== gen) return;
      ingest(d);
    } catch { if (g !== gen) return; renderStatus(); }
    imuTimer = setTimeout(() => pollImu(g), CFG.IMU_POLL_INTERVAL_MS);
  }

  // ---------- Drawing ----------

  function drawStrip(k, color, range) {
    const { ctx, w, h } = fitCanvas(el(`gyro-${k}`));
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "rgba(160,185,225,.35)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, h / 2 + 0.5); ctx.lineTo(w, h / 2 + 0.5); ctx.stroke();   // zero line
    if (buf.length < 2) return;
    const step = w / (W - 1), off = W - buf.length;
    ctx.beginPath();
    buf.forEach((s, i) => {
      const v = s[`${k}_dps`] ?? s[k] * R2D, y = h / 2 - (v / range) * (h / 2 - 3);
      i ? ctx.lineTo((off + i) * step, y) : ctx.moveTo((off + i) * step, y);
    });
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.lineJoin = "round"; ctx.stroke();
  }

  function draw() {
    const vals = buf.map((s) => Math.hypot(s.ax, s.ay, s.az));
    const unitG = vals.length && vals[vals.length - 1] < 3;
    drawSpark(el("accel-canvas"), vals, ACCEL_COLOR, W, unitG ? 0.4 : 4);
    let peak = 0;
    buf.forEach((s) => AXES.forEach(([k]) => { peak = Math.max(peak, Math.abs(s[`${k}_dps`] ?? s[k] * R2D)); }));
    const range = Math.max(CFG.IMU_MIN_RANGE_DPS, Math.ceil((peak * 1.1) / 25) * 25);   // shared scale, rounded to 25
    AXES.forEach(([k, c]) => drawStrip(k, c, range));
    scaleNote.textContent = `deg/s, ±${range}`;
  }

  (function frame() { if (dirty) { dirty = false; draw(); } requestAnimationFrame(frame); })();
  window.addEventListener("resize", () => { dirty = true; });
  setInterval(() => { renderStatus(); }, 500);   // so "Live" turns "Stale" when samples stop

  // ---------- Calibration ----------

  const calBox = el("cal"), calBtn = el("cal-btn"), calReset = el("cal-reset"), ringFill = el("ring-fill");
  const CIRC = 2 * Math.PI * 16;
  ringFill.style.strokeDasharray = String(CIRC);

  function renderCal() {
    const m = mode(), st = cal ? cal.state : "idle", yes = !!(cal && cal.calibrated), collecting = st === "collecting";
    calBox.dataset.state = collecting ? "collecting" : st === "failed" ? "failed" : yes ? "done" : "idle";
    const b = cal && cal.bias_deg_s;
    let tone = "none", chip = "Not calibrated";
    if (collecting) chip = "Calibrating";
    else if (st === "failed") { tone = "crit"; chip = "Calibration failed"; }
    else if (yes) { tone = "ok"; chip = b ? `Calibrated · bias x ${fmt(b.gx, 2)}, y ${fmt(b.gy, 2)}, z ${fmt(b.gz, 2)} deg/s` : "Calibrated"; }
    el("cal-chip").dataset.tone = tone;
    setText("cal-chip-text", chip);

    calBtn.disabled = m === "idle" || collecting;
    calBtn.textContent = collecting ? "Calibrating" : st === "failed" ? "Retry" : yes ? "Recalibrate gyro" : "Calibrate gyro";
    calReset.hidden = !yes || collecting;

    const p = Math.min(1, Math.max(0, (cal && cal.progress) || 0));
    ringFill.style.strokeDashoffset = String(CIRC * (1 - p));
    setText("ring-label", collecting ? String(Math.round(p * 100)) : "");
    let msg;
    if (m === "idle") msg = "Connect the board or press Demo to calibrate.";
    else if (collecting) msg = "Keep the board still";
    else if (st === "failed") msg = (cal.message || "Calibration did not finish.") + " Lay the board flat and press Retry.";
    else if (yes) msg = "Offset removed. Calibrate again if the traces drift away from the zero line.";
    else msg = "Lay the board flat and still, then press Calibrate gyro.";
    setText("cal-msg", msg);
  }

  async function pollCal(g) {
    try { const c = await getJSON("/api/calibration", { device_id: state.deviceId }); if (g !== gen) return; cal = c; renderCal(); }
    catch { if (g !== gen) return; }
    calTimer = setTimeout(() => pollCal(g), cal && cal.state === "collecting" ? CFG.CALIB_POLL_MS : CFG.CALIB_IDLE_POLL_MS);
  }

  calBtn.addEventListener("click", async () => {
    try { cal = await postJSON("/api/calibrate/gyro", { device_id: state.deviceId }); }
    catch (e) { if (e.status !== 409) { cal = { state: "failed", progress: 0, calibrated: false, message: e.message }; } }
    renderCal(); restartCal();
  });
  calReset.addEventListener("click", async () => {
    try { await postJSON("/api/calibrate/reset", { device_id: state.deviceId }); cal = null; }
    catch (e) { cal = { state: "failed", progress: 0, calibrated: false, message: e.message }; }
    renderCal(); restartCal();
  });
  function restartCal() { clearTimeout(calTimer); pollCal(gen); }

  // ---------- Lifecycle ----------

  function restart() {
    gen++; clearTimeout(imuTimer); clearTimeout(calTimer);
    buf = []; lastSeq = -1; rxAt = 0; rate = 0; cal = null; dirty = true;
    renderStatus(); renderCal();
    if (mode() !== "idle") { pollImu(gen); pollCal(gen); }
  }
  window.addEventListener("sh:mode", restart);
  window.addEventListener("sh:reset", restart);
  restart();
})();
