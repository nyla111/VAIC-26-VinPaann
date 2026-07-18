# Data contract - version 3.0

Tài liệu này là contract cho 11 bảng canonical. Tên cột, enum và quan hệ khóa không được đổi âm thầm. CSV và JSON canonical có cùng schema logic và được xuất từ cùng DataFrame; JSON dùng `records`.

## Quy ước chung

| Quy ước | Contract |
|---|---|
| Encoding | UTF-8 |
| ID và enum | ASCII, phân biệt hoa/thường |
| Timestamp | ISO 8601, offset `+07:00` |
| Date | `YYYY-MM-DD` |
| Boolean CSV | Giá trị có thể parse nhất quán thành true/false |
| Boolean JSON | JSON boolean `true/false` |
| Null JSON | `null` |
| Đơn vị | Nằm trong tên cột: `_kg`, `_ton`, `_km`, `_hr`, `_vnd`, `_m`, `_mm` |
| Factor thời tiết | `1.0` bình thường; `>1.0` bất lợi hơn |
| Source type trong bảng | Enum theo từng bảng; đối chiếu taxonomy tài liệu tại `ANCHORS.md` |

Không thêm output của optimizer/agent vào input, gồm `recommended_route`, `predicted_cost`, `selected_vehicle`, `dispatch_decision`.

## Quan hệ

~~~text
nodes (node_id)
  ├──< legs.from_node_id
  ├──< legs.to_node_id
  ├──< orders.hub_id
  ├──< orders.destination_node_id
  ├──< weather.node_id
  ├──< weather_bulletins.node_id
  ├──< fleet.current_node_id
  ├──< fleet.owner_hub_id
  └──< ops_notes.hub_id

commodities (commodity_id)
  └──< orders.commodity_id

legs (leg_id)
  └──< freight_rates.leg_id

fleet (vehicle_id)
  └──< ops_notes.vehicle_id
~~~

Các FK phải tồn tại. `orders.hub_id` và `fleet.owner_hub_id` phải trỏ tới node phù hợp vai trò hub; `destination_node_id` mặc định là `HCM_MARKET`.

## 1. `nodes`

PK: `node_id`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `node_id` | string | no | Unique, ASCII |
| `name_vi` | string | no | Nhãn hiển thị tiếng Việt |
| `node_type` | enum | no | `farm_hub`, `transshipment`, `market` |
| `location_label` | string | no | Địa danh vận hành |
| `lat` | float64 | no | `-90 <= lat <= 90` |
| `lon` | float64 | no | `-180 <= lon <= 180` |
| `on_river` | boolean | no | |
| `active` | boolean | no | |
| `source_type` | enum | no | `verified`, `user_provided`, `assumption` |

Node active bắt buộc:

- `HUB_VITHANH`
- `HUB_LONGXUYEN`
- `HUB_SOCTRANG`
- `HUB_VINHLONG`
- `CT_HUB`
- `HCM_MARKET`

Các node optional trong config không tham gia annual/scenario khi `extra_hubs: false`.

## 2. `legs`

PK: `leg_id`. FK: `from_node_id`, `to_node_id` -> `nodes.node_id`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `leg_id` | string | no | Unique, ASCII |
| `from_node_id` | string | no | FK |
| `to_node_id` | string | no | FK |
| `mode` | enum | no | `road`, `water` |
| `distance_km` | float64 | no | `> 0` |
| `duration_hr_base` | float64 | no | `> 0` |
| `weather_sensitivity` | enum | no | `road_flood`, `water_level`, `mixed`, `low` |
| `bidirectional` | boolean | no | Không có nghĩa là generator nhân đôi row |
| `active` | boolean | no | |
| `source_type` | enum | no | `verified`, `user_provided`, `assumption` |
| `source_note` | string | no | Provenance/giả định ngắn |

Coverage active:

- Mỗi hub có road leg thẳng tới `HCM_MARKET`.
- Mỗi hub có road leg tới `CT_HUB`.
- Bốn hub demo có water leg riêng tới `CT_HUB`.
- `CT_HUB` có road và water leg tới `HCM_MARKET`.

`bidirectional=true` cho phép downstream tạo cạnh ngược trong graph. ID và distance trong file vẫn mô tả row theo `from -> to`; không tự tạo thêm charge hai chiều.

## 3. `commodities`

PK: `commodity_id`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `commodity_id` | string | no | Unique, ASCII |
| `name_vi` | string | no | |
| `category` | string | no | `grain`, `fruit`, `aquatic`, `vegetable`, `industrial_crop` |
| `perishability_level` | int64 | no | `1..5` |
| `max_hold_hours` | float64 | no | `> 0` |
| `loss_pct_per_hour` | float64 | no | `>= 0`, đơn vị phần trăm/giờ |
| `value_vnd_per_kg` | float64 | no | `> 0` |
| `needs_reefer` | boolean | no | |
| `water_ok` | boolean | no | |
| `compatible_vehicle_types` | string | no | Enum list nối bằng `|` |
| `source_type` | enum | no | `verified`, `user_provided`, `assumption` |

Commodity canonical hiện có:

`COM_RICE`, `COM_PANGASIUS`, `COM_SHRIMP`, `COM_POMELO`, `COM_SWEET_POTATO`, `COM_SUGARCANE`, `COM_PINEAPPLE`, `COM_PURPLE_ONION`, `COM_ORANGE`, `COM_VEGETABLE`.

Danh sách `compatible_vehicle_types` chỉ dùng các enum fleet bên dưới. Khi parse:

~~~python
allowed = set(row["compatible_vehicle_types"].split("|"))
~~~

## 4. `orders`

PK: `order_id`. FK: `hub_id`, `destination_node_id`, `commodity_id`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `order_id` | string | no | Unique |
| `hub_id` | string | no | FK -> active farm hub |
| `commodity_id` | string | no | FK -> `commodities` |
| `weight_kg` | float64 | no | `> 0` |
| `arrival_ts` | datetime-tz | no | ISO 8601 `+07:00` |
| `ready_ts` | datetime-tz | no | `>= arrival_ts` |
| `deadline_ts` | datetime-tz | no | `> ready_ts` |
| `destination_node_id` | string | no | FK; mặc định `HCM_MARKET` |
| `priority_level` | int64 | no | `1..5` |
| `status` | enum | no | `new`, `ready`, `cancelled` |

Orders là event stream. Không yêu cầu một row mỗi giờ. Annual target nằm trong `6000..12000` row và phải phủ 12 tháng.

## 5. `weather`

Khóa tự nhiên: `ts + node_id`. FK: `node_id`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `ts` | datetime-tz | no | Hourly, ISO 8601 `+07:00` |
| `node_id` | string | no | FK -> active node |
| `rainfall_mm` | float64 | no | `>= 0` |
| `river_level_m` | float64 | conditional | Null chỉ ở node không liên quan đường thủy |
| `flood_risk_idx` | float64 | no | `0..1` |
| `road_factor` | float64 | no | `>= 1.0` |
| `water_factor` | float64 | no | `>= 1.0` |
| `alert_level` | enum | no | `none`, `watch`, `warning`, `severe` |

Weather giữa các node có regional component chung và local noise nhỏ; không được xem các chuỗi node là độc lập. Dùng `road_factor` cho road leg và `water_factor` cho water leg.

## 6. `fleet`

PK: `vehicle_id`. FK: `current_node_id`, `owner_hub_id`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `vehicle_id` | string | no | Unique |
| `vehicle_type` | enum | no | Xem danh sách dưới |
| `mode` | enum | no | `road`, `water` |
| `capacity_ton` | float64 | no | `> 0` |
| `current_node_id` | string | no | FK |
| `status` | enum | no | `available`, `en_route`, `maintenance`, `reserved` |
| `available_from_ts` | datetime-tz | no | ISO 8601 `+07:00` |
| `cost_fixed_vnd` | float64 | no | `>= 0` |
| `cost_per_km_vnd` | float64 | no | `>= 0` |
| `speed_kmh` | float64 | no | `> 0` |
| `has_reefer` | boolean | no | |
| `owner_hub_id` | string | yes | FK -> node |

Vehicle type:

| `vehicle_type` | Mode | Capacity config |
|---|---|---:|
| `truck_5t` | road | 5 t |
| `truck_15t` | road | 15 t |
| `reefer_8t` | road | 8 t |
| `boat_50t` | water | 50 t |
| `barge_200t` | water | 200 t |
| `barge_500t` | water | 500 t |

Feasibility tối thiểu:

~~~text
status == available
available_from_ts <= decision_ts
capacity_ton >= required_weight_ton
vehicle_type thuộc compatible_vehicle_types
has_reefer == true nếu needs_reefer == true
mode phù hợp leg
~~~

Nếu split order được policy cho phép, capacity được kiểm tra theo phần order được gán, không âm thầm coi một xe chở quá tải.

## 7. `fuel_prices`

Khóa tự nhiên: `ts + fuel_type`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `ts` | datetime-tz | no | ISO 8601 `+07:00` |
| `fuel_type` | enum | no | `diesel_005s`, `gasoline`, `marine_diesel` |
| `price_vnd_per_liter` | float64 | no | `> 0` |
| `adjustment_date` | date | no | Ngày bắt đầu mức giá |
| `source_type` | enum | no | `verified`, `user_provided`, `simulated` |

Annual thay đổi theo kỳ 14 ngày và giữ nguyên trong kỳ. Scenario có thể thêm breakpoint có timestamp; S3 dùng ba bậc trong 72 giờ. Khi lookup, dùng mốc trước gần nhất theo `fuel_type`; không nội suy tuyến tính giữa hai kỳ.

## 8. `freight_rates`

Khóa tự nhiên: `ts + leg_id + vehicle_type + rate_type`. FK: `leg_id`; `mode` phải khớp mode của leg và vehicle.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `ts` | datetime-tz | no | ISO 8601 `+07:00` |
| `mode` | enum | no | `road`, `water` |
| `leg_id` | string | no | FK -> active leg |
| `vehicle_type` | string enum | no | Mode phải khớp |
| `fuel_type` | enum | no | road=`diesel_005s`, water=`marine_diesel` theo YAML |
| `fuel_price_vnd_per_liter` | float64 | no | Giá as-of đã dùng cho row |
| `fuel_cost_factor` | float64 | no | `> 0`, causal pass-through factor |
| `rate_vnd_per_ton_km` | float64 | no | `> 0` |
| `fixed_fee_vnd` | float64 | no | `>= 0` |
| `demand_idx` | float64 | no | `> 0` |
| `rate_type` | enum | no | `spot`, `contract` |

Tần suất cấu hình là 6 giờ. `rate_vnd_per_ton_km` đã hấp thụ cả `demand_idx` và `fuel_cost_factor`; downstream không nhân thêm lần nữa. Quan hệ fuel:

~~~text
fuel_cost_factor = max(
  minimum_factor,
  1 + beta_mode * (fuel_price_vnd_per_liter/base_fuel_price - 1)
)
~~~

Quote tối thiểu:

~~~text
weight_ton = weight_kg / 1000
freight_vnd = fixed_fee_vnd
            + rate_vnd_per_ton_km * weight_ton * distance_km
~~~

## 9. `weather_bulletins`

PK: `bulletin_id`; FK: `node_id`. Grain: một node × ngày.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `bulletin_id` | string | no | Unique, ASCII |
| `issued_at`, `valid_from`, `valid_to` | datetime-tz | no | `issued_at <= valid_from <= valid_to` |
| `node_id` | string | no | FK -> node |
| `severity` | enum | no | `none`, `watch`, `warning`, `severe` |
| `road_status` | enum | no | `open`, `restricted`, `closed` |
| `water_navigation_status` | enum | no | `open`, `caution`, `closed`, `not_applicable` |
| `max_rainfall_mm` | float64 | no | Max của weather trong ngày |
| `max_flood_risk_idx` | float64 | no | `0..1`, max trong ngày |
| `headline`, `bulletin_text` | text | no | Nội dung grounding tiếng Việt |
| `evidence_ref` | string | no | Khóa truy ngược `weather:date:node` |
| `source_type` | enum | no | `simulated` |

`closed` là hard constraint cho cửa sổ hiệu lực, không phải finite cost penalty.

## 10. `ops_notes`

PK: `note_id`; FK: `hub_id`, optional `vehicle_id`.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `note_id` | string | no | Unique, ASCII |
| `created_at`, `valid_until` | datetime-tz | no | `created_at <= valid_until` |
| `hub_id` | string | no | FK -> node |
| `vehicle_id` | string | yes | FK -> fleet |
| `note_type` | enum | no | `vehicle_status`, `daily_intake` |
| `constraint_code` | enum | no | Machine-readable constraint/reason |
| `is_blocking` | boolean | no | Hard block tại thời điểm note nếu true |
| `note_text` | text | no | Ghi chú mô phỏng, không chứa route winner |
| `evidence_ref` | string | no | `fleet:*` hoặc `orders:*` |
| `source_type` | enum | no | `simulated` |

## 11. `policy_docs`

PK: `policy_id`. Đây là SOP/policy text để agent cite; không phải văn bản pháp lý.

| Cột | Kiểu logic | Null | Ràng buộc |
|---|---|---:|---|
| `policy_id` | string | no | Unique, ASCII |
| `title` | string | no | Tiêu đề hiển thị |
| `effective_from` | date | no | Ngày hiệu lực trong pack |
| `applies_to` | string | no | Agent/entity scope |
| `policy_text` | text | no | Quy tắc đầy đủ |
| `citation_ref` | string | no | File/section nguồn |
| `source_type` | enum | no | `assumption`, `user_provided`, `verified` |

## Lookup thời gian an toàn

Không dùng giá/weather/rate ở tương lai. Với event time `t`:

~~~text
weather: latest row where node_id matches and ts <= t
fuel:    latest row where fuel_type matches and ts <= t
freight: latest row where leg_id, vehicle_type, rate_type match and ts <= t
~~~

Nếu không có mốc trước, đó là data gap; không backfill từ tương lai.

## Bốn JSON compatibility

Compatibility JSON chỉ có trong thư mục `compat/`. Chúng giữ format mảng object đơn giản như brief, timestamp vẫn là ISO 8601 `+07:00`.

### `dataset_orders.json`

| Field compatibility | Nguồn canonical | Biến đổi |
|---|---|---|
| `hub_id` | `orders.hub_id` | Giữ ID canonical `HUB_*` để join ổn định |
| `hub_name` | `nodes.name_vi` | Join `orders.hub_id = nodes.node_id` |
| `timestamp` | `orders.arrival_ts` | Đổi tên |
| `loai_hang` | commodity config | Mã tiếng Việt ASCII, ví dụ `lua_gao`, `tom`, `khom` |
| `khoi_luong_kg` | `orders.weight_kg` | Đổi tên |

Các field order bị lược: `order_id`, ready/deadline, destination, priority và status.

Ví dụ `hg_01` trong brief không được phát sinh vì config không khai báo alias đó. Nếu team cần alias bên ngoài, thêm một mapping explicit trong YAML ở release sau; không hard-code và không thay `HUB_VITHANH` âm thầm.

### `dataset_weather.json`

| Field compatibility | Nguồn canonical | Biến đổi |
|---|---|---|
| `region` | `weather.node_id` | Map qua `compatibility_exports.location_codes` |
| `timestamp` | `weather.ts` | Đổi tên |
| `canh_bao_mua_lu` | `weather.alert_level` | `none -> thap`, `watch -> trung_binh`, `warning/severe -> cao` |
| `muc_nuoc_song_cm` | `weather.river_level_m` | `river_level_m * 100`; null được giữ null |

Các field rainfall, risk và factor bị lược.

### `dataset_fleet.json`

| Field compatibility | Nguồn canonical | Biến đổi |
|---|---|---|
| `vehicle_id` | `fleet.vehicle_id` | Giữ nguyên |
| `loai` | `fleet.mode` | `road -> xe_tai`, `water -> sa_lan` |
| `suc_chua_kg` | `fleet.capacity_ton` | `capacity_ton * 1000` |
| `vi_tri_hien_tai` | `fleet.current_node_id` | Map qua location code |
| `trang_thai` | `fleet.status` | `available -> ranh`, `en_route -> dang_chay`, `maintenance -> bao_tri`, `reserved -> da_dat` |

`loai` cố ý collapse ghe và sà lan thành `sa_lan`, và collapse truck/reefer thành `xe_tai`. Dùng canonical fleet để kiểm tra reefer/capacity chính xác.

### `dataset_price.json`

| Field compatibility | Nguồn | Biến đổi |
|---|---|---|
| `timestamp` | `freight_rates.ts` | Nhịp 6 giờ của demand projection |
| `gia_nhien_lieu_per_km` | diesel + YAML | `diesel_005s.price_vnd_per_liter * 0.35 liter/km` |
| `gia_thue_xe_tai_per_km` | reference `truck_5t` + freight | `median(cost_per_km) * mean(road demand_idx * fuel_cost_factor)` |
| `gia_thue_sa_lan_per_km` | reference `boat_50t` + freight | `median(cost_per_km) * mean(water demand_idx * fuel_cost_factor)` |

Diesel được join backward-asof vào từng timestamp freight. Các reference hiện tại lần lượt là `diesel_005s`, `truck_5t`, `boat_50t`. Compatibility price đã hấp thụ demand index vào hai giá thuê/km nhưng không lộ `rate_vnd_per_ton_km`, leg multiplier, fixed fee, spot/contract hoặc loại xe khác; optimizer phải dùng `fuel_prices` và `freight_rates`.

## Nguồn CSV/JSON và checksum

Mỗi table được tạo một lần trong bộ nhớ:

~~~text
generation rules + resolved YAML + RNG stream
                    |
                 DataFrame
                 /       \
         csv/<table>.csv  json/<table>.json
                    |
             compatibility projection
~~~

Canonical serialization phải ổn định về thứ tự cột/row để checksum tái lập được. Compatibility export là downstream projection của canonical object, không chạy random lần hai.

## Versioning

- Thêm cột optional hoặc projection mới: tăng minor version và giữ reader cũ nếu có thể.
- Đổi tên/xóa cột, đổi enum/nghĩa/đơn vị: breaking change, tăng major version.
- Mọi thay đổi phải cập nhật đồng thời file này và `CHANGELOG.md`.
- `compat/` không nới contract của 11 bảng và không được dùng để che một breaking change canonical.
