"""T7: Patient prediction for improved staffing.

Forecast daily emergency-department arrivals 7 days ahead (the horizon a weekly roster is built on), then turn the
forecast into a nurse roster and compare it with a flat roster.

  models : seasonal-naive (same weekday last week), linear regression on calendar/Fourier/trend features,
           gradient boosting on calendar + lag features
  metric : MAE and MAPE on the last 120 days, never seen in training
  staffing: nurses needed = ceil(arrivals * 3.2 nurse-hours / 10 productive hours per 12 h shift)
            cost = 1 per idle nurse-shift + 4 per missing nurse-shift

Run: python t7_staffing_forecast.py
Output: outputs/t7_forecast.png, outputs/t7_staffing.png, outputs/t7_results.json
"""

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge

from hospital_data import daily_arrivals

warnings.filterwarnings("ignore", category=RuntimeWarning)   # benign BLAS matmul warnings on macOS

OUT = Path(__file__).parent / "outputs"
H, TEST_DAYS = 7, 120
NURSE_HOURS_PER_ARRIVAL, PRODUCTIVE_HOURS = 3.2, 10.0
IDLE_COST, SHORT_COST = 1.0, 4.0


def features(d):
    f = pd.DataFrame(index=d.index)
    t = np.arange(len(d))
    doy = d.date.dt.dayofyear.values
    f["trend"] = t / 365.25
    for k in (1, 2):
        f[f"s{k}"], f[f"c{k}"] = np.sin(2 * np.pi * k * doy / 365.25), np.cos(2 * np.pi * k * doy / 365.25)
    for i in range(7):
        f[f"dow{i}"] = (d.date.dt.dayofweek.values == i).astype(int)
    f["holiday"] = d.is_holiday.values
    return f


def lag_features(d):
    """Only information available H days before the day being forecast."""
    f = features(d)
    y = d.arrivals
    f["lag7"], f["lag14"] = y.shift(H), y.shift(14)
    f["roll7"] = y.shift(H).rolling(7).mean()
    f["roll28"] = y.shift(H).rolling(28).mean()
    return f


def metrics(y, p):
    return {"MAE": float(np.mean(np.abs(y - p))), "MAPE": float(np.mean(np.abs(y - p) / y) * 100)}


def nurses_needed(arrivals):
    return np.ceil(np.asarray(arrivals) * NURSE_HOURS_PER_ARRIVAL / PRODUCTIVE_HOURS).astype(int)


def roster_cost(staff, need):
    short, idle = np.maximum(need - staff, 0), np.maximum(staff - need, 0)
    return {"short_days": int((short > 0).sum()), "nurse_shifts_short": int(short.sum()),
            "nurse_shifts_idle": int(idle.sum()), "cost": float(IDLE_COST * idle.sum() + SHORT_COST * short.sum())}


if __name__ == "__main__":
    d = daily_arrivals()
    n = len(d)
    tr, te = slice(28, n - TEST_DAYS), slice(n - TEST_DAYS, n)
    y = d.arrivals.values
    print(f"{n} days of arrivals; mean {y.mean():.0f}/day, range {y.min()}-{y.max()}; test = last {TEST_DAYS} days\n")

    preds = {"seasonal naive (t-7)": d.arrivals.shift(7).values[te]}
    Xl = features(d)
    lin = Ridge(alpha=1.0).fit(Xl.iloc[tr], y[tr])
    preds["linear (calendar + Fourier)"] = lin.predict(Xl.iloc[te])
    Xg = lag_features(d)
    gbr = GradientBoostingRegressor(n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0)
    gbr.fit(Xg.iloc[tr].dropna(), y[tr][Xg.iloc[tr].notna().all(axis=1).values])
    preds["gradient boosting (+ lags)"] = gbr.predict(Xg.iloc[te])

    res = {}
    print(f"{'model':32s} {'MAE':>7s} {'MAPE %':>8s}")
    for name, p in preds.items():
        res[name] = metrics(y[te], p)
        print(f"{name:32s} {res[name]['MAE']:7.2f} {res[name]['MAPE']:8.2f}")
    best = min(res, key=lambda k: res[k]["MAE"])
    print(f"\nBest model: {best}")

    # --- staffing -------------------------------------------------------------------------------------------
    need = nurses_needed(y[te])
    resid = y[tr] - lin.predict(Xl.iloc[tr])
    buffer = float(np.quantile(resid, 0.90))               # cover the 90th-percentile forecast miss
    policies = {
        "flat roster (train mean)": np.full(TEST_DAYS, nurses_needed(y[tr].mean())),
        "flat roster (train 90th pct)": np.full(TEST_DAYS, nurses_needed(np.quantile(y[tr], 0.90))),
        "forecast roster": nurses_needed(preds[best]),
        f"forecast + {buffer:.0f}-patient buffer": nurses_needed(preds[best] + buffer),
    }
    staff_res = {}
    print(f"\n{'roster policy':34s} {'short days':>10s} {'shifts short':>13s} {'shifts idle':>12s} {'cost':>8s}")
    for name, s in policies.items():
        staff_res[name] = roster_cost(s, need)
        r = staff_res[name]
        print(f"{name:34s} {r['short_days']:10d} {r['nurse_shifts_short']:13d} {r['nurse_shifts_idle']:12d} {r['cost']:8.0f}")

    # --- plots ----------------------------------------------------------------------------------------------
    dates = d.date.values[te]
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(dates, y[te], color="black", lw=1.4, label="actual")
    for (name, p), c in zip(preds.items(), ("tab:gray", "tab:blue", "tab:red")):
        ax.plot(dates, p, lw=1, color=c, alpha=0.9, label=f"{name} (MAE {res[name]['MAE']:.1f})")
    ax.set_ylabel("ED arrivals / day"); ax.set_title("T7: 7-day-ahead forecast on the held-out last 120 days")
    ax.legend(fontsize=8, ncol=2); fig.tight_layout(); fig.savefig(OUT / "t7_forecast.png", dpi=130); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(10, 4.2))
    axs[0].step(dates, need, color="black", label="nurses needed", where="mid")
    axs[0].step(dates, policies["flat roster (train mean)"], color="tab:orange", label="flat roster", where="mid")
    axs[0].step(dates, policies[f"forecast + {buffer:.0f}-patient buffer"], color="tab:green", label="forecast + buffer", where="mid")
    axs[0].set_title("Nurses per day"); axs[0].legend(fontsize=8)
    names = list(staff_res)
    axs[1].barh(range(len(names)), [staff_res[k]["cost"] for k in names], color=["tab:orange", "tab:gray", "tab:blue", "tab:green"])
    axs[1].set_yticks(range(len(names))); axs[1].set_yticklabels([k.replace(" roster", "") for k in names], fontsize=8)
    axs[1].set_title("Total roster cost (lower is better)"); axs[1].invert_yaxis()
    fig.tight_layout(); fig.savefig(OUT / "t7_staffing.png", dpi=130); plt.close(fig)

    (OUT / "t7_results.json").write_text(json.dumps({"models": res, "best": best, "staffing": staff_res, "buffer": buffer}, indent=1))

    assert res[best]["MAE"] < res["seasonal naive (t-7)"]["MAE"], "model should beat seasonal naive"
    assert min(v["cost"] for k, v in staff_res.items() if k.startswith("forecast")) < staff_res["flat roster (train mean)"]["cost"]
    print("\nSelf-check passed: forecast beats seasonal-naive, forecast-driven roster is cheaper than a flat one.")
