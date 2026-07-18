import os

# SQLite database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///agri_orchestrator.db")

# CORS Settings - allow all for hackathon convenience, configurable for production
cors_env = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [orig.strip() for orig in cors_env.split(",") if orig.strip()]

# Dispatch threshold in kg for Can Tho consolidation hub (50.0 tons = 50,000 kg)
CANTHO_DISPATCH_THRESHOLD_KG = 50000.0

# Supported cargo priority tiers, hubs, and weather types
CARGO_TYPES = ["seafood", "vegetable", "hard_fruit", "grain_dry"]
HUBS = ["HUB_VITHANH", "HUB_LONGXUYEN", "HUB_SOCTRANG", "HUB_VINHLONG", "CT_HUB"]
WEATHER_CONDITIONS = ["Clear", "Rainy", "Stormy"]

# Pre-defined user accounts for dashboard login
USERS = {
    "business1": {"password": "demo123", "role": "business", "name": "Business Demo"},
    "logistics1": {"password": "demo123", "role": "logistics", "name": "Logistics Demo"},
    "admin1": {"password": "demo123", "role": "admin", "name": "Admin Demo"},
    "opslead": {"password": "demo123", "role": "admin", "name": "Ops Lead"},
}


