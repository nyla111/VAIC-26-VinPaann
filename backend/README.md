# Mekong Delta Agri-Logistics Orchestrator Backend

Welcome to the backend API of the **Mekong Delta Agri-Logistics Orchestrator**. This backend is built using **FastAPI** (asynchronous) and **SQLModel** (SQLite ORM). It exposes a 2-Layer AI routing system and registers real-time inventory consolidation states, pushing them instantly to the dashboard over **WebSockets**.

---

## 🚀 Quick Start (Local Development)

### 1. Setup Virtual Environment
Run the following from the root directory to activate the environment and install dependencies:
```bash
cd backend
source .venv/bin/activate
# dependencies are already installed. If you need to rebuild:
# uv pip install -r requirements.txt
```

### 2. Start the Development Server
Run the live server using Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```
- **API Swagger Documentation**: Access the interactive docs at `http://127.0.0.1:8000/docs` to execute requests.
- **WebSocket Gateway**: Listen on `ws://127.0.0.1:8000/ws/status`.

### 3. Run the Test Suite
Ensure everything is verified:
```bash
pytest tests/test_api.py
```

---

## 🔌 API Endpoints (For Frontend Integration)

### 1. Route Optimizer (Layer 1)
* **Endpoint**: `POST /api/layer1/optimize`
* **Purpose**: Fetches 3 routing options for a shipment from a local hub to HCM City, indicating which one is recommended by AI.
* **Request Payload (`OptimizeRequest`)**:
  ```json
  {
    "hub_id": "An Giang",
    "cargo_type": "Fruit",
    "volume": 12.5,
    "urgency_level": "Medium",
    "weather": "Clear"
  }
  ```
* **Supported Options**:
  - `hub_id`: `"An Giang"`, `"Hau Giang"`, `"Soc Trang"`, `"Bac Lieu"`, `"Vinh Long"`, `"Dong Thap"`, `"Can Tho"`
  - `cargo_type`: `"Fruit"`, `"Vegetable"`, `"Seafood"`
  - `urgency_level`: `"Low"`, `"Medium"`, `"High"`
  - `weather`: `"Clear"`, `"Rainy"`, `"Stormy"` (defaults to `"Clear"`)
* **Response Payload (`List[RouteOption]`)**:
  ```json
  [
    {
      "route_id": "direct_road",
      "route_name": "Direct to HCM via Road",
      "estimated_cost": 437.5,
      "eta": 3.8,
      "recommendation_flag": false,
      "reason": "Recommended for balanced cost-savings via Can Tho consolidation."
    },
    {
      "route_id": "cantho_road",
      "route_name": "Via Can Tho Hub via Road",
      "estimated_cost": 275.0,
      "eta": 6.23,
      "recommendation_flag": true,
      "reason": "Recommended for balanced cost-savings via Can Tho consolidation."
    },
    {
      "route_id": "cantho_waterway",
      "route_name": "Via Can Tho Hub via Waterway",
      "estimated_cost": 132.5,
      "eta": 13.83,
      "recommendation_flag": false,
      "reason": "Recommended for low-cost, bulk agricultural cargo logistics."
    }
  ]
  ```

---

### 2. Route Selection
* **Endpoint**: `POST /api/hub/select-route`
* **Purpose**: Registers a hub's chosen route. If the route goes through Can Tho (`cantho_road` or `cantho_waterway`), cargo accumulates in the consolidation hub database and immediately triggers a Layer 2 background forecast.
* **Request Payload (`RouteSelectRequest`)**:
  ```json
  {
    "hub_id": "An Giang",
    "selected_route_id": "cantho_road",
    "cargo_type": "Fruit",
    "volume": 12.5,
    "weather": "Clear"
  }
  ```
* **Response Payload (`SystemState`)**:
  Returns the updated system state snapshot (see **SystemState** structure below).

---

### 3. Retrieve Can Tho Hub Status (Pull Fallback)
* **Endpoint**: `GET /api/hub/status`
* **Purpose**: Fetch the latest snapshot of inventory, logs, and dispatch state (useful for initial page load).
* **Response Payload (`SystemState`)**:
  ```json
  {
    "inventory": {
      "Fruit": 20.0,
      "Vegetable": 0.0,
      "Seafood": 0.0
    },
    "dispatch_status": "WAIT",
    "weather": "Clear",
    "logs": [
      {
        "timestamp": "2026-07-18 07:55:01",
        "message": "Weather Initialized: Setting state to Clear."
      },
      {
        "timestamp": "2026-07-18 07:56:12",
        "message": "Hub Incoming: Received 20.00 tons of Fruit from An Giang."
      }
    ],
    "last_updated": "2026-07-18 07:56:12"
  }
  ```

---

### 4. Simulator (Hackathon Judges Hook)
* **Endpoint**: `POST /api/hub/simulate-incoming`
* **Purpose**: Instantly generates a randomized incoming cargo shipment event (random cargo, random hub, random weather, and volume), optimizes the route, selects the recommended path, updates the SQLite database, and executes the Layer 2 dispatch logic. Pushes all updates to the WebSocket server in real-time.
* **Response Payload**:
  ```json
  {
    "message": "Simulation Event Triggered: Inbound cargo from Vinh Long.",
    "cargo_details": {
      "origin": "Vinh Long",
      "cargo_type": "Vegetable",
      "volume_tons": 18.4,
      "urgency": "Low",
      "weather": "Clear"
    },
    "optimized_decision": {
      "route_id": "cantho_road",
      "route_name": "Via Can Tho Hub via Road",
      "recommendation_reason": "Recommended for balanced cost-savings via Can Tho consolidation."
    },
    "current_system_state": { ... }
  }
  ```

---

## 📡 WebSockets Guide (Real-time Pushes)

To create a reactive, live dashboard that updates without refreshing:

1. **Connect to Websocket**:
   * **URL**: `ws://localhost:8000/ws/status`
2. **On Connection**:
   * The server immediately pushes the current `SystemState` payload.
3. **During Operations**:
   * The server will push a new `SystemState` JSON string **every time**:
     - Cargo is added to the consolidation inventory.
     - Global weather conditions update.
     - The Layer 2 background checker evaluates and triggers a `WAIT` or `DISPATCH` state (when dispatching, inventory clears to `0`).

---

## 🧠 Extensibility (For AI Teammates)

The ML prediction models are completely isolated from the routes. AI developers can import libraries like `joblib` or `onnxruntime` and replace the placeholder logic inside:
* **Layer 1 Routing**: Edit `predict_routes()` in `app/ai/layer1_helper.py`
* **Layer 2 Dispatching**: Edit `evaluate_dispatch()` in `app/ai/layer2_helper.py`
* Models can be dropped into a `backend/models/` folder.
