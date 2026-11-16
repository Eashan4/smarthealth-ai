"""T11: Information extraction and entity recognition on clinical text.

Three extractors, all scored against the gold annotations that notes_data.py records by construction:
  1. Regex rules     -> dose, frequency, blood pressure, heart rate (v1, then v2 after reading v1's misses)
  2. Dictionary NER  -> DRUG / CONDITION / SYMPTOM by lexicon lookup (the lexicon knows only 5 of each specialty's 8 drugs)
  3. Learned tagger  -> BIO token classifier (logistic regression on word shape, suffix and context features)
Test notes contain drugs the lexicon and the training notes have never seen: that is where the methods differ.
A small NegEx-style rule then flags negated symptoms ("denies chest pain").

Run: python t11_information_extraction_ner.py
Output: outputs/t11_ner_scores.png, outputs/t11_example.txt, outputs/t11_results.json
"""

import json
import re
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

from notes_data import SPECIALTIES, generate_notes, known_unseen_drugs

warnings.filterwarnings("ignore", category=RuntimeWarning)
OUT = Path(__file__).parent / "outputs"
TOKEN = re.compile(r"\w+(?:[-/]\w+)*|[^\w\s]")


# ---------------------------------------------------------------- 1. regex ---------------------------------------
def regex_extract(text, v2):
    bp = re.search(r"\b(\d{2,3})\s*(?:/|over)\s*(\d{2,3})\b" if v2 else r"\b(\d{2,3})/(\d{2,3})\b", text)
    hr = re.search(r"\b(?:HR|pulse)\s*[:=]?\s*(\d{2,3})", text)
    dose = re.search(r"\b(\d+(?:\.\d+)?)\s*(mg|mcg)\b", text)
    freq = re.search(r"\b(once daily|twice daily|three times daily|every \d+ hours|at night|every morning)\b", text)
    return {"bp": (int(bp[1]), int(bp[2])) if bp else None, "hr": int(hr[1]) if hr else None,
            "dose": f"{dose[1]} {dose[2]}" if dose else None, "freq": freq[1] if freq else None}


def score_regex(notes, v2):
    hit = defaultdict(int)
    for n in notes:
        g = regex_extract(n.text, v2)
        for k in ("bp", "hr", "dose", "freq"):
            hit[k] += g[k] == n.facts[k]
    return {k: v / len(notes) for k, v in hit.items()}


# ------------------------------------------------------------ span utilities -------------------------------------
def tokenize(text):
    return [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)]


def bio_tags(text, ents):
    toks = tokenize(text)
    tags = ["O"] * len(toks)
    for a, b, typ, _ in ents:
        inside = [i for i, (_, s, e) in enumerate(toks) if s >= a and e <= b]
        for j, i in enumerate(inside):
            tags[i] = ("B-" if j == 0 else "I-") + typ
    return toks, tags


def spans_from_tags(toks, tags):
    out, cur = set(), None
    for (w, s, e), t in zip(toks, tags):
        if t.startswith("B-") or (t.startswith("I-") and (cur is None or cur[2] != t[2:])):
            if cur: out.add((cur[0], cur[1], cur[2]))
            cur = [s, e, t[2:]]
        elif t.startswith("I-"):
            cur[1] = e
        else:
            if cur: out.add((cur[0], cur[1], cur[2]))
            cur = None
    if cur: out.add((cur[0], cur[1], cur[2]))
    return out


# ------------------------------------------------------------ 2. dictionary --------------------------------------
def build_lexicon(known_drugs):
    lex = defaultdict(list)
    for sp, v in SPECIALTIES.items():
        for c in v["conditions"]: lex[c].append("CONDITION")
        for s in v["symptoms"]: lex[s].append("SYMPTOM")
    for sp, ds in known_drugs.items():
        for d in ds: lex[d].append("DRUG")
    return {k: v[0] for k, v in lex.items()}


def dictionary_ner(text, lexicon):
    low, out = text.lower(), set()
    for phrase in sorted(lexicon, key=len, reverse=True):                     # longest match first
        for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", low):
            if not any(m.start() < e and m.end() > s for s, e, _ in out):
                out.add((m.start(), m.end(), lexicon[phrase]))
    return out


# ------------------------------------------------------------ 3. learned tagger ----------------------------------
def shape(w):
    return re.sub(r"\d", "0", re.sub(r"[a-z]+", "a", re.sub(r"[A-Z]+", "A", w)))[:4]


def token_features(toks, i, lexicon):
    w = toks[i][0].lower()
    f = {"w": w, "suf3": w[-3:], "suf4": w[-4:], "pre3": w[:3], "shape": shape(toks[i][0]), "len": min(len(w), 12),
         "in_lex": lexicon.get(w, "-")}
    for off in (-2, -1, 1, 2):
        j = i + off
        f[f"w{off}"] = toks[j][0].lower() if 0 <= j < len(toks) else "<pad>"
    f["next_is_dose"] = bool(i + 1 < len(toks) and re.fullmatch(r"\d+", toks[i + 1][0]))
    return f


def featurize(notes, lexicon):
    rows, tags, owner = [], [], []
    for k, n in enumerate(notes):
        toks, t = bio_tags(n.text, n.entities)
        rows += [token_features(toks, i, lexicon) for i in range(len(toks))]
        tags += t
        owner += [k] * len(toks)
    return rows, tags, owner


def predict_spans(model, dv, notes, lexicon):
    out = []
    for n in notes:
        toks = tokenize(n.text)
        X = dv.transform([token_features(toks, i, lexicon) for i in range(len(toks))])
        out.append(spans_from_tags(toks, model.predict(X)))
    return out


# ------------------------------------------------------------ negation --------------------------------------------
NEG_TRIGGERS = ("denies", "no ", "without", "negative for")


def is_negated(text, start):
    left = text[max(0, start - 25):start].lower()
    sentence_left = left.split(".")[-1]
    return any(t in sentence_left for t in NEG_TRIGGERS)


if __name__ == "__main__":
    known, unseen = known_unseen_drugs()
    train = generate_notes(1500, seed=11, drug_pool=known)
    test = generate_notes(600, seed=12)                                        # every drug, incl. the held-out ones
    unseen_set = {d for v in unseen.values() for d in v}
    drug_mentions = [n.text[a:b] for n in test for a, b, t, _ in n.entities if t == "DRUG"]
    n_drug, n_unseen = len(drug_mentions), sum(d in unseen_set for d in drug_mentions)
    print(f"train {len(train)} notes (known drugs only); test {len(test)} notes; "
          f"{n_unseen} of {n_drug} test drug mentions are drugs never seen in training\n")

    # 1. regex
    v1, v2 = score_regex(test, False), score_regex(test, True)
    print("Regex extraction accuracy on test notes")
    print(f"  {'field':6s} {'v1':>7s} {'v2 (fixed)':>11s}")
    for k in v1:
        print(f"  {k:6s} {v1[k]:7.3f} {v2[k]:11.3f}")
    print("  v1 missed blood pressure written as '150 over 90'; v2 adds that pattern.\n")

    # 2 + 3. NER
    lexicon = build_lexicon(known)
    gold = [{(a, b, t) for a, b, t, _ in n.entities} for n in test]
    dict_pred = [dictionary_ner(n.text, lexicon) for n in test]
    rows, tags, _ = featurize(train, lexicon)
    dv = DictVectorizer()
    clf = LogisticRegression(max_iter=300, C=5.0).fit(dv.fit_transform(rows), tags)
    ml_pred = predict_spans(clf, dv, test, lexicon)

    # a second tagger that gets no dictionary feature at all: how much does it depend on the lexicon?
    rows_nl, _, _ = featurize(train, {})
    dv_nl = DictVectorizer()
    clf_nl = LogisticRegression(max_iter=300, C=5.0).fit(dv_nl.fit_transform(rows_nl), tags)
    ml_nl_pred = predict_spans(clf_nl, dv_nl, test, {})

    scores = {}
    print(f"{'method':26s} {'type':10s} {'P':>6s} {'R':>6s} {'F1':>6s}")
    for name, pred in (("dictionary", dict_pred), ("tagger (with lexicon)", ml_pred), ("tagger (no lexicon)", ml_nl_pred)):
        for typ in ("DRUG", "CONDITION", "SYMPTOM", None):
            tp = fp = fn = 0
            for g, p in zip(gold, pred):
                gg = {x for x in g if typ is None or x[2] == typ}
                pp = {x for x in p if typ is None or x[2] == typ}
                tp += len(gg & pp); fp += len(pp - gg); fn += len(gg - pp)
            pr, rc = tp / (tp + fp) if tp + fp else 0, tp / (tp + fn) if tp + fn else 0
            f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0
            scores[(name, typ or "ALL")] = (pr, rc, f1)
            print(f"{name:26s} {typ or 'ALL':10s} {pr:6.3f} {rc:6.3f} {f1:6.3f}")
        print()

    # drug recall split into seen / unseen
    def drug_recall(pred, which):
        tp = tot = 0
        for n, p in zip(test, pred):
            for a, b, t, _ in n.entities:
                if t == "DRUG" and ((n.text[a:b] in unseen_set) == (which == "unseen")):
                    tot += 1; tp += (a, b, "DRUG") in p
        return tp / tot if tot else 0
    recall_split = {nm: {w: drug_recall(pr_, w) for w in ("seen", "unseen")}
                    for nm, pr_ in (("dictionary", dict_pred), ("tagger (with lexicon)", ml_pred), ("tagger (no lexicon)", ml_nl_pred))}
    print("Drug recall, seen vs never-seen drug names")
    for nm, r in recall_split.items():
        print(f"  {nm:26s} seen {r['seen']:.3f}   unseen {r['unseen']:.3f}")

    # negation
    correct = total = 0
    for n in test:
        for a, b, t, neg in n.entities:
            if t == "SYMPTOM":
                total += 1; correct += is_negated(n.text, a) == neg
    print(f"\nNegation rule accuracy on symptom mentions: {correct / total:.3f} ({correct}/{total})")

    ex = test[0]
    lines = [ex.text, "", "dictionary: " + str(sorted((ex.text[a:b], t) for a, b, t in dict_pred[0])),
             "tagger:     " + str(sorted((ex.text[a:b], t) for a, b, t in ml_pred[0])),
             "gold:       " + str(sorted((ex.text[a:b], t) for a, b, t in gold[0]))]
    (OUT / "t11_example.txt").write_text("\n".join(lines))

    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    names = ["dictionary", "tagger (with lexicon)", "tagger (no lexicon)"]; xs = np.arange(4); w = 0.27
    for i, nm in enumerate(names):
        axs[0].bar(xs + (i - 1) * w, [scores[(nm, t)][2] for t in ("DRUG", "CONDITION", "SYMPTOM", "ALL")], w, label=nm)
    axs[0].set_xticks(xs); axs[0].set_xticklabels(["DRUG", "CONDITION", "SYMPTOM", "ALL"]); axs[0].set_ylim(0, 1.05)
    axs[0].set_ylabel("span-level F1"); axs[0].legend(fontsize=7, loc="lower right"); axs[0].set_title("Entity recognition")
    for i, nm in enumerate(names):
        axs[1].bar(np.arange(2) + (i - 1) * w, [recall_split[nm]["seen"], recall_split[nm]["unseen"]], w, label=nm)
    axs[1].set_xticks([0, 1]); axs[1].set_xticklabels(["drug seen in training", "drug NEVER seen"]); axs[1].set_ylim(0, 1.05)
    axs[1].set_ylabel("drug recall"); axs[1].set_title("Generalising to new drug names")
    fig.tight_layout(); fig.savefig(OUT / "t11_ner_scores.png", dpi=130); plt.close(fig)

    res = {"regex_v1": v1, "regex_v2": v2, "ner": {f"{k[0]}|{k[1]}": v for k, v in scores.items()}, "drug_recall": recall_split,
           "negation_accuracy": correct / total, "n_unseen_mentions": n_unseen, "n_drug_mentions": n_drug}
    (OUT / "t11_results.json").write_text(json.dumps(res, indent=1))

    assert v2["bp"] > v1["bp"], "regex v2 should fix the 'over' format"
    assert recall_split["tagger (no lexicon)"]["unseen"] > recall_split["dictionary"]["unseen"] + 0.3
    assert recall_split["tagger (with lexicon)"]["unseen"] < recall_split["tagger (no lexicon)"]["unseen"], "lexicon shortcut should hurt"
    print("\nSelf-check passed: tagger without the lexicon finds drugs the dictionary has never seen; the lexicon feature "
          "is a shortcut that hurts; regex v2 fixes v1's misses.")
    print("Note: notes are templated, so scores near 1.0 are a ceiling effect of the synthetic text, not a real-world claim.")
