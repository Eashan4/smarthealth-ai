"""T9: Using healthcare data for informed strategic planning, Part 2 -- where are we heading and what should we do?

Predictive: per service line, fit log(monthly admissions) = trend + seasonality, project 2025-2029 with an 80%
  interval on the trend, and convert admissions to beds needed at the 85% occupancy planners aim for.
Prescriptive: when demand exceeds the beds the hospital has, solve a linear programme for the admissions mix that
  maximises margin, compare it with cutting every line equally, and price one extra bed with the LP's shadow price.

Assumptions (stated, not hidden): 420 licensed beds, 85% planning occupancy, no line is cut below 80% of its demand
(community obligation), margin per admission held at its 2024 level. All data is synthetic (see hospital_data.py).

Run: python t9_strategic_planning_predictive.py
Output: outputs/t9_projection.png, outputs/t9_allocation.png, outputs/t9_bed_value.png, outputs/t9_results.json
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linprog

from hospital_data import encounters

OUT = Path(__file__).parent / "outputs"
BEDS, TARGET_OCC, MIN_SERVE = 420, 0.85, 0.80
PLAN_YEAR = 2027
YEARS = list(range(2025, 2030))


def fit_trend(counts):
    """OLS of log(monthly admissions) on [1, t, sin, cos]; returns annual growth rate and its standard error."""
    t = np.arange(len(counts))
    X = np.column_stack([np.ones_like(t), t / 12.0, np.sin(2 * np.pi * t / 12), np.cos(2 * np.pi * t / 12)])
    y = np.log(counts)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    sigma2 = resid @ resid / (len(y) - X.shape[1])
    cov = sigma2 * np.linalg.inv(X.T @ X)
    return beta[1], float(np.sqrt(cov[1, 1]))      # slope per year in log units


def beds_needed(admissions, alos):
    return float(np.sum(np.asarray(admissions) * np.asarray(alos)) / (365 * TARGET_OCC))


def allocate(demand, alos, margin, beds):
    """max sum(margin*x)  s.t.  sum(alos*x) <= beds*365*occ,  MIN_SERVE*demand <= x <= demand."""
    cap = beds * 365 * TARGET_OCC
    res = linprog(-margin, A_ub=[alos], b_ub=[cap], bounds=list(zip(MIN_SERVE * demand, demand)), method="highs")
    return res.x, float(-res.fun), float(-res.ineqlin.marginals[0])     # allocation, total margin, shadow price / bed-day


if __name__ == "__main__":
    e = encounters()
    lines = sorted(e.service_line.unique())
    monthly = e.assign(m=e.admit_date.dt.to_period("M")).groupby(["service_line", "m"]).size().unstack(0)
    last = e[e.year == 2024].groupby("service_line")
    adm24, alos = last.size()[lines].values, last.los_days.mean()[lines].values
    margin = ((last.revenue.sum() - last.cost.sum()) / last.size())[lines].values       # margin per admission

    growth = {}
    for s in lines:
        g, se = fit_trend(monthly[s].values)
        growth[s] = (g, se)
    print(f"{'service line':16s} {'trend %/yr':>10s} {'80% interval':>16s}")
    for s in lines:
        g, se = growth[s]
        print(f"{s:16s} {100*g:10.1f} {100*(g-1.28*se):7.1f} .. {100*(g+1.28*se):5.1f}")

    # -- projection: beds needed under three scenarios ---------------------------------------------------------
    scen = {"low": -1.28, "base": 0.0, "high": 1.28}
    proj = {k: [] for k in scen}
    demand_by_year = {}
    for k, z in scen.items():
        for y in YEARS:
            adm = np.array([adm24[i] * np.exp((growth[s][0] + z * growth[s][1]) * (y - 2024)) for i, s in enumerate(lines)])
            proj[k].append(beds_needed(adm, alos))
            if k == "base":
                demand_by_year[y] = adm
    print(f"\nBeds needed at {TARGET_OCC:.0%} occupancy (licensed: {BEDS}); 2024 actual = {beds_needed(adm24, alos):.0f}")
    print(f"{'year':6s}" + "".join(f"{k:>8s}" for k in scen))
    for i, y in enumerate(YEARS):
        print(f"{y:<6d}" + "".join(f"{proj[k][i]:8.0f}" for k in scen))
    first_short = next((y for i, y in enumerate(YEARS) if proj["base"][i] > BEDS), None)
    print(f"Base case first exceeds {BEDS} beds in: {first_short}")

    # -- prescriptive ------------------------------------------------------------------------------------------
    demand = demand_by_year[PLAN_YEAR]
    x, best, shadow = allocate(demand, alos, margin, BEDS)
    cap = BEDS * 365 * TARGET_OCC
    scale = cap / float(demand @ alos)
    prop = demand * scale                                           # cut every line by the same factor
    prop_margin = float(margin @ prop)
    full_margin = float(margin @ demand)
    print(f"\n{PLAN_YEAR} base demand needs {beds_needed(demand, alos):.0f} beds; capacity supports {BEDS}.")
    print(f"{'service line':16s} {'demand':>8s} {'LP admits':>10s} {'cut %':>7s} {'margin/adm':>11s}")
    for i, s in enumerate(lines):
        print(f"{s:16s} {demand[i]:8.0f} {x[i]:10.0f} {100*(1-x[i]/demand[i]):7.1f} {margin[i]:11.0f}")
    print(f"\nMargin if every line were fully served (not possible): {full_margin/1e6:8.1f} M")
    print(f"Margin, equal cut across lines:                         {prop_margin/1e6:8.1f} M")
    print(f"Margin, LP optimal mix:                                 {best/1e6:8.1f} M  (+{(best-prop_margin)/1e6:.1f} M)")
    print(f"Shadow price of one bed-day: {shadow:,.0f} per bed-day  ->  one extra bed is worth about {shadow*365*TARGET_OCC/1e3:,.0f} k per year")

    beds_grid = np.arange(BEDS, BEDS + 121, 10)
    value = [allocate(demand, alos, margin, b)[1] / 1e6 for b in beds_grid]

    # -- plots -------------------------------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.5))
    xs = [2024] + YEARS
    base0 = beds_needed(adm24, alos)
    ax.fill_between(xs, [base0] + proj["low"], [base0] + proj["high"], color="tab:blue", alpha=0.2, label="80% scenario band")
    ax.plot(xs, [base0] + proj["base"], "o-", color="tab:blue", label="base case")
    ax.axhline(BEDS, color="tab:red", ls="--", label=f"{BEDS} licensed beds")
    ax.set_ylabel(f"Beds needed at {TARGET_OCC:.0%} occupancy"); ax.set_title("T9: bed demand projection"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "t9_projection.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    idx = np.arange(len(lines)); w = 0.38
    ax.bar(idx - w / 2, demand, w, label=f"{PLAN_YEAR} demand", color="lightgray", edgecolor="k")
    ax.bar(idx + w / 2, x, w, label="LP allocation", color="tab:green")
    ax.set_xticks(idx); ax.set_xticklabels(lines, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Admissions"); ax.set_title(f"Who gets the beds when capacity binds ({PLAN_YEAR})"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT / "t9_allocation.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(beds_grid, value, "o-", color="tab:purple")
    ax.set_xlabel("Licensed beds"); ax.set_ylabel("Optimal margin (M)"); ax.set_title("Value of adding beds (diminishing as demand is met)")
    fig.tight_layout(); fig.savefig(OUT / "t9_bed_value.png", dpi=130); plt.close(fig)

    res = {"beds": BEDS, "target_occupancy": TARGET_OCC, "plan_year": PLAN_YEAR,
           "growth_pct": {s: round(100 * growth[s][0], 2) for s in lines},
           "beds_needed": {k: [round(v) for v in vals] for k, vals in proj.items()}, "years": YEARS,
           "first_year_short_base": first_short, "beds_2024": round(beds_needed(adm24, alos)),
           "margin_full_m": full_margin / 1e6, "margin_equal_cut_m": prop_margin / 1e6, "margin_lp_m": best / 1e6,
           "lp_gain_m": (best - prop_margin) / 1e6, "shadow_price_per_bed_day": shadow,
           "lp_cut_pct": {s: round(100 * (1 - x[i] / demand[i]), 1) for i, s in enumerate(lines)}}
    (OUT / "t9_results.json").write_text(json.dumps(res, indent=1))

    assert best >= prop_margin - 1e-6, "LP optimum cannot be worse than a feasible equal cut"
    assert float(alos @ x) <= cap * (1 + 1e-9), "allocation must respect bed capacity"
    assert (x >= MIN_SERVE * demand - 1e-6).all() and (x <= demand + 1e-6).all()
    print("\nSelf-check passed: LP respects capacity and service floors and beats the equal-cut policy.")
