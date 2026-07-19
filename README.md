# Mekong Delta Agri-Logistics Orchestrator

The **Mekong Delta Agri-Logistics Orchestrator (ALO)** is a web-based decision support system designed to optimize the transportation of agricultural products from the Mekong Delta region (Đồng bằng Sông Cửu Long) to Ho Chi Minh City. By combining multi-modal transportation (road and waterway) and a 2-Layer AI decision-making pipeline, the system aims to:
- Minimize overall shipping costs.
- Reduce food spoilage (perishability management) through time-sensitivity and safe wait constraints.
- Maximize vehicle fleet utilization (fill ratio) through automated cargo consolidation at the Can Tho Hub.

---

## 1. Technology Stack & Component Architecture

The system is designed as an event-driven client-server architecture with real-time push synchronization using WebSockets.

### Tech Stack Details
- **Backend (FastAPI)**:
  - **Python 3 / FastAPI**: High-performance, asynchronous web framework for building APIs and WebSockets.
  - **SQLModel & SQLite**: SQLModel ORM (combining SQLAlchemy & Pydantic) interacting with a lightweight SQLite database.
  - **Uvicorn**: High-performance ASGI web server.
- **Frontend (Next.js)**:
  - **Next.js (App Router) & React & TypeScript**: Premium SPA interface utilizing role-scoped dashboards.
  - **Leaflet & OpenStreetMap**: Interactive mapping library to render nodes, route paths, polylines, and real-time vehicle movement.
  - **WebSockets**: Permanent client-server communication channels to push system updates in real time.

### Component Architecture Diagram

```
                       +---------------------------------------------+
                       |              FRONTEND NEXT.JS               |
                       |  (Enterprise / Admin / Logistics Dashboards) |
                       +------+------------------^--------------+----+
                              |                  |              |
                    HTTP API  |       WebSockets |     HTTP API |
                    Requests  |       Real-Time  |      Request |
                   (REST)     |       Streaming  |     (Auth)   |
                              v                  |              v
     +------------------------+------------------+--------------+------------------+
     |                                                                             |
     |                              BACKEND FASTAPI                                |
     |                                                                             |
     |  +--------------------+   +--------------------+   +---------------------+  |
     |  |   Auth Router &    |   |     Layer 1 / 2    |   |   Websocket Router  |  |
     |  |   Session Cookie   |   |     API Routers    |   |   & Connection Mgr  |  |
     |  +---------+----------+   +---------+----------+   +----------+----------+  |
     |            |                        |                         ^             |
     |            |                        v                         |             |
     |            |            +-----------+-----------+             |             |
     |            |            |   AI Decision Engine  |             |             |
     |            |            |  - Layer 1 Optimizer  |             |             |
     |            v            |  - Layer 2 Forecaster |             |             |
     |   +--------+--------+   +-----------+-----------+             |             |
     |   | SQLModel ORM &  |<--------------+                         |             |
     |   | SQLite Database |               |                         |             |
     |   +--------+--------+               |                         |             |
     |            |                        v                         |             |
     |            |           +------------+------------+            |             |
     |            +-----------+   Background Supervisors|            |             |
     |                        |   - Simulation Clock    +------------+             |
     |                        |   - Layer 2 Supervisor  |                          |
     |                        +-------------------------+                          |
     +-----------------------------------------------------------------------------+
```

---

## 2. Database Schema Specification

All transactional and state information is persisted in SQLite via SQLModel definitions:

1. **User Table**:
   - `id`: Primary key.
   - `email`: Unique email address.
   - `password_hash`: Raw password string (used for hackathon verification).
   - `role`: Scoped access roles (`"enterprise"`, `"logistics"`, or `"admin"`).

2. **Order Table (The Inbound & Outbound Shipment Entity)**:
   - `id`: Order ID.
   - `hub_id`: Origin collection hub (`HUB_VITHANH`, `HUB_LONGXUYEN`, `HUB_SOCTRANG`, `HUB_VINHLONG`).
   - `commodity_id` / `loai_hang`: Agricultural commodity code (e.g. `COM_RICE`, `COM_PANGASIUS`, `COM_SHRIMP`, `COM_POMELO`) and raw Vietnamese name.
   - `khoi_luong_kg`: Cargo weight in kilograms.
   - `state`: Lifecycle state (`created` -> `routed_to_can_tho` -> `arrived_waiting` -> `dispatched` -> `delivered`).
   - `user_id`: ID of the Enterprise account that placed the order.
   - `assigned_vehicle_id`: License plate of the assigned transport vehicle.
   - `assigned_provider_id`: ID of the logistics provider managing the transport.
   - `provider_assignment_status`: Transport booking status (`unassigned`, `assigned`, `accepted`, `rejected`, `dispatched`).
   - **Layer 1 Snapshots**: `route_options_json` (JSON list of calculated paths), `selected_route_id` (the selected RouteCode), `selected_route_cost_vnd`, `selected_route_eta_hours`, `selected_route_geometry_json`.
   - **Layer 2 Snapshots**: `predicted_full_load_time` (estimated time when the outbound vehicle is full), `reason_codes_json` (Layer 2 decision codes), `priority_score_json` (calculated Priority Score components), `dispatch_proposal_id` (ID of the outbound DispatchOrder), `eta_can_tho` / `actual_arrival_at`.

3. **DispatchOrder Table (The Outbound Voyage Entity)**:
   - `id`: Primary key.
   - `proposal_id`: Unique proposal hash representing one consolidated chặng ngoài dispatch.
   - `vehicle_id`: License plate of the assigned vehicle.
   - `outbound_mode`: Mode of transport (`road` or `water`).
   - `shipment_ids_json`: JSON array of Order IDs consolidated in this shipment.
   - `total_weight_kg` / `capacity_kg`: Consolidated weight vs vehicle cargo capacity.
   - `fill_ratio`: Ratio of consolidated weight to vehicle capacity ($=\text{total\_weight\_kg} / \text{capacity\_kg}$).
   - `status`: Outbound journey status (`waiting_for_pickup` -> `dispatching_to_hcm` -> `completed`).
   - `dispatched_at` / `eta_hcm`: Actual departure time and expected arrival time in Ho Chi Minh City.

4. **Vehicle Table**:
   - `license_plate`: License plate of the truck or barge (Primary Key).
   - `provider_id`: ID of the logistics provider who owns the vehicle.
   - `mode`: Vehicle transport type (`road` or `water`).
   - `capacity_kg`: Payload limit in kilograms.
   - `status`: Current status (`available`, `en_route`, `in_transit`, `maintenance`).
   - `location`: Current node location (`can_tho` or origin hubs).
   - `supports_refrigeration`: Boolean indicating if the vehicle supports temperature control (reefer) for seafood and vegetables.
   - `current_lat` / `current_lng`: Geocoordinates for live map markers.

5. **CargoInventory Table**:
   - `cargo_type`: Category of consolidated inventory (`seafood`, `vegetable`, `grain_dry`, `hard_fruit`).
   - `volume`: Total weight (kg) currently stored at the Can Tho Hub.

6. **SystemLog Table**:
   - Logs of decisions, weather updates, alerts, and model errors.

---

## 3. End-to-End Business Logic Flows

The orchestrator operates through five main integrated business flows:

### Flow 1: Order Placement & Layer 1 Route Optimization

*Goal: Evaluates constraints and computes cost-optimal path configurations from provincial hubs to HCMC.*

```
+------------+      Place Shipment      +-------------+      Query Data       +--------------+
| Enterprise | ----------------------> | Backend API | ---------------------> |  DataStore   |
| (Producer) |  (Weight, Deadline)     |             |  (Weather, Legs, Fuel) | (Static CSVs)|
+------------+                         +------+------+                        +------+-------+
                                              |                                      |
                                              | Forward Order ID                     | Return static
                                              v                                      v
                                       +------+------+                        +------+-------+
                                       |  Layer 1    | <---------------------+  Evaluate     |
                                       |  Optimizer  |  Feasibility checks   | constraints  |
                                       +------+------+  Weather, Tide & Loss  +--------------+
                                              |
                                              | Compute Costs & Durations
                                              v
                                       +------+------+      Return Options     +--------------+
                                       | Pricing &   | ----------------------> | Save Order   |
                                       | Spoilage    | (VND, Hours, Routes)   | in SQLite DB |
                                       +-------------+                        +--------------+
```

1. **Submission**: An Enterprise user submits a cargo request specifying: Origin hub, Commodity type, Weight (kg), Harvest timestamp, and Delivery deadline.
2. **Execution**:
   - The backend creates an Order record in SQLite with a `created` state.
   - The Layer 1 Optimizer (`optimize_route`) is triggered, loading network topology nodes, legs, and weather time-series records.
3. **Feasibility Validation**:
   - For each of the 5 possible candidate corridors (Direct or via Can Tho transshipment):
     - **Waterway check**: If the commodity does not support waterway transit (e.g. `water_ok = False`) or if active water bulletins report unsafe conditions (`tuyen_duong_thuy_khong_an_toan`), water legs are marked unavailable.
     - **Weather check**: If the trạm khí tượng reports road/river blockages due to storms or flooding, the respective leg is flagged as `currently_unavailable`.
     - **Deadline check**: If the adjusted travel duration (base duration multiplied by weather delay factors) exceeds the delivery deadline, the route is marked `vuot_deadline`.
4. **Cost Model Evaluation**:
   - **Freight Cost**: Calculated from fixed pricing sheets matching the origin leg and vehicle type. If no direct rate exists, the model falls back to fuel prices (Marine Diesel / Diesel 0.05S) multiplied by distance and fuel factor.
   - **Spoilage Cost**: Calculated based on the commodity value per kg, hourly perishability loss percentage, cargo weight, and travel duration.
   - **Transshipment Fee**: Adds a fixed handling fee of $150.0$ VND/kg if the route requires transshipment at the Can Tho Hub.
5. **Recommendation**: The route with the lowest sum of Freight + Spoilage + Transshipment costs is selected as the recommended path (`recommended_route`). The options are stored in the database as a JSON snapshot (`route_options_json`).

---

### Flow 2: Route Confirmation & Inbound Transit

*Goal: Enterprise confirms route recommendations and dispatches cargo from provincial hubs to Can Tho Hub.*

1. **Route Confirmation**: The Enterprise selects a route and submits a confirmation (`/select-route` or WebSocket `CONFIRM_ROUTE`).
2. **Inbound Dispatch**:
   - **Via Can Tho Hub**:
     - The order state updates to `routed_to_can_tho`.
     - The system queries for an `available` vehicle at Can Tho matching the inbound transit mode. If found, it links the vehicle to the order, changes the vehicle status to `en_route`, and shifts its location to the origin hub.
     - The expected arrival time at Can Tho (`eta_can_tho`) is computed based on the inbound leg duration.
   - **Direct Road to HCM (`A_DIRECT_ROAD`)**:
     - The order state shifts to `dispatched`.
     - `create_direct_dispatch` assigns an available vehicle, changes its status to `in_transit`, creates a direct `DispatchOrder` record, and estimates the final delivery time (`eta_hcm`).

---

### Flow 3: Simulation Clock Tick & Inbound Arrival

*Goal: Runs a background process-local timer to simulate cargo movement and arrival events.*

```
                       +------------------------------+
                       |   Simulation Loop (Every 10s) |
                       +--------------+---------------+
                                      |
                                      | Increment Virtual Time (SYSTEM_CLOCK)
                                      v
                       +--------------+---------------+
                       | Check 'routed_to_can_tho' DB  |
                       +--------------+---------------+
                                      |
                                      +----> [ If SYSTEM_CLOCK >= eta_can_tho ]
                                      |
                                      v
                       +--------------+---------------+
                       | 1. State -> 'arrived_waiting'|
                       | 2. Reset vehicle to available|
                       | 3. Add weight to Can Tho Hub |
                       |    CargoInventory metrics    |
                       +--------------+---------------+
                                      |
                                      v
                       +--------------+---------------+
                       | Trigger Layer 2 Decision     |
                       |  (Gom hàng outbound to HCM)  |
                       +------------------------------+
```

1. **Time Advancement**: A background loop `run_simulation_loop` runs every 10 seconds, advancing the `SYSTEM_CLOCK` by `TIME_ACCELERATION_FACTOR` hours.
2. **Inbound Arrival Handling**:
   - The loop queries the database for orders in the `routed_to_can_tho` state where `eta_can_tho` is older than or equal to `SYSTEM_CLOCK`.
   - It transitions these orders to the `arrived_waiting` state.
   - It resets the assigned inbound vehicle to `available` and marks its location as `can_tho`.
   - It identifies the commodity classification and increases the corresponding `CargoInventory` volume at the Can Tho Hub.
   - It logs the arrival event in `SystemLog`.
3. **Outbound Arrival Handling**:
   - It queries for active `DispatchOrder` records.
   - If the clock passes the departure time, it updates the dispatch status to `dispatching_to_hcm` and the vehicle status to `en_route`.
   - When the clock reaches `eta_hcm`, the dispatch status is updated to `completed`, all associated orders are set to `delivered`, and the vehicle returns to `available` at `can_tho`.
4. **Trigger**: If any status changes occur, the loop automatically triggers the Layer 2 Decision Engine.

---

### Flow 4: Layer 2 Forecasting, Decision Engine & Outbound Dispatch

*Goal: Automatically evaluates consolidation levels at the Can Tho Hub and triggers dispatches to TP.HCM.*

```
                 +-------------------------------------------------+
                 |        Layer 2 Supervisor (Every 5 seconds)     |
                 +-----------------------+-------------------------+
                                         |
                                         | Run evaluation loop
                                         v
                 +-----------------------+-------------------------+
                 |    decision_engine.evaluate(ROAD / WATER)      |
                 +-----------------------+-------------------------+
                                         |
                 +-----------------------+-------------------------+
                 | 1. Select available vehicle at Can Tho Hub      |
                 | 2. Build 6-hour forecast (known + predicted)    |
                 +-----------------------+-------------------------+
                                         |
                 +-----------------------+-------------------------+
                 | Evaluate Hard Constraints                       |
                 | - Vehicle unavailable? -> WAIT                  |
                 | - Weather blocked? -> WAIT                      |
                 | - Safe wait limit reached? -> DISPATCH NOW      |
                 | - Vehicle fully loaded? -> DISPATCH NOW         |
                 +-----------------------+-------------------------+
                                         |
                                         | Hard constraints not breached
                                         v
                 +-----------------------+-------------------------+
                 | Calculate Priority Score:                       |
                 | S = 0.55 * Fill + 0.35 * Urgency + 0.1 * Weather|
                 +-----------------------+-------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
           [ S >= Threshold 0.75 ]                 [ S < Threshold 0.75 ]
                       v                                   v
        +--------------+--------------+             +------+------+
        | DECISION: DISPATCH_NOW      |             | DECISION:    |
        | - Create DispatchOrder      |             | WAIT_FOR_LOAD|
        | - Transition orders to disp |             | (Keep waiting|
        | - Deduct Can Tho inventory  |             | for more cargo)
        +-----------------------------+             +--------------+
```

1. **Evaluation Cycle**: The `run_layer2_supervisor` loop evaluates the database state every 5 seconds for the **Road** and **Water** pipelines.
2. **Vehicle Selection**:
   - Queries available vehicles at Can Tho Hub. If reefer transport is required by any pending shipment, it selects a vehicle supporting refrigeration.
   - If the total pending weight is within a single vehicle's limit, it selects the smallest vehicle that can hold the load (optimizing fill ratio). If no single vehicle can fit the load, it selects the largest available vehicle.
3. **Hybrid Forecasting**:
   - The forecaster `build_forecast` projects cargo accumulation over a 6-hour horizon (in 30-minute buckets):
     $$L_{\text{cumulative}} = L_{\text{arrived}} + L_{\text{inbound}} + L_{\text{predicted}}$$
     - $L_{\text{arrived}}$: Cumulative weight of orders currently at Can Tho.
     - $L_{\text{inbound}}$: Weight of orders in transit to Can Tho (calculated via inbound ETAs).
     - $L_{\text{predicted}}$: Estimated cargo arrival based on historic averages (`rolling_mean_kg_per_bucket`).
   - The engine calculates the `predicted_full_load_time` when the selected vehicle is expected to be full.
4. **Hard Constraints Check**:
   - **No vehicle**: If no suitable vehicle is available, decision is `WAIT_FOR_VEHICLE`.
   - **Weather block**: If outbound bulletins indicate closed highways or rivers due to weather/floods, decision is `WAIT_FOR_LOAD` with code `WEATHER_BLOCKED`.
   - **Safe Wait breach**: If the elapsed time since harvest/creation for any order exceeds its commodity's `max_safe_wait_hours` (e.g. seafood waits less than rice), it forces dispatch: `DISPATCH_NOW` with code `SAFE_WAIT_LIMIT_REACHED`.
   - **Fully loaded**: If the current load matches or exceeds the vehicle capacity, it forces dispatch: `DISPATCH_NOW` with code `VEHICLE_FULL`.
5. **Priority Score Calculation**:
   - If no hard constraints force an action, the engine computes a weighted score:
     $$\text{Priority Score} = \alpha_{\text{fill}} \cdot \text{FillRatio} + \beta_{\text{urgency}} \cdot \text{UrgencyRatio} + \gamma_{\text{weather}} \cdot \text{WeatherRisk}$$
     *(Weights config: $\alpha=0.55$, $\beta=0.35$, $\gamma=0.10$)*
   - If $\text{Priority Score} \ge 0.75$, the decision is `DISPATCH_NOW`.
   - Otherwise, the decision is `WAIT_FOR_LOAD` with the suggested departure time set to `predicted_full_load_time`.
6. **Execution**: On a `DISPATCH_NOW` decision:
   - A `DispatchOrder` is created with state `waiting_for_pickup` and departure details.
   - Associated orders are transitioned to `dispatched` and linked to the dispatch ID.
   - The consolidated cargo weight is deducted from the hub's `CargoInventory`.
   - The vehicle status is set to `in_transit`.

---

### Flow 5: Logistics Partner Portal Operations

*Goal: Enables third-party logistics companies to manually book orders, dispatch fleets, and forecast capacity.*

1. **Order Acceptance**: Logistics providers view available orders at Can Tho Hub (`/orders`). They can accept an order and assign one of their available vehicles (`/orders/{order_id}/accept`), shifting the order status to `accepted`.
2. **Manual Dispatch**: The provider selects a batch of accepted orders, links them to the assigned vehicle, and dispatches them (`/orders/dispatch`). This updates the orders to `dispatched`, deducts cargo weight from `CargoInventory`, and creates a `DispatchOrder`.
3. **Fleet Demand Forecasting**:
   - Providers query capacity forecasts (`/fleet/forecast`) for a future date.
   - The backend calculates the sum of cargo weight arriving on that date (via inbound order ETAs) plus historical averages to forecast demand.
   - It compares this demand against the provider's active fleet capacity to calculate the `capacity_gap_kg` and alert the provider to dispatch more vehicles.

---

## 4. Codebase Directory Map

### Backend Layout (`/backend`)

```
backend/
├── app/
│   ├── ai/
│   │   ├── forecast_dispatch/      # Layer 2 Consolidation & Forecasting (AI2)
│   │   │   ├── data_loader.py       # Loads commodity profiles and outbound weather data
│   │   │   ├── decision_engine.py   # Computes hard constraints and Priority Scores
│   │   │   ├── enums.py             # Order states, vehicle statuses, and reason codes
│   │   │   ├── forecasting.py       # Implements 6-hour rolling-mean accumulation forecasts
│   │   │   ├── main.py              # Main execution loops for Layer 2 evaluation
│   │   │   ├── schemas.py           # Pydantic schemas for Layer 2 requests/responses
│   │   │   └── state_store.py       # Translates database tables to AI evaluation objects
│   │   ├── route_optimizer/         # Layer 1 Routing Optimization (AI1)
│   │   │   ├── candidates.py        # Generates candidate paths (direct & transshipment)
│   │   │   ├── data_loader.py       # Loads CSV database files (pricing, weather, fuel)
│   │   │   ├── feasibility.py       # Evaluates weather, tide, and deadline feasibility
│   │   │   ├── optimizer.py         # Entry point for Layer 1 route optimizer
│   │   │   ├── pricing.py           # Evaluates freight, spoilage, and transshipment costs
│   │   │   └── schemas.py           # API schemas for Layer 1
│   │   └── normalizers.py           # Commodity classification helpers
│   ├── routes/                      # REST API and WebSocket Router controllers
│   │   ├── auth.py                  # Session-cookie login, logout, and session checks
│   │   ├── dashboard.py             # Core router generating role-scoped view context
│   │   ├── hub.py                   # Route selection and inbound arrival simulation triggers
│   │   ├── layer1.py                # Direct Route Optimizer execution endpoint
│   │   ├── layer2.py                # Forecast status and weather event overrides
│   │   ├── logistics.py             # Provider acceptance, fleet views, and manual dispatches
│   │   ├── orders.py                # Scoped order listing endpoints
│   │   ├── simulation.py            # Simulation clock configuration
│   │   └── websocket.py             # WebSocket server handling orders and real-time tracking
│   ├── services/                    # Business Service Layer
│   │   ├── ai1_client.py            # Wrapper client for Layer 1 calculations
│   │   ├── ai2_client.py            # Local/remote evaluator for Layer 2 dispatches
│   │   ├── layer2_supervisor.py     # Background supervisor running every 5s
│   │   ├── map_data.py              # Map layout models, geocoding, and KPI calculator
│   │   ├── order_lifecycle.py       # Helpers for direct dispatch creation
│   │   └── order_views.py           # User-role order visibility projections
│   ├── config.py                    # App environment settings and databases URLs
│   ├── database.py                  # Database engines and bootstrap seeds
│   ├── main.py                      # FastAPI initialization and async lifespan tasks
│   ├── models.py                    # SQLModel database tables and Pydantic fields
│   ├── order_times.py               # Time formatting utilities
│   └── simulation.py                # Background simulation clock executor
├── data/                            # Static CSV Datasets
│   └── generated/three_year/csv_adapted/  # Leg routes, weather, nodes, fleet CSV files
└── requirements.txt                 # Backend Python package requirements
```

### Frontend Layout (`/frontend`)

```
frontend/
├── src/
│   ├── app/                         # Next.js App Router Pages
│   │   ├── admin/                   # Operations Admin Panel view
│   │   ├── enterprise/              # Enterprise Farmer submission and tracking view
│   │   ├── logistics/               # Logistics Provider portal view
│   │   ├── login/                   # User Login page
│   │   ├── layout.tsx               # Master HTML Layout shell
│   │   └── page.tsx                 # Root router redirecting users based on roles
│   ├── components/                  # Shared React UI Components
│   │   ├── Brand.tsx                # Branding logo component
│   │   ├── DashboardShell.tsx       # Navigation shell and sidebar layouts
│   │   ├── LanguageToggle.tsx       # VI/EN localization toggle
│   │   └── VaicMap.tsx              # Interactive map canvas using Leaflet
│   ├── context/                     # Global State Context Providers
│   │   ├── AuthContext.tsx          # Manages user session state and API logout actions
│   │   └── LanguageContext.tsx      # Handles dictionary localization lookups
│   ├── features/                    # Feature components
│   │   └── dashboard/
│   │       └── DashboardSection.tsx # Swaps dashboard view cards based on active sidebar tab
│   ├── lib/                         # General Utilities
│   │   ├── api.ts                   # Fetch API wrappers connecting with FastAPI endpoints
│   │   └── labels.ts                # Localization translators for route strings
│   ├── styles/                      # Base CSS styles
│   └── types/                       # TypeScript interfaces
├── next.config.ts                   # Next.js Server config and API Proxies
└── tailwind.config.ts               # Custom styles configuration (if applicable)
```

---

## 5. WebSocket Integration Specifications

The real-time synchronization between dashboard components is orchestrated using JSON payloads sent over WebSocket connections.

### Client-to-Server Actions (`/ws` endpoint)

*   **`CREATE_ORDER`**:
    ```json
    {
      "action": "CREATE_ORDER",
      "hub_id": "HUB_SOCTRANG",
      "loai_hang": "Tôm",
      "khoi_luong_kg": 15000,
      "timestamp": "2026-07-19T09:00:00+07:00",
      "delivery_deadline": "2026-07-20T09:00:00+07:00",
      "harvested_at": "2026-07-19T06:00:00+07:00"
    }
    ```
    *Server response*: Sends a `ROUTE_OPTIONS` event containing the Layer 1 path candidates.

*   **`CONFIRM_ROUTE`**:
    ```json
    {
      "action": "CONFIRM_ROUTE",
      "order_id": 42,
      "selected_route_id": "D_WATER_VIA_CT"
    }
    ```
    *Server response*: Sends `ROUTE_CONFIRMED` and broadcasts updated state to all connected status sockets.

*   **`TRACK_CARGO`**:
    ```json
    {
      "action": "TRACK_CARGO",
      "order_id": 42
    }
    ```
    *Server response*: Streams periodic `CARGO_TRACKING` events (every 1 second).

---

### Server-to-Client Broadcasts

*   **`STATE_UPDATE`**: Sent when inventory changes, weather is overridden, or dispatches occur.
*   **`TIME_TICK`**: Sent on every simulation tick, distributing the current `system_clock`, active deliveries, and fleet coordinates.
*   **`CARGO_TRACKING`**: Includes live lat/lon points, progress percentages, and order stages.
    ```json
    {
      "event": "CARGO_TRACKING",
      "order_id": 42,
      "state": "routed_to_can_tho",
      "location": { "lat": 9.940, "lon": 105.650 },
      "progress": 0.38,
      "provider_name": "Mekong Logistics",
      "timeline": [ ... ]
    }
    ```
*   **`AI_ERROR`**: Sent if Layer 2 fails during a run to log exception issues for administrators.

---

## 6. Map Visualizations & Geolocation Interpolation

The system displays the position of transshipments without relying on physical GPS trackers:

### Inbound Progress Calculation
When an order's status is `routed_to_can_tho`:
1. The backend retrieves the coordinates of the route segments connecting the origin hub to Can Tho.
2. It calculates progress:
   $$p = \frac{\text{SYSTEM\_CLOCK} - \text{created\_at}}{\text{eta\_can\_tho} - \text{created\_at}}$$
3. The function `_point_along_segments` interpolates progress against segment lengths to calculate the current coordinates $(\text{lat}, \text{lng})$.
4. This position is broadcasted inside `TIME_TICK` events, updating Leaflet markers in real time.

### Leaflet Render Layout
In [VaicMap.tsx](file:///mnt/data/VAIC/frontend/src/components/VaicMap.tsx):
- **Barge routes** are drawn as teal dashed polylines (`#0f766e`).
- **Truck routes** are drawn as solid slate polylines (`#64748b`).
- **Vehicles** are rendered as custom DivIcons (🚚 for road, 🚢 for water), colored yellow when consolidating at the Can Tho Hub and orange/blue when in transit.

---

## 7. Local Installation & Setup

### Running the Backend (FastAPI)
1. Navigate to `/backend`.
2. Create and activate a python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the development server:
   ```bash
   uvicorn app.main:app --reload
   ```
   *The backend runs on `http://127.0.0.1:8000`*

### Running the Frontend (Next.js)
1. Navigate to `/frontend`.
2. Install npm packages:
   ```bash
   npm install
   ```
3. Create your `.env` configuration:
   ```bash
   cp .env.example .env
   ```
4. Run the Next.js dev server:
   ```bash
   npm run dev
   ```
   *Access the web app at `http://localhost:3000`*
