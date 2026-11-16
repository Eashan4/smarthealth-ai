"""T15: Analysing the complexity of behavioural factors that influence weight in adults, Part 2 -- modelling.

Part 1 asked "which factors matter". Part 2 asks "how well can behaviour predict weight, and how complex is the relationship?"
  1. Leakage check: a classifier that is given Height and Weight "predicts" the class perfectly because the class IS a
     function of them. Behaviour-only models are the honest question.
  2. Linear vs non-linear: OLS vs random forest vs gradient boosting on BMI (5-fold CV R^2) and on the 7 weight classes
     (accuracy, macro-F1, and within-one-class accuracy, since classes are ordered).
  3. Is the gap complexity? Give the linear model the two things it cannot see on its own (snacking is non-monotone, diet x
     activity interact) and see how much of the gap closes.
  4. What drives predictions: permutation importance on held-out data, partial dependence of the top factors.
  5. Behaviour phenotypes: cluster people on behaviours alone (k-means) and compare their weight outcomes.
Data: synthetic (weight_data.py).  Run: python t15_behavioral_factors_part2.py  (after t14 has written the data; it will
regenerate it otherwise)
Output: outputs/t15_models.png, outputs/t15_importance.png, outputs/t15_partial_dependence.png, outputs/t15_phenotypes.png,
        outputs/t15_results.json
"""

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from weight_data import CLASSES, NOISE_SD, make_weight_data

warnings.filterwarnings("ignore", category=RuntimeWarning)
OUT = Path(__file__).parent / "outputs"
CAT = ["CAEC", "CALC", "MTRANS", "Gender"]
NUM = ["Age", "family_history", "FAVC", "FCVC", "NCP", "SMOKE", "CH2O", "SCC", "FAF", "TUE"]
BEHAV = NUM + CAT


def prep(extra_num=()):
    return ColumnTransformer([("num", StandardScaler(), NUM + list(extra_num)), ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])


if __name__ == "__main__":
    d = make_weight_data()
    y_bmi, y_cls = d.BMI.values, d.Class.cat.codes.values
    kf, skf = KFold(5, shuffle=True, random_state=0), StratifiedKFold(5, shuffle=True, random_state=0)
    print(f"{len(d)} adults (synthetic); 5-fold cross-validation throughout\n")

    # 1. leakage
    leak = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=50))
    acc_leak = cross_val_score(leak, d[["Height", "Weight"]], y_cls, cv=skf).mean()
    clf_b = make_pipeline(prep(), LogisticRegression(max_iter=3000))
    acc_beh = cross_val_score(clf_b, d[BEHAV], y_cls, cv=skf).mean()
    print(f"Leakage check: class from Height + Weight alone = {acc_leak:.3f} accuracy (the class is defined from them);")
    print(f"               class from behaviours only         = {acc_beh:.3f}  <- the honest number\n")

    # 2. models on BMI
    models = {"OLS (linear)": make_pipeline(prep(), LinearRegression()),
              "Random forest": make_pipeline(prep(), RandomForestRegressor(300, min_samples_leaf=5, random_state=0, n_jobs=-1)),
              "Gradient boosting": make_pipeline(prep(), GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0))}
    r2 = {}
    print(f"{'BMI regression':22s} {'CV R^2':>7s}")
    for k, m in models.items():
        r2[k] = float(cross_val_score(m, d[BEHAV], y_bmi, cv=kf, scoring="r2").mean())
        print(f"{k:22s} {r2[k]:7.3f}")

    # 3. is the gap complexity?
    d2 = d.assign(caec_sometimes=(d.CAEC == "Sometimes").astype(int), favc_x_inactive=((d.FAVC == 1) & (d.FAF == 0)).astype(int))
    lin_plus = make_pipeline(ColumnTransformer([("num", StandardScaler(), NUM + ["caec_sometimes", "favc_x_inactive"]),
                                                ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)]), LinearRegression())
    r2_plus = float(cross_val_score(lin_plus, d2[BEHAV + ["caec_sometimes", "favc_x_inactive"]], y_bmi, cv=kf, scoring="r2").mean())
    gap = max(r2["Random forest"], r2["Gradient boosting"]) - r2["OLS (linear)"]
    print(f"\nOLS + 'sometimes snacks' flag + 'high-calorie AND inactive' term: R^2 {r2_plus:.3f} "
          f"(closes {100 * (r2_plus - r2['OLS (linear)']) / gap if gap > 0 else 0:.0f}% of the linear-to-non-linear gap of {gap:.3f})")
    ceiling = 1 - NOISE_SD ** 2 / d.BMI.var()
    print(f"Ceiling: the planted noise has sd {NOISE_SD} BMI units, so no model can exceed R^2 of about {ceiling:.2f} on this data.")

    # classification of the 7 classes (behaviours only)
    cls = {"Logistic regression": make_pipeline(prep(), LogisticRegression(max_iter=3000)),
           "Random forest": make_pipeline(prep(), RandomForestClassifier(300, min_samples_leaf=3, random_state=0, n_jobs=-1))}
    cres = {}
    print(f"\n{'7-class classification':24s} {'accuracy':>9s} {'macro-F1':>9s} {'within 1 class':>15s}")
    for k, m in cls.items():
        p = cross_val_predict(m, d[BEHAV], y_cls, cv=skf)
        cres[k] = {"accuracy": float((p == y_cls).mean()), "macro_f1": float(f1_score(y_cls, p, average="macro")),
                   "within_one": float((np.abs(p - y_cls) <= 1).mean())}
        print(f"{k:24s} {cres[k]['accuracy']:9.3f} {cres[k]['macro_f1']:9.3f} {cres[k]['within_one']:15.3f}")
    print(f"Majority-class baseline accuracy: {np.bincount(y_cls).max() / len(y_cls):.3f}")

    # 4. importance and partial dependence (gradient boosting, held-out split)
    Xtr, Xte, ytr, yte = train_test_split(d[BEHAV], y_bmi, test_size=0.25, random_state=1)
    gb = make_pipeline(prep(), GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0)).fit(Xtr, ytr)
    pi = permutation_importance(gb, Xte, yte, n_repeats=20, random_state=0, scoring="r2")
    imp = pd.Series(pi.importances_mean, index=BEHAV).sort_values(ascending=False)
    print("\nPermutation importance (drop in held-out R^2 when a factor is shuffled):")
    for k, v in imp.head(6).items():
        print(f"  {k:15s} {v:.4f}")

    def pd_curve(col, values):
        out = []
        for v in values:
            X = Xte.copy(); X[col] = v
            out.append(gb.predict(X).mean())
        return np.array(out)
    pd_faf = pd_curve("FAF", [0, 1, 2, 3])
    pd_caec = pd_curve("CAEC", ["no", "Sometimes", "Frequently", "Always"])
    pd_age = pd_curve("Age", [18, 25, 32, 40, 50])
    print(f"Partial dependence, FAF 0->3: {np.round(pd_faf, 2)}  |  CAEC no/Sometimes/Frequently/Always: {np.round(pd_caec, 2)}")

    # 5. phenotypes
    Z = ColumnTransformer([("n", StandardScaler(), ["FAVC", "FCVC", "NCP", "CH2O", "SCC", "FAF", "TUE"]),
                           ("c", OneHotEncoder(), ["CAEC", "CALC", "MTRANS"])]).fit_transform(d)
    inertia = {k: KMeans(k, n_init=10, random_state=0).fit(Z).inertia_ for k in range(2, 9)}
    km = KMeans(4, n_init=10, random_state=0).fit(Z)
    d["cluster"] = km.labels_
    prof = d.groupby("cluster").agg(n=("BMI", "size"), BMI=("BMI", "mean"), obese_pct=("BMI", lambda s: (s >= 30).mean() * 100),
                                    FAF=("FAF", "mean"), FAVC=("FAVC", "mean"), TUE=("TUE", "mean"), FCVC=("FCVC", "mean")).round(2).sort_values("BMI")
    print("\nBehaviour phenotypes (k-means, 4 clusters, behaviours only):")
    print(prof.to_string())

    # plots
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    names = list(r2) + ["OLS + 2 hand-made terms"]; vals = list(r2.values()) + [r2_plus]
    axs[0].bar(range(4), vals, color=["tab:gray", "tab:green", "tab:green", "tab:orange"]); axs[0].set_xticks(range(4))
    axs[0].set_xticklabels([n.replace(" ", "\n", 1) for n in names], fontsize=8); axs[0].set_ylabel("CV R^2 on BMI"); axs[0].set_title("Linear vs non-linear")
    for i, v in enumerate(vals): axs[0].text(i, v + 0.005, f"{v:.2f}", ha="center", fontsize=8)
    axs[1].bar(["leaky\n(Height+Weight)", "behaviours\nonly"], [acc_leak, acc_beh], color=["tab:red", "tab:blue"]); axs[1].set_ylim(0, 1.05)
    axs[1].set_ylabel("7-class accuracy"); axs[1].set_title("Leakage check")
    for i, v in enumerate([acc_leak, acc_beh]): axs[1].text(i, v + 0.01, f"{v:.2f}", ha="center")
    fig.tight_layout(); fig.savefig(OUT / "t15_models.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.barh(imp.index[::-1][-10:], imp.values[::-1][-10:], color="tab:purple"); ax.set_xlabel("drop in held-out R^2"); ax.set_title("T15: what the model relies on")
    fig.tight_layout(); fig.savefig(OUT / "t15_importance.png", dpi=130); plt.close(fig)

    fig, axs = plt.subplots(1, 3, figsize=(12, 3.6))
    axs[0].plot([0, 1, 2, 3], pd_faf, "o-"); axs[0].set_title("Physical activity (FAF)"); axs[0].set_ylabel("predicted BMI")
    axs[1].plot(["no", "Sometimes", "Frequently", "Always"], pd_caec, "o-", color="tab:red"); axs[1].set_title("Snacking (CAEC): non-monotone"); axs[1].tick_params(axis="x", labelsize=7)
    axs[2].plot([18, 25, 32, 40, 50], pd_age, "o-", color="tab:green"); axs[2].set_title("Age")
    fig.tight_layout(); fig.savefig(OUT / "t15_partial_dependence.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.bar([f"P{i + 1}\n(n={int(r.n)})" for i, (_, r) in enumerate(prof.iterrows())], prof.BMI, color="tab:blue")
    for i, (_, r) in enumerate(prof.iterrows()): ax.text(i, r.BMI + 0.2, f"{r.obese_pct:.0f}% obese", ha="center", fontsize=8)
    ax.set_ylabel("mean BMI"); ax.set_title("Four behaviour phenotypes"); ax.set_ylim(20, prof.BMI.max() + 2)
    fig.tight_layout(); fig.savefig(OUT / "t15_phenotypes.png", dpi=130); plt.close(fig)

    (OUT / "t15_results.json").write_text(json.dumps({
        "acc_leaky": float(acc_leak), "acc_behaviour_only": float(acc_beh), "r2": r2, "r2_ols_plus_terms": r2_plus, "classification": cres,
        "majority_baseline": float(np.bincount(y_cls).max() / len(y_cls)), "importance": imp.round(4).to_dict(),
        "pd_faf": pd_faf.round(2).tolist(), "pd_caec": pd_caec.round(2).tolist(), "phenotypes": json.loads(prof.reset_index().to_json(orient="records"))}, indent=1))

    assert acc_leak > 0.95 > acc_beh, "Height+Weight must leak the label; behaviours alone must not"
    assert max(r2["Random forest"], r2["Gradient boosting"]) > r2["OLS (linear)"], "non-linear models should beat OLS here"
    assert r2_plus > r2["OLS (linear)"]
    assert prof.BMI.iloc[-1] - prof.BMI.iloc[0] > 2
    print("\nSelf-check passed: leakage demonstrated, non-linearity found and partly recovered by hand, phenotypes separate on BMI.")
