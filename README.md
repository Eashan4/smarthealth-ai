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

Early scaffold — see [docs/PLAN.md](docs/PLAN.md) for the phase-by-phase development order and current phase, and [docs/AUDIT.md](docs/AUDIT.md) for the compliance/success-criteria checklist.

## Getting started

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Backend, firmware, and dashboard setup instructions will be added as each phase lands (see docs/PLAN.md, Phase 1 onward).

## License

Academic project — license to be decided by the team.
