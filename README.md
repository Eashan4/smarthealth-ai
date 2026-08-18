# SmartHealth AI

Deep learning-based wearable healthcare monitoring system for **Activity, Fall, Tremor, and Vital Sign** monitoring.

> **Academic prototype disclaimer:** This is a 2-person student project for a Healthcare Analytics course. It performs **monitoring / detection / classification** on a low-cost prototype. It is **not** a certified medical device and does **not** diagnose disease, replace clinical judgment, or provide clinically certified vital sign or fall-detection measurements. See [docs/AUDIT.md](docs/AUDIT.md) for the full scope-limits checklist.

## What it does

A wearable (ESP32 + MPU6050 + MAX30102) streams motion and physiological data over Wi-Fi to a Flask backend, which segments the IMU stream into sliding windows and runs deep-learning inference (1D CNN, compared against an LSTM) to classify:

- Walking, Standing, Sitting, Running, Lying
- Fall (AI prediction + rule-based verification)
- Tremor-like abnormal movement

Heart rate and estimated SpO₂ from the MAX30102 are captured as a separate, timestamp-synchronized stream. Results are stored in SQLite and shown on a real-time web dashboard, with a local buzzer and dashboard alert on a confirmed fall.

## Architecture

```
MPU6050 (Ax,Ay,Az,Gx,Gy,Gz)          MAX30102 (HR, SpO2)
        │                                    │
        └───────────────┬────────────────────┘
                     ESP32 (timestamp, JSON)
                         │  Wi-Fi / REST
                         ▼
                  Flask Backend
          (validate → preprocess → sliding
           window 3s@50Hz → 150x6 tensor)
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
           1D CNN                 LSTM
       (primary, deployed)   (comparison model)
              │
      Activity / Fall / Tremor
              │
       Decision Engine (AI + rule verification)
              │
        ┌─────┴─────┐
        ▼           ▼
     SQLite    Alert Logic
                    │
             ┌──────┴──────┐
             ▼             ▼
          Buzzer      Web Dashboard
```

Full technical detail (data flow, model specs, API, DB schema, config) lives in [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md). The baseline architecture is fixed — changes are evaluated against it rather than added casually.

## Repository structure

```
smarthealth-ai/
├── firmware/esp32/     # ESP32 C/C++ firmware (sensors, Wi-Fi, buzzer)
├── backend/            # Flask API: routes, services, database access
│   ├── routes/
│   ├── services/
│   └── database/
├── ml/                 # All machine learning code
│   ├── datasets/       # Public + custom dataset loaders and adapters
│   ├── preprocessing/  # Filtering, normalization, timestamp alignment
│   ├── segmentation/   # Sliding-window segmentation (train + inference)
│   ├── cnn/            # 1D CNN model definition
│   ├── lstm/           # LSTM model definition (comparison)
│   ├── training/       # Training scripts, experiment configs
│   ├── evaluation/     # Metrics, confusion matrices, model comparison
│   └── inference/      # Real-time rolling-window inference
├── dashboard/          # Web dashboard (HTML/JS or React + Chart.js)
├── models/             # Trained model artifacts (not real sensor data)
├── data/               # Raw/processed datasets (gitignored beyond samples)
├── tests/              # Hardware, backend, ML, and system tests
├── docs/               # Plan, documentation, audit, architecture notes
├── requirements.txt
└── README.md
```

## Tech stack

| Layer          | Choice                                  |
|----------------|------------------------------------------|
| Embedded       | ESP32, Arduino IDE / PlatformIO, C/C++   |
| Sensors        | MPU6050 (IMU), MAX30102 (HR/SpO₂)        |
| ML             | Python, NumPy, Pandas, Scikit-learn, PyTorch |
| Backend        | Flask                                    |
| Dashboard      | HTML/CSS/JS + Chart.js (or React)        |
| Database       | SQLite                                   |

## Project status

**Full software stack implemented and tested (2026-08-19).** All 9 phases have code; Phase 3 (ML), 4 (LSTM comparison), 5 (backend), 6 (real-time inference), 7 (dashboard), 8 (decision engine), and 9 (end-to-end, non-hardware scenarios) are verified against real data. Phases 1, 2, and the ESP32 side of Phase 5/8 are **code-complete but hardware-unverified** — firmware compiles cleanly against the real ESP32 toolchain but has never run on a physical board (none available in this environment). See [docs/PLAN.md](docs/PLAN.md) for the per-phase status and [docs/AUDIT.md](docs/AUDIT.md) for the full checklist.

Trained on the [BITS-2 dataset](https://doi.org/10.5281/zenodo.10013090) (same MPU6500+MAX30102 sensor pair as this project's hardware): the deployed 1D CNN reaches **85.1% accuracy / 89.6% fall recall** on a held-out, subject-disjoint test split, beating an LSTM comparison model on every measured axis. `Standing` and `Tremor` are not trained in v1 (no matching data in BITS-2) — see [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) sec 5/16/21 for the full, honest accounting of what is and isn't covered.

## Getting started

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Train the models** (downloads nothing itself — see `ml/datasets/bits2_adapter.py` for the BITS-2 dataset source; place it at `data/raw/bits2/Dataset/`):

```bash
python -m ml.training.train                 # trains CNN + LSTM, saves models/deployed_model.pt
python -m ml.evaluation.threshold_analysis   # derives Phase 8 decision thresholds
```

**Run the backend + dashboard:**

```bash
python -m backend.app                        # serves the API and dashboard at http://localhost:5000
```

**Simulate a device** (no ESP32 hardware needed):

```bash
python -m tests.fake_esp32_sender --trial data/raw/bits2/Dataset/fall/user2/user2_fall1.csv
python -m tests.e2e_demo                      # full Phase 9 demo across held-out test subjects
```

**Firmware** (compiles against the real ESP32 toolchain; see [firmware/esp32/README.md](firmware/esp32/README.md) for build/flash steps and hardware-verification status):

```bash
cd firmware/esp32 && pio run
```

## License

Academic project — license to be decided by the team.
