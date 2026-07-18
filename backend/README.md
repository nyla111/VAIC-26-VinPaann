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
pytest tests/
```

---

## Multiple Views Frontend Architecture Support

The backend fully supports building two decoupled frontend views/sites running on separate hosts or ports (e.g., Customer Portal on Port 3000 and Can Tho Hub Admin Portal on Port 3001). Cross-Origin Resource Sharing (CORS) is enabled (`*`) to allow seamless cross-port communication.

### View 1: Customer / Sender Portal
Allows provincial senders to submit cargo parameters, get recommended routes from **Layer 1 AI Route Optimizer**, and select a route.
* **Flow**:
  1. Customer inputs parameters -> calls `POST /api/layer1/optimize`.
  2. Frontend displays the 5 comparison cards.
  3. Customer clicks "Select Route" -> calls `POST /api/hub/select-route` with the `order_id` and chosen `selected_route_id`.

### View 2: Can Tho Hub Admin Portal
Allows logistics supervisors to view consolidated inventory, track weather warnings, view rolling demand forecasts, check auto-dispatch decisions, and override environment parameters.
* **Flow**:
  1. Open Dashboard -> Connects to WebSocket `/ws/status` to receive live inventory levels and system logs.
  2. Call `GET /api/layer2/dispatch-status` and `GET /api/layer2/forecast` to fetch AI recommendations and rolling-demand graphs.
  3. (Optional) Dispatchers can manually override vehicle statuses or weather events.

---

## Timezone Management (Important GMT+7 Guidelines)

To prevent visual inconsistencies (such as 7-hour timezone shift issues for local judges), both backend algorithms and frontend rendering must align on the ISO 8601 standard:

1. **Storage and Database (UTC)**:
   * The backend strictly calculates and saves database records (`Order.timestamp`, `Order.actual_arrival_at`, and `predicted_full_load_time`) in the **UTC (+00:00)** timezone.
2. **Frontend Requests (GMT+7 Offset)**:
   * When submitting payloads containing date/time strings (e.g., to `/api/layer1/optimize` or `/api/hub/select-route`), the frontend MUST format dates using ISO 8601 with the local timezone offset representation, e.g., `2026-07-18T17:30:00+07:00`.
3. **Frontend Display (GMT+7 Conversion)**:
   * When receiving ISO datetime strings from backend APIs or WebSocket streams (e.g., `"predicted_full_load_time": "2026-07-18T11:00:00+00:00"`), the frontend MUST convert them to the user's local timezone.
   * *JavaScript Example*:
     ```javascript
     const utcDateStr = "2026-07-18T11:00:00+00:00";
     const localTime = new Date(utcDateStr).toLocaleTimeString("vi-VN"); 
     // Will correctly output "18:00:00" in Vietnam Timezone (+07:00)
     ```

---

## API Endpoints Reference

### 1. Route Optimizer (Layer 1)
* **Endpoint**: `POST /api/layer1/optimize`
* **Request Payload (`RouteOptimizeRequest`)**:
  ```json
  {
    "order_id": null,
    "hub_id": "HUB_VINHLONG",
    "commodity_id": "COM_VEGETABLE",
    "loai_hang": "rau_mau",
    "khoi_luong_kg": 3495.7,
    "timestamp": "2026-07-18T17:42:00+07:00",
    "deadline_ts": "2026-07-19T17:42:00+07:00"
  }
  ```
* **Response Payload (`RouteOptimizeResponse`)**:
  Returns 5 comparison routes (A-E) showing transport costs, handling fees, predicted spoilage costs, and availability. Includes the dynamic auto-generated `order_id` in SQLite.

---

### 2. Route Selection
* **Endpoint**: `POST /api/hub/select-route`
* **Purpose**: Locks in the customer's route choice.
  * If the route goes through Can Tho (`B` to `E` codes), the order is saved in the state `routed_to_can_tho`, and a **Background Task** is initiated to simulate travel.
  * After **3 seconds** (simulated travel time for demo), the order state changes to `arrived_waiting`, its weight is added to Can Tho's inventory, and the **Layer 2 Decision Engine** is automatically triggered to evaluate dispatch choices.
* **Request Payload (`RouteSelectRequest`)**:
  ```json
  {
    "hub_id": "HUB_VINHLONG",
    "selected_route_id": "B_ROAD_VIA_CT",
    "cargo_type": "vegetable",
    "volume": 3495.7,
    "weather": "Clear",
    "order_id": "1"
  }
  ```

---

### 3. Layer 2 Forecast & Dispatch Status
* **Get Forecast**: `GET /api/layer2/forecast?outbound_mode=road`
  * Returns rolling accumulation demand forecast buckets (30-minute steps up to 6 hours) and predicts the exact datetime the target vehicle will be full.
* **Get Dispatch Status**: `GET /api/layer2/dispatch-status?outbound_mode=road`
  * Evaluates constraints (vehicle, route weather blocks, maximum safe waiting hours for produce, and fill capacity).
  * Returns the current decision: `DISPATCH_NOW`, `WAIT_FOR_LOAD`, or `WAIT_FOR_VEHICLE` along with detailed priority score components (`fill`, `urgency`, `weather`).
  * If `DISPATCH_NOW`, it provides a concrete `dispatch_order_proposal` assigning waiting shipment IDs to a selected vehicle.

---

### 4. Admin Event Overrides (Demo Scenarios)
* **Update Vehicle Status**: `POST /api/layer2/events/vehicle-status`
  * Registers or changes Can Tho fleet availability parameters.
* **Update Weather Override**: `POST /api/layer2/events/weather-update`
  * Simulates natural disaster blocks (floods, rain, storm indexes) to test routing flexibility and alert triggers.

---

## WebSockets Guide (Real-time Dashboard Status)

Connect to the WebSocket gateway at:
```text
ws://localhost:8000/ws/status
```

* **On Initial Connection**: The server instantly pushes a JSON snapshot of the consolidated `SystemState`.
* **State Updates**: Whenever a shipment changes state (`routed_to_can_tho` -> `arrived_waiting` -> `dispatched`), a new `SystemState` message is pushed to all listening clients, allowing both the Customer site and the Can Tho Hub Admin site to refresh dynamically.
