"""T14: Analysing the complexity of behavioural factors that influence weight in adults, Part 1 -- exploration and inference.

Question: which everyday behaviours go with higher BMI, how strongly, and can we trust the pattern?
  1. Profile the data (distribution, class balance) and define classes from BMI cut-offs.
  2. One factor at a time: mean BMI by level, Kruskal-Wallis test, effect size (eta-squared) -> ranked.
  3. Many tests at once -> Benjamini-Hochberg correction so we do not celebrate false positives.
  4. Association with weight class for categorical factors: chi-square and Cramer's V.
  5. Are the factors independent of each other? Spearman correlations and variance inflation factors.
  6. Interaction: does the harm of high-calorie food depend on physical activity? (FAVC x FAF heat-map)
Data: synthetic (weight_data.py) -- see that file for the generating model.
Run: python t14_behavioral_factors_part1.py
Output: outputs/t14_bmi_distribution.png, outputs/t14_effect_sizes.png, outputs/t14_interaction.png,
        outputs/t14_correlation.png, outputs/t14_results.json, outputs/weight_data.csv
"""

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from weight_data import CLASSES, make_weight_data

warnings.filterwarnings("ignore", category=RuntimeWarning)
OUT = Path(__file__).parent / "outputs"
FACTORS = ["family_history", "FAVC", "FCVC", "NCP", "CAEC", "SMOKE", "CH2O", "SCC", "FAF", "TUE", "CALC", "MTRANS", "Gender"]
ORDINAL = ["FCVC", "NCP", "CH2O", "FAF", "TUE"]


def eta_squared(h, k, n):
    return max((h - k + 1) / (n - k), 0.0)


def cramers_v(a, b):
    ct = pd.crosstab(a, b)
    chi2, p, *_ = stats.chi2_contingency(ct)
    return float(np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))), float(p)


def bh(p):
    p = np.asarray(p); order = np.argsort(p); n = len(p)
    adj = np.empty(n); prev = 1.0
    for rank, i in zip(range(n, 0, -1), order[::-1]):
        prev = min(prev, p[i] * n / rank); adj[i] = prev
    return adj


def vif(df):
    X = df.values.astype(float); X = (X - X.mean(0)) / X.std(0)
    out = []
    for j in range(X.shape[1]):
        y, o = X[:, j], np.delete(X, j, axis=1)
        beta, *_ = np.linalg.lstsq(o, y, rcond=None)
        r2 = 1 - ((y - o @ beta) ** 2).sum() / (y ** 2).sum()
        out.append(1 / (1 - r2))
    return dict(zip(df.columns, np.round(out, 2)))


if __name__ == "__main__":
    d = make_weight_data()
    d.to_csv(OUT / "weight_data.csv", index=False)
    print(f"{len(d)} adults, age {int(d.Age.min())}-{int(d.Age.max())}, BMI mean {d.BMI.mean():.1f} (sd {d.BMI.std():.1f}); synthetic data\n")
    print("Weight class balance:")
    print((d.Class.value_counts().reindex(CLASSES) / len(d) * 100).round(1).to_string())

    # 2. one factor at a time
    rows = []
    for f in FACTORS:
        groups = [g.BMI.values for _, g in d.groupby(f)]
        h, p = stats.kruskal(*groups)
        rows.append({"factor": f, "levels": len(groups), "H": h, "p": p, "eta2": eta_squared(h, len(groups), len(d)),
                     "range_of_means": max(g.mean() for g in groups) - min(g.mean() for g in groups)})
    t = pd.DataFrame(rows)
    t["p_adj_BH"] = bh(t.p.values)
    t = t.sort_values("eta2", ascending=False).reset_index(drop=True)
    pd.set_option("display.width", 140)
    print("\nBMI by factor (Kruskal-Wallis, effect size eta-squared, BH-adjusted p):")
    print(t.assign(H=t.H.round(1), eta2=t.eta2.round(3), range_of_means=t.range_of_means.round(2), p=t.p.map("{:.1e}".format),
                   p_adj_BH=t.p_adj_BH.map("{:.1e}".format)).to_string(index=False))
    n_sig = int((t.p_adj_BH < 0.05).sum())
    print(f"{n_sig} of {len(t)} factors significant after correction")

    # 3. a closer look at one non-obvious factor
    print("\nMean BMI by snacking between meals (CAEC):")
    caec = d.groupby("CAEC").BMI.agg(["mean", "count"]).reindex(["no", "Sometimes", "Frequently", "Always"]).round(2)
    print(caec.to_string())

    # 4. categorical association with class
    print("\nAssociation with weight class (Cramer's V):")
    cv = {f: cramers_v(d[f], d.Class)[0] for f in ["CAEC", "CALC", "MTRANS", "FAVC", "family_history", "Gender"]}
    for f, v in sorted(cv.items(), key=lambda kv: -kv[1]):
        print(f"  {f:15s} V = {v:.3f}")

    # 5. correlations and collinearity
    num = d[ORDINAL + ["FAVC", "family_history", "SCC", "SMOKE", "Age", "BMI"]]
    corr = num.corr(method="spearman")
    vifs = vif(num.drop(columns="BMI"))
    print(f"\nSpearman correlation of each factor with BMI: " + ", ".join(f"{k} {v:+.2f}" for k, v in corr.BMI.drop("BMI").sort_values(key=abs, ascending=False).items()))
    print(f"Max variance inflation factor: {max(vifs.values()):.2f} (below 5 means factors are not collinear)")

    # 6. interaction
    pivot = d.pivot_table(index="FAF", columns="FAVC", values="BMI", aggfunc="mean").round(2)
    pivot.columns = ["low-calorie diet", "high-calorie food"]
    print("\nMean BMI: physical activity (FAF 0-3) x high-calorie food")
    print(pivot.to_string())
    gap = pivot["high-calorie food"] - pivot["low-calorie diet"]
    print(f"Gap from high-calorie food: {', '.join(f'FAF={i}: +{g:.2f}' for i, g in gap.items())}  -> the harm is largest when inactive")

    # plots -------------------------------------------------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    for g, c in (("Male", "tab:blue"), ("Female", "tab:red")):
        axs[0].hist(d[d.Gender == g].BMI, bins=30, alpha=0.55, label=g, color=c)
    for cut in (18.5, 25, 30, 35, 40): axs[0].axvline(cut, color="k", ls=":", lw=0.8)
    axs[0].set_xlabel("BMI"); axs[0].set_ylabel("people"); axs[0].legend(); axs[0].set_title("BMI distribution")
    cnt = d.Class.value_counts().reindex(CLASSES)
    axs[1].barh(CLASSES[::-1], cnt.values[::-1], color="tab:green"); axs[1].set_title("Weight classes")
    fig.tight_layout(); fig.savefig(OUT / "t14_bmi_distribution.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    tt = t.iloc[::-1]
    ax.barh(tt.factor, tt.eta2, color=["tab:red" if p < 0.05 else "lightgray" for p in tt.p_adj_BH])
    ax.set_xlabel("effect size (eta-squared)"); ax.set_title("T14: how much each factor explains BMI (red = significant after BH)")
    fig.tight_layout(); fig.savefig(OUT / "t14_effect_sizes.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 4))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto"); plt.colorbar(im, label="mean BMI")
    ax.set_xticks([0, 1]); ax.set_xticklabels(pivot.columns, fontsize=8); ax.set_yticks(range(4)); ax.set_yticklabels(pivot.index); ax.set_ylabel("physical activity (FAF)")
    for i in range(4):
        for j in range(2): ax.text(j, i, pivot.values[i, j], ha="center", va="center", fontsize=9)
    ax.set_title("Interaction: diet x activity"); fig.tight_layout(); fig.savefig(OUT / "t14_interaction.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.columns, fontsize=8); plt.colorbar(im)
    ax.set_title("Spearman correlation"); fig.tight_layout(); fig.savefig(OUT / "t14_correlation.png", dpi=130); plt.close(fig)

    (OUT / "t14_results.json").write_text(json.dumps({
        "n": len(d), "bmi_mean": float(d.BMI.mean()), "class_pct": (d.Class.value_counts().reindex(CLASSES) / len(d) * 100).round(1).to_dict(),
        "factors": json.loads(t.round(4).to_json(orient="records")), "n_significant": n_sig, "caec_means": caec["mean"].to_dict(),
        "cramers_v": cv, "max_vif": float(max(vifs.values())), "faf_gap": {int(i): float(g) for i, g in gap.items()}}, indent=1))

    top3 = set(t.factor[:5])
    assert {"FAF", "FAVC"} <= top3 or {"FAF", "CAEC"} <= top3, "the strongest planted effects should rank near the top"
    assert max(vifs.values()) < 5
    assert gap.iloc[0] > gap.iloc[-1], "interaction: high-calorie harm should be larger when inactive"
    print("\nSelf-check passed: planted effects recovered and ranked, multiple-testing handled, interaction visible.")
