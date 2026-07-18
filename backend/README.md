# Mekong Delta Agri-Logistics Orchestrator Backend

Welcome to the backend API of the **Mekong Delta Agri-Logistics Orchestrator**. This backend is built using **FastAPI** (asynchronous) and **SQLModel** (SQLite ORM). It exposes a 2-Layer AI routing system and registers real-time inventory consolidation states, pushing them instantly to the dashboard over **WebSockets**.

---

## Quick Start (Local Development)

### 1. Setup Virtual Environment
Run the following from the `backend/` directory to activate the environment and run setup:
```bash
cd backend
source .venv/bin/activate
# Dependencies are already installed. If you need to rebuild/install new packages:
# pip install -r requirements.txt
```

### 2. Start the Development Server
Run the live server using Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```
* **API Swagger Documentation**: Access the interactive docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to test the endpoints.
* **WebSocket Gateway**: Connect at `ws://127.0.0.1:8000/ws/status`.

### 3. Run the Test Suite
Ensure the backend services are fully operational:
```bash
pytest tests/test_api.py
```

---

## Configuration Settings (`app/config.py`)

* **Supported Hubs**: `HUB_VITHANH`, `HUB_LONGXUYEN`, `HUB_SOCTRANG`, `HUB_VINHLONG`, `CT_HUB`
* **Supported Cargo Types / Priority Tiers**: `seafood`, `vegetable`, `hard_fruit`, `grain_dry`
* **Supported Weather Conditions**: `Clear`, `Rainy`, `Stormy`
* **Can Tho Dispatch Threshold**: `50,000.0 kg` (50 tons)

---

## API Endpoints

### 1. Root Status
* **Endpoint**: `GET /`
* **Purpose**: Quick check to verify if the server is running.
* **Response Example**:
  ```json
  {
    "project": "Mekong Delta Agri-Logistics Orchestrator",
    "region": "Đồng bằng sông Cửu Long (ĐBSCL) to HCMC",
    "architecture": "2-Layer AI Consolidation Loop",
    "docs_url": "/docs",
    "status": "Operational"
  }
  ```

---

### 2. Route Optimizer (Layer 1)
* **Endpoint**: `POST /api/layer1/optimize`
* **Purpose**: Evaluates agricultural cargo parameters, saves the order dynamically in SQLite, runs the predictive models, and returns 5 routing options indicating which is recommended.
* **Request Payload (`RouteOptimizeRequest`)**:
  ```json
  {
    "order_id": null, 
    "hub_id": "HUB_VINHLONG",
    "commodity_id": "COM_VEGETABLE",
    "loai_hang": "rau_mau",
    "khoi_luong_kg": 3495.7,
    "timestamp": "2026-01-01T09:58:52+07:00",
    "deadline_ts": "2026-01-01T23:27:12+07:00"
  }
  ```
* **Response Payload (`RouteOptimizeResponse`)**:
  ```json
  {
    "hub_id": "HUB_VINHLONG",
    "priority": {
      "tier": "vegetable",
      "score": 0.8,
      "label": "High Spoilage Risk"
    },
    "recommended_route": "B_ROAD_VIA_CT",
    "phuong_an": [
      {
        "ten": "Đường bộ đi thẳng HCM",
        "route_code": "A_DIRECT_ROAD",
        "chi_phi_du_doan_vnd": 4500000.0,
        "thoi_gian_du_kien_gio": 3.5,
        "trang_thai": "available",
        "ly_do": null,
        "cost_breakdown": {
          "raw_transport_cost_vnd": 3800000.0,
          "spoilage_cost_vnd": 700000.0,
          "transshipment_fee_vnd": 0.0,
          "total_cost_vnd": 4500000.0,
          "pricing_source": "dynamic_routing_model"
        }
      },
      {
        "ten": "Đường bộ qua trung chuyển Cần Thơ",
        "route_code": "B_ROAD_VIA_CT",
        "chi_phi_du_doan_vnd": 3200000.0,
        "thoi_gian_du_kien_gio": 5.0,
        "trang_thai": "available",
        "ly_do": null,
        "cost_breakdown": {
          "raw_transport_cost_vnd": 2500000.0,
          "spoilage_cost_vnd": 500000.0,
          "transshipment_fee_vnd": 200000.0,
          "total_cost_vnd": 3200000.0,
          "pricing_source": "dynamic_routing_model"
        }
      }
      // ... up to 5 routes matching RouteCode literals
    ],
    "khuyen_nghi": "duong_bo_qua_can_tho",
    "evidence": {
      "weather_ts": "2026-01-01 09:00:00",
      "price_ts": "2026-01-01 09:00:00"
    },
    "order_id": "1"
  }
  ```
* **Supported `RouteCode` literals**:
  - `A_DIRECT_ROAD` (Direct Road to HCM)
  - `B_ROAD_VIA_CT` (Road to CT Hub, then Road to HCM)
  - `C_WATER_ROAD_VIA_CT` (Waterway to CT Hub, then Road to HCM)
  - `D_WATER_VIA_CT` (Waterway to CT Hub, then Waterway to HCM)
  - `E_ROAD_WATER_VIA_CT` (Road to CT Hub, then Waterway to HCM)

---

### 3. Route Selection
* **Endpoint**: `POST /api/hub/select-route`
* **Purpose**: Registers a hub's final route choice. If the route passes through Can Tho (`B_ROAD_VIA_CT`, `C_WATER_ROAD_VIA_CT`, `D_WATER_VIA_CT`, `E_ROAD_WATER_VIA_CT`), the cargo is added to the consolidation inventory. Triggers a background evaluation of the Layer 2 dispatch logic.
* **Request Payload (`RouteSelectRequest`)**:
  ```json
  {
    "hub_id": "HUB_VINHLONG",
    "selected_route_id": "B_ROAD_VIA_CT",
    "cargo_type": "vegetable",
    "volume": 2000.0,
    "weather": "Clear"
  }
  ```
* **Response Payload (`SystemState`)**: Returns the updated system state snapshot.

---

### 4. Can Tho Hub Status (Pull Fallback)
* **Endpoint**: `GET /api/hub/status`
* **Purpose**: Retrieve the current consolidated status (inventory, weather, logs, and dispatch state).
* **Response Example (`SystemState`)**:
  ```json
  {
    "inventory": {
      "seafood": 12500.0,
      "vegetable": 2000.0,
      "hard_fruit": 0.0,
      "grain_dry": 0.0
    },
    "dispatch_status": "WAIT",
    "weather": "Clear",
    "logs": [
      {
        "timestamp": "2026-07-18 16:30:00",
        "message": "Hub Incoming: Received 2000.00 kg of vegetable from HUB_VINHLONG."
      }
    ],
    "last_updated": "2026-07-18 16:30:00"
  }
  ```

---

### 5. Simulator Hook
* **Endpoint**: `POST /api/hub/simulate-incoming`
* **Purpose**: Utility for testing or demo purposes. Generates a randomized shipment from a provincial hub, queries the Layer 1 Optimizer, selects the recommended route, and runs the entire Layer 2 dispatch pipeline.
* **Response Example**:
  ```json
  {
    "message": "Simulation Event Triggered: Inbound cargo from HUB_VINHLONG.",
    "cargo_details": {
      "origin": "HUB_VINHLONG",
      "cargo_type": "seafood",
      "volume_kg": 14230.5,
      "weather": "Clear"
    },
    "optimized_decision": {
      "route_id": "B_ROAD_VIA_CT",
      "route_name": "duong_bo_qua_can_tho",
      "recommendation_reason": "Recommended by Layer 1 actual Optimizer model"
    },
    "current_system_state": { ... }
  }
  ```

---

## WebSockets Guide (Real-time Pushes)

To construct reactive frontends without periodic API polling:

1. **Connect**: Open a persistent WebSocket connection to `ws://localhost:8000/ws/status`.
2. **On Initial Connection**: The server immediately sends a snapshot of the current `SystemState` JSON.
3. **On state update**: The server broadcasts a new `SystemState` message to all connected clients whenever:
   - Cargo is accumulated at the hub.
   - The weather state changes.
   - The dispatch process transitions (e.g. dispatch threshold met -> state becomes `DISPATCH` and inventories are cleared to `0.0`).

---

## Extensibility

The ML predictive components are isolated from the routers to ease modular upgrades:
* **Layer 1 Optimization**: Logic is located in [optimizer.py](file:///mnt/data/VAIC/backend/app/ai/route_optimizer/optimizer.py), [pricing.py](file:///mnt/data/VAIC/backend/app/ai/route_optimizer/pricing.py), and [feasibility.py](file:///mnt/data/VAIC/backend/app/ai/route_optimizer/feasibility.py).
* **Layer 2 Dispatch State Management**: Configured inside [state.py](file:///mnt/data/VAIC/backend/app/state.py).
