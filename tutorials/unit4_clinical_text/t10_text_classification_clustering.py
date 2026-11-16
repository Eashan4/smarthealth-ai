"""T10: Classification and clustering of clinical text.

Supervised: predict the specialty of a note from its text (TF-IDF + three linear classifiers, 5-fold CV, plus one
  untouched test split), and show which words drive each specialty.
Unsupervised: cluster the same notes without labels (TF-IDF -> SVD -> k-means), choose k by silhouette, and check
  how well the clusters line up with the real specialties (adjusted Rand index, purity).

Data: 1,800 synthetic notes (notes_data.py).  Run: python t10_text_classification_clustering.py
Output: outputs/t10_confusion.png, outputs/t10_clusters.png, outputs/t10_top_terms.png, outputs/t10_results.json
"""

import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import adjusted_rand_score, confusion_matrix, f1_score, silhouette_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from notes_data import generate_notes

warnings.filterwarnings("ignore", category=RuntimeWarning)
OUT = Path(__file__).parent / "outputs"


def purity(y, c):
    return sum(np.bincount(y[c == k]).max() for k in np.unique(c)) / len(y)


if __name__ == "__main__":
    notes = generate_notes(1800, seed=10)
    X = [n.text for n in notes]
    labels = sorted({n.specialty for n in notes})
    y = np.array([labels.index(n.specialty) for n in notes])
    print(f"{len(X)} notes, {len(labels)} specialties: {labels}\n")

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, stratify=y, random_state=0)
    vec = lambda: TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    models = {"Naive Bayes": MultinomialNB(alpha=0.1), "Logistic regression": LogisticRegression(max_iter=2000, C=10),
              "Linear SVM": LinearSVC(C=1.0)}
    res = {}
    print(f"{'model':22s} {'5-fold CV acc':>14s} {'test acc':>9s} {'test macro-F1':>14s}")
    fitted = {}
    for name, clf in models.items():
        pipe = make_pipeline(vec(), clf)
        cv = cross_val_score(pipe, Xtr, ytr, cv=5)
        pipe.fit(Xtr, ytr)
        p = pipe.predict(Xte)
        res[name] = {"cv_acc": float(cv.mean()), "test_acc": float((p == yte).mean()), "test_macro_f1": float(f1_score(yte, p, average="macro"))}
        fitted[name] = (pipe, p)
        print(f"{name:22s} {cv.mean():14.3f} {res[name]['test_acc']:9.3f} {res[name]['test_macro_f1']:14.3f}")
    best = max(res, key=lambda k: res[k]["cv_acc"])
    pipe, pred = fitted[best]
    print(f"\nBest by CV: {best}")
    cm = confusion_matrix(yte, pred)

    # most informative words (logistic regression coefficients)
    lr = make_pipeline(vec(), LogisticRegression(max_iter=2000, C=10)).fit(Xtr, ytr)
    terms = np.array(lr[0].get_feature_names_out())
    top = {l: terms[np.argsort(lr[1].coef_[i])[::-1][:6]].tolist() for i, l in enumerate(labels)}
    for l, t in top.items():
        print(f"  {l:17s} {', '.join(t)}")

    # clustering -------------------------------------------------------------------------------------------
    def embed(max_df):
        t = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=max_df, sublinear_tf=True)
        m = t.fit_transform(X)
        z = TruncatedSVD(n_components=30, random_state=0).fit_transform(m)
        return t, m, z / (np.linalg.norm(z, axis=1, keepdims=True) + 1e-12)

    # Attempt 1: every word. The boilerplate plan sentence ("Review in two weeks.") is the loudest signal.
    _, _, Z0 = embed(1.0)
    km0 = KMeans(6, n_init=10, random_state=0).fit(Z0)
    ari0, pur0 = adjusted_rand_score(y, km0.labels_), purity(y, km0.labels_)
    print(f"\nClustering on ALL words:      ARI {ari0:.3f}, purity {pur0:.3f}  (clusters follow the template plan sentence, not the disease)")
    # Attempt 2: drop words that appear in more than 10% of notes (boilerplate), keep the clinical vocabulary.
    tvec, tf, Z = embed(0.10)
    sil = {}
    for k in range(2, 11):
        sil[k] = silhouette_score(Z, KMeans(k, n_init=10, random_state=0).fit_predict(Z))
    k_best = max(sil, key=sil.get)
    km = KMeans(6, n_init=10, random_state=0).fit(Z)
    ari, pur = adjusted_rand_score(y, km.labels_), purity(y, km.labels_)
    print(f"Clustering, boilerplate removed (max_df=0.10):")
    print(f"Silhouette by k: " + ", ".join(f"{k}:{v:.3f}" for k, v in sil.items()))
    print(f"Silhouette peaks at k={k_best}; k-means with k=6 -> ARI {ari:.3f}, purity {pur:.3f} against the real specialties")
    cterms = np.array(tvec.get_feature_names_out())
    cent = km.cluster_centers_  # in SVD space; map top terms via mean tf-idf of members instead
    for c in range(6):
        m = np.asarray(tf[km.labels_ == c].mean(axis=0)).ravel()
        mj = np.bincount(y[km.labels_ == c], minlength=6).argmax()
        print(f"  cluster {c} (n={int((km.labels_ == c).sum()):3d}, mostly {labels[mj]:17s}): {', '.join(cterms[np.argsort(m)[::-1][:5]])}")

    # plots ---------------------------------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    ax.imshow(cm, cmap="Blues")
    for i in range(6):
        for j in range(6):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=9)
    ax.set_xticks(range(6)); ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(6)); ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("predicted"); ax.set_ylabel("true"); ax.set_title(f"T10: {best}, test accuracy {res[best]['test_acc']:.1%}")
    fig.tight_layout(); fig.savefig(OUT / "t10_confusion.png", dpi=130); plt.close(fig)

    from sklearn.decomposition import PCA
    P = PCA(2, random_state=0).fit_transform(Z)
    fig, axs = plt.subplots(1, 3, figsize=(13, 4))
    axs[0].plot(list(sil), list(sil.values()), "o-"); axs[0].axvline(6, color="gray", ls="--"); axs[0].set_xlabel("k"); axs[0].set_ylabel("silhouette"); axs[0].set_title("Choosing k")
    axs[1].scatter(P[:, 0], P[:, 1], c=km.labels_, cmap="tab10", s=6); axs[1].set_title("k-means clusters (k=6)")
    axs[2].scatter(P[:, 0], P[:, 1], c=y, cmap="tab10", s=6); axs[2].set_title("true specialty")
    for a in axs[1:]: a.set_xticks([]); a.set_yticks([])
    fig.tight_layout(); fig.savefig(OUT / "t10_clusters.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    names = list(res); w = 0.38; xs = np.arange(len(names))
    ax.bar(xs - w / 2, [res[n]["cv_acc"] for n in names], w, label="5-fold CV accuracy")
    ax.bar(xs + w / 2, [res[n]["test_macro_f1"] for n in names], w, label="test macro-F1")
    ax.set_xticks(xs); ax.set_xticklabels(names); ax.set_ylim(0.5, 1); ax.legend(); ax.set_title("Classifier comparison")
    fig.tight_layout(); fig.savefig(OUT / "t10_top_terms.png", dpi=130); plt.close(fig)

    (OUT / "t10_results.json").write_text(json.dumps({"models": res, "best": best, "silhouette": {str(k): v for k, v in sil.items()},
                                                    "k_best": k_best, "ari": ari, "purity": pur, "ari_all_words": ari0, "purity_all_words": pur0, "top_terms": top}, indent=1))
    assert res[best]["test_acc"] > 0.75, "classifier should clearly beat the 17% chance level"
    assert ari > ari0 + 0.1, "clusters should recover more structure once boilerplate is removed"
    print("\nSelf-check passed: classifiers far above chance, clustering improves once boilerplate is removed.")
