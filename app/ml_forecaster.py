"""Load + áp dụng model dự báo đã train (`scripts/train_forecaster.py`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "arrival_forecaster.joblib"


@lru_cache(maxsize=1)
def load_model_bundle(model_path: Path = MODEL_PATH) -> Optional[dict[str, Any]]:
    if not model_path.exists():
        return None
    try:
        import joblib
    except ImportError:
        return None
    try:
        return joblib.load(model_path)
    except Exception:
        return None


def predict_bucket_weight(bundle: dict[str, Any], features: dict[str, float]) -> float:
    import pandas as pd

    columns = bundle["feature_columns"]
    row = pd.DataFrame([{col: features.get(col, 0) for col in columns}])
    prediction = float(bundle["model"].predict(row)[0])
    return max(prediction, 0.0)
