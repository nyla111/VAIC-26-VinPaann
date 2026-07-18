# Layer AI 1 — Route & Cost Optimizer — Hợp đồng tích hợp

Tài liệu này phản ánh code hiện tại trong `route_optimizer/` và dùng cho Người 5
(Backend/Integration), Người 6 (UI) và Người 4 (Layer AI 2). Nguồn dữ liệu mặc định là
`VAIC_Data_Simulation_Package_v3_2026-07-18/data/generated/annual/csv/`.

## 1. Endpoint

`POST /api/v1/route-optimize`

FastAPI app nằm ở `route_optimizer/api.py`:

```python
app = FastAPI(title="Layer AI 1 - Route & Cost Optimizer")
```

Handler nhận `RouteOptimizeRequest` và trả về `RouteOptimizeResponse`.

## 2. Request schema

Schema thật lấy từ `route_optimizer/schemas.py`.

```json
{
  "order_id": "ORD_2026_000001",
  "hub_id": "HUB_VINHLONG",
  "commodity_id": "COM_VEGETABLE",
  "loai_hang": "rau_mau",
  "khoi_luong_kg": 3495.704632,
  "timestamp": "2026-01-01T09:58:52+07:00"
}
```

| Field | Type | Required | Ghi chú |
|---|---|---:|---|
| `order_id` | string hoặc null | no | Nếu có, optimizer tra `orders.csv` trong data dir hiện tại để lấy `deadline_ts`. Nếu không có, bỏ qua deadline check. |
| `hub_id` | string | yes | Chấp nhận canonical node id, slug compat, hub name tiếng Việt, hoặc location label. Được normalize bằng `normalizers.to_node_id()`. |
| `commodity_id` | string hoặc null | no | Nếu khớp 10 mã canonical thì dùng trực tiếp loss/value/vehicle compatibility đã verify. |
| `loai_hang` | string hoặc null | no | Dùng để fallback phân loại hàng nếu `commodity_id` không khớp canonical. Mặc định `""`. |
| `khoi_luong_kg` | number | yes | Bắt buộc `> 0`. |
| `timestamp` | string | yes | ISO datetime; dùng làm decision time để tra weather, freight/fuel nearest-previous. |

`hub_id` đầu vào phải map về một trong bốn hub thu gom:

- `HUB_VITHANH`
- `HUB_LONGXUYEN`
- `HUB_SOCTRANG`
- `HUB_VINHLONG`

Nếu không map được hub hoặc hub không phải collection hub, `optimize_route()` raise `ValueError`.

## 3. Định nghĩa 5 route cố định

Code route nằm ở `route_optimizer/candidates.py`. Mỗi route trả về `route_code`, `ten`,
`leg_ids`, tổng `distance_km`, tổng `duration_hr_base`.

| Code | `ten` trả về | Chặng |
|---|---|---|
| `A_DIRECT_ROAD` | `di_thang_hcm` | Hub → HCM bằng road |
| `B_ROAD_VIA_CT` | `qua_can_tho_duong_bo` | Hub → CT bằng road, CT → HCM bằng road |
| `C_WATER_ROAD_VIA_CT` | `qua_can_tho_sa_lan_duong_bo` | Hub → CT bằng water, CT → HCM bằng road |
| `D_WATER_VIA_CT` | `qua_can_tho_duong_thuy` | Hub → CT bằng water, CT → HCM bằng water |
| `E_ROAD_WATER_VIA_CT` | `qua_can_tho_duong_bo_sa_lan` | Hub → CT bằng road, CT → HCM bằng water |

Leg thật được lookup từ `legs.csv` theo `from_node_id`, `to_node_id`, `mode`, `active=True`.
Nếu không có đúng 1 leg active cho một cặp, `build_candidates()` raise `ValueError`.

## 4. Response schema

Schema thật lấy từ `route_optimizer/schemas.py`.

```json
{
  "hub_id": "HUB_VINHLONG",
  "priority": {
    "tier": "vegetable",
    "score": 0.7,
    "label": "Rau củ quả"
  },
  "recommended_route": "A_DIRECT_ROAD",
  "phuong_an": [
    {
      "ten": "di_thang_hcm",
      "route_code": "A_DIRECT_ROAD",
      "chi_phi_du_doan_vnd": 1045769.03,
      "thoi_gian_du_kien_gio": 3.21,
      "trang_thai": "available",
      "cost_breakdown": {
        "raw_transport_cost_vnd": 843784.19,
        "spoilage_cost_vnd": 201984.83,
        "transshipment_fee_vnd": 0.0,
        "total_cost_vnd": 1045769.03,
        "pricing_source": "freight_rates"
      }
    }
  ],
  "khuyen_nghi": "di_thang_hcm",
  "evidence": {
    "weather_ts": "2026-01-01T09:00:00+07:00",
    "price_ts": "2026-01-01T06:00:00+07:00"
  }
}
```

Top-level fields:

| Field | Type | Ghi chú |
|---|---|---|
| `hub_id` | string | Canonical node id sau normalize. |
| `priority` | object | Kết quả phân loại độ nhạy hàng hóa. |
| `recommended_route` | route code hoặc null | Route available có `chi_phi_du_doan_vnd` thấp nhất. |
| `phuong_an` | array | Luôn trả đủ 5 route A-E, mỗi route available hoặc currently_unavailable. |
| `khuyen_nghi` | string hoặc null | Trả về `ten` của route winner; null nếu không có route available. |
| `evidence` | object | Timestamp weather/price đã dùng gần nhất. |

`priority`:

| Field | Type |
|---|---|
| `tier` | string: `seafood`, `vegetable`, `hard_fruit`, `grain_dry` |
| `score` | number |
| `label` | string tiếng Việt |

`phuong_an[]`:

| Field | Type | Ghi chú |
|---|---|---|
| `ten` | string | Tên route dạng slug tiếng Việt. |
| `route_code` | route code | Một trong 5 code A-E. |
| `chi_phi_du_doan_vnd` | number hoặc null | Null nếu route unavailable. |
| `thoi_gian_du_kien_gio` | number hoặc null | Null nếu route unavailable. |
| `trang_thai` | `available` hoặc `currently_unavailable` | Trạng thái route. |
| `ly_do` | string hoặc null | Chỉ có ý nghĩa khi unavailable. |
| `cost_breakdown` | object hoặc null | Chỉ có cho route available. |

`cost_breakdown`:

| Field | Type | Ghi chú |
|---|---|---|
| `raw_transport_cost_vnd` | number | Tổng chi phí vận chuyển trước spoilage và handling, đã nhân weather factor. |
| `spoilage_cost_vnd` | number | Chi phí hao hụt hàng hóa. |
| `transshipment_fee_vnd` | number | Phí trung chuyển tại Cần Thơ; route A là `0`. |
| `total_cost_vnd` | number | Bằng `chi_phi_du_doan_vnd`. |
| `pricing_source` | string hoặc null | Thường là `freight_rates`; có thể là `fuel_fallback` nếu thiếu freight rate. |

## 5. Feasibility và lý do unavailable

Route road không bị chặn bởi thời tiết trong `feasibility.py`; road factor chỉ làm tăng time/cost.
Route water có thể bị chặn.

Các `ly_do` hiện tại trong code:

| `ly_do` | Nguồn trong code | Khi nào xảy ra |
|---|---|---|
| `hang_khong_phu_hop_duong_thuy` | `feasibility.py` | Commodity canonical có `water_ok=False` và route có ít nhất một leg water. |
| `muc_nuoc_khong_an_toan` | `feasibility.py` | Leg water có `water_factor > 1.0`. |
| `tuyen_duong_thuy_khong_an_toan` | `feasibility.py` | `weather_bulletins.water_navigation_status` tại node leg water không thuộc `open` hoặc `not_applicable`. |
| `missing_weather` | `feasibility.py` | Không tìm được weather nearest-previous cho node của leg. |
| `vuot_deadline` | `optimizer.py` | Có `order_id`, tìm được `deadline_ts`, và `decision_ts + adjusted_duration > deadline_ts`. |
| `khong_co_phuong_tien_phu_hop` | `pricing.py` | Không có vehicle available, đúng mode, đúng compatible type, đủ capacity, available trước decision time. |
| `missing_fuel_price` | `pricing.py` | Freight rate không có và fallback cũng không tìm được fuel price. |

Deadline check chỉ chạy sau weather/commodity feasibility và trước pricing. Nếu route vượt deadline,
route đó không có cost/time trong response.

## 6. Công thức chi phí hiện tại

Pricing nằm ở `route_optimizer/pricing.py`.

Với mỗi leg, optimizer chọn vehicle rẻ nhất theo `cost_per_km_vnd` trong tập vehicle:

- cùng mode với leg
- `vehicle_type` thuộc `compatible_vehicle_types`
- `capacity_ton >= khoi_luong_kg / 1000`
- `status == "available"`
- `available_from_ts <= timestamp`

Chi phí vận chuyển ưu tiên dùng `freight_rates.csv`:

```text
raw_transport_leg_vnd =
  (fixed_fee_vnd + rate_vnd_per_ton_km * (khoi_luong_kg / 1000) * distance_km)
  * weather_factor
```

Trong đó:

- road leg dùng `road_factor`
- water leg dùng `water_factor`
- freight rate được lookup nearest-previous theo `(leg_id, vehicle_type)`

Nếu không có freight rate khớp, fallback về công thức cũ:

```text
raw_transport_leg_vnd =
  distance_km * vehicle.cost_per_km_vnd * fuel_price_ratio * weather_factor
```

Fallback được log vào `pricing.FREIGHT_RATE_FALLBACKS`.

Chi phí hao hụt:

```text
spoilage_cost_vnd =
  (loss_pct_per_hour / 100)
  * value_vnd_per_kg
  * khoi_luong_kg
  * thoi_gian_du_kien_gio
```

Phí trung chuyển:

```text
transshipment_fee_vnd =
  150 * khoi_luong_kg nếu route có leg đi qua CT_HUB
  0 nếu A_DIRECT_ROAD
```

Tổng chi phí:

```text
chi_phi_du_doan_vnd =
  raw_transport_cost_vnd
  + spoilage_cost_vnd
  + transshipment_fee_vnd
```

## 7. Khuyến nghị và quyền chọn của user

`khuyen_nghi` và `recommended_route` chỉ là gợi ý tự động dựa trên route available có chi phí thấp
nhất. Đây không phải quyết định bắt buộc.

Người 5/Người 6 vẫn phải hiển thị đủ mọi route có `trang_thai="available"` để user chọn. Route có
`currently_unavailable` vẫn nên hiển thị nhưng disable, kèm `ly_do`.

Gợi ý nối với Người 4:

- Nếu user chọn hoặc hệ thống khuyến nghị route qua Cần Thơ (`B`, `C`, `D`, `E`), Backend có thể
  gọi Layer AI 2, kèm `priority.score`.
- Nếu chọn `A_DIRECT_ROAD`, luồng có thể kết thúc ở Layer AI 1 vì không qua Cần Thơ.

## 8. Mapping và commodity priority

Mapping nằm ở root `normalizers.py`; `route_optimizer/normalizers.py` import lại từ đó.

Node mapping đã verify:

| node_id | slug | hub_name_vi |
|---|---|---|
| `HUB_VITHANH` | `vi_thanh` | `Hub Vị Thanh` |
| `HUB_LONGXUYEN` | `long_xuyen` | `Hub Long Xuyên` |
| `HUB_SOCTRANG` | `soc_trang` | `Hub Sóc Trăng` |
| `HUB_VINHLONG` | `vinh_long` | `Hub Vĩnh Long` |
| `CT_HUB` | `can_tho` | `Trung tâm trung chuyển Cần Thơ` |
| `HCM_MARKET` | `tp_hcm` | `Thị trường TP.HCM` |

Commodity tiers:

| Tier | Score | Commodity IDs |
|---|---:|---|
| `seafood` | 1.0 | `COM_PANGASIUS`, `COM_SHRIMP` |
| `vegetable` | 0.7 | `COM_SWEET_POTATO`, `COM_PURPLE_ONION`, `COM_VEGETABLE` |
| `hard_fruit` | 0.4 | `COM_POMELO`, `COM_PINEAPPLE`, `COM_ORANGE` |
| `grain_dry` | 0.1 | `COM_RICE`, `COM_SUGARCANE` |

Nếu `commodity_id` không khớp canonical, code dùng keyword từ `loai_hang`; nếu vẫn không match,
fallback tier là `hard_fruit`.

## 9. Ví dụ input và output thật

Input chạy bằng `optimize_route()` trên annual data mặc định:

```json
{
  "order_id": "ORD_2026_000001",
  "hub_id": "HUB_VINHLONG",
  "commodity_id": "COM_VEGETABLE",
  "loai_hang": "",
  "khoi_luong_kg": 3495.704632,
  "timestamp": "2026-01-01T09:58:52+07:00"
}
```

Output thật:

```json
{
  "hub_id": "HUB_VINHLONG",
  "priority": {
    "tier": "vegetable",
    "score": 0.7,
    "label": "Rau củ quả"
  },
  "recommended_route": "A_DIRECT_ROAD",
  "phuong_an": [
    {
      "ten": "di_thang_hcm",
      "route_code": "A_DIRECT_ROAD",
      "chi_phi_du_doan_vnd": 1045769.03,
      "thoi_gian_du_kien_gio": 3.21,
      "trang_thai": "available",
      "cost_breakdown": {
        "raw_transport_cost_vnd": 843784.19,
        "spoilage_cost_vnd": 201984.83,
        "transshipment_fee_vnd": 0.0,
        "total_cost_vnd": 1045769.03,
        "pricing_source": "freight_rates"
      }
    },
    {
      "ten": "qua_can_tho_duong_bo",
      "route_code": "B_ROAD_VIA_CT",
      "chi_phi_du_doan_vnd": 2228516.04,
      "thoi_gian_du_kien_gio": 4.72,
      "trang_thai": "available",
      "cost_breakdown": {
        "raw_transport_cost_vnd": 1407458.57,
        "spoilage_cost_vnd": 296701.78,
        "transshipment_fee_vnd": 524355.69,
        "total_cost_vnd": 2228516.04,
        "pricing_source": "freight_rates"
      }
    },
    {
      "ten": "qua_can_tho_sa_lan_duong_bo",
      "route_code": "C_WATER_ROAD_VIA_CT",
      "chi_phi_du_doan_vnd": null,
      "thoi_gian_du_kien_gio": null,
      "trang_thai": "currently_unavailable",
      "ly_do": "hang_khong_phu_hop_duong_thuy"
    },
    {
      "ten": "qua_can_tho_duong_thuy",
      "route_code": "D_WATER_VIA_CT",
      "chi_phi_du_doan_vnd": null,
      "thoi_gian_du_kien_gio": null,
      "trang_thai": "currently_unavailable",
      "ly_do": "hang_khong_phu_hop_duong_thuy"
    },
    {
      "ten": "qua_can_tho_duong_bo_sa_lan",
      "route_code": "E_ROAD_WATER_VIA_CT",
      "chi_phi_du_doan_vnd": null,
      "thoi_gian_du_kien_gio": null,
      "trang_thai": "currently_unavailable",
      "ly_do": "hang_khong_phu_hop_duong_thuy"
    }
  ],
  "khuyen_nghi": "di_thang_hcm",
  "evidence": {
    "weather_ts": "2026-01-01T09:00:00+07:00",
    "price_ts": "2026-01-01T06:00:00+07:00"
  }
}
```

## 10. Giả định và giới hạn hiện tại

- `handling_fee_per_kg_vnd = 150 VND/kg` là giả định mô phỏng, không phải số liệu thật.
- Deadline chỉ được check khi request có `order_id` và order đó tồn tại trong `orders.csv` của data dir đang load; nếu không có `order_id`, bỏ qua deadline check và không lỗi.
- Pricing ưu tiên `freight_rates.csv`; nếu thiếu dòng khớp `leg_id + vehicle_type + timestamp`, fallback về `fuel_prices x distance x fleet cost_per_km`.
- Tần suất fallback đo ngày 18/7/2026 trên 50 case `eval/reference_routes.csv`: `0/50`.
- `eval/reference_routes.csv` chỉ là bộ tự kiểm tra công thức; kết quả hiện tại đạt `94%` (`47/50`), không phải chuẩn bắt buộc phải khớp 100%.
- Vehicle được chọn độc lập theo từng leg bằng heuristic rẻ nhất trong nhóm compatible available; chưa có giữ cùng tài sản xuyên nhiều leg hoặc reserve fleet thật.
- Chưa xử lý concurrent request/state mutation; dữ liệu được load read-only và cache bằng `lru_cache`.

## 11. Checklist trạng thái hiện tại

- [x] DONE — Mapping node/slug/hub name 6/6 đã verify.
- [x] DONE — Mapping commodity tier/loss/value/compatible vehicle 10/10 đã verify.
- [x] DONE — Build đủ 5 route A-E từ `legs.csv`.
- [x] DONE — Feasibility water/weather/commodity.
- [x] DONE — Deadline feasibility khi có `order_id`.
- [x] DONE — Cost formula dùng `freight_rates.csv`, weather factor, spoilage, handling fee.
- [x] DONE — Output có `cost_breakdown`.
- [x] DONE — Test với `eval/reference_routes.csv`: `47/50 = 94%`.
- [ ] NOT DONE — API chưa test end-to-end với service của Người 5.
- [ ] NOT DONE — Chưa có test concurrent request/load test.
- [ ] NOT DONE — Chưa có stateful vehicle reservation sau khi user chọn route.
- [ ] NOT DONE — Chưa có cấu hình runtime cho `data_dir`; hiện mặc định annual data trong code.
- [ ] NOT DONE — Chưa có auth/logging production cho endpoint.
