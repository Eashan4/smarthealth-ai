"""Figures shared by the report, poster and decks. Everything is drawn from real files in the repo:
models/training_results.json (CNN/LSTM metrics), ml/inference/tremor.py (spectra), image.png / image copy.png (hardware)."""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
A = ROOT / "final" / "assets"
sys.path.insert(0, str(ROOT))
NAVY, TEAL, CORAL, GOLD, GREY = "#0B2A4A", "#0E8C8C", "#E4572E", "#F2A93B", "#6B7A8C"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})

# ---- hardware photos (crop away the people in the background) -----------------------------------------------------
RAW = ROOT / "docs" / "photos"          # originals are not committed (people in the background); the crops in assets/ are
if (RAW / "prototype_wired.png").exists() and (RAW / "prototype_parts.png").exists():
    Image.open(RAW / "prototype_wired.png").convert("RGB").crop((0, 380, 1200, 1000)).save(A / "hw_wired.jpg", quality=90)
    Image.open(RAW / "prototype_parts.png").convert("RGB").crop((0, 330, 1200, 1000)).save(A / "hw_parts.jpg", quality=90)

R = json.load(open(ROOT / "models" / "training_results.json"))
CLS = ["Walking", "Running", "Sitting", "Lying", "Fall"]

# ---- architecture ----------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 4.2)); ax.axis("off"); ax.set_xlim(0, 11); ax.set_ylim(0, 4.2)
def box(x, y, w, h, t, c, fs=9, tc="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=c, ec="none"))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", color=tc, fontsize=fs, fontweight="bold", linespacing=1.25)
def arr(x1, y1, x2, y2): ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, color=GREY, lw=1.4))
row1 = [("MPU6050\nax ay az gx gy gz", TEAL), ("MAX30102\nheart rate, SpO2", TEAL), ("NodeMCU ESP8266\n50 Hz, USB serial", NAVY), ("Flask backend\nvalidate, ingest", NAVY)]
for i, (t, c) in enumerate(row1):
    box(0.2 + i * 2.7, 3.05, 2.2, 0.85, t, c)
    if i: arr(0.2 + i * 2.7 - 0.5, 3.47, 0.2 + i * 2.7, 3.47)
arr(9.15, 3.05, 9.15, 2.55)
row2 = [("Event segmenter\n150 x 6 tensor", GOLD, "black"), ("1D CNN (deployed)\nactivity + P(fall)", CORAL, "white"),
        ("Decision engine\nfall confirm + cooldown", NAVY, "white"), ("SQLite, dashboard\n+ buzzer", TEAL, "white")]
for i, (t, c, tc) in enumerate(row2):
    x = 0.2 + (3 - i) * 2.7
    box(x, 1.65, 2.2, 0.85, t, c, tc=tc)
    if i: arr(x + 2.7, 2.07, x + 2.2, 2.07)
box(0.2, 0.2, 5.2, 0.9, "Tremor detector (signal processing)\n3 s window, FFT, 3-8 Hz band power", "#7A5CFA", fs=8.5)
box(5.7, 0.2, 5.1, 0.9, "Same preprocessing in training and live\nresample to 150 steps, z-score fit on train only", GREY, fs=8.5)
arr(1.3, 1.1, 1.3, 1.65); ax.text(1.45, 1.3, "tremor status", fontsize=7.5, color=GREY)
fig.savefig(A / "architecture.png", dpi=200, bbox_inches="tight", transparent=False, facecolor="white"); plt.close(fig)

# ---- confusion matrix ------------------------------------------------------------------------------------------------
cm = np.array(R["selected_test"]["confusion_matrix"])
fig, ax = plt.subplots(figsize=(4.6, 4.0))
ax.imshow(cm / cm.sum(1, keepdims=True), cmap="Blues", vmin=0, vmax=1)
for i in range(5):
    for j in range(5): ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] / cm[i].sum() > .5 else "black", fontsize=10)
ax.set_xticks(range(5)); ax.set_xticklabels(CLS, rotation=35, ha="right", fontsize=8); ax.set_yticks(range(5)); ax.set_yticklabels(CLS, fontsize=8)
ax.set_xlabel("predicted"); ax.set_ylabel("true"); ax.set_title("CNN on 114 held-out windows (6 unseen subjects)", fontsize=9)
fig.tight_layout(); fig.savefig(A / "confusion.png", dpi=200, facecolor="white"); plt.close(fig)

# ---- CNN vs LSTM -----------------------------------------------------------------------------------------------------
c, l = R["selected_test"], R["other_test"]
fig, axs = plt.subplots(1, 2, figsize=(8.2, 3.4), gridspec_kw={"width_ratios": [2.2, 1]})
m = ["Accuracy", "Macro-F1", "Fall recall"]; cv = [c["accuracy"], c["macro_f1"], c["fall_recall"]]; lv = [l["accuracy"], l["macro_f1"], l["fall_recall"]]
x = np.arange(3); w = .36
axs[0].bar(x - w / 2, cv, w, color=CORAL, label="1D CNN (deployed)"); axs[0].bar(x + w / 2, lv, w, color=GREY, label="LSTM")
for i in range(3): axs[0].text(i - w / 2, cv[i] + .01, f"{cv[i]:.3f}", ha="center", fontsize=8); axs[0].text(i + w / 2, lv[i] + .01, f"{lv[i]:.3f}", ha="center", fontsize=8)
axs[0].set_xticks(x); axs[0].set_xticklabels(m); axs[0].set_ylim(0.5, 1.08); axs[0].legend(fontsize=8, loc="upper center", ncol=2); axs[0].set_title("Held-out test set", fontsize=10)
axs[1].bar(["CNN", "LSTM"], [R["selected_latency_ms"], R["other_latency_ms"]], color=[CORAL, GREY]); axs[1].set_ylabel("ms per window (CPU)")
axs[1].set_title(f"{R['other_latency_ms'] / R['selected_latency_ms']:.0f}x faster", fontsize=10)
fig.tight_layout(); fig.savefig(A / "cnn_vs_lstm.png", dpi=200, facecolor="white"); plt.close(fig)

# ---- per-class ------------------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.4, 3.2)); x = np.arange(5); w = .26
for k, (key, col) in enumerate((("per_class_precision", TEAL), ("per_class_recall", CORAL), ("per_class_f1", NAVY))):
    ax.bar(x + (k - 1) * w, c[key], w, color=col, label=key.split("_")[-1].replace("f1", "F1").capitalize())
ax.set_xticks(x); ax.set_xticklabels(CLS); ax.set_ylim(0, 1.08); ax.legend(fontsize=8, ncol=3, loc="upper center"); ax.set_title("CNN per-class scores (test)", fontsize=10)
fig.tight_layout(); fig.savefig(A / "per_class.png", dpi=200, facecolor="white"); plt.close(fig)

# ---- validation sweep ------------------------------------------------------------------------------------------------
runs = R["all_val_runs"]
fig, ax = plt.subplots(figsize=(6.4, 3.2))
lab = [f"{r['model_name']}\n{r['params'] // 1000 if r['params'] >= 1000 else r['params']}k" for r in runs]
ax.bar(range(len(runs)), [r["val_macro_f1"] for r in runs], color=[CORAL if r["model_name"] == "CNN" else GREY for r in runs])
ax.set_xticks(range(len(runs))); ax.set_xticklabels(lab, fontsize=7); ax.set_ylim(0.5, 1); ax.set_ylabel("validation macro-F1"); ax.set_title(f"All {len(runs)} configurations tried (selection on validation only)", fontsize=9)
fig.tight_layout(); fig.savefig(A / "val_sweep.png", dpi=200, facecolor="white"); plt.close(fig)

# ---- tremor: cases first, in the same order as tests/test_tremor.py, so the numbers match its printout ---------------
from tests.test_tremor import CASES, FS, T, sig, run
cases = []
for name, (comps, expect) in CASES.items():
    d_ = run(sig(comps)); cases.append([name, expect, bool(d_.detected), {k: float(v) for k, v in d_.last.items()}])
json.dump(cases, open(A / "tremor_cases.json", "w"), indent=1)
assert all(e == g for _, e, g, _ in cases), "a tremor case disagrees with its expectation"
# ---- tremor spectra --------------------------------------------------------------------------------------------------
fig, axs = plt.subplots(1, 3, figsize=(10.5, 3), sharey=True)
for ax, name in zip(axs, ("resting, sensor noise only", "5 Hz tremor, 0.6 m/s2", "walking (1.9 Hz + harmonics)")):
    a = sig(CASES[name][0]); x = a - a.mean(0); w_ = np.hanning(len(x))
    sp = np.abs(np.fft.rfft(x * w_[:, None], axis=0)) ** 2; psd = sp.sum(1); f = np.fft.rfftfreq(len(x), 1 / FS)
    ax.semilogy(f, psd / psd.max() + 1e-6, color=NAVY); ax.axvspan(3, 8, color=GOLD, alpha=.3); ax.set_xlim(0, 15)
    ax.set_title(name.replace("m/s2", "m/s²"), fontsize=9); ax.set_xlabel("frequency (Hz)")
axs[0].set_ylabel("relative power"); axs[1].text(5.2, 0.3, "3-8 Hz\ntremor band", fontsize=7.5)
fig.tight_layout(); fig.savefig(A / "tremor_spectra.png", dpi=200, facecolor="white"); plt.close(fig)
print("assets:", sorted(p.name for p in A.iterdir()))
