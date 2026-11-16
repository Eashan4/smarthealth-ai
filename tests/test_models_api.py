"""Model-comparison API check. Run: python -m tests.test_models_api (needs trained models in models/)."""

import numpy as np

from backend.app import create_app
from backend.services import live_state


def main():
    c = create_app().test_client()
    r = c.get("/api/models").get_json()
    assert r["available"], "train first: python -m ml.training.train"
    cnn, lstm = r["models"]
    assert (cnn["role"], lstm["role"]) == ("deployed", "comparison") and cnn["name"] != lstm["name"]
    n = len(r["classes"])
    for m in r["models"]:
        assert 0 < m["accuracy"] <= 1 and len(m["per_class"]["f1"]) == n and len(m["confusion_matrix"]) == n
    print("PASS /api/models:", [(m["name"], round(m["accuracy"], 3)) for m in r["models"]])

    assert c.get("/api/models/live?device_id=m_test").get_json()["cnn"] is None
    rng, stream, ev = np.random.default_rng(0), live_state.get_stream("m_test"), None
    for i in range(300):                       # a synthetic motion event: both models must classify the same window
        a = [rng.normal(0, .2), rng.normal(0, .2), 9.8 + (6 * np.sin(i / 4) if 20 < i < 120 else 0) + rng.normal(0, .1), 0, 0, 0]
        ev = stream.push_sample(a) or ev
    assert ev is not None and ev["comparison"]["model_name"] == "LSTM"
    live_state.set_last_models("m_test", ev)
    live = c.get("/api/models/live?device_id=m_test").get_json()
    assert live["cnn"]["model_name"] == "CNN" and live["lstm"]["model_name"] == "LSTM" and isinstance(live["agree"], bool)
    print("PASS /api/models/live:", live["cnn"]["activity"], "vs", live["lstm"]["activity"], "agree =", live["agree"])
    live_state.reset_device("m_test")
    print("OK: model comparison api")


if __name__ == "__main__":
    main()
