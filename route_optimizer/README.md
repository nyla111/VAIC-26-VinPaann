# Route Optimizer

`route_optimizer` là module Layer AI 1 - Route & Cost Optimizer trong hệ thống điều phối logistics nông sản ĐBSCL. Với một lô hàng từ một hub thu gom, module so sánh 5 phương án vận chuyển qua đường bộ/đường thủy. Kết quả tính chi phí, thời gian dự kiến, trạng thái khả dụng và đề xuất phương án rẻ nhất. `khuyen_nghi` chỉ là gợi ý; mọi route `available` vẫn nên được hiển thị để user chọn.

## Cấu Trúc

| File | Chức năng |
|---|---|
| `schemas.py` | Pydantic request/response models cho API, gồm `order_id`, `phuong_an`, `cost_breakdown`, `evidence`. |
| `data_loader.py` | Load canonical CSV từ `data/generated/annual/csv/`: nodes, legs, commodities, orders, weather, fleet, fuel_prices, freight_rates, weather_bulletins. |
| `normalizers.py` | Re-export mapping từ root `normalizers.py`: node slug/name mapping, commodity tiers, loss/value fallback. |
| `candidates.py` | Dựng 5 route A-E từ `legs.csv`, trả `leg_ids`, tổng distance và base duration. |
| `feasibility.py` | Check water compatibility, water factor, weather bulletins, missing weather; tính adjusted time theo weather factor. |
| `pricing.py` | Tính cost bằng `freight_rates.csv`, fallback fuel/fleet nếu thiếu, cộng spoilage và phí trung chuyển Cần Thơ. |
| `optimizer.py` | Hàm chính `optimize_route(input: dict) -> dict`: normalize input, build route, check deadline, chọn route rẻ nhất. |
| `api.py` | FastAPI wrapper expose `POST /api/v1/route-optimize`. |

## Cài Đặt

Dependencies từ package data: `pandas`, `numpy`, `PyYAML`. API cần thêm `fastapi`, `uvicorn`.

Chạy từ `/Users/bichphuong/Desktop/VAIC`:

```bash
python3 -m pip install -r VAIC_Data_Simulation_Package_v3_2026-07-18/requirements.txt fastapi uvicorn --break-system-packages
```

Lệnh trên đã được test trên máy này; hiện `fastapi==0.139.2` và `uvicorn==0.46.0`.

## Chạy Nhanh Không Cần API

```bash
python3 - <<'PY'
import json
from route_optimizer import optimize_route

payload = {
    "order_id": "ORD_2026_000001",
    "hub_id": "HUB_VINHLONG",
    "commodity_id": "COM_VEGETABLE",
    "loai_hang": "",
    "khoi_luong_kg": 3495.704632,
    "timestamp": "2026-01-01T09:58:52+07:00",
}

print(json.dumps(optimize_route(payload), ensure_ascii=False, indent=2))
PY
```

## Chạy API Server

```bash
uvicorn route_optimizer.api:app --reload --host 127.0.0.1 --port 8000
```

Server chạy tại:

```text
http://127.0.0.1:8000
```

Swagger UI tự sinh của FastAPI:

```text
http://127.0.0.1:8000/docs
```

Lệnh `uvicorn ... --reload` và `/docs` đã được test trên máy này.

## Gọi API Bằng Curl

Ví dụ 1:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/route-optimize \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ORD_2026_000001","hub_id":"HUB_VINHLONG","commodity_id":"COM_VEGETABLE","loai_hang":"","khoi_luong_kg":3495.704632,"timestamp":"2026-01-01T09:58:52+07:00"}'
```

Response rút gọn:

```json
{
  "hub_id": "HUB_VINHLONG",
  "recommended_route": "A_DIRECT_ROAD",
  "khuyen_nghi": "di_thang_hcm",
  "phuong_an": [
    {
      "route_code": "A_DIRECT_ROAD",
      "trang_thai": "available",
      "chi_phi_du_doan_vnd": 1045769.03,
      "cost_breakdown": {
        "raw_transport_cost_vnd": 843784.19,
        "spoilage_cost_vnd": 201984.83,
        "transshipment_fee_vnd": 0.0,
        "total_cost_vnd": 1045769.03,
        "pricing_source": "freight_rates"
      }
    }
  ]
}
```

Ví dụ 2:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/route-optimize \
  -H 'Content-Type: application/json' \
  -d '{"hub_id":"long_xuyen","commodity_id":"COM_RICE","loai_hang":"lua_gao","khoi_luong_kg":9000,"timestamp":"2026-02-10T08:00:00+07:00"}'
```

Response rút gọn:

```json
{
  "hub_id": "HUB_LONGXUYEN",
  "priority": {
    "tier": "grain_dry",
    "score": 0.1,
    "label": "Gạo / nông sản khô"
  },
  "recommended_route": "A_DIRECT_ROAD",
  "khuyen_nghi": "di_thang_hcm",
  "evidence": {
    "weather_ts": "2026-02-10T08:00:00+07:00",
    "price_ts": "2026-02-10T06:00:00+07:00"
  }
}
```

## Chạy Test

Từ `/Users/bichphuong/Desktop/VAIC`:

```bash
python3 test_against_reference.py
```

Script này đọc `eval/reference_routes.csv`, dựng input từ scenario orders, gọi `optimize_route()`, rồi so sánh route được khuyến nghị với 50 case tham khảo. Đây là test sanity cho công thức hiện tại, không phải benchmark bắt buộc phải đạt 100%.

Kết quả hiện tại đã test:

```text
Matched 47/50 = 94.00%
```

Report mismatch được ghi ra:

```text
/Users/bichphuong/Desktop/VAIC/reference_mismatch_classification.json
```

## Giả Định Quan Trọng

- `handling_fee_per_kg_vnd = 150 VND/kg` là giả định mô phỏng cho bốc dỡ/chuyển tải tại Cần Thơ.
- Deadline chỉ được check khi request có `order_id` và order đó tồn tại trong `orders.csv` của data dir đang load; nếu không có `order_id`, optimizer bỏ qua deadline check.
- Pricing ưu tiên `freight_rates.csv` theo `leg_id + vehicle_type` nearest-previous timestamp.
- Nếu thiếu freight rate phù hợp, code fallback về `fuel_prices x distance x fleet cost_per_km`; fallback được log trong `pricing.FREIGHT_RATE_FALLBACKS`.
- Tần suất fallback đo trên 50 case reference ngày 18/7/2026 là `0/50`.
- Module chưa reserve vehicle sau khi trả recommendation; vehicle selection hiện là heuristic rẻ nhất trong nhóm compatible available.

## Tài Liệu Chi Tiết

Xem tài liệu bàn giao đầy đủ ở:

```text
/Users/bichphuong/Desktop/VAIC/INTEGRATION_LOP_AI_1.md
```

File đó mô tả chi tiết request/response schema, 5 route A-E, feasibility, cost formula, lý do unavailable, và checklist tích hợp.
