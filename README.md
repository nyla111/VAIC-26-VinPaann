# Mekong Delta Agri-Logistics Orchestrator

The Mekong Delta Agri-Logistics Orchestrator is a web-based decision support system designed to optimize the transportation of agricultural products from the Mekong Delta region (Dong Bang Song Cuu Long) to Ho Chi Minh City. By combining multi-modal transportation (road and waterway) and dynamic decision-making, the project aims to minimize shipping costs, reduce food spoilage, and coordinate fleet dispatching.

---

## Core Idea & Architecture

The system utilizes a 2-Layer decision-making pipeline:

### Layer 1: Route Optimization (Enterprise Decision)
When an enterprise submits a cargo request, the Layer 1 AI component evaluates multiple routes from the local hub to Ho Chi Minh City. It evaluates constraints such as cargo perishability, delivery deadlines, historical weather conditions, and water levels to recommend the most cost-effective and reliable path. Routes can be direct (road or water) or transshipped via the Can Tho Hub.

### Layer 2: Dispatch and Consolidation (Ops/Logistics Decision)
For shipments routed through the Can Tho Hub, Layer 2 coordinates consolidation. It tracks accumulated cargo and compares it against dispatch thresholds (e.g., 50.0 tons). Once the threshold is met, the system schedules fleet vehicles (trucks and barges) based on cargo priority and real-time transit conditions, ensuring efficient cargo aggregation.

---

## User Guide

This system supports three roles: Enterprise, Admin/Operations, and Logistics. Pre-defined accounts are provided for testing.

### Prerequisites

Navigate to the project dashboards by starting the development servers.
Log in at the `/login` route using the credentials below:

| Role | Username / Email | Password |
|---|---|---|
| Enterprise (Farmer/Producer) | enterprise1@vaic.vn | demo123 |
| Logistics (Fleet Manager) | logistics1@vaic.vn | demo123 |
| Admin / Operations Manager | admin1@vaic.vn | demo123 |

---

### 1. Enterprise Dashboard (/enterprise)
For agricultural producers to submit and track shipments.

1. **Submit a Shipment Order**:
   - Select the starting hub (e.g., Hub Vi Thanh, Hub Long Xuyen, Hub Soc Trang, Hub Vinh Long).
   - Select the agricultural commodity type (e.g., Rice, Pangasius fish, Shrimp, Pomelo).
   - Enter the cargo weight in kilograms.
   - Provide timestamps for harvesting, planned departure, and delivery deadline.
   - Click "Nop don (Optimize Route)" to run the Layer 1 optimizer.

2. **Select and Confirm Route**:
   - Review the AI-recommended route card (flagged as "Goi y AI") alongside alternative paths.
   - Compare estimated costs and transit durations.
   - View path previews on the interactive map.
   - Click "Xac nhan tuyen duong" to initiate shipment.

3. **Real-time Tracking**:
   - The map displays a live marker representing your cargo.
   - Observe tracking progress from the origin to Can Tho Hub or directly to Ho Chi Minh City.

---

### 2. Admin & Operations Dashboard (/admin)
For regional operations leads managing transshipment at the Can Tho Hub.

1. **System Status & Logs**:
   - Monitor total active cargo volumes and pending weight consolidated at the Can Tho Hub.
   - View real-time system logs capturing route confirmations and fleet dispatches.

2. **Weather Controls**:
   - Change system weather conditions (Clear, Rainy, Stormy).
   - Observe how weather restrictions dynamically affect routing availability (e.g., heavy rain or storms closing waterway paths).

3. **Consolidation & Dispatch Control**:
   - View accumulated weights for different cargo categories (seafood, vegetables, hard fruits, dry grain).
   - Control dispatch statuses to coordinate multi-modal operations.

---

### 3. Logistics Dashboard (/logistics)
For transport providers managing fleet operations.

1. **Fleet Monitoring**:
   - View the complete list of registered transport vehicles (Trucks and Barges).
   - Monitor current locations, load capacities, status (idle, transit, maintenance), and refrigeration features.

---

## Technical Setup

### Backend (FastAPI)
1. Navigate to `/backend`.
2. Install dependencies: `pip install -r requirements.txt`
3. Start the server: `uvicorn app.main:app --reload`
4. The backend runs on `http://127.0.0.1:8000`.

### Frontend (Next.js)
1. Navigate to `/frontend`.
2. Install dependencies: `npm install`
3. Configure environment variables in `.env` (or copy `.env.example`):
   `NEXT_PUBLIC_VAIC_API_BASE_URL=http://127.0.0.1:8000`
4. Start the server: `npm run dev`
5. Access the application at `http://localhost:3000`.
