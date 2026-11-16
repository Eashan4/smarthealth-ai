// Model comparison: 1D-CNN (deployed) vs LSTM (comparison).
//   /api/models       offline held-out test results. Real backend data in every mode, never time-filtered.
//   /api/models/live  both models' prediction for the most recent motion event.
// Uses helpers from app.js (getJSON, state, store, el, setText, CLASS_COLOR) and config.js.
(() => {
  "use strict";
  const COLORS = { CNN: "#46e0c4", LSTM: "#9c8cfb" };
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const pct = (v, d = 1) => (v * 100).toFixed(d) + "%";
  let data = null, cmMode = store.get("smarthealth_cm_mode") === "pct" ? "pct" : "counts";

  const color = (m) => COLORS[m.name] || "#9c8cfb";
  const key = (m) => (m.role === "deployed" ? "cnn" : "lstm");   // legend swatch slot
  const label = (m) => `${m.name} (${m.role})`;

  // ---------- Metrics table ----------

  const ROWS = [
    { name: "Accuracy", get: (m) => m.accuracy, show: (v) => pct(v), higher: true, bar: (v) => v },
    { name: "Macro-F1", get: (m) => m.macro_f1, show: (v) => pct(v), higher: true, bar: (v) => v },
    { name: "Fall recall", get: (m) => m.fall_recall, show: (v) => pct(v), higher: true, bar: (v) => v },
    { name: "Inference latency", unit: "ms per window", get: (m) => m.latency_ms, show: (v) => v.toFixed(2) + " ms", higher: false },
    { name: "Parameters", get: (m) => m.params, show: (v) => v.toLocaleString(), higher: false },
  ];

  function renderTable() {
    const [a, b] = data.models;
    let html = `<table class="mtable"><thead><tr><th scope="col"><span class="sr">Metric</span></th>` +
      data.models.map((m) => `<th scope="col" data-m="${key(m)}"><span class="mname">${esc(m.name)}</span> <span class="mrole">${esc(m.role)}</span></th>`).join("") + `</tr></thead><tbody>`;
    ROWS.forEach((r) => {
      const va = r.get(a), vb = r.get(b), tie = va === vb;
      const win = tie ? null : (r.higher ? va > vb : va < vb) ? a : b;
      const maxV = Math.max(va, vb);
      html += `<tr><th scope="row">${esc(r.name)}${r.unit ? `<span class="runit">${esc(r.unit)}</span>` : ""}</th>`;
      [a, b].forEach((m) => {
        const v = r.get(m), w = Math.round((r.bar ? r.bar(v) : v / maxV) * 100), best = win === m;
        html += `<td data-m="${key(m)}"${best ? ' data-best="true"' : ""}><span class="mval">${esc(r.show(v))}</span>` +
          (best ? `<span class="best">Better</span>` : "") +
          `<span class="mbar" aria-hidden="true"><i style="width:${w}%;background:${color(m)}"></i></span></td>`;
      });
      html += `</tr>`;
    });
    el("m-table").innerHTML = html + `</tbody></table>`;
    document.querySelectorAll(".legend .key").forEach((k, i) => { k.querySelector("i").style.background = color(data.models[i % 2]); });
  }

  // ---------- Per-class F1 (grouped bars, inline SVG) ----------

  function renderF1() {
    const box = el("m-f1"), W = Math.max(280, Math.floor(box.clientWidth || 360)), H = W > 560 ? 340 : 230;
    const pad = { l: 30, r: 6, t: 14, b: 26 }, pw = W - pad.l - pad.r, ph = H - pad.t - pad.b;
    const cls = data.classes, gw = pw / cls.length, bw = Math.min(26, (gw * 0.8) / 2);
    const y = (v) => pad.t + ph * (1 - v);
    let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="F1 score per activity for ${data.models.map((m) => esc(m.name)).join(" and ")}">`;
    [0, 0.25, 0.5, 0.75, 1].forEach((t) => {
      s += `<line class="grid" x1="${pad.l}" x2="${W - pad.r}" y1="${y(t)}" y2="${y(t)}"/><text class="axis" x="${pad.l - 6}" y="${y(t) + 3.5}" text-anchor="end">${t.toFixed(t % 1 ? 2 : 0)}</text>`;
    });
    cls.forEach((c, i) => {
      const cx = pad.l + gw * i + gw / 2;
      data.models.forEach((m, j) => {
        const v = m.per_class.f1[i], x = cx + (j - 1) * bw + (j === 0 ? -1 : 1), top = y(v);
        s += `<rect x="${x}" y="${top}" width="${bw}" height="${y(0) - top}" rx="2" fill="${color(m)}"><title>${esc(m.name)}, ${esc(c)}: F1 ${v.toFixed(2)}</title></rect>`;
        s += `<text class="vlab" x="${x + bw / 2}" y="${top - 4}" text-anchor="middle">${v.toFixed(2).replace(/^0/, "")}</text>`;
      });
      s += `<text class="axis cls" x="${cx}" y="${H - 8}" text-anchor="middle">${esc(c)}</text>`;
    });
    box.innerHTML = s + `</svg>`;
  }

  // ---------- Dataset note + validation sweep ----------

  function renderData() {
    const d = data.dataset || {}, sp = data.split || {}, per = d.included_per_class || {};
    const total = Object.values(per).reduce((a, v) => a + v, 0);
    let html = `<dl class="facts">
      <div><dt>Dataset</dt><dd>BITS-2, wrist motion trials</dd></div>
      <div><dt>Subjects (train / validation / test)</dt><dd>${esc(sp.train)} / ${esc(sp.val)} / ${esc(sp.test)}</dd></div>
      <div><dt>Trials per activity${total ? ` (${total} total)` : ""}</dt><dd class="chips">${data.classes.filter((c) => per[c] != null).map((c) => `<span>${esc(c)} <b>${esc(per[c])}</b></span>`).join("")}</dd></div>
    </dl>`;
    html += `<p class="caveat">Offline test accuracy on held-out BITS-2 subjects. Live motion rules are used for the real-time label on this board.</p>`;
    html += sweepSvg();
    el("m-data").innerHTML = html;
  }

  // One dot per hyperparameter run: how stable each model was on the validation subjects.
  function sweepSvg() {
    const runs = data.val_runs || [];
    if (!runs.length) return "";
    const W = 300, H = 92, l = 44, r = 8, lo = 0.5, hi = 1, x = (v) => l + ((v - lo) / (hi - lo)) * (W - l - r);
    let s = `<figure class="sweep"><figcaption>Validation sweep: accuracy of each trial run</figcaption><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Validation accuracy of each hyperparameter run, per model">`;
    [0.5, 0.75, 1].forEach((t) => { s += `<line class="grid" x1="${x(t)}" x2="${x(t)}" y1="4" y2="${H - 22}"/><text class="axis" x="${x(t)}" y="${H - 8}" text-anchor="middle">${Math.round(t * 100)}%</text>`; });
    data.models.forEach((m, j) => {
      const yy = 22 + j * 30;
      s += `<text class="axis" x="${l - 6}" y="${yy + 3.5}" text-anchor="end">${esc(m.name)}</text>`;
      runs.filter((rn) => rn.model_name === m.name).forEach((rn, i) => {
        s += `<circle cx="${x(rn.val_accuracy)}" cy="${yy + ((i % 3) - 1) * 6}" r="4" fill="${color(m)}" fill-opacity=".8" stroke="#0e1729"><title>${esc(m.name)} run: ${pct(rn.val_accuracy)} validation accuracy, ${Number(rn.params).toLocaleString()} parameters</title></circle>`;
      });
    });
    return s + `</svg></figure>`;
  }

  // ---------- Confusion matrices ----------

  function renderCM() {
    const cls = data.classes;
    el("m-cm").innerHTML = data.models.map((m) => {
      const cm = m.confusion_matrix;
      let t = `<table class="cm" data-m="${key(m)}"><caption><span class="sw" style="background:${color(m)}"></span>${esc(label(m))}</caption><thead><tr><td></td>` +
        cls.map((c) => `<th scope="col">${esc(c)}</th>`).join("") + `</tr></thead><tbody>`;
      cm.forEach((row, i) => {
        const sum = row.reduce((a, v) => a + v, 0) || 1;
        t += `<tr><th scope="row">${esc(cls[i])}</th>` + row.map((v, j) => {
          const f = v / sum, ok = i === j, bg = ok ? color(m) : "#ff5c74", a = v ? (0.12 + f * 0.7).toFixed(2) : 0;
          const txt = cmMode === "pct" ? (v ? Math.round(f * 100) + "%" : "0") : String(v);
          return `<td${ok ? ' class="diag"' : ""} style="background:${bg}${Math.round(a * 255).toString(16).padStart(2, "0")}" title="True ${esc(cls[i])}, predicted ${esc(cls[j])}: ${v} (${Math.round(f * 100)}% of row)">${txt}</td>`;
        }).join("") + `</tr>`;
      });
      return t + `</tbody></table>`;
    }).join("");
    el("cm-counts").setAttribute("aria-pressed", String(cmMode === "counts"));
    el("cm-pct").setAttribute("aria-pressed", String(cmMode === "pct"));
  }
  [["cm-counts", "counts"], ["cm-pct", "pct"]].forEach(([id, v]) => el(id).addEventListener("click", () => {
    cmMode = v; store.set("smarthealth_cm_mode", v); if (data) renderCM();
  }));

  // ---------- Load ----------

  function renderAll() {
    el("m-status").hidden = true; el("m-body").hidden = false;
    renderTable(); renderF1(); renderData(); renderCM();
  }

  async function load() {
    try {
      const d = await getJSON("/api/models");
      if (!d.available) { setText("m-status", "Model results are not available yet. Run python -m ml.training.train to produce them."); el("m-status").hidden = false; return; }
      data = d; renderAll();
    } catch (e) {
      setText("m-status", "Could not load model results. Retrying.");
      el("m-status").hidden = false;
      setTimeout(load, 5000);
    }
  }
  let rzT = 0;
  window.addEventListener("resize", () => { clearTimeout(rzT); rzT = setTimeout(() => data && renderF1(), 120); });

  // ---------- Live: last motion event ----------

  function liveCol(name, role, p) {
    if (!p) return `<div class="lm"><h4>${esc(name)} <span class="mrole">${esc(role)}</span></h4><p class="lm-act dim">Unavailable</p></div>`;
    return `<div class="lm"><h4>${esc(name)} <span class="mrole">${esc(role)}</span></h4>
      <p class="lm-act">${esc(p.activity)}</p>
      <p class="lm-sub">${Math.round((p.confidence ?? 0) * 100)}% confidence, ${Number(p.latency_ms).toFixed(2)} ms</p></div>`;
  }

  function renderLive(d) {
    const badge = el("live-badge");
    if (!d || !d.cnn) {
      badge.hidden = true;
      el("live-body").innerHTML = `<p class="empty-note">Waiting for a motion event</p>`;
      return;
    }
    el("live-body").innerHTML = `<div class="lm-pair">${liveCol("CNN", "deployed", d.cnn)}${liveCol("LSTM", "comparison", d.lstm)}</div>` +
      `<p class="lm-age">${d.age_s != null ? `Event ${Math.round(d.age_s)} s ago` : ""}</p>`;
    badge.hidden = d.agree == null;
    if (d.agree != null) { badge.dataset.tone = d.agree ? "ok" : "warn"; setText("live-badge-text", d.agree ? "Agree" : "Disagree"); }
  }

  let liveTimer = 0, liveGen = 0;
  async function pollLive(g) {
    let d = null;
    try { d = await getJSON("/api/models/live", { device_id: state.deviceId }); } catch { /* empty state */ }
    if (g !== liveGen) return;
    renderLive(d);
    liveTimer = setTimeout(() => pollLive(g), CFG.LIVE_MODELS_POLL_MS);
  }
  function restartLive() { liveGen++; clearTimeout(liveTimer); renderLive(null); pollLive(liveGen); }
  window.addEventListener("sh:mode", restartLive);
  window.addEventListener("sh:reset", restartLive);

  load();
  restartLive();
})();
