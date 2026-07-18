import os
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# =====================================================================
# AI / ML Model Loading Wrappers (Mock/Placeholder for Hackathon)
# =====================================================================
class Layer2ModelWrapper:
    """
    Simulates loading a trained Machine Learning model (e.g., PyTorch to ONNX or Scikit-Learn to pkl)
    for predicting consolidated inventory volume or optimal dispatch schedules.
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self.loaded = False
        self._load_model()

    def _load_model(self):
        try:
            if not os.path.exists(self.model_path):
                logger.warning(f"AI Model path {self.model_path} not found. Running in fallback mode.")
                return

            # Example: loading with joblib
            if self.model_path.endswith('.pkl'):
                import joblib
                self.model = joblib.load(self.model_path)
                self.loaded = True
                logger.info(f"Successfully loaded joblib model from {self.model_path}")
            
            # Example: loading with onnxruntime
            elif self.model_path.endswith('.onnx'):
                import onnxruntime as ort
                self.model = ort.InferenceSession(self.model_path)
                self.loaded = True
                logger.info(f"Successfully loaded ONNX model from {self.model_path}")

        except Exception as e:
            logger.error(f"Error loading AI model from {self.model_path}: {e}")

# Global placeholder model instance
layer2_model = Layer2ModelWrapper("models/layer2_dispatcher.onnx")

# =====================================================================
# Dispatch Orchestrator Business Logic
# =====================================================================
def evaluate_dispatch(inventory: Dict[str, float], weather: str, threshold: float = 50000.0) -> Tuple[str, str]:
    """
    Layer 2 Decision Engine:
    Evaluates current inventory at Can Tho Hub (in kg) and weather to determine:
    - DISPATCH: Send a truck/barge cargo to HCM
    - WAIT: Keep accumulating cargo to achieve loading efficiency
    """
    total_volume = sum(inventory.values())
    seafood_volume = inventory.get("seafood", 0.0)
    
    # 1. Weather Stormy override:
    # If weather is Stormy and there is seafood or high volume, we must dispatch via road immediately to avoid spoilage.
    if weather == "Stormy":
        if total_volume >= 25000.0:
            if seafood_volume > 0.0:
                return "DISPATCH", f"Stormy weather detected! Dispatching {total_volume:.0f} kg (including {seafood_volume:.0f} kg Seafood) immediately via road convoy to prevent spoilage."
            return "DISPATCH", f"Stormy weather safety dispatch: {total_volume:.0f} kg consolidated cargo routed via secure road transportation."
        else:
            return "WAIT", f"Stormy weather active. Low cargo load ({total_volume:.0f} kg / {threshold:.0f} kg). Holding shipments for consolidation."

    # 2. Normal operational threshold check
    if total_volume >= threshold:
        return "DISPATCH", f"Capacity threshold reached! Dispatching {total_volume:.0f} kg of agricultural goods (Limit: {threshold:.0f} kg)."

    # 3. Time-sensitive/perishable cargo priority dispatch
    # If seafood is sitting in Can Tho hub and reaches a minor threshold (e.g. 15,000 kg), we dispatch to keep it fresh
    if seafood_volume >= 15000.0:
        return "DISPATCH", f"Perishable alert! Dispatching cargo due to high seafood accumulation ({seafood_volume:.0f} kg) to meet storage guidelines."

    # 4. Otherwise, continue accumulating
    return "WAIT", f"Consolidating cargo. Current hub load is {total_volume:.0f} kg ({round(total_volume/threshold * 100, 1)}% of {threshold:.0f} kg capacity)."

