"""Synthetic hospital data for T7-T9 (no real patient data is used anywhere in these tutorials).

daily_arrivals()  -> 3 years of emergency-department arrivals with weekly + annual seasonality, a slow upward
                     trend, holiday bumps and flu bursts (T7).
encounters()      -> one row per inpatient admission across 6 service lines, with length of stay, revenue and
                     cost (T8, T9).
Fixed seeds, so every run is identical.
"""

import numpy as np
import pandas as pd

HOLIDAYS = {(1, 1), (7, 4), (12, 25), (11, 28)}


def daily_arrivals(seed=42):
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({"date": pd.date_range("2022-01-01", "2024-12-31")})
    t = np.arange(len(d))
    doy = d.date.dt.dayofyear.values
    dow = d.date.dt.dayofweek.values
    winter = np.cos(2 * np.pi * (doy - 20) / 365.25)
    flu = np.zeros(len(d))
    for year_start in (0, 365, 730):                      # one flu burst per winter, random size/timing
        c = year_start + rng.integers(10, 50)
        flu += rng.uniform(0.5, 1.0) * np.exp(-0.5 * ((t - c) / 12.0) ** 2)
    hol = np.array([(m, dd) in HOLIDAYS for m, dd in zip(d.date.dt.month, d.date.dt.day)])
    mu = (190 * np.array([1.12, 1.05, 1.0, 0.98, 1.0, 0.93, 0.92])[dow]
          * (1 + 0.10 * winter) * (1 + 0.04 * t / 365.25) * (1 + 0.15 * flu) * (1 + 0.10 * hol))
    d["arrivals"] = rng.negative_binomial(60, 60 / (60 + mu))      # over-dispersed counts
    d["is_holiday"] = hol.astype(int)
    return d


SERVICE_LINES = {
    #            share  mean_los  rev/day  cost/day  yearly growth
    "Cardiology":   (0.20, 4.8, 3600, 2500, 0.05),
    "Orthopaedics": (0.17, 3.6, 4300, 2900, 0.03),
    "Pulmonology":  (0.17, 5.4, 2900, 2600, 0.06),
    "Oncology":     (0.12, 6.9, 4700, 3600, 0.08),
    "Neurology":    (0.14, 5.9, 3300, 2900, 0.04),
    "General Surgery": (0.20, 4.1, 3900, 3500, -0.01),
}
WINTER_AMPLITUDE = {"Pulmonology": 0.35, "Cardiology": 0.12}      # other lines are flat across the year


def encounters(seed=7, n_base=26000):
    """3 years of admissions; volume per line grows at its own rate."""
    rng = np.random.default_rng(seed)
    rows = []
    for name, (share, los, rev, cost, g) in SERVICE_LINES.items():
        for yi, year in enumerate((2022, 2023, 2024)):
            n = int(n_base * share * (1 + g) ** yi)
            doy = np.arange(365)
            w = 1 + WINTER_AMPLITUDE.get(name, 0.0) * np.cos(2 * np.pi * (doy - 20) / 365)
            admit = pd.to_datetime(year * 10000 + 101, format="%Y%m%d") + pd.to_timedelta(rng.choice(doy, n, p=w / w.sum()), "D")
            stay = np.maximum(1, np.round(rng.gamma(shape=3.0, scale=los / 3.0, size=n))).astype(int)
            rows.append(pd.DataFrame({
                "service_line": name, "year": year, "admit_date": admit, "los_days": stay,
                "revenue": stay * rev * rng.normal(1, 0.08, n),
                "cost": stay * cost * rng.normal(1, 0.10, n)}))
    e = pd.concat(rows, ignore_index=True)
    e["month"] = e.admit_date.dt.month
    return e
