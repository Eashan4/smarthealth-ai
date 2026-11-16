# Live demo guide (real hardware)

Setup: `source venv/bin/activate && python -m backend.app`, open http://localhost:5000, pick the USB port, **Connect**.
Watch the Vitals tiles, the Tremor and motion panel and the Fall status as you go.
Detection is rule-based on your board (see [DEMO_TUNING.md](DEMO_TUNING.md)); numbers there are starting values, not validated.

| # | Show | How to do it | What the dashboard shows |
|---|------|--------------|--------------------------|
| 1 | **Calibrate** | Lay the board flat and still. Press **Calibrate gyro**, wait ~2 s. | Gyro strips sit on the zero line. Chip reads "Calibrated · bias ...". "Keep the board still" means you moved: retry. |
| 1b | **Heart rate and SpO2** | Rest a fingertip lightly on the MAX30102 for ~10 s. | HR and SpO2 cards fill in with min / avg / max. "No finger detected" when you lift off. |
| 2 | **Still** | Rest the board on the table, or hold it against your chest. | Sitting / Standing, gyro flat. |
| 3 | **Walking** | Hold the board in your hand (or strap it to your waist) and walk at a normal pace for ~10 s. | Walking, dominant frequency about 1.5-2.2 Hz, accel wave swings. |
| 4 | **Tremor** | Hold the board and shake your hand fast and small, about 5 times a second, for ~3-4 s. | Tremor card: "Detected", 4-6 Hz, gyro traces oscillate. |
| 5 | **Running** (optional) | Jog on the spot holding the board. | Running (cadence above 2.6 Hz, large swing). |
| 6 | **Fall** | Lift the board ~30 cm and drop it onto a pillow or bed, then leave it still for 2 s. | Fall status goes Checking, then DETECTED. Red alert bar and the buzzer sounds. D6 button silences it. |
| 7 | **Model comparison** | Scroll to *Model comparison* (always visible). | CNN vs LSTM test metrics, per-class F1, confusion matrices. After any motion, *Live: last motion event* shows what each model predicted and whether they agree. |

Tips for a clean demo:
- Do the fall last, because it triggers the alert. Do the calibration first, and again if the gyro strips drift off zero.
- Tremor: a small, fast, steady shake works best. A big slow wave is read as walking.
- Fall: just throwing the board around does not count. It needs weightlessness, then a hit, then stillness.
- No hardware? Press **Demo** for a labelled simulated cycle (Sitting, Walking, Tremor, Fall).

If something is not detected, open http://localhost:5000/api/motion?device_id=wearable_01 while doing the motion.
It shows `dom_freq_hz`, `accel_std`, `gyro_rms` and `fall_state`. Compare them with the thresholds in
[DEMO_TUNING.md](DEMO_TUNING.md) and edit `ml/config.py`; the backend reloads on save.

## Pipeline

```
MPU6050 + MAX30102 -> NodeMCU (50 Hz) -> USB serial "D,ax..gz,hr,spo2"
  -> serial_bridge.py -> ingest.process_sample
       1 calibration: subtract gyro bias; push to live IMU buffer (/api/imu)
       2 store raw reading (SQLite)
       3 tremor detector (accel + gyro spectrum, 3-8 Hz)
       4 motion rules, 1 Hz: Walking / Running / Sitting / Standing / Lying
       5 fall state machine: free-fall -> impact -> stillness (+ CNN as supporting evidence)
       6 decision engine -> alert + buzzer command "B" back to the board
       7 both models (CNN deployed, LSTM comparison) classify each captured motion event
  -> Flask API (/api/vitals, /api/tremor, /api/motion, /api/imu, /api/calibration, /api/models, ...) -> dashboard
```
