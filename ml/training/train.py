"""Train and compare the 1D CNN (primary) against an LSTM (comparison) on the
BITS-2 dataset, per docs/DOCUMENTATION.md sec 6.3 (Model Selection Experiment).

Runs a small hyperparameter sweep per architecture, selects per-config best
epoch by validation macro-F1, then picks the final deployed model weighting
fall recall over raw accuracy (never on the held-out test set). Every metric
printed/saved comes from an actual run against real BITS-2 data -- see
ml/datasets/bits2_adapter.py for how that dataset was mapped into our label
set and where it deviates from a continuous live stream.

Usage: python -m ml.training.train
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

from ml.cnn.model import ActivityCNN
from ml.config import CLASSES, DATA_PROCESSED_DIR, FALL_CLASS_IDX, MODELS_DIR, NUM_CHANNELS
from ml.datasets.bits2_adapter import load_dataset
from ml.lstm.model import ActivityLSTM
from ml.preprocessing.normalize import ChannelScaler

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)


def subject_wise_split(subjects: np.ndarray, train_frac=0.70, val_frac=0.15, seed=SEED):
    unique = np.unique(subjects)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique)
    n = len(unique)
    n_train = int(round(n * train_frac))
    n_val = int(round(n * val_frac))
    train_subj = set(unique[:n_train].tolist())
    val_subj = set(unique[n_train:n_train + n_val].tolist())
    test_subj = set(unique[n_train + n_val:].tolist())
    return train_subj, val_subj, test_subj


def split_masks(subjects, train_subj, val_subj, test_subj):
    return (
        np.isin(subjects, list(train_subj)),
        np.isin(subjects, list(val_subj)),
        np.isin(subjects, list(test_subj)),
    )


@dataclass
class RunResult:
    model_name: str
    config: dict
    val_accuracy: float
    val_macro_f1: float
    val_fall_recall: float
    params: int
    epochs_trained: int


def make_loader(X, y, batch_size=32, shuffle=True):
    ds = torch.utils.data.TensorDataset(torch.from_numpy(X), torch.from_numpy(y))
    return torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=shuffle)


def augment_training_set(X_norm, y, n_copies=2, noise_std=0.05, scale_range=(0.9, 1.1), seed=SEED):
    """Jitter + random-scale augmentation of the (already-normalized) training
    set only -- combats overfitting on a small (547-sample) training set.
    Each copy perturbs real recorded windows; it does not synthesize new
    semantic content or labels (see docs/DOCUMENTATION.md sec 16)."""
    rng = np.random.default_rng(seed)
    xs, ys = [X_norm], [y]
    for _ in range(n_copies):
        noise = rng.normal(0, noise_std, size=X_norm.shape).astype(np.float32)
        scale = rng.uniform(scale_range[0], scale_range[1], size=(X_norm.shape[0], 1, 1)).astype(np.float32)
        xs.append(X_norm * scale + noise)
        ys.append(y.copy())
    return np.concatenate(xs).astype(np.float32), np.concatenate(ys)


def train_one(model, train_loader, val_loader, class_weights, max_epochs=80, patience=12, lr=1e-3):
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=5)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    best_f1 = -1.0
    best_state = None
    best_epoch = 0
    epochs_no_improve = 0

    for epoch in range(1, max_epochs + 1):
        model.train()
        for xb, yb in train_loader:
            opt.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            opt.step()

        model.eval()
        all_preds, all_targets = [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                preds = model(xb).argmax(dim=1)
                all_preds.append(preds.numpy())
                all_targets.append(yb.numpy())
        all_preds = np.concatenate(all_preds)
        all_targets = np.concatenate(all_targets)
        macro_f1 = f1_score(all_targets, all_preds, average="macro", zero_division=0)
        scheduler.step(macro_f1)

        if macro_f1 > best_f1:
            best_f1 = macro_f1
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            best_epoch = epoch
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                break

    model.load_state_dict(best_state)
    return model, best_epoch


def evaluate(model, X, y):
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(X))
        preds = logits.argmax(dim=1).numpy()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, preds, labels=list(range(len(CLASSES))), zero_division=0
    )
    acc = float((preds == y).mean())
    macro_f1 = float(f1_score(y, preds, average="macro", zero_division=0))
    fall_recall = float(recall[FALL_CLASS_IDX])
    cm = confusion_matrix(y, preds, labels=list(range(len(CLASSES))))
    return {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "fall_recall": fall_recall,
        "per_class_precision": precision.tolist(),
        "per_class_recall": recall.tolist(),
        "per_class_f1": f1.tolist(),
        "confusion_matrix": cm.tolist(),
        "preds": preds,
    }


def measure_inference_latency_ms(model, sample_x, n_runs=50):
    model.eval()
    x = torch.from_numpy(sample_x[:1])
    with torch.no_grad():
        for _ in range(5):
            model(x)  # warmup
        start = time.perf_counter()
        for _ in range(n_runs):
            model(x)
        elapsed = time.perf_counter() - start
    return (elapsed / n_runs) * 1000.0


def count_params(model):
    return sum(p.numel() for p in model.parameters())


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading BITS-2 dataset...")
    X, y, subjects, summary = load_dataset()
    print(f"  files seen={summary.total_files_seen} skipped_short={summary.skipped_short}")
    print(f"  excluded ADL ids -> counts: {summary.excluded_adl}")
    print(f"  included per class: {summary.included}")
    print(f"  X={X.shape} y={y.shape} subjects={np.unique(subjects).size}")

    train_subj, val_subj, test_subj = subject_wise_split(subjects)
    train_mask, val_mask, test_mask = split_masks(subjects, train_subj, val_subj, test_subj)
    print(f"Subject split: train={sorted(train_subj)}")
    print(f"               val={sorted(val_subj)}")
    print(f"               test={sorted(test_subj)}")

    X_train, y_train = X[train_mask], y[train_mask]
    X_val, y_val = X[val_mask], y[val_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    print(f"Split sizes: train={len(y_train)} val={len(y_val)} test={len(y_test)}")
    for name, yy in (("train", y_train), ("val", y_val), ("test", y_test)):
        counts = {CLASSES[i]: int((yy == i).sum()) for i in range(len(CLASSES))}
        print(f"  {name} class counts: {counts}")

    scaler = ChannelScaler().fit(X_train)
    X_train_n = scaler.transform(X_train)
    X_val_n = scaler.transform(X_val)
    X_test_n = scaler.transform(X_test)

    class_counts = np.bincount(y_train, minlength=len(CLASSES)).astype(np.float32)
    class_weights = torch.tensor(class_counts.sum() / (len(CLASSES) * np.maximum(class_counts, 1)),
                                  dtype=torch.float32)
    print(f"Class weights (train, inverse-frequency): {dict(zip(CLASSES, class_weights.tolist()))}")

    X_train_aug, y_train_aug = augment_training_set(X_train_n, y_train, n_copies=2)
    print(f"Augmented train set: {X_train_n.shape[0]} -> {X_train_aug.shape[0]} windows "
          f"(jitter+scale augmentation of real recorded windows)")

    train_loader = make_loader(X_train_aug, y_train_aug)
    val_loader = make_loader(X_val_n, y_val, shuffle=False)

    cnn_configs = [
        {"filters": (16, 32), "kernel_size": 5, "dropout": 0.2},
        {"filters": (32, 64), "kernel_size": 5, "dropout": 0.3},
        {"filters": (32, 64), "kernel_size": 7, "dropout": 0.4},
        {"filters": (64, 128), "kernel_size": 5, "dropout": 0.4},
        {"filters": (32, 64), "kernel_size": 3, "dropout": 0.3},
        {"filters": (48, 96), "kernel_size": 5, "dropout": 0.3},
    ]
    lstm_configs = [
        {"hidden_size": 32, "num_layers": 1, "dropout": 0.2},
        {"hidden_size": 64, "num_layers": 1, "dropout": 0.3},
        {"hidden_size": 64, "num_layers": 2, "dropout": 0.4},
        {"hidden_size": 128, "num_layers": 1, "dropout": 0.4},
    ]

    results = []
    trained_models = {}

    for i, cfg in enumerate(cnn_configs):
        print(f"\n[CNN config {i+1}/{len(cnn_configs)}] {cfg}")
        model = ActivityCNN(NUM_CHANNELS, len(CLASSES), **cfg)
        model, best_epoch = train_one(model, train_loader, val_loader, class_weights)
        val_metrics = evaluate(model, X_val_n, y_val)
        key = f"CNN_{i}"
        trained_models[key] = model
        results.append(RunResult("CNN", cfg, val_metrics["accuracy"], val_metrics["macro_f1"],
                                  val_metrics["fall_recall"], count_params(model), best_epoch))
        print(f"  -> val_acc={val_metrics['accuracy']:.4f} val_macro_f1={val_metrics['macro_f1']:.4f} "
              f"val_fall_recall={val_metrics['fall_recall']:.4f} best_epoch={best_epoch}")

    for i, cfg in enumerate(lstm_configs):
        print(f"\n[LSTM config {i+1}/{len(lstm_configs)}] {cfg}")
        model = ActivityLSTM(NUM_CHANNELS, len(CLASSES), **cfg)
        model, best_epoch = train_one(model, train_loader, val_loader, class_weights)
        val_metrics = evaluate(model, X_val_n, y_val)
        key = f"LSTM_{i}"
        trained_models[key] = model
        results.append(RunResult("LSTM", cfg, val_metrics["accuracy"], val_metrics["macro_f1"],
                                  val_metrics["fall_recall"], count_params(model), best_epoch))
        print(f"  -> val_acc={val_metrics['accuracy']:.4f} val_macro_f1={val_metrics['macro_f1']:.4f} "
              f"val_fall_recall={val_metrics['fall_recall']:.4f} best_epoch={best_epoch}")

    # Selection: weight fall recall first (rounded to 2dp buckets), then macro-F1.
    def rank_key(r: RunResult):
        return (round(r.val_fall_recall, 2), round(r.val_macro_f1, 4))

    results_sorted = sorted(results, key=rank_key, reverse=True)
    print("\n=== Validation leaderboard (fall recall, then macro-F1) ===")
    for r in results_sorted:
        print(f"  {r.model_name:5s} {r.config} val_acc={r.val_accuracy:.4f} "
              f"macro_f1={r.val_macro_f1:.4f} fall_recall={r.val_fall_recall:.4f} params={r.params}")

    best = results_sorted[0]
    best_key = f"{best.model_name}_{cnn_configs.index(best.config) if best.model_name == 'CNN' else lstm_configs.index(best.config)}"
    best_model = trained_models[best_key]

    print(f"\nSelected deployed model: {best.model_name} config={best.config}")

    test_metrics = evaluate(best_model, X_test_n, y_test)
    latency_ms = measure_inference_latency_ms(best_model, X_test_n)

    print("\n=== FINAL held-out TEST metrics (selected model) ===")
    print(f"accuracy={test_metrics['accuracy']:.4f} macro_f1={test_metrics['macro_f1']:.4f} "
          f"fall_recall={test_metrics['fall_recall']:.4f}")
    for i, c in enumerate(CLASSES):
        print(f"  {c:8s} precision={test_metrics['per_class_precision'][i]:.3f} "
              f"recall={test_metrics['per_class_recall'][i]:.3f} f1={test_metrics['per_class_f1'][i]:.3f}")
    print(f"confusion_matrix (rows=true, cols=pred, order={CLASSES}):")
    for row in test_metrics["confusion_matrix"]:
        print(f"  {row}")
    print(f"inference latency: {latency_ms:.3f} ms/window (CPU, single sample)")

    # --- Also evaluate the runner-up of the OTHER architecture family for the
    # comparison table (best CNN vs best LSTM), even if not selected. ---
    other_family = "LSTM" if best.model_name == "CNN" else "CNN"
    other_results = [r for r in results if r.model_name == other_family]
    other_best = sorted(other_results, key=rank_key, reverse=True)[0]
    other_idx_list = cnn_configs if other_family == "CNN" else lstm_configs
    other_key = f"{other_family}_{other_idx_list.index(other_best.config)}"
    other_model = trained_models[other_key]
    other_test_metrics = evaluate(other_model, X_test_n, y_test)
    other_latency = measure_inference_latency_ms(other_model, X_test_n)

    comparison = {
        "selected_model": best.model_name,
        "selected_config": best.config,
        "selected_test": {k: v for k, v in test_metrics.items() if k != "preds"},
        "selected_latency_ms": latency_ms,
        "selected_params": count_params(best_model),
        "other_model": other_family,
        "other_config": other_best.config,
        "other_test": {k: v for k, v in other_test_metrics.items() if k != "preds"},
        "other_latency_ms": other_latency,
        "other_params": count_params(other_model),
        "all_val_runs": [asdict(r) for r in results],
        "subject_split": {
            "train": sorted(train_subj), "val": sorted(val_subj), "test": sorted(test_subj),
        },
        "dataset_summary": {
            "total_files_seen": summary.total_files_seen,
            "skipped_short": summary.skipped_short,
            "excluded_adl": summary.excluded_adl,
            "included_per_class": summary.included,
        },
        "seed": SEED,
    }

    # Save artifacts
    torch.save(best_model.state_dict(), MODELS_DIR / "deployed_model.pt")
    torch.save(other_model.state_dict(), MODELS_DIR / "comparison_model.pt")
    scaler.save(MODELS_DIR / "scaler.json")
    with open(MODELS_DIR / "model_meta.json", "w") as fh:
        json.dump({
            "deployed": {"arch": best.model_name, "config": best.config, "classes": CLASSES},
            "comparison": {"arch": other_family, "config": other_best.config, "classes": CLASSES},
        }, fh, indent=2)
    with open(MODELS_DIR / "training_results.json", "w") as fh:
        json.dump(comparison, fh, indent=2)

    import os
    deployed_size_kb = os.path.getsize(MODELS_DIR / "deployed_model.pt") / 1024
    print(f"\nSaved deployed model ({best.model_name}) -> models/deployed_model.pt "
          f"({deployed_size_kb:.1f} KB)")
    print(f"Saved comparison model ({other_family}) -> models/comparison_model.pt")
    print("Saved scaler.json, model_meta.json, training_results.json")


if __name__ == "__main__":
    main()
