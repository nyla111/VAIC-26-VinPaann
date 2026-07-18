import os

# SQLite database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///agri_orchestrator.db")

# CORS Settings - allow all for hackathon convenience, configurable for production
CORS_ORIGINS = ["*"]

# Dispatch threshold in kg for Can Tho consolidation hub (50.0 tons = 50,000 kg)
CANTHO_DISPATCH_THRESHOLD_KG = 50000.0

# Supported cargo priority tiers, hubs, and weather types
CARGO_TYPES = ["seafood", "vegetable", "hard_fruit", "grain_dry"]
HUBS = ["HUB_VITHANH", "HUB_LONGXUYEN", "HUB_SOCTRANG", "HUB_VINHLONG", "CT_HUB"]
WEATHER_CONDITIONS = ["Clear", "Rainy", "Stormy"]

