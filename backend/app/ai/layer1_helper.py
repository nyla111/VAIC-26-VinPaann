import os
import logging
from typing import List
from app.models import RouteOption

logger = logging.getLogger(__name__)

# =====================================================================
# AI / ML Model Loading Wrappers (Mock/Placeholder for Hackathon)
# =====================================================================
class Layer1ModelWrapper:
    """
    Simulates loading a trained Machine Learning model (e.g., Random Forest from joblib
    or a Deep Learning model from ONNX runtime) for Route Optimization.
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

# Global placeholder model instance (points to non-existent file for fallback mode)
layer1_model = Layer1ModelWrapper("models/layer1_route_optimizer.pkl")

# =====================================================================
# Route Optimization Business Logic
# =====================================================================
def predict_routes(hub_id: str, cargo_type: str, volume: float, urgency_level: str, weather: str) -> List[RouteOption]:
    """
    Layer 1 Route Optimizer:
    Evaluates 3 routing options from regional delta hubs to HCM City.
    Calculates dynamic ETA, Costs, and Recommendations based on weather and urgency.
    """
    # Base configuration values for regional hubs
    hub_distances = {
        "An Giang": 190.0,
        "Hau Giang": 200.0,
        "Soc Trang": 220.0,
        "Bac Lieu": 250.0,
        "Vinh Long": 130.0,
        "Dong Thap": 140.0,
        "Can Tho": 170.0
    }
    
    distance = hub_distances.get(hub_id, 170.0)

    # 1. Option 1: Direct to HCM via Road
    eta_direct = distance / 50.0  # ~50 km/h average truck speed
    cost_direct = 250.0 + (volume * 15.0)  # Base cost + volume weight charge
    
    # Adjust for weather
    if weather == "Rainy":
        eta_direct += 1.0
        cost_direct += 20.0
    elif weather == "Stormy":
        eta_direct += 3.0
        cost_direct += 50.0

    # 2. Option 2: Via Can Tho Hub via Road
    # Travel to Can Tho + consolidation buffer + travel Can Tho to HCM
    to_can_tho_dist = abs(distance - 170.0)
    eta_via_cantho_road = (to_can_tho_dist / 50.0) + 3.0 + (170.0 / 60.0)  # 3 hr consolidation buffer, faster highway speed
    cost_via_cantho_road = 150.0 + (volume * 10.0)  # Lower base cost due to hub sharing
    
    if weather == "Rainy":
        eta_via_cantho_road += 0.8
    elif weather == "Stormy":
        eta_via_cantho_road += 2.0

    # 3. Option 3: Via Can Tho Hub via Waterway
    # Barges are slower but highly cost-efficient and unaffected by traffic, but vulnerable to storms
    eta_via_cantho_waterway = (to_can_tho_dist / 15.0) + 4.0 + (170.0 / 20.0)  # ~15-20 km/h barge speed
    cost_via_cantho_waterway = 70.0 + (volume * 5.0)  # Ultra-low cost
    
    if weather == "Rainy":
        eta_via_cantho_waterway += 2.0
    elif weather == "Stormy":
        eta_via_cantho_waterway += 24.0  # Port closure/delays

    # Determine Recommendations based on urgency, cargo, and weather constraints
    rec_id = "cantho_road"  # Default
    reasons = {
        "direct_road": "Recommended for expedited direct delivery to avoid delay.",
        "cantho_road": "Recommended for balanced cost-savings via Can Tho consolidation.",
        "cantho_waterway": "Recommended for low-cost, bulk agricultural cargo logistics."
    }

    if weather == "Stormy":
        # Waterways are dangerous, road is needed
        if urgency_level == "High":
            rec_id = "direct_road"
            reasons["direct_road"] = "Recommended due to high shipment urgency and severe storm risk on waterways."
        else:
            rec_id = "cantho_road"
            reasons["cantho_road"] = "Consolidation via road is recommended to bypass storm-sensitive waterways."
        reasons["cantho_waterway"] = "WARNING: Not recommended. Waterway transit suspended due to severe storm warnings."
    else:
        if urgency_level == "High" or cargo_type == "Seafood":
            # High urgency or highly perishable seafood prefers direct road
            rec_id = "direct_road"
            if cargo_type == "Seafood":
                reasons["direct_road"] = "Recommended to prevent spoilage of highly perishable seafood cargo."
        elif urgency_level == "Low" and volume > 10.0:
            # Low urgency heavy bulk prefers waterway
            rec_id = "cantho_waterway"
            reasons["cantho_waterway"] = "Recommended for high-volume, low-urgency shipment efficiency."

    return [
        RouteOption(
            route_id="direct_road",
            route_name="Direct to HCM via Road",
            estimated_cost=round(cost_direct, 2),
            eta=round(eta_direct, 2),
            recommendation_flag=(rec_id == "direct_road"),
            reason=reasons["direct_road"]
        ),
        RouteOption(
            route_id="cantho_road",
            route_name="Via Can Tho Hub via Road",
            estimated_cost=round(cost_via_cantho_road, 2),
            eta=round(eta_via_cantho_road, 2),
            recommendation_flag=(rec_id == "cantho_road"),
            reason=reasons["cantho_road"]
        ),
        RouteOption(
            route_id="cantho_waterway",
            route_name="Via Can Tho Hub via Waterway",
            estimated_cost=round(cost_via_cantho_waterway, 2),
            eta=round(eta_via_cantho_waterway, 2),
            recommendation_flag=(rec_id == "cantho_waterway"),
            reason=reasons["cantho_waterway"]
        )
    ]
