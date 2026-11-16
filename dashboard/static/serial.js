// USB port selector: lets the user feed the dashboard from a wired board instead of WiFi.
// Talks to /api/serial/* (backend/routes/serial_routes.py). Independent of app.js's polling:
// once connected, the backend ingests the serial stream and app.js shows it like any other data.
(() => {
  const CFG = window.SMARTHEALTH_CONFIG;
  const $ = (id) => document.getElementById(id);
  const select = $("port-select"), btn = $("port-btn"), refreshBtn = $("port-refresh"), msg = $("port-msg"), led = $("link-led");
  let connected = false, busy = false;

  async function api(path, opts) {
    const res = await fetch(CFG.API_BASE_URL + path, opts);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || `${path} -> ${res.status}`);
    return body;
  }
  const post = (path, data) => api(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data || {}),
  });
  const setMsg = (t) => { msg.textContent = t || ""; msg.title = t || ""; };

  async function loadPorts() {
    const { ports } = await api("/api/serial/ports");
    const prev = select.value;
    select.replaceChildren();
    const usb = ports.filter((p) => p.usb), other = ports.filter((p) => !p.usb);
    const group = (label, list) => {
      if (!list.length) return;
      const g = document.createElement("optgroup"); g.label = label;
      list.forEach((p) => g.append(new Option(`${p.device.replace("/dev/", "")} — ${p.description}`, p.device)));
      select.append(g);
    };
    group("USB devices", usb);
    group("Other ports", other);
    if (!ports.length) select.append(new Option("No serial ports found", ""));
    if ([...select.options].some((o) => o.value === prev)) select.value = prev;
    else if (usb.length) select.value = usb[0].device;  // auto-select the first USB board
    if (!usb.length && !connected) setMsg("No USB board detected (install the CH340 driver / replug)");
    else if (!connected) setMsg("");
    render();
  }

  function render(st) {
    if (st) connected = st.connected;
    btn.textContent = connected ? "Disconnect" : "Connect";
    btn.dataset.mode = connected ? "disconnect" : "connect";
    select.disabled = refreshBtn.disabled = connected || busy;
    btn.disabled = busy || (!connected && !select.value);
    if (!st) return;
    // Hardware connected -> live mode (real data since this session started); disconnected -> idle.
    const m = window.__getMode();
    if (st.connected && (m.mode !== "live" || m.since !== st.connected_at)) {
      window.__setMode("live", { since: st.connected_at, label: st.port.replace("/dev/", "") });
    } else if (!st.connected && m.mode === "live") {
      window.__setMode("idle");
    }
    const age = st.last_sample_age_s;
    const streaming = age !== null && age < 2;
    const noSensors = st.imu_ok === false && st.vitals_ok === false;
    const missing = [];   // the board keeps working with whichever sensor is alive
    if (st.imu_ok === false) missing.push("motion sensor missing (no activity/fall detection)");
    if (st.vitals_ok === false) missing.push("heart-rate sensor missing");
    led.dataset.state = !connected ? "idle" : streaming && !missing.length ? "live" : "warn";
    if (connected) {
      if (noSensors) setMsg("No sensors detected — check wiring");
      else if (streaming) {
        const base = `Streaming ${st.port.replace("/dev/", "")} · ${st.samples.toLocaleString()} samples`;
        setMsg(missing.length ? `${base} · ${missing.join(", ")}` : base);
      } else setMsg(st.error || `Waiting for data… ${st.last_message || ""}`);
    } else if (st.error) {
      setMsg(st.error);  // e.g. cable pulled: the bridge stopped on its own
    }
  }

  async function pollStatus() {
    try { render(await api("/api/serial/status")); }
    catch { led.dataset.state = "idle"; }
  }

  btn.addEventListener("click", async () => {
    busy = true; render(); setMsg(connected ? "Disconnecting…" : "Connecting…");
    try {
      const st = connected
        ? await post("/api/serial/disconnect")
        : await post("/api/serial/connect", { port: select.value, device_id: $("device-input").value.trim() || CFG.DEFAULT_DEVICE_ID });
      busy = false; render(st);
      if (!st.connected) setMsg("Disconnected");
    } catch (e) {
      busy = false; render(); setMsg(e.message);
    }
  });
  refreshBtn.addEventListener("click", () => loadPorts().catch((e) => setMsg(e.message)));

  loadPorts().then(pollStatus).catch(() => { $("linkbar").hidden = true; });  // no backend (e.g. mock mode): hide
  setInterval(pollStatus, 1500);
  setInterval(() => { if (!connected && !busy && document.activeElement !== select) loadPorts().catch(() => {}); }, 4000);
})();
