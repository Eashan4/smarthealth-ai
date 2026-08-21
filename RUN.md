# Running SmartHealth AI

Every command below was actually run to verify it works (2026-08-19). Run everything from the repo root unless noted. See [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) for the full technical writeup and [docs/PLAN.md](docs/PLAN.md) / [docs/AUDIT.md](docs/AUDIT.md) for phase-by-phase status.

## 0. One-time setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 1. Models — train and check accuracy

The dataset isn't in the repo (gitignored, large). Download the [BITS-2 dataset](https://doi.org/10.5281/zenodo.10013090) and place it so raw trial CSVs live at `data/raw/bits2/Dataset/{adl,fall}/user*/*.csv`:

```bash
mkdir -p data/raw
curl -L -o data/raw/bits2.zip "https://zenodo.org/records/10013090/files/full_dataset.zip?download=1"
unzip data/raw/bits2.zip -d data/raw/bits2
```

Train (CNN + LSTM sweep, ~1-2 min on CPU) and derive the Phase 8 decision thresholds:

```bash
python -m ml.training.train
python -m ml.evaluation.threshold_analysis
```

This writes `models/deployed_model.pt` (the CNN), `models/comparison_model.pt` (the LSTM), `models/scaler.json`, `models/model_meta.json`, `models/training_results.json`, and `models/threshold_experiment.json`.

**Real, measured accuracy** (held-out test split — 6 subjects never seen in training or validation; full breakdown in DOCUMENTATION.md sec 6.3):

| Model | Test Accuracy | Macro-F1 | Fall Recall | Inference (CPU) | Params |
|---|---|---|---|---|---|
| **CNN (deployed)** | **85.1%** | **0.805** | **89.6%** | 0.12 ms/window | 11,813 |
| LSTM (comparison) | 81.6% | 0.755 | 87.5% | 2.11 ms/window | 52,037 |

Trained classes: `Walking, Running, Sitting, Lying, Fall`. `Standing` and `Tremor` are **not** trained in v1 — no matching data in BITS-2 (see DOCUMENTATION.md sec 5/16).

**Verify the models actually work end-to-end** (not just the offline numbers above — see step 3):

```bash
python -m tests.e2e_demo
```

Expected output: `Walking PASS`, `Sitting PASS`, `Running PASS`, `Fall PASS` (all against real, held-out data), plus a note that the Tremor scenario is not run (no trained class — reported honestly, not silently skipped).

## 2. Backend — run and check

```bash
python -m backend.app
```

Serves the API + dashboard at **http://localhost:5000**. Leave this running in its own terminal for everything below.

Quick health/API checks in another terminal:

```bash
curl http://localhost:5000/api/health
curl -X POST http://localhost:5000/api/sensor-data -H "Content-Type: application/json" \
  -d '{"device_id":"wearable_01","timestamp":1700000000,"imu":{"ax":0.1,"ay":0.2,"az":9.8,"gx":0,"gy":0,"gz":0},"vitals":{"heart_rate":75,"spo2":98}}'
# malformed payload should be rejected with 400:
curl -X POST http://localhost:5000/api/sensor-data -H "Content-Type: application/json" -d '{"timestamp":1}'
```

Config lives in [ml/config.py](ml/config.py) (sampling rate, window size, thresholds — all central, nothing hard-coded elsewhere per PLAN.md's engineering rules).

## 3. Frontend — run and check

The dashboard is served by the same backend (step 2) at **http://localhost:5000**. With no data yet it'll show `--` everywhere; feed it live data with the simulated-device sender (no physical ESP32 needed):

```bash
python -m tests.fake_esp32_sender --trial data/raw/bits2/Dataset/adl/user2/user2_adl1.csv --device-id wearable_01   # Walking
python -m tests.fake_esp32_sender --trial data/raw/bits2/Dataset/fall/user2/user2_fall4.csv --device-id wearable_01  # Fall alert
```

Open http://localhost:5000 in a browser (works on phone too — it's mobile-first responsive; point your phone at `http://<your-machine-ip>:5000` on the same network). The device ID field in the top bar can point the dashboard at any `device_id` you've sent data for.

**All dashboard behavior is config-driven** — edit [dashboard/static/config.js](dashboard/static/config.js), no code changes needed, to change:

| Setting | What it controls |
|---|---|
| `DEFAULT_DEVICE_ID` | which device the dashboard shows on load |
| `POLL_INTERVAL_MS` | how often it polls the backend |
| `TRACE_HISTORY_LENGTH` | how many points the waveform/sparkline traces keep |
| `ACTIVITY_LOG_LENGTH` | how many rows the activity log/timeline show |
| `API_BASE_URL` | point the dashboard at a backend running elsewhere |
| `STALE_AFTER_MS` | how long before the connection indicator goes idle |

**Visual verification:** screenshotted at mobile (390×844) and desktop (1280×900) widths with Playwright during development, both with a live data feed and with an active fall alert — no console errors, confirmed bars/traces/alert states render correctly.

## 4. Firmware — compile-check (no hardware needed)


pip install platformio
cd firmware/esp32
cp src/secrets.h.example src/secrets.h   # fill in real WiFi/backend values before flashing
pio run                    # live-streaming build — compiles against the real ESP32 toolchain
pio run -e esp32dev_logger # Phase 2 CSV-logger build


Both compile successfully (verified) but have not run on physical hardware — none is available in this environment. See [firmware/esp32/README.md](firmware/esp32/README.md).

## 5. Everything at once (typical dev session)


source venv/bin/activate
python -m backend.app &                 # terminal stays open, or run in background
python -m tests.fake_esp32_sender --trial data/raw/bits2/Dataset/adl/user2/user2_adl1.csv --device-id wearable_01
open http://localhost:5000              # macOS; xdg-open on Linux

