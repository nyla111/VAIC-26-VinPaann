# VAIC Mekong Delta Agri-Logistics

Hệ thống demo điều phối logistics nông sản từ các hub ĐBSCL về TP.HCM, với Cần Thơ là trung tâm trung chuyển. Repo hiện có:

- **AI1 Route & Cost Optimizer**: so sánh 5 route `A_DIRECT_ROAD`, `B_ROAD_VIA_CT`, `C_WATER_ROAD_VIA_CT`, `D_WATER_VIA_CT`, `E_ROAD_WATER_VIA_CT`.
- **FastAPI Backend**: API tích hợp AI1, lưu order vào SQLite, API hub, WebSocket, Layer 2 dispatch/forecast.
- **Dashboard theo role**: một FastAPI app riêng có login session và menu theo `business`, `logistics`, `admin`.
- **Water/road consolidation & dispatch planner**: nằm trong `backend/app/ai/forecast_dispatch/`, dùng pending shipments tại Cần Thơ, forecast rolling mean, hard constraints và priority score để quyết định `dispatch_now`, `wait_for_load`, `wait_for_vehicle`.

Trạng thái AI2 hiện tại: backend đã có API thật tại `/api/layer2/*` và chạy bằng SQLite/SQLModel. Forecast v1 là rolling-mean baseline, không phải model ML đã train. Dashboard vẫn dùng `dashboard/services/ai2_client.py`; mặc định `AI2_AVAILABLE=false` nên Jobs/Dispatch hiển thị demo data, chỉ gọi service ngoài nếu bật env `AI2_AVAILABLE=true` và cấu hình `AI2_BASE_URL`.

Ý tưởng vận hành: **AI1 trả lời "đi tuyến nào", AI2 trả lời "khi nào nên xuất bến/xuất xe"**. AI1 đánh giá từng order theo chi phí, thời gian, khả năng đi đường bộ/đường thủy, thời tiết, spoilage và phí trung chuyển. Với các order đi qua Cần Thơ, backend lưu trạng thái và AI2 theo dõi tải tích lũy theo outbound mode để quyết định dispatch ngay, chờ thêm tải, hoặc chờ phương tiện.

Các hub đang được mô hình hóa:

```text
HUB_VITHANH
HUB_LONGXUYEN
HUB_SOCTRANG
HUB_VINHLONG
CT_HUB
HCM_MARKET
```

## Cấu Trúc Repo

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI backend entrypoint
│   │   ├── routes/                     # layer1, layer2, hub, websocket APIs
│   │   ├── ai/route_optimizer/         # AI1 copy dùng trong backend
│   │   └── ai/forecast_dispatch/       # AI2 forecast/dispatch planner
│   ├── data/generated/three_year/      # data 3 năm cho backend
│   ├── tests/                          # pytest backend
│   └── requirements.txt
├── dashboard/
│   ├── main.py                         # FastAPI dashboard entrypoint
│   ├── auth.py                         # session login/logout
│   ├── config/users.py                 # tài khoản demo hardcoded
│   ├── routers/dashboard.py            # role-based dashboard sections
│   ├── services/                       # AI1, AI2, map/KPI data helpers
│   ├── static/                         # CSS/JS, Leaflet map, charts
│   ├── templates/                      # login/layout/sections
│   ├── Procfile
│   ├── start.sh
│   └── requirements.txt
├── route_optimizer/                    # AI1 standalone module/API
├── VAIC_Data_Simulation_Package_v3_2026-07-18/
│   ├── data/generated/annual/csv/      # canonical annual CSV
│   ├── data/generated/three_year/      # synthetic 3-year source data
│   ├── eval/reference_routes.csv       # reference test cases
│   └── requirements.txt
├── normalizers.py
├── test_against_reference.py
└── reference_mismatch_classification.json
```

## Môi Trường

Đã kiểm tra trên máy hiện tại với:

```bash
Python 3.13.2
```

Tạo và kích hoạt virtual environment:

```bash
cd /Users/bichphuong/Desktop/VAIC
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r dashboard/requirements.txt -r backend/requirements.txt -r VAIC_Data_Simulation_Package_v3_2026-07-18/requirements.txt
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Repo không có root `requirements.txt` hoặc `pyproject.toml`; dependencies đang nằm theo module như trên.

Dashboard map dùng Leaflet CDN, OpenStreetMap tile và OSRM public demo API cho road geometry trong `dashboard/static/js/map.js`, nên phần bản đồ cần network để tải basemap/road route. Không có Docker config trong repo hiện tại.

## Quick Start

Terminal 1: chạy backend API.

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload --port 8000
```

Backend URLs:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
ws://127.0.0.1:8000/ws/status
```

Terminal 2: chạy dashboard.

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
uvicorn dashboard.main:app --reload --port 8001
```

Dashboard URL:

```text
http://127.0.0.1:8001/login
```

Tài khoản demo:

| Username | Password | Role |
|---|---|---|
| `business1` | `demo123` | `business` |
| `logistics1` | `demo123` | `logistics` |
| `admin1` | `demo123` | `admin` |
| `opslead` | `demo123` | `admin` |

## Chạy Dashboard Với AI2 Backend Thật

Mặc định dashboard dùng demo data cho Jobs/Dispatch. Để dashboard gọi một AI2 service qua HTTP, bật:

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
AI2_AVAILABLE=true AI2_BASE_URL=http://127.0.0.1:8000 uvicorn dashboard.main:app --reload --port 8001
```

Lưu ý: dashboard client hiện gọi `${AI2_BASE_URL}/dispatch/jobs`. Backend tích hợp hiện expose Layer 2 tại `/api/layer2/*`, nên Jobs/Dispatch dashboard vẫn có thể rơi về demo data nếu endpoint `/dispatch/jobs` không tồn tại ở service được trỏ tới.

## API Chính

Backend tích hợp:

```text
POST /api/layer1/optimize
POST /api/hub/select-route
GET  /api/hub/status
POST /api/hub/simulate-incoming
GET  /api/layer2/forecast
GET  /api/layer2/dispatch-status
POST /api/layer2/events/vehicle-status
POST /api/layer2/events/weather-update
WS   /ws/status
```

AI1 standalone nếu chỉ muốn chạy optimizer riêng:

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
uvicorn route_optimizer.api:app --reload --port 8002
```

Endpoint standalone:

```text
POST http://127.0.0.1:8002/api/v1/route-optimize
```

## Data Paths Và Env Vars

AI1 standalone ở `route_optimizer/` mặc định đọc:

```text
VAIC_Data_Simulation_Package_v3_2026-07-18/data/generated/annual/csv/
```

Dashboard `ai1_client.py` mặc định cũng đọc annual CSV qua `VAIC_DATA_DIR`, có thể override:

```bash
VAIC_DATA_DIR=/path/to/csv uvicorn dashboard.main:app --reload --port 8001
```

Backend copy của AI1 mặc định đọc:

```text
backend/data/generated/three_year/csv_adapted/
```

Override backend data path bằng:

```bash
cd /Users/bichphuong/Desktop/VAIC/backend
DATA_DIR=/path/to/csv uvicorn app.main:app --reload --port 8000
```

Backend SQLite mặc định tạo file:

```text
backend/agri_orchestrator.db
```

Override bằng:

```bash
cd /Users/bichphuong/Desktop/VAIC/backend
DATABASE_URL=sqlite:///custom.db uvicorn app.main:app --reload --port 8000
```

Dashboard session cookie:

```text
DASHBOARD_SECRET_KEY
DASHBOARD_COOKIE_HTTPS
```

AI2 client trong dashboard:

```text
AI2_AVAILABLE
AI2_BASE_URL
```

## Scripts Và Tests

Route Optimizer reference test:

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
python test_against_reference.py
```

Kết quả đã ghi nhận trước đó cho AI1 standalone là `Matched 47/50 = 94.00%`.

Chạy batch optimize toàn bộ annual orders:

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
python route_optimizer/run_all_orders.py
```

Output:

```text
route_optimizer/output/all_orders_optimized.csv
route_optimizer/output/errors.csv
```

Chạy adapter tạo CSV 3 năm cho AI1 standalone:

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
python route_optimizer/adapt_three_year.py
```

Backend tests:

```bash
cd /Users/bichphuong/Desktop/VAIC/backend
source ../.venv/bin/activate
pytest tests/
```

Data package tests:

```bash
cd /Users/bichphuong/Desktop/VAIC
source .venv/bin/activate
pytest VAIC_Data_Simulation_Package_v3_2026-07-18/tests/
```

## Deploy Notes

Dashboard có sẵn:

```text
dashboard/Procfile
dashboard/start.sh
```

`dashboard/start.sh` dùng biến `PORT` và chạy:

```bash
uvicorn dashboard.main:app --host 0.0.0.0 --port "$PORT"
```

Backend chưa có Procfile riêng trong repo hiện tại. Khi deploy backend, entrypoint thật là:

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```
