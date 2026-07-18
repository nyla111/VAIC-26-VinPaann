import os

# SQLite database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///agri_orchestrator.db")

# CORS Settings - allow all for hackathon convenience, configurable for production
CORS_ORIGINS = ["*"]

# Dispatch threshold in tons for Can Tho consolidation hub
CANTHO_DISPATCH_THRESHOLD_TONS = 50.0

# Supported cargo types, hubs, and weather types
CARGO_TYPES = ["Fruit", "Vegetable", "Seafood"]
HUBS = ["An Giang", "Hau Giang", "Can Tho", "Soc Trang", "Bac Lieu", "Vinh Long", "Dong Thap"]
WEATHER_CONDITIONS = ["Clear", "Rainy", "Stormy"]
