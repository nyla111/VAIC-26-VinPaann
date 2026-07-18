# AI Layer 2 - Forecast + Dispatch Agent (Cần Thơ)

`ai2_dispatch` là service Layer AI 2 trong hệ thống điều phối logistics nông sản ĐBSCL. Nhận
shipment đã được Layer AI 1 chọn đi qua Cần Thơ, gom tải theo `outbound_mode` (road/water),
forecast lượng hàng sẽ tích lũy, và ra quyết định `dispatch_now` / `wait_for_load` /
`wait_for_vehicle` kèm giải thích.


## 1. Cài đặt & chạy nhanh

```bash
cd VAIC-26-VinPaann
python -m pip install -r ai2_dispatch/requirements.txt
```

Chạy server (từ `VAIC-26-VinPaann/`):

```bash
python -m uvicorn ai2_dispatch.app.main:app --reload --host 127.0.0.1 --port 8001
```

Swagger UI: `http://127.0.0.1:8001/docs` - dùng để Backend/Frontend tự thử request mà không
cần chờ ai viết client.

Chạy test (không mock data, dùng đúng data canonical thật):

```bash
python -m pytest ai2_dispatch/tests/test_smoke.py -v
```

Sample request/response thật (chạy ngày 2026-07-18 trên data canonical v3) nằm ở
`ai2_dispatch/examples/`.

## 2. Cấu trúc thư mục

```text
ai2_dispatch/
├── app/
│   ├── main.py            # FastAPI app, wiring toàn bộ endpoint
│   ├── schemas.py         # Pydantic request/response models
│   ├── enums.py           # RouteEnum, Mode, Decision, ReasonCode, map route AI1 <-> AI2
│   ├── data_loader.py     # Đọc canonical CSV thật (tái dùng route_optimizer.data_loader)
│   ├── state_store.py     # In-memory state: shipment, vehicle, idempotency, rolling history
│   ├── forecasting.py     # Forecast v1: rolling-mean baseline + known ETA
│   └── decision_engine.py # Hard constraints + additive Priority Score
├── tests/
│   └── test_smoke.py      # End-to-end test qua FastAPI TestClient, dùng data thật
├── examples/
│   ├── sample_events.json
│   └── sample_responses.json
└── requirements.txt
```

Không có `config/*.json` riêng ở v1 (khác với cấu trúc `ai2_dispatch/config/` từng phác thảo ở
bản draft cũ) - `DecisionConfig` (α/β/γ/threshold, bucket_minutes, horizon_hours) hiện là
dataclass default trong `decision_engine.py`, dễ sửa, chưa cần externalize ra JSON vì chưa
chạy grid-search tuning (xem Roadmap).

## 3. Nguồn dữ liệu

**Dùng thẳng data canonical thật** từ
`VAIC_Data_Simulation_Package_v3_2026-07-18/data/generated/annual/csv/` - **cùng data_dir với
AI1** (`route_optimizer`). `ai2_dispatch/app/data_loader.py` tái sử dụng
`route_optimizer.data_loader.load_data()` thay vì viết parser CSV riêng, nên AI1 và AI2 luôn
đọc đúng cùng một bản ghi cho `commodities`, `fleet`, `weather_bulletins`, `nodes`.

AI2 **không** dùng dataset simulate riêng trong `vaic_phase1_notebook_and_datasets/` (hub
`hau_giang/vinh_long/an_giang/soc_trang`, cargo `mango/rambutan/...`) làm nguồn cho service
thật - dataset đó vẫn giữ nguyên để training/reproduce notebook (xem mục 8), nhưng **API chạy
trên canonical v3** với 4 hub thật (`HUB_VITHANH`, `HUB_LONGXUYEN`, `HUB_SOCTRANG`,
`HUB_VINHLONG`) và 10 `commodity_id` thật (`COM_RICE`, `COM_PANGASIUS`, `COM_SHRIMP`,
`COM_POMELO`, `COM_SWEET_POTATO`, `COM_SUGARCANE`, `COM_PINEAPPLE`, `COM_PURPLE_ONION`,
`COM_ORANGE`, `COM_VEGETABLE`).

### Cargo profile - build từ `commodities.csv`, không hard-code

`data_loader.build_cargo_profiles()` build cargo profile trực tiếp từ `commodities.csv`:

| Field AI2 | Nguồn canonical | Công thức/ghi chú |
|---|---|---|
| `time_sensitivity` (0..1) | `perishability_level` (int 1..5) | `perishability_level / 5.0` - **giả định cần Data Lead xác nhận**, chưa có văn bản chính thức nào định nghĩa mapping này |
| `max_safe_wait_hours` | `max_hold_hours` | Dùng thẳng - **giả định**: `max_hold_hours` tính từ lúc thu hoạch cho toàn hành trình; AI2 hiện dùng nguyên số đó làm ngân sách chờ riêng tại Cần Thơ, có thể lạc quan vì chưa trừ thời gian đã đi từ hub. Cần Data Lead xác nhận. |
| `needs_reefer` | `needs_reefer` | Giữ nguyên |
| `compatible_vehicle_types` | `compatible_vehicle_types` | Giữ nguyên (dùng để lọc vehicle) |

Không có field `temperature_min/max_celsius` riêng theo commodity trong canonical (chỉ có
`needs_reefer` boolean) - AI2 **không** yêu cầu nhiệt độ cụ thể ở v1.

### Vehicle - bootstrap từ `fleet.csv`, state runtime giữ riêng

`fleet.csv` có 77 vehicle toàn hệ thống; AI2 chỉ bootstrap **vehicle đang ở `CT_HUB`** lúc khởi
động service (27 vehicle trong snapshot 2026-01-01). Sau đó, state vehicle được cập nhật qua
event `POST /api/v1/events/vehicle-status`, **không** đọc lại `fleet.csv` mỗi request - vì
`fleet.csv` là snapshot chung của cả hệ thống, không phản ánh trạng thái real-time riêng cho
luồng dispatch tại Cần Thơ (VD "đang load hàng" là state chỉ AI2 biết).

`vehicle.status` dùng đúng 4 giá trị canonical (`available`, `en_route`, `maintenance`,
`reserved`) - xem mục 8 về lý do khác 6 giá trị ở bản draft cũ.

### Weather - đọc `weather_bulletins.csv` thật

`data_loader.get_outbound_weather_assessment()` lấy bulletin của cả `CT_HUB` và `HCM_MARKET`
tại thời điểm quyết định (`decision_ts`), rồi cộng dồn theo hướng bảo thủ:

- `road_blocked = True` nếu 1 trong 2 node có `road_status == "closed"`.
- `water_blocked = True` nếu 1 trong 2 node có `water_navigation_status == "closed"`.
- `risk` (0..1) = `max(max_flood_risk_idx)` của 2 node.

Có thể override thủ công qua `POST /api/v1/events/weather-update` để demo kịch bản khác (VD
giả lập lũ) - override hết hiệu lực ngoài `[valid_from, valid_until]`.

## 4. Route enum - map với AI1 thật

AI1 (`route_optimizer/`, xem `INTEGRATION_LOP_AI_1.md`) trả `route_code` dạng `A_DIRECT_ROAD`
.. `E_ROAD_WATER_VIA_CT`. AI2 dùng route enum tiếng Anh snake_case
(`direct_hcm_road`..`via_can_tho_road_then_water`). Bảng map cố định trong
`app/enums.py::AI1_ROUTE_TO_AI2_ROUTE`:

| Route code AI1 | Route enum AI2 | Hub→Cần Thơ | Cần Thơ→HCM |
|---|---|---|---|
| `A_DIRECT_ROAD` | `direct_hcm_road` | (không qua CT) | road |
| `B_ROAD_VIA_CT` | `via_can_tho_road_then_road` | road | road |
| `C_WATER_ROAD_VIA_CT` | `via_can_tho_water_then_road` | water | road |
| `D_WATER_VIA_CT` | `via_can_tho_water_then_water` | water | water |
| `E_ROAD_WATER_VIA_CT` | `via_can_tho_road_then_water` | road | water |

**Backend/AI1 cần convert route code A-E sang route enum AI2 trước khi gọi
`POST /api/v1/events/shipment-routed`** (hoặc AI2 có thể expose thêm 1 hàm convert nếu team
muốn Backend forward nguyên route code A-E - hỏi Nghiệp trước khi quyết định ai làm việc
convert này). `A_DIRECT_ROAD`/`direct_hcm_road` **không được gửi vào AI2** - validate qua
Pydantic sẽ từ chối nếu `selected_route`/`inbound_mode`/`outbound_mode` không khớp bảng trên.

## 5. API - event endpoints

Tất cả event có `event_id`; gửi lại `event_id` đã thấy sẽ trả `duplicate: true`, không cộng
state 2 lần.

| Endpoint | Khi nào gọi | Field bắt buộc |
|---|---|---|
| `POST /api/v1/events/shipment-routed` | Ngay khi AI1/Backend chốt route đi qua Cần Thơ (4/5 route, trừ `direct_hcm_road`) | `shipment_id, hub_id, commodity_id, weight_kg, selected_route, inbound_mode_to_can_tho, outbound_mode_from_can_tho, created_at, eta_can_tho`; `harvested_at` optional nhưng nên gửi nếu có |
| `POST /api/v1/events/shipment-arrived` | Khi shipment thực tế tới Cần Thơ | `shipment_id, actual_arrival_at, actual_weight_kg` |
| `POST /api/v1/events/shipment-cancelled` | Khi hub/khách hủy đơn | `shipment_id, reason` |
| `POST /api/v1/events/vehicle-status` | Khi 1 vehicle đổi status/vị trí | `vehicle_id, mode, capacity_kg, status, available_from, ...` |
| `POST /api/v1/events/weather-update` | Optional - chỉ dùng để override demo, mặc định AI2 tự đọc `weather_bulletins.csv` | `road_risk, water_risk, road_blocked, water_blocked, valid_from, valid_until` |

Response mọi event endpoint:

```json
{"accepted": true, "event_id": "evt_001", "state_version": 3, "recomputed": true, "duplicate": false}
```

Lỗi domain trả `{"error": {"code": ..., "message": ...}}`, HTTP status tương ứng:

| `code` | HTTP | Khi nào |
|---|---:|---|
| `SHIPMENT_NOT_FOUND` | 404 | `shipment_id` chưa từng có event `shipment-routed` |
| `INVALID_STATE_TRANSITION` | 409 | VD shipment đã `dispatched` mà gửi lại `shipment-arrived` |

Lỗi validate schema/route-mode mismatch (VD `selected_route` không khớp
`inbound_mode_to_can_tho`) trả **422 theo format mặc định của FastAPI/Pydantic**, không phải
envelope `{"error": {...}}` tùy biến - đây là điểm đơn giản hóa so với thiết kế lỗi custom đầy
đủ, xem mục 8.

## 6. API - forecast & dispatch status

```text
GET /api/v1/forecast?outbound_mode=road|water&decision_ts=<ISO8601>
GET /api/v1/dispatch-status?outbound_mode=road|water&decision_ts=<ISO8601>
```

- `outbound_mode`: bắt buộc chọn 1 trong 2 vì road/water là 2 pipeline tải riêng (mỗi pipeline
  1 nhóm shipment + 1 vehicle pool). Nếu bỏ trống, AI2 tự chọn mode có tổng weight đang chờ lớn
  hơn.
- `decision_ts`: bỏ trống thì dùng thời điểm hiện tại (UTC). Backend nên **luôn truyền tường
  minh** trong demo để kết quả tái lập được.

`GET /api/v1/forecast` trả `predicted_full_load`, `buckets[]` (mỗi bucket 30 phút, mặc định
horizon 6 giờ) - đúng shape thiết kế "rolling bucket + predicted_full_load_time", không dùng
field cố định kiểu "dự báo 2h tới".

`GET /api/v1/dispatch-status` trả `decision`, `reason_codes[]`, `explanation`, `priority_score`
breakdown, `selected_vehicle`, và `dispatch_order_proposal` (chỉ có khi
`decision == dispatch_now`). Ví dụ output thật nằm ở `examples/sample_responses.json`.

## 7. Cách hoạt động - decision flow

Với mỗi `outbound_mode`, thứ tự check (giống nhau mỗi lần gọi, không có side effect ngoài đọc
state - an toàn để Backend poll nhiều lần):

1. Không có shipment nào đang `arrived_waiting` → `wait_for_load`, reason
   `no_pending_shipments`.
2. Không có vehicle available phù hợp (đúng mode, đủ reefer nếu cần) → `wait_for_vehicle`,
   reason `vehicle_unavailable`.
3. Tuyến outbound bị `closed` theo weather bulletin → `wait_for_load`, reason
   `weather_blocked`.
4. Có shipment đã chạm/vượt `max_safe_wait_hours` (tính từ `harvested_at`, hoặc `created_at`
   nếu không có `harvested_at`) → `dispatch_now`, reason `safe_wait_limit_reached`.
5. `fill_ratio >= 1.0` → `dispatch_now`, reason `vehicle_full`.
6. Còn lại: tính `priority_score = 0.55×fill + 0.35×urgency + 0.10×weather`; nếu
   `>= 0.75` → `dispatch_now` (`priority_score_reached`), ngược lại `wait_for_load`
   (`score_below_threshold`, kèm `full_load_expected_soon` nếu forecast có
   `predicted_full_load_time` trong horizon).

`urgency_component` = `max` qua các shipment đang chờ của
`min(elapsed_hours / max_safe_wait_hours × time_sensitivity, 1.0)` - loại hàng nhạy cảm nhất
quyết định mức khẩn cấp của cả lô, đúng thiết kế additive score (không dùng phép nhân, để một
component = 0 không kéo cả điểm về 0).


