"""T12: Ranking and word-sense disambiguation of clinical text.

Ranking:  retrieve the notes about a given diagnosis. TF-IDF cosine vs BM25 (written out, ~15 lines) vs a random
  baseline, scored with precision@10, mean average precision and nDCG@10. Then TextRank (PageRank over a word
  co-occurrence graph) ranks the key terms inside one note.
Word-sense disambiguation (WSD): clinical abbreviations are ambiguous ("RA" = rheumatoid arthritis or right atrium).
  Three methods pick the sense from context: most-frequent-sense baseline, simplified Lesk (overlap with a sense
  gloss) and a Naive Bayes context classifier.

Data: notes_data.py for ranking, a small context generator below for WSD (synthetic).
Run: python t12_ranking_disambiguation.py
Output: outputs/t12_ranking.png, outputs/t12_wsd.png, outputs/t12_textrank.txt, outputs/t12_results.json
"""

import json
import math
import random
import re
import warnings
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.model_selection import cross_val_score
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline

from notes_data import SPECIALTIES, generate_notes

warnings.filterwarnings("ignore", category=RuntimeWarning)
OUT = Path(__file__).parent / "outputs"
STOP = set("a an the and of for on in with at to is was by or no not as are this that".split())
tok = lambda t: [w for w in re.findall(r"[a-z0-9\-]+", t.lower()) if w not in STOP]


# ----------------------------------------------------------------- ranking --------------------------------------
class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs])
        self.avg = self.len.mean()
        df = Counter(w for d in docs for w in set(d))
        n = len(docs)
        self.idf = {w: math.log((n - c + 0.5) / (c + 0.5) + 1) for w, c in df.items()}

    def score(self, query):
        s = np.zeros(len(self.docs))
        for w in query:
            if w not in self.idf: continue
            f = np.array([t.get(w, 0) for t in self.tf])
            s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len / self.avg))
        return s


def metrics(order, rel, k=10):
    hits = rel[order]
    p_at_k = hits[:k].mean()
    ap = (np.cumsum(hits) / (np.arange(len(hits)) + 1) * hits).sum() / max(hits.sum(), 1)
    dcg = (hits[:k] / np.log2(np.arange(2, k + 2))).sum()
    idcg = (np.sort(rel)[::-1][:k] / np.log2(np.arange(2, k + 2))).sum()
    return p_at_k, ap, dcg / idcg


NOTE_BOILERPLATE = set("presents known case denies year-old days weeks months hours review referred further investigation prescribed "
                       "started continue also history examination pulse mmhg mg mcg daily twice three times every night morning "
                       "advised lifestyle changes follow-up clinic repeat bloods next visit patient counselled adherence admit "
                       "observation chronic illness regular takes".split())


def textrank(text, top=6, window=4, d=0.85):
    words = [w for w in tok(text) if w.isalpha() and len(w) > 3 and w not in NOTE_BOILERPLATE]
    vocab = sorted(set(words))
    idx = {w: i for i, w in enumerate(vocab)}
    A = np.zeros((len(vocab), len(vocab)))
    for i, w in enumerate(words):
        for v in words[i + 1:i + window]:
            if v != w: A[idx[w], idx[v]] = A[idx[v], idx[w]] = 1
    A = A / np.maximum(A.sum(axis=0, keepdims=True), 1)
    r = np.ones(len(vocab)) / len(vocab)
    for _ in range(50):
        r = (1 - d) / len(vocab) + d * A @ r
    return [vocab[i] for i in np.argsort(r)[::-1][:top]]


# ------------------------------------------------------------------- WSD ----------------------------------------
SENSES = {   # term -> {sense: (gloss, cue words)}
    "RA": {"rheumatoid arthritis": ("autoimmune joint disease swelling stiffness methotrexate",
                                     "joint swelling morning stiffness methotrexate dmard synovitis hands antibodies flare".split()),
           "right atrium": ("upper right chamber of the heart echo",
                            "echo enlarged ventricle pressure catheter atrial valve tricuspid thrombus".split())},
    "MS": {"multiple sclerosis": ("demyelinating disease of the brain relapse mri",
                                   "relapse mri lesions optic neuritis demyelination weakness interferon".split()),
           "mitral stenosis": ("narrowing of the mitral valve murmur",
                                "murmur valve rheumatic diastolic echo atrial fibrillation gradient".split())},
    "PT": {"physical therapy": ("exercise rehabilitation mobility training",
                                 "exercise rehabilitation mobility gait strengthening walking sessions".split()),
           "prothrombin time": ("blood clotting test inr",
                                 "inr warfarin bleeding coagulation prolonged anticoagulant monitoring".split())},
    "cold": {"common cold": ("viral infection of the nose and throat",
                              "rhinorrhoea sore throat cough congestion sneezing viral".split()),
             "cold extremities": ("low temperature sensation in the limbs",
                                   "extremities pale peripheral perfusion fingers intolerance raynaud".split())},
    "discharge": {"hospital discharge": ("patient leaves hospital to go home",
                                          "home follow-up summary planned medication advised ward".split()),
                  "wound discharge": ("fluid draining from a wound",
                                       "purulent wound swab drainage dressing odour redness".split())},
}
GENERIC = "patient noted reports review today clinic history examination stable mild recent seen".split()


def wsd_data(n_per_sense=120, seed=5):
    rng, X, y, terms = random.Random(seed), [], [], []
    for term, senses in SENSES.items():
        for si, (sense, (_, cues)) in enumerate(senses.items()):
            for _ in range(n_per_sense):
                other = [c for s2, (_, c2) in senses.items() if s2 != sense for c in c2]
                ctx = rng.sample(cues, 2) + rng.sample(GENERIC, 3) + (rng.sample(other, 1) if rng.random() < 0.3 else [])
                rng.shuffle(ctx); ctx.insert(rng.randint(0, len(ctx)), term)
                X.append(" ".join(ctx)); y.append(f"{term}:{sense}"); terms.append(term)
    return X, y, terms


def lesk(text, term):
    ctx = set(tok(text)) - {term.lower()}
    best = max(SENSES[term], key=lambda s: len(ctx & set(tok(SENSES[term][s][0]))))
    return f"{term}:{best}"


if __name__ == "__main__":
    # ---------------- ranking
    notes = generate_notes(2000, seed=20)
    docs_txt = [n.text for n in notes]
    docs = [tok(t) for t in docs_txt]
    conds = sorted({n.condition for n in notes})
    queries = [(c, tok(c)) for c in conds]
    tfidf = TfidfVectorizer(tokenizer=tok, lowercase=False, token_pattern=None, sublinear_tf=True)
    M = tfidf.fit_transform(docs_txt)
    bm = BM25(docs)
    rng = np.random.default_rng(0)
    res = {m: [] for m in ("random", "TF-IDF cosine", "BM25")}
    for c, q in queries:
        rel = np.array([(n.condition == c) and n.condition_mentioned for n in notes], dtype=float)   # must actually name it
        if rel.sum() < 10: continue
        scores = {"random": rng.random(len(notes)),
                  "TF-IDF cosine": (M @ tfidf.transform([c]).T).toarray().ravel(), "BM25": bm.score(q)}
        for m, s in scores.items():
            res[m].append(metrics(np.argsort(-s, kind="stable"), rel))
    summary = {m: dict(zip(("P@10", "MAP", "nDCG@10"), np.mean(v, axis=0).round(3).tolist())) for m, v in res.items()}
    print(f"Ranking: {len(res['BM25'])} diagnosis queries over {len(notes)} notes (relevant = note names that diagnosis)")
    print(f"{'method':16s} {'P@10':>7s} {'MAP':>7s} {'nDCG@10':>8s}")
    for m, v in summary.items():
        print(f"{m:16s} {v['P@10']:7.3f} {v['MAP']:7.3f} {v['nDCG@10']:8.3f}")

    # one multi-term query where the two methods can differ
    ex_q = "chest pain atrial fibrillation"
    top = np.argsort(-bm.score(tok(ex_q)))[:3]
    print(f"\nTop BM25 hit for '{ex_q}':\n  {docs_txt[top[0]]}")
    tr = textrank(docs_txt[0])
    print(f"\nTextRank key terms of note 0: {tr}")
    (OUT / "t12_textrank.txt").write_text(docs_txt[0] + "\n\nTextRank: " + ", ".join(tr))

    # ---------------- WSD
    X, y, terms = wsd_data()
    maj = Counter(y)
    ysplit = np.array(y)
    acc = {}
    acc["most frequent sense"] = float(np.mean([max((l for l in maj if l.startswith(t + ":")), key=maj.get) == lab for t, lab in zip(terms, y)]))
    acc["simplified Lesk"] = float(np.mean([lesk(x, t) == lab for x, t, lab in zip(X, terms, y)]))
    cv_scores = []
    per_term = {}
    for t in SENSES:
        m = [i for i, tt in enumerate(terms) if tt == t]
        pipe = make_pipeline(CountVectorizer(binary=True), MultinomialNB(alpha=0.5))
        sc = cross_val_score(pipe, [X[i] for i in m], ysplit[m], cv=5)
        per_term[t] = {"lesk": float(np.mean([lesk(X[i], t) == y[i] for i in m])), "nb": float(sc.mean())}
        cv_scores.append(sc.mean())
    acc["Naive Bayes (5-fold CV)"] = float(np.mean(cv_scores))
    print(f"\nWSD over {len(SENSES)} ambiguous terms, {len(X)} contexts")
    for k, v in acc.items():
        print(f"  {k:26s} {v:.3f}")
    print("  per term (Lesk / NB): " + ", ".join(f"{t} {v['lesk']:.2f}/{v['nb']:.2f}" for t, v in per_term.items()))
    ex = "joint swelling and morning stiffness, RA flare, methotrexate continued"
    print(f"  e.g. '{ex}' -> {lesk(ex, 'RA')}")

    # ---------------- plots
    fig, ax = plt.subplots(figsize=(7, 4)); w = 0.26
    for i, (m, v) in enumerate(summary.items()):
        ax.bar(np.arange(3) + (i - 1) * w, list(v.values()), w, label=m)
    ax.set_xticks(range(3)); ax.set_xticklabels(["P@10", "MAP", "nDCG@10"]); ax.legend(); ax.set_ylim(0, 1.05)
    ax.set_title("T12: ranking notes by diagnosis"); fig.tight_layout(); fig.savefig(OUT / "t12_ranking.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(range(len(acc)), list(acc.values()), color=["tab:gray", "tab:orange", "tab:green"])
    ax.set_xticks(range(len(acc))); ax.set_xticklabels([k.replace(" (", "\n(") for k in acc], fontsize=8); ax.set_ylim(0, 1.05)
    for i, v in enumerate(acc.values()): ax.text(i, v + 0.01, f"{v:.2f}", ha="center")
    ax.set_title("Word-sense disambiguation accuracy"); fig.tight_layout(); fig.savefig(OUT / "t12_wsd.png", dpi=130); plt.close(fig)

    (OUT / "t12_results.json").write_text(json.dumps({"ranking": summary, "wsd": acc, "wsd_per_term": per_term, "n_queries": len(res["BM25"]),
                                                    "textrank_note0": tr}, indent=1))
    assert summary["BM25"]["MAP"] > summary["random"]["MAP"] * 3
    assert acc["Naive Bayes (5-fold CV)"] > acc["most frequent sense"] + 0.3
    print("\nSelf-check passed: BM25 far above random; context-aware WSD far above the most-frequent-sense baseline.")
