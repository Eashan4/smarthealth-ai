"""T13: Dimensionality reduction for exploratory data analysis in daily medical research.

Data: the Wisconsin diagnostic breast-cancer dataset that ships with scikit-learn (REAL measurements, 569 patients,
30 numeric features computed from fine-needle-aspirate images, benign vs malignant).
  1. Why reduce: 30 features, many near-duplicates (radius/perimeter/area) -> count highly correlated pairs.
  2. PCA: scree and cumulative variance, how many components keep 90% / 95%, what PC1 is made of.
  3. Four 2-D maps (PCA, LDA, t-SNE, Isomap) compared with the same yardsticks: how well benign and malignant
     separate (5-NN accuracy, silhouette) and how faithfully local neighbourhoods are preserved (trustworthiness).
  4. Does reduction cost accuracy? Logistic regression on the first k principal components, k = 1..30.
Run: python t13_dimensionality_reduction.py
Output: outputs/t13_scree.png, outputs/t13_embeddings.png, outputs/t13_pc_accuracy.png, outputs/t13_loadings.png,
        outputs/t13_results.json
"""

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.manifold import TSNE, Isomap, trustworthiness
from sklearn.metrics import silhouette_score
from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=RuntimeWarning)
OUT = Path(__file__).parent / "outputs"

if __name__ == "__main__":
    data = load_breast_cancer()
    X, y, names = data.data, data.target, np.array(data.feature_names)
    Z = StandardScaler().fit_transform(X)
    print(f"{X.shape[0]} patients x {X.shape[1]} features; {int((y == 0).sum())} malignant, {int((y == 1).sum())} benign\n")

    # 1. redundancy
    r = np.corrcoef(Z.T)
    iu = np.triu_indices_from(r, 1)
    n_pairs, n_high = len(iu[0]), int((np.abs(r[iu]) > 0.9).sum())
    print(f"Redundancy: {n_high} of {n_pairs} feature pairs have |r| > 0.9 (e.g. radius vs perimeter r = {r[0, 2]:.3f})")

    # 2. PCA
    pca = PCA().fit(Z)
    cum = np.cumsum(pca.explained_variance_ratio_)
    k90, k95 = int(np.searchsorted(cum, 0.90) + 1), int(np.searchsorted(cum, 0.95) + 1)
    print(f"PCA: PC1 {pca.explained_variance_ratio_[0]:.1%}, PC2 {pca.explained_variance_ratio_[1]:.1%}; "
          f"{k90} components keep 90% of the variance, {k95} keep 95% (from 30)")
    load = pca.components_[0]
    top = np.argsort(-np.abs(load))[:5]
    print("PC1 is made of: " + ", ".join(f"{names[i]} ({load[i]:+.2f})" for i in top))

    # 3. embeddings
    emb = {"PCA": PCA(2, random_state=0).fit_transform(Z),
           "LDA (supervised)": LinearDiscriminantAnalysis(n_components=1).fit_transform(Z, y),
           "t-SNE": TSNE(2, perplexity=30, random_state=0, init="pca").fit_transform(Z),
           "Isomap": Isomap(n_neighbors=10, n_components=2).fit_transform(Z)}
    emb["LDA (supervised)"] = np.column_stack([emb["LDA (supervised)"][:, 0], np.zeros(len(y))])        # LDA of 2 classes has 1 axis
    scores = {}
    print(f"\n{'method':18s} {'5-NN acc':>9s} {'silhouette':>11s} {'trustworthiness':>16s}")
    for name, E in emb.items():
        knn = cross_val_score(KNeighborsClassifier(5), E, y, cv=5).mean()
        sil = silhouette_score(E, y)
        tw = trustworthiness(Z, E, n_neighbors=10)
        scores[name] = {"knn_acc": float(knn), "silhouette": float(sil), "trustworthiness": float(tw)}
        print(f"{name:18s} {knn:9.3f} {sil:11.3f} {tw:16.3f}")
    print("(LDA uses the labels, so its separation is an upper bound, not a fair unsupervised score; "
          "t-SNE/Isomap kNN scores are descriptive: the embedding was fit on all points.)")

    # 4. accuracy vs number of components (reduction fit inside each CV fold: no leakage)
    ks = [1, 2, 3, 5, 7, 10, 15, 20, 30]
    acc = []
    for k in ks:
        pipe = make_pipeline(StandardScaler(), PCA(k, random_state=0), LogisticRegression(max_iter=2000))
        acc.append(float(cross_val_score(pipe, X, y, cv=5).mean()))
    full = float(cross_val_score(make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)), X, y, cv=5).mean())
    print(f"\nLogistic regression, 5-fold CV: all 30 features {full:.3f}")
    print("  " + "  ".join(f"k={k}: {a:.3f}" for k, a in zip(ks, acc)))

    # plots
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    axs[0].bar(range(1, 31), pca.explained_variance_ratio_ * 100, color="tab:blue"); axs[0].set_xlabel("component"); axs[0].set_ylabel("% variance"); axs[0].set_title("Scree plot")
    axs[1].plot(range(1, 31), cum * 100, "o-", ms=3); axs[1].axhline(90, color="gray", ls="--"); axs[1].axhline(95, color="gray", ls=":")
    axs[1].set_xlabel("components kept"); axs[1].set_ylabel("cumulative % variance"); axs[1].set_title(f"{k90} PCs = 90%, {k95} PCs = 95%")
    fig.tight_layout(); fig.savefig(OUT / "t13_scree.png", dpi=130); plt.close(fig)

    fig, axs = plt.subplots(1, 4, figsize=(15, 3.6))
    for ax, (name, E) in zip(axs, emb.items()):
        for lab, col, nm in ((0, "tab:red", "malignant"), (1, "tab:blue", "benign")):
            ax.scatter(E[y == lab, 0], E[y == lab, 1] + (np.random.default_rng(0).normal(0, 0.15, (y == lab).sum()) if name.startswith("LDA") else 0), s=8, c=col, alpha=0.6, label=nm)
        ax.set_title(f"{name}\nkNN {scores[name]['knn_acc']:.2f} | trust {scores[name]['trustworthiness']:.2f}", fontsize=9); ax.set_xticks([]); ax.set_yticks([])
    axs[0].legend(fontsize=7); fig.tight_layout(); fig.savefig(OUT / "t13_embeddings.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(ks, acc, "o-", label="first k PCs"); ax.axhline(full, color="k", ls="--", label="all 30 features")
    ax.set_xlabel("k principal components"); ax.set_ylabel("5-fold CV accuracy"); ax.set_ylim(0.85, 1); ax.legend(); ax.set_title("Reduction without losing accuracy")
    fig.tight_layout(); fig.savefig(OUT / "t13_pc_accuracy.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    o = np.argsort(-np.abs(load))[:10][::-1]
    ax.barh(names[o], load[o], color="tab:purple"); ax.set_title("PC1 loadings (top 10): concavity + compactness drive it")
    fig.tight_layout(); fig.savefig(OUT / "t13_loadings.png", dpi=130); plt.close(fig)

    (OUT / "t13_results.json").write_text(json.dumps({"n": int(len(y)), "features": 30, "corr_pairs_gt_0.9": n_high, "pairs": n_pairs,
                                                    "pc1_var": float(pca.explained_variance_ratio_[0]), "pc2_var": float(pca.explained_variance_ratio_[1]),
                                                    "k90": k90, "k95": k95, "embeddings": scores, "acc_ks": ks, "acc": acc, "acc_full": full}, indent=1))
    assert k90 < 10 and k95 < 12, "30 correlated features should compress into few components"
    assert acc[ks.index(10)] > full - 0.02, "10 components should be nearly as accurate as all 30"
    print("\nSelf-check passed: 30 features compress to ~7-10 components with no meaningful loss in accuracy.")
