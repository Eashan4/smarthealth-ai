"""T8: Using healthcare data for informed strategic planning, Part 1 -- where are we? (descriptive analytics)

From three years of inpatient encounters, build the service-line scorecard a planning committee starts from:
volume, bed-days, average length of stay, margin, growth, seasonality and bed occupancy, then place every service
line on a growth-vs-margin matrix to see which to grow, protect, fix or review.

Run: python t8_strategic_planning_descriptive.py
Output: outputs/t8_scorecard.csv, outputs/t8_matrix.png, outputs/t8_seasonality.png, outputs/t8_pareto.png,
        outputs/t8_results.json
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from hospital_data import encounters

OUT = Path(__file__).parent / "outputs"
LICENSED_BEDS = 420


def scorecard(e):
    g = e.groupby("service_line")
    s = pd.DataFrame({
        "admissions": g.size(),
        "bed_days": g.los_days.sum(),
        "alos": g.los_days.mean(),
        "revenue_m": g.revenue.sum() / 1e6,
        "cost_m": g.cost.sum() / 1e6,
    })
    s["margin_m"] = s.revenue_m - s.cost_m
    s["margin_pct"] = s.margin_m / s.revenue_m * 100
    s["margin_per_bed_day"] = s.margin_m * 1e6 / s.bed_days
    yr = e.groupby(["service_line", "year"]).size().unstack()
    s["cagr_pct"] = ((yr[2024] / yr[2022]) ** 0.5 - 1) * 100
    return s.sort_values("margin_per_bed_day", ascending=False)


def quadrant(row, g_med, m_med):
    hi_g, hi_m = row.cagr_pct >= g_med, row.margin_pct >= m_med
    return {(True, True): "GROW", (False, True): "PROTECT", (True, False): "FIX COST / PRICE", (False, False): "REVIEW"}[(hi_g, hi_m)]


if __name__ == "__main__":
    e = encounters()
    print(f"{len(e):,} encounters, {e.service_line.nunique()} service lines, {e.year.min()}-{e.year.max()}\n")

    s = scorecard(e)
    g_med, m_med = s.cagr_pct.median(), s.margin_pct.median()
    s["strategy"] = s.apply(quadrant, axis=1, g_med=g_med, m_med=m_med)
    pd.set_option("display.width", 160)
    print(s.round(2).to_string())
    s.round(3).to_csv(OUT / "t8_scorecard.csv")

    last = e[e.year == 2024]
    occ = last.los_days.sum() / (LICENSED_BEDS * 366) * 100        # 2024 is a leap year
    print(f"\n2024 occupancy against {LICENSED_BEDS} licensed beds: {occ:.1f}% (rule of thumb: plan around 85%)")

    month = e.groupby(["year", "month"]).los_days.sum().groupby("month").mean()
    peak, trough = month.idxmax(), month.idxmin()
    print(f"Bed-day demand peaks in month {peak} and bottoms out in month {trough} ({month.max() / month.min():.2f}x)")

    # -- plots -------------------------------------------------------------------------------------------------
    colors = {"GROW": "tab:green", "PROTECT": "tab:blue", "FIX COST / PRICE": "tab:orange", "REVIEW": "tab:red"}
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    for name, r in s.iterrows():
        ax.scatter(r.cagr_pct, r.margin_pct, s=r.bed_days / 25, color=colors[r.strategy], alpha=0.65, edgecolor="k")
        ax.annotate(name, (r.cagr_pct, r.margin_pct), ha="center", va="center", fontsize=8)
    ax.axvline(g_med, color="gray", ls="--", lw=0.8); ax.axhline(m_med, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("Admissions growth, % per year (2022-24)"); ax.set_ylabel("Margin, % of revenue")
    ax.set_title("T8: service-line matrix (bubble = bed-days)"); fig.tight_layout()
    fig.savefig(OUT / "t8_matrix.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar(month.index, month.values, color="tab:blue")
    ax.axhline(month.mean(), color="k", lw=0.8, ls="--")
    ax.set_xlabel("Month"); ax.set_ylabel("Bed-days (mean of 3 years)"); ax.set_title("Seasonality of bed demand")
    fig.tight_layout(); fig.savefig(OUT / "t8_seasonality.png", dpi=130); plt.close(fig)

    p = s.bed_days.sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar(range(len(p)), p.values / p.sum() * 100, color="tab:purple")
    ax.plot(range(len(p)), p.cumsum().values / p.sum() * 100, "ko-")
    ax.set_xticks(range(len(p))); ax.set_xticklabels(p.index, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("% of bed-days"); ax.set_title("Pareto: where the beds go")
    fig.tight_layout(); fig.savefig(OUT / "t8_pareto.png", dpi=130); plt.close(fig)

    res = {"encounters": int(len(e)), "occupancy_2024_pct": float(occ), "licensed_beds": LICENSED_BEDS,
           "top_margin_per_bed_day": s.index[0], "lowest_margin_per_bed_day": s.index[-1],
           "scorecard": json.loads(s.round(3).reset_index().to_json(orient="records")),
           "peak_month": int(peak), "trough_month": int(trough), "peak_to_trough": float(month.max() / month.min())}
    (OUT / "t8_results.json").write_text(json.dumps(res, indent=1))

    assert s.bed_days.sum() == e.los_days.sum()
    assert abs(s.admissions.sum() - len(e)) == 0
    print("\nSelf-check passed: scorecard totals reconcile with the raw encounter table.")
