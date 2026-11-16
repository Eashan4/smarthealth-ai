"""Synthetic-signal check of the tremor detector. Run: python -m tests.test_tremor"""

import numpy as np

from ml.inference.tremor import TremorDetector, analyze, looks_like_tremor

FS, T = 50, np.arange(0, 8, 1 / 50)
rng = np.random.default_rng(0)


def sig(components, noise=0.03, axis=2):
    """components: [(freq_hz, peak_amplitude_m_s2)]; gravity on z, tiny sensor noise on all axes."""
    a = rng.normal(0, noise, (len(T), 3))
    a[:, 2] += 9.81
    for f, amp in components:
        a[:, axis] += amp * np.sin(2 * np.pi * f * T + rng.uniform(0, 6.28))
    return a


def run(a):
    d = TremorDetector(FS)
    for i, row in enumerate(a):
        d.push([*row, 0, 0, 0], ts=i / FS)
    return d


CASES = {   # name: (signal components, expect detected)
    "resting, sensor noise only":      ([], False),
    "5 Hz tremor, 0.6 m/s2":           ([(5.0, 0.6)], True),
    "4 Hz tremor, 1.5 m/s2":           ([(4.0, 1.5)], True),
    "6.5 Hz tremor, 0.4 m/s2":         ([(6.5, 0.4)], True),
    "tremor + slow arm drift":         ([(5.0, 0.6), (0.7, 0.5)], True),
    "walking (1.9 Hz + harmonics)":    ([(1.9, 5.0), (3.8, 2.0), (5.7, 1.0)], False),
    "running (2.8 Hz + harmonics)":    ([(2.8, 10.0), (5.6, 4.0)], False),
    "slow arm movement 0.5 Hz":        ([(0.5, 2.0)], False),
    "11 Hz vibration (above band)":    ([(11.0, 0.6)], False),
    "tiny 5 Hz (below noise floor)":   ([(5.0, 0.1)], False),
}

if __name__ == "__main__":
    for name, (comps, expect) in CASES.items():
        d = run(sig(comps))
        got = d.detected
        m = d.last
        print(f"{'PASS' if got == expect else 'FAIL'}  {name:34s} detected={got!s:5} "
              f"f={m['freq_hz']:.1f}Hz amp={m['amplitude']:.2f} ratio={m['band_ratio']:.2f} "
              f"peak={m['peak_ratio']:.0f} low={m['low_rms']:.2f}")
        assert got == expect, name
    # amplitude + frequency are accurate: 5 Hz, 0.6 peak on one axis -> rms 0.6/sqrt(2)=0.424
    m = analyze(sig([(5.0, 0.6)])[:150], FS)
    assert abs(m["freq_hz"] - 5.0) < 0.5 and abs(m["amplitude"] - 0.424) < 0.06, m
    # slow stream (35 Hz real rate) still reports 5 Hz thanks to timestamp-based rate estimate
    d = TremorDetector(FS)
    tt = np.arange(0, 8, 1 / 35)
    for t in tt:
        d.push([0, 0, 9.81 + 0.6 * np.sin(2 * np.pi * 5 * t), 0, 0, 0], ts=t)
    assert d.detected and abs(d.last["freq_hz"] - 5.0) < 0.6, d.last
    # clears again after the tremor stops
    a = np.vstack([sig([(5.0, 0.6)]), sig([])])
    d = TremorDetector(FS)
    for i, row in enumerate(a):
        d.push([*row, 0, 0, 0], ts=i / FS)
    assert not d.detected
    print("OK: tremor detector")
