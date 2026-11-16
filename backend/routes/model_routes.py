"""Model comparison endpoints: offline test metrics (CNN vs LSTM) and the live side-by-side on the last motion event."""

from __future__ import annotations

import json
import time

from flask import Blueprint, jsonify, request

from backend.services import live_state
from ml.config import MODELS_DIR

model_bp = Blueprint("models", __name__)


def _model_entry(name: str, role: str, cfg: dict, test: dict, latency_ms: float, params: int) -> dict:
    return {
        "name": name, "role": role, "config": cfg, "params": params, "latency_ms": latency_ms,
        "accuracy": test["accuracy"], "macro_f1": test["macro_f1"], "fall_recall": test["fall_recall"],
        "per_class": {k: test[f"per_class_{k}"] for k in ("precision", "recall", "f1")},
        "confusion_matrix": test["confusion_matrix"],
    }


@model_bp.route("/api/models", methods=["GET"])
def models():
    """Held-out test-set results written by ml/training/train.py (models/training_results.json)."""
    try:
        r = json.loads((MODELS_DIR / "training_results.json").read_text())
        classes = json.loads((MODELS_DIR / "model_meta.json").read_text())["deployed"]["classes"]
    except (OSError, ValueError, KeyError):
        return jsonify({"available": False, "error": "models/training_results.json not found: run python -m ml.training.train"}), 200
    entries = [
        _model_entry(r["selected_model"], "deployed", r["selected_config"], r["selected_test"], r["selected_latency_ms"], r["selected_params"]),
        _model_entry(r["other_model"], "comparison", r["other_config"], r["other_test"], r["other_latency_ms"], r["other_params"]),
    ]
    return jsonify({
        "available": True, "classes": classes, "deployed": r["selected_model"], "models": entries,
        "val_runs": r["all_val_runs"], "dataset": r["dataset_summary"],
        "split": {k: len(v) for k, v in r["subject_split"].items()},   # subjects per train/val/test
    })


@model_bp.route("/api/models/live", methods=["GET"])
def models_live():
    """Both models' prediction for the most recent captured motion event (event-triggered, not continuous)."""
    device_id = request.args.get("device_id") or "wearable_01"
    last = live_state.get_last_models(device_id)
    if last is None:
        return jsonify({"at": None, "age_s": None, "cnn": None, "lstm": None, "agree": None})
    cnn, lstm = last["cnn"], last["lstm"]
    return jsonify({**last, "age_s": round(time.time() - last["at"], 1),
                    "agree": None if lstm is None else cnn["activity"] == lstm["activity"]})
