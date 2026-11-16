"""Synthetic-signal check of the tremor detector (accel + gyro). Run: python -m tests.test_tremor
Prints PASS/FAIL per case, exits non-zero on failure. Units: accel m/s^2, gyro rad/s, 50 Hz."""

import sys

import numpy as np

from ml.inference.tremor import TremorDetector, analyze

FS, T = 50, np.arange(0, 8, 1 / 50)
rng = np.random.default_rng(0)


def sig(acc=(), gyro=(), a_noise=0.05, g_noise=0.01, g_broadband=0.0):
    """acc/gyro: [(freq_hz, peak_amplitude)] on z / x. Gravity on z; MPU6050-like noise (0.05 m/s2, 0.01 rad/s)."""
    a = rng.normal(0, a_noise, (len(T), 3)); a[:, 2] += 9.81
    g = rng.normal(0, g_noise + g_broadband, (len(T), 3))
    for f, amp in acc:
        a[:, 2] += amp * np.sin(2 * np.pi * f * T + rng.uniform(0, 6.28))
    for f, amp in gyro:
        g[:, 0] += amp * np.sin(2 * np.pi * f * T + rng.uniform(0, 6.28))
    return np.hstack([a, g])


def run(x, fs=FS):
    d = TremorDetector(FS)
    for i, row in enumerate(x):
        d.push(list(row), ts=i / fs)
    return d


CASES = {   # name: (signal, expect detected)
    "resting, sensor noise only":         (lambda: sig(), False),
    "accel 5 Hz 0.6":                     (lambda: sig([(5.0, 0.6)]), True),
    "accel 4 Hz 1.5":                     (lambda: sig([(4.0, 1.5)]), True),
    "accel 6.5 Hz 0.4":                   (lambda: sig([(6.5, 0.4)]), True),
    "accel 5 Hz 0.3 (weak)":              (lambda: sig([(5.0, 0.3)]), True),
    "accel tremor + slow drift 0.7 Hz":   (lambda: sig([(5.0, 0.6), (0.7, 0.5)]), True),
    "accel tremor + big slow drift":      (lambda: sig([(5.0, 0.8), (0.6, 2.0)]), True),
    "gyro-only 5 Hz 0.3 rad/s":           (lambda: sig(gyro=[(5.0, 0.3)]), True),
    "gyro-only 4.5 Hz 0.1 rad/s":         (lambda: sig(gyro=[(4.5, 0.1)]), True),
    "gyro 5 Hz 1.5 + accel 3 (shake)":    (lambda: sig([(5.0, 3.0)], [(5.0, 1.5)]), True),
    "gyro tremor + gyro slow drift":      (lambda: sig(gyro=[(5.0, 0.2), (0.8, 0.8)]), True),
    "walking (1.9 Hz + harmonics)":       (lambda: sig([(1.9, 5.0), (3.8, 2.0), (5.7, 1.0)], [(0.95, 1.5), (1.9, 0.6), (3.8, 0.5)]), False),
    "walking, 2nd harmonic dominant":     (lambda: sig([(1.9, 2.0), (3.8, 4.0)], [(1.9, 0.4), (3.8, 0.8)]), False),
    "running (2.8 Hz + harmonics)":       (lambda: sig([(2.8, 10.0), (5.6, 4.0)], [(1.4, 3.0), (2.8, 1.0), (5.6, 0.5)]), False),
    "slow arm movement 0.5 Hz":           (lambda: sig([(0.5, 2.0)], [(0.5, 1.0)]), False),
    "11 Hz vibration (above band)":       (lambda: sig([(11.0, 0.6)], [(11.0, 0.2)]), False),
    "tiny 5 Hz (below noise floor)":      (lambda: sig([(5.0, 0.05)], [(5.0, 0.01)]), False),
    "broadband gyro noise 0.15 rad/s":    (lambda: sig(g_broadband=0.15), False),
    "broadband accel noise 0.5 m/s2":     (lambda: sig(a_noise=0.5), False),
}

if __name__ == "__main__":
    bad = 0

    def report(name, ok, extra=""):
        global bad
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:36s} {extra}")

    for name, (mk, expect) in CASES.items():
        d = run(mk())
        got, m = d.detected, d.last
        s = d.status()
        report(name, got == expect, f"detected={got!s:5} f={s['freq_hz']:.1f}Hz acc={s['amplitude']:.2f} "
               f"gyro={s['gyro_amplitude']:.2f} score={s['score']:.2f}")
    # amplitude + frequency accuracy: 5 Hz, 0.6 peak on one axis -> rms 0.6/sqrt(2)=0.424
    m = analyze(sig([(5.0, 0.6)])[:150, :3], FS)
    report("accel freq/amplitude accuracy", abs(m["freq_hz"] - 5.0) < 0.5 and abs(m["amplitude"] - 0.424) < 0.06, str(m))
    m = analyze(sig(gyro=[(5.0, 0.3)])[:150, 3:], FS)
    report("gyro freq/amplitude accuracy", abs(m["freq_hz"] - 5.0) < 0.5 and abs(m["amplitude"] - 0.212) < 0.04, str(m))
    # bursty arrival (serial lines come in bursts): per-sample jitter must not move the frequency
    d = TremorDetector(FS)
    x = sig([(5.0, 0.6)])
    for i, row in enumerate(x):
        d.push(list(row), ts=(i // 10) * 10 / FS)           # 10 samples share one arrival time
    report("bursty timestamps still 5 Hz", d.detected and abs(d.last["freq_hz"] - 5.0) < 0.5, f"{d.last['freq_hz']:.2f}")
    # genuinely slow stream (35 Hz) is detected via the whole-window rate estimate
    d, tt = TremorDetector(FS), np.arange(0, 8, 1 / 35)
    for t in tt:
        d.push([0, 0, 9.81 + 0.6 * np.sin(2 * np.pi * 5 * t), 0, 0, 0], ts=t)
    report("35 Hz stream still 5 Hz", d.detected and abs(d.last["freq_hz"] - 5.0) < 0.6, f"{d.last['freq_hz']:.2f}")
    # clears again after the tremor stops; status keys intact
    d = run(np.vstack([sig([(5.0, 0.6)]), sig()]))
    st = d.status()
    report("clears after tremor stops", not d.detected and {"state", "freq_hz", "amplitude", "band_ratio"} <= st.keys(), str(st))
    print("OK: tremor detector" if not bad else f"{bad} FAILED")
    sys.exit(1 if bad else 0)
