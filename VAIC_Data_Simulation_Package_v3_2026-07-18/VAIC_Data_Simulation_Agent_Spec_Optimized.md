---
title: "Execution Contract — Data & Simulation Lead"
project: "VAIC 2026 — AI Logistics for Mekong Delta Agriculture"
version: "2.0"
language: "vi"
default_timezone: "Asia/Bangkok"
default_seed: 20260717
---

# 0. CÁCH SỬ DỤNG TÀI LIỆU NÀY

Toàn bộ file này là **chỉ thị thực thi**, không phải tài liệu để tóm tắt hoặc thảo luận.

Khi nhận file này, AI phải:

1. Đọc toàn bộ yêu cầu.
2. Bắt đầu tạo cấu trúc thư mục, schema, generator, dữ liệu và validation.
3. Không dừng ở mức kế hoạch, pseudo-code hoặc gợi ý.
4. Không hỏi “có muốn tôi làm tiếp không?”.
5. Chỉ nêu blocker khi blocker đó thực sự ngăn không thể tạo deliverable.

## Thứ tự ưu tiên khi có mâu thuẫn

1. **Execution Contract** và Definition of Done.
2. **Data Contract / Schema**.
3. **Generation Rules và Acceptance Tests**.
4. **Scenario Rules**.
5. **Project Context / Proposal**.
6. Các ví dụ, con số minh họa hoặc ghi chú cũ.

Quy định ở mức ưu tiên cao hơn luôn thắng.

---

# 1. ROLE VÀ NHIỆM VỤ

Bạn là **Data & Simulation Lead** trong hackathon 48 giờ về ứng dụng AI trong nông nghiệp.

Nhiệm vụ duy nhất của bạn là tạo một **bộ dữ liệu semi-synthetic có thể tái lập**, đủ để:

- viết proposal có căn cứ;
- chạy demo end-to-end;
- chạy simulation cho Route & Cost Optimizer;
- chạy simulation cho Forecast & Dispatch Agent;
- tính impact so với baseline;
- bàn giao ngay cho backend, frontend, data science và business team.

Bạn **không** chịu trách nhiệm xây giao diện, huấn luyện mô hình ML hoàn chỉnh hoặc viết pitch deck. Bạn chỉ tạo dữ liệu, generator, validation và tài liệu giao tiếp dữ liệu.

---

# 2. DEFINITION OF DONE

Task chỉ được xem là hoàn thành khi có đủ các deliverable sau.

## 2.1. Năm logical data pack

| Pack | Nội dung | Các bảng vật lý |
|---|---|---|
| Reference Pack | node, tuyến/chặng, thuộc tính nông sản | `nodes`, `legs`, `commodities` |
| Dataset 1 | đơn hàng theo hub | `orders` |
| Dataset 2 | thời tiết, mưa, lũ, mực nước | `weather` |
| Dataset 3 | đội xe tải, xe lạnh, ghe, sà lan | `fleet` |
| Dataset 4 | giá nhiên liệu và giá cước | `fuel_prices`, `freight_rates` |

**Tổng cộng: 5 logical pack và 8 bảng vật lý.**

Không được gọi toàn bộ đầu ra là “4 bảng”. Bốn dataset trong brief là bốn nhóm dữ liệu động; Reference Pack là đầu vào tĩnh bắt buộc.

## 2.2. Bộ file bắt buộc

```text
project_root/
├── README.md
├── SCHEMA.md
├── ANCHORS.md
├── CHANGELOG.md
├── requirements.txt
├── config/
│   ├── base.yaml
│   ├── baseline_policy.yaml
│   └── scenarios/
│       ├── S1_normal.yaml
│       ├── S2_flood.yaml
│       └── S3_price_shock.yaml
├── src/
│   ├── generate_data.py
│   └── validate_data.py
├── data/
│   ├── stubs/
│   │   ├── nodes.csv
│   │   ├── legs.csv
│   │   ├── commodities.csv
│   │   ├── orders.csv
│   │   ├── weather.csv
│   │   ├── fleet.csv
│   │   ├── fuel_prices.csv
│   │   └── freight_rates.csv
│   └── generated/
│       ├── annual/
│       │   ├── csv/
│       │   ├── json/
│       │   └── metadata.json
│       └── scenarios/
│           ├── S1_normal/{csv,json,metadata.json}
│           ├── S2_flood/{csv,json,metadata.json}
│           └── S3_price_shock/{csv,json,metadata.json}
└── reports/
    └── validation_report.json
```

## 2.3. Điều kiện hoàn thành kỹ thuật

- `generate_data.py` chạy được từ command line.
- `validate_data.py` chạy được từ command line.
- Cùng `seed` và cùng config phải tạo ra dữ liệu giống hệt nhau.
- Mỗi bảng phải xuất cả CSV và JSON từ cùng một DataFrame/object nguồn.
- Validation phải pass toàn bộ hard checks.
- Có báo cáo rõ phần nào là dữ liệu có nguồn, phần nào là giả định mô phỏng.
- Không có logic quan trọng nào chỉ tồn tại trong code mà không được khai báo trong YAML hoặc tài liệu.

---

# 3. CÁC QUY TẮC KHÔNG ĐƯỢC VI PHẠM

1. **Tạo generator, không sửa CSV thủ công.** CSV chỉ là output.
2. **Schema trước, data sau.** Tạo `SCHEMA.md` và tám file stub trước khi sinh dữ liệu đầy đủ.
3. **Deterministic.** Seed mặc định là `20260717`; mọi random generator phải dùng seed truyền từ config hoặc CLI.
4. **Không hard-code kết luận demo.** Chỉ hard-code quy tắc sinh dữ liệu và ràng buộc nghiệp vụ. Kết quả route phải xuất hiện từ dữ liệu và công thức downstream.
5. **Mọi magic number phải nằm trong YAML.** Ví dụ: seasonality multiplier, flood threshold, diesel shock, capacity mix, loss rate.
6. **Không tự ý đổi schema sau khi freeze.** Khi buộc phải đổi, cập nhật `SCHEMA.md`, `CHANGELOG.md`, version và giữ backward compatibility nếu khả thi.
7. **Key dùng ASCII.** Ví dụ: `HUB_VITHANH`, `COM_RICE`, `MODE_ROAD`.
8. **Label hiển thị được dùng tiếng Việt.** Ví dụ: `name_vi = "Hub Vị Thanh"`.
9. **Encoding:** UTF-8, không phụ thuộc Excel.
10. **Thời gian:** ISO 8601 có offset `+07:00`.
11. **Đơn vị phải nằm trong tên cột.** Ví dụ: `_kg`, `_ton`, `_km`, `_hr`, `_vnd`, `_vnd_per_liter`.
12. **Không trộn fact và assumption.** Mọi trường hoặc giá trị anchor phải có provenance trong `ANCHORS.md`.
13. **Không dùng tên địa giới hành chính làm logic.** Dùng tên địa danh/hub như “Hub Vị Thanh”, “Hub Long Xuyên” để tránh phụ thuộc thay đổi hành chính.
14. **Không tạo output của mô hình trong input data.** Ví dụ: không tạo sẵn `recommended_route` hoặc `dispatch_decision` trong `orders.csv`.
15. **Không để Layer 1 và Layer 2 dùng hai định nghĩa chi phí khác nhau.** Cả hai phải đọc chung `legs.csv`, `fleet.csv`, `fuel_prices.csv` và `freight_rates.csv`.

---

# 4. PROJECT CONTEXT TỐI THIỂU

Hệ thống logistics có hai lớp quyết định nối tiếp:

```text
Nông dân
  → Hub thu gom tại địa phương
  → Layer 1: Route & Cost Optimizer
      A. Đi thẳng TP.HCM bằng đường bộ
      B. Đi đường bộ tới Cần Thơ, sau đó gộp tải
      C. Đi đường thủy tới Cần Thơ, sau đó gộp tải
  → Cần Thơ Transshipment Hub
  → Layer 2: Forecast & Dispatch Agent
  → TP.HCM
```

Dữ liệu phải hỗ trợ hai chức năng:

- **Layer 1:** tính tính khả thi, thời gian và chi phí dự kiến của A/B/C.
- **Layer 2:** gom hàng, chọn phương tiện, quyết định chạy/chờ và phát lệnh dispatch.

## Quy ước route cho bản demo v1

- Phương án A: chặng road từ hub đến TP.HCM.
- Phương án B: chặng road từ hub đến Cần Thơ + outbound leg từ Cần Thơ đến TP.HCM.
- Phương án C: chặng water từ hub đến Cần Thơ + outbound leg từ Cần Thơ đến TP.HCM.
- Outbound leg có thể là road hoặc water nếu commodity và fleet cho phép.
- Hàng dễ hư phải bị ràng buộc bởi `max_hold_hours`, `needs_reefer` và thời gian hành trình; không được chọn water chỉ vì rẻ.

---

# 5. TRÌNH TỰ THỰC THI BẮT BUỘC

## Phase P0 — Freeze contract và unblock team

Tạo trước:

- `SCHEMA.md`;
- tám file CSV stub, mỗi file tối thiểu 10 dòng hợp lệ;
- `config/base.yaml`;
- `README.md` bản đầu.

**Gate P0:** backend/frontend có thể đọc file và code theo đúng tên cột mà không chờ data hoàn chỉnh.

## Phase P1 — Tạo Reference Pack

Tạo và kiểm tra:

- `nodes.csv`;
- `legs.csv`;
- `commodities.csv`;
- `ANCHORS.md`.

**Gate P1:** Layer 1 có thể dựng graph route và tính cost prototype.

## Phase P2 — Generator annual baseline

Sinh dữ liệu năm 2026 theo giờ hoặc theo event:

- `orders`;
- `weather`;
- `fleet`;
- `fuel_prices`;
- `freight_rates`.

**Gate P2:** `generate_data.py --config config/base.yaml` tạo đủ CSV/JSON annual.

## Phase P3 — Scenario packs và baseline

Tạo:

- `S1_normal`;
- `S2_flood`;
- `S3_price_shock`;
- `baseline_policy.yaml`.

**Gate P3:** ít nhất một route-sensitive signal thay đổi giữa các scenario mà không sửa code.

## Phase P4 — Validation và handoff

Tạo:

- `validate_data.py`;
- `validation_report.json`;
- hướng dẫn join dữ liệu;
- lệnh chạy generator và validator.

**Gate P4:** validation pass và toàn bộ team có thể dùng dữ liệu ngay.

---

# 6. DATA CONTRACT — 8 BẢNG VẬT LÝ

Các cột dưới đây là contract. Không tự ý đổi tên.

## 6.1. `nodes.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `node_id` | string | yes | PK, ASCII, unique |
| `name_vi` | string | yes | nhãn tiếng Việt |
| `node_type` | enum | yes | `farm_hub`, `transshipment`, `market` |
| `location_label` | string | yes | địa danh vận hành, không cần phụ thuộc tên tỉnh hiện hành |
| `lat` | float | yes | `-90..90` |
| `lon` | float | yes | `-180..180` |
| `on_river` | boolean | yes | `true/false` |
| `active` | boolean | yes | mặc định `true` |
| `source_type` | enum | yes | `verified`, `user_provided`, `assumption` |

Node bắt buộc:

- `HUB_VITHANH` — Hub Vị Thanh;
- `HUB_LONGXUYEN` — Hub Long Xuyên;
- `HUB_SOCTRANG` — Hub Sóc Trăng;
- `HUB_VINHLONG` — Hub Vĩnh Long;
- `CT_HUB` — Trung tâm trung chuyển Cần Thơ;
- `HCM_MARKET` — thị trường TP.HCM.

## 6.2. `legs.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `leg_id` | string | yes | PK, ASCII |
| `from_node_id` | string | yes | FK → `nodes.node_id` |
| `to_node_id` | string | yes | FK → `nodes.node_id` |
| `mode` | enum | yes | `road`, `water` |
| `distance_km` | float | yes | `> 0` |
| `duration_hr_base` | float | yes | `> 0` |
| `weather_sensitivity` | enum | yes | `road_flood`, `water_level`, `mixed`, `low` |
| `bidirectional` | boolean | yes | mặc định theo config |
| `active` | boolean | yes | `true/false` |
| `source_type` | enum | yes | `verified`, `user_provided`, `assumption` |
| `source_note` | string | yes | mô tả nguồn/giả định ngắn |

Coverage bắt buộc:

- Mỗi hub có direct road leg tới TP.HCM.
- Mỗi hub có road leg tới Cần Thơ.
- Hub có điều kiện thủy phù hợp phải có water leg tới Cần Thơ.
- Cần Thơ có ít nhất một road leg và một water leg tới TP.HCM.

## 6.3. `commodities.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `commodity_id` | string | yes | PK, ASCII |
| `name_vi` | string | yes | tên hiển thị |
| `category` | string | yes | grain, fruit, aquatic, vegetable, industrial_crop |
| `perishability_level` | int | yes | `1..5` |
| `max_hold_hours` | float | yes | `> 0` |
| `loss_pct_per_hour` | float | yes | `>= 0` |
| `value_vnd_per_kg` | float | yes | `> 0` |
| `needs_reefer` | boolean | yes | ràng buộc phương tiện |
| `water_ok` | boolean | yes | có thể đi water hay không |
| `compatible_vehicle_types` | string | yes | danh sách phân cách bằng `|` |
| `source_type` | enum | yes | `verified`, `user_provided`, `assumption` |

Commodity tối thiểu:

- lúa/gạo;
- cá tra;
- tôm;
- bưởi;
- khoai lang;
- mía;
- khóm/dứa;
- hành tím hoặc cam sành.

## 6.4. `orders.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `order_id` | string | yes | PK |
| `hub_id` | string | yes | FK → farm hub |
| `commodity_id` | string | yes | FK → commodities |
| `weight_kg` | float | yes | `> 0` |
| `arrival_ts` | datetime | yes | ISO 8601 `+07:00` |
| `ready_ts` | datetime | yes | `>= arrival_ts` |
| `deadline_ts` | datetime | yes | `> ready_ts` |
| `destination_node_id` | string | yes | mặc định `HCM_MARKET` |
| `priority_level` | int | yes | `1..5`, suy ra từ commodity + deadline |
| `status` | enum | yes | `new`, `ready`, `cancelled` |

Không tạo các cột output của optimizer như `recommended_route`, `predicted_cost` hoặc `selected_vehicle`.

## 6.5. `weather.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `ts` | datetime | yes | hourly, ISO 8601 `+07:00` |
| `node_id` | string | yes | FK → nodes |
| `rainfall_mm` | float | yes | `>= 0` |
| `river_level_m` | float | yes | nullable chỉ khi node không liên quan đường thủy |
| `flood_risk_idx` | float | yes | `0..1` |
| `road_factor` | float | yes | `>= 1.0`; multiplier thời gian/chi phí |
| `water_factor` | float | yes | `>= 1.0`; multiplier thời gian/chi phí |
| `alert_level` | enum | yes | `none`, `watch`, `warning`, `severe` |

`road_factor` và `water_factor` luôn có cùng nghĩa: **1.0 là bình thường, lớn hơn 1.0 là bất lợi hơn**.

## 6.6. `fleet.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `vehicle_id` | string | yes | PK |
| `vehicle_type` | enum | yes | `truck_5t`, `truck_15t`, `reefer_8t`, `boat_50t`, `barge_200t`, `barge_500t` |
| `mode` | enum | yes | `road`, `water` |
| `capacity_ton` | float | yes | `> 0` |
| `current_node_id` | string | yes | FK → nodes |
| `status` | enum | yes | `available`, `en_route`, `maintenance`, `reserved` |
| `available_from_ts` | datetime | yes | ISO 8601 `+07:00` |
| `cost_fixed_vnd` | float | yes | `>= 0` |
| `cost_per_km_vnd` | float | yes | `>= 0` |
| `speed_kmh` | float | yes | `> 0` |
| `has_reefer` | boolean | yes | compatibility constraint |
| `owner_hub_id` | string | no | FK → nodes, nullable |

## 6.7. `fuel_prices.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `ts` | datetime | yes | ISO 8601 `+07:00` |
| `fuel_type` | enum | yes | `diesel_005s`, `gasoline`, `marine_diesel` |
| `price_vnd_per_liter` | float | yes | `> 0` |
| `adjustment_date` | date | yes | ngày bắt đầu mức giá |
| `source_type` | enum | yes | `verified`, `user_provided`, `simulated` |

Giá nhiên liệu phải có dạng **bậc thang theo kỳ điều chỉnh**, không dùng random walk mượt từng giờ.

## 6.8. `freight_rates.csv`

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---:|---|
| `ts` | datetime | yes | ISO 8601 `+07:00` |
| `mode` | enum | yes | `road`, `water` |
| `leg_id` | string | yes | FK → legs |
| `vehicle_type` | string | yes | phải phù hợp với mode |
| `rate_vnd_per_ton_km` | float | yes | `> 0` |
| `fixed_fee_vnd` | float | yes | `>= 0` |
| `demand_idx` | float | yes | `> 0` |
| `rate_type` | enum | yes | `spot`, `contract` |

---

# 7. QUY TẮC SINH DỮ LIỆU

## 7.1. Phạm vi thời gian

- Annual baseline: từ `2026-01-01T00:00:00+07:00` đến `2026-12-31T23:00:00+07:00`.
- Weather: hourly.
- Fuel prices: stepwise theo kỳ, có thể forward-fill theo giờ khi xuất annual table.
- Freight rates: hourly hoặc mỗi 6 giờ, nhưng phải join được theo nearest previous timestamp.
- Orders: event stream, không bắt buộc có event mỗi giờ.
- Scenario pack: cửa sổ 72 giờ, sinh từ cùng engine với override config.

## 7.2. Orders phải có pattern có ý nghĩa

Dùng Poisson/negative-binomial hoặc phương pháp tương đương, có kiểm soát bởi:

- hub;
- commodity mix;
- mùa vụ;
- ngày trong tuần;
- giờ trong ngày;
- scenario modifier.

Pattern tối thiểu:

| Hub | Commodity chính | Pattern mô phỏng |
|---|---|---|
| Hub Long Xuyên | lúa, cá tra | lúa có các đợt mùa vụ; cá tra tương đối quanh năm |
| Hub Sóc Trăng | tôm, lúa, hành tím | tôm mạnh hơn giữa năm; hành tím mạnh cuối/đầu năm |
| Hub Vĩnh Long | bưởi, cam, khoai lang | trái cây có mùa cao điểm; khoai có nhiều đợt |
| Hub Vị Thanh | mía, khóm, lúa, cá | mía tăng cuối năm; khóm tương đối quanh năm |

Yêu cầu:

- Tổng annual orders mục tiêu: `6,000–12,000` dòng.
- Mỗi hub và commodity chính phải xuất hiện đủ để vẽ chart.
- Trọng lượng phải có distribution hợp lý, có min/max và không âm.
- Hàng dễ hư có deadline ngắn hơn hàng bền.
- Không dùng cùng một distribution cho mọi hub và commodity.

## 7.3. Weather phải có tương quan vùng

Không sinh mưa độc lập hoàn toàn cho từng node.

Phải có:

- regional weather component chung;
- local noise nhỏ theo node;
- mùa mưa/lũ và mùa khô;
- mực nước có seasonality;
- extreme event hiếm nhưng có chủ đích;
- `road_factor` tăng khi ngập/rain/flood risk tăng;
- `water_factor` tăng khi mực nước quá thấp hoặc quá cao nguy hiểm;
- điều kiện nước vừa phải có factor gần `1.0`.

## 7.4. Fleet phải hỗ trợ constraint thật

Fleet tối thiểu phải có:

- xe tải 5 tấn;
- xe tải 15 tấn;
- xe lạnh 8 tấn;
- ghe 50 tấn;
- sà lan 200 tấn;
- sà lan 500 tấn.

Yêu cầu:

- Có phương tiện `available`, `en_route`, `maintenance`, `reserved`.
- Có đủ phương tiện road và water tại các hub phù hợp.
- Scenario price shock phải giảm availability road hoặc tăng cost road.
- Reefer compatibility phải hoạt động qua `has_reefer`.
- Không để toàn bộ fleet luôn rảnh.

## 7.5. Giá phải có cấu trúc, không phải noise trắng

Fuel:

- stepwise theo kỳ điều chỉnh;
- mức biến động được khai báo trong YAML;
- không thay đổi ngẫu nhiên từng giờ.

Freight:

- base rate theo mode, leg, vehicle type;
- demand index theo giờ/ngày/mùa;
- spot rate biến động mạnh hơn contract rate;
- road và water có cấu trúc cost khác nhau;
- không để water luôn thắng hoặc road luôn thắng.

---

# 8. DISTANCE VÀ PROVENANCE POLICY

## 8.1. Thứ tự ưu tiên nguồn khoảng cách

1. Nguồn được xác minh và ghi trong `ANCHORS.md`.
2. Bảng khoảng cách người dùng cung cấp bên dưới.
3. Giá trị giả định có ghi rõ `source_type = assumption`.
4. Con số ví dụ trong narrative cũ chỉ dùng tham khảo, không được âm thầm đưa vào data.

## 8.2. Bảng khoảng cách người dùng cung cấp

Các giá trị này là **provisional anchors**, không mặc định là fact đã xác minh:

| From | To | Distance km |
|---|---|---:|
| Cần Thơ | TP.HCM | 191.0 |
| Cần Thơ | An Giang/Long Xuyên | 87.8 |
| Cần Thơ | Cà Mau | 199.0 |
| Cần Thơ | Đồng Tháp | 67.7 |
| Cần Thơ | Vĩnh Long | 79.2 |
| Cần Thơ | Tây Ninh | 264.0 |
| An Giang/Long Xuyên | TP.HCM | 233.0 |
| Cà Mau | TP.HCM | 314.0 |
| Đồng Tháp | TP.HCM | 144.0 |
| Vĩnh Long | TP.HCM | 144.0 |
| Tây Ninh | TP.HCM | 104.0 |

Quy tắc:

- Current demo scope chỉ bắt buộc bốn hub: Vị Thanh, Long Xuyên, Sóc Trăng, Vĩnh Long.
- Cà Mau, Đồng Tháp và Tây Ninh là optional; không thêm vào demo trừ khi `extra_hubs: true`.
- Khoảng cách còn thiếu cho Vị Thanh và Sóc Trăng phải được xác minh hoặc ghi là assumption.
- Không được trộn hai giá trị khác nhau cho cùng một leg mà không ghi conflict trong `ANCHORS.md`.
- Road distance và water distance phải là hai leg khác nhau; không lấy road distance thay cho water distance.

---

# 9. SCENARIO CONTRACT

Mỗi scenario phải dùng cùng codebase và cùng schema. Chỉ thay config/override.

## 9.1. `S1_normal`

- Cửa sổ đại diện mùa khô/bình thường.
- Mưa thấp đến vừa.
- Không có flood alert nghiêm trọng.
- Diesel và freight demand ở mức baseline.
- Fleet availability bình thường.

Sanity expectation cho lô hàng **không dễ hư**:

- Hub Vĩnh Long thường có lợi thế đi thẳng TP.HCM.
- Hub Vị Thanh hoặc Sóc Trăng có thể hưởng lợi từ consolidation qua Cần Thơ.
- Hub Long Xuyên phải có ít nhất một trường hợp water khả thi.

## 9.2. `S2_flood`

- Cửa sổ đại diện mùa mưa/lũ hoặc triều cường.
- Rainfall, flood risk và road factor tăng rõ ở các node/leg bị ảnh hưởng.
- Water factor không mặc định tốt hơn: mức nước vừa có thể thuận lợi, mức cực đoan phải gây penalty.
- Ít nhất một hub-route ranking phải thay đổi so với S1 khi downstream optimizer dùng dữ liệu.

## 9.3. `S3_price_shock`

- Diesel road tăng `18%` so với baseline, khai báo trong YAML.
- Road fleet availability giảm hoặc demand index road tăng.
- Water freight không tăng cùng tỷ lệ.
- Consolidation qua Cần Thơ trở nên hấp dẫn hơn cho một số lô hàng bền.
- Không ép hàng dễ hư sang water nếu vi phạm deadline hoặc reefer constraint.

## 9.4. Không hard-code expected winner

Các expectation trên là **sanity checks**, không phải nhãn cần viết thẳng vào dữ liệu.

Nếu kết quả downstream không đúng expectation, AI phải:

1. kiểm tra geometry, rate, duration, weather factor và consolidation assumptions;
2. điều chỉnh config có lý do;
3. không chèn cột route recommendation vào input data;
4. ghi thay đổi trong `CHANGELOG.md`.

---

# 10. BASELINE POLICY CHO IMPACT

Tạo `config/baseline_policy.yaml` để business team chạy so sánh “cách cũ” và “có AI”.

Baseline mặc định:

```yaml
policy_name: habit_based_v1
route_rule: always_direct_road_to_hcm
dispatch_rule:
  min_load_factor: 0.60
  max_wait_hours: 24
weather_awareness: false
price_awareness: false
vehicle_rule: first_available_compatible_vehicle
split_large_orders: true
```

Không tính sẵn impact giả tạo. Chỉ cung cấp policy machine-readable để cùng simulation engine có thể chạy baseline và optimized policy trên cùng data.

Impact downstream tối thiểu cần tính được:

- tổng chi phí vận chuyển;
- chi phí trên mỗi tấn;
- thời gian giao trung bình;
- load factor trung bình;
- số chuyến thiếu tải;
- estimated spoilage loss;
- số lô trễ deadline;
- CO2 proxy nếu team có hệ số phát thải.

---

# 11. VALIDATION CONTRACT

`validate_data.py` phải chạy hard checks và trả exit code khác 0 khi fail.

## 11.1. Schema checks

- Đủ tám bảng.
- Đủ cột, đúng tên, không thừa cột output của model.
- Kiểu dữ liệu có thể parse.
- Required field không null.

## 11.2. Key và referential integrity

- PK unique.
- Mọi FK tồn tại.
- Không orphan `hub_id`, `commodity_id`, `node_id`, `leg_id`.

## 11.3. Range checks

- Không có weight, distance, cost, capacity, speed âm hoặc bằng 0 khi không hợp lệ.
- `0 <= flood_risk_idx <= 1`.
- `road_factor >= 1` và `water_factor >= 1`.
- `1 <= perishability_level <= 5`.
- `1 <= priority_level <= 5`.

## 11.4. Temporal checks

- `arrival_ts <= ready_ts < deadline_ts`.
- Timestamp có timezone.
- Weather có đủ hourly coverage.
- Fuel/freight có thể forward-fill/join theo thời gian.
- `available_from_ts` hợp lệ.

## 11.5. Coverage checks

- Đủ bốn hub bắt buộc.
- Đủ commodity tối thiểu.
- Orders xuất hiện ở cả 12 tháng trong annual baseline.
- Có road và water data.
- Có available và unavailable fleet states.

## 11.6. Scenario signal checks

- S2 có rainfall/flood/road factor cao hơn S1 ở vùng mục tiêu.
- S3 có diesel road tăng đúng mức config.
- S3 có road fleet availability thấp hơn hoặc road demand cao hơn S1.
- File của ba scenario khác hash nhưng cùng schema.

## 11.7. Reproducibility checks

Chạy generator hai lần với cùng seed/config phải cho cùng:

- row count;
- primary keys;
- checksum từng file hoặc checksum canonical representation.

## 11.8. Báo cáo

`reports/validation_report.json` tối thiểu gồm:

```json
{
  "status": "PASS",
  "dataset_version": "2.0",
  "seed": 20260717,
  "checks_passed": 0,
  "checks_failed": 0,
  "row_counts": {},
  "file_checksums": {},
  "warnings": [],
  "generated_at": "ISO-8601"
}
```

---

# 12. ANCHORS VÀ ASSUMPTIONS

`ANCHORS.md` phải có bảng tối thiểu:

| Biến/nhóm biến | Giá trị hoặc range | Loại | Nguồn/giải thích | Ngày kiểm tra | Dùng ở đâu |
|---|---|---|---|---|---|

Loại chỉ được dùng:

- `verified_fact`;
- `user_provided_anchor`;
- `simulation_assumption`;
- `derived_value`.

Các nhóm phải được ghi rõ:

- tọa độ node;
- road distance;
- water distance;
- base duration/speed;
- mùa vụ commodity;
- seasonality weather/flood;
- capacity và vehicle mix;
- fuel price anchor;
- freight rate range;
- loss rate;
- consolidation assumptions.

Nếu có internet/tool tra cứu:

- xác minh các fact dễ bị judge kiểm tra;
- ghi URL/tên nguồn và ngày truy cập trong `ANCHORS.md`;
- không thay đổi schema vì tìm được nguồn mới.

Nếu không có internet:

- không giả vờ đã xác minh;
- dùng `user_provided_anchor` hoặc `simulation_assumption`;
- thêm warning rõ trong validation report.

---

# 13. CONFIG CONTRACT

Mọi tham số sau phải nằm trong YAML, không hard-code trong Python:

- seed;
- date range;
- timezone;
- hub list;
- commodity mix;
- seasonality multiplier;
- hourly arrival pattern;
- weight distribution parameters;
- weather seasonal parameters;
- flood thresholds;
- factor mapping;
- fleet count và status mix;
- base fuel prices;
- base freight rates;
- scenario shock multiplier;
- baseline policy parameters;
- output paths;
- optional extra hubs.

CLI tối thiểu:

```bash
python src/generate_data.py --config config/base.yaml
python src/generate_data.py --config config/scenarios/S1_normal.yaml
python src/generate_data.py --config config/scenarios/S2_flood.yaml
python src/generate_data.py --config config/scenarios/S3_price_shock.yaml
python src/validate_data.py --root data/generated --report reports/validation_report.json
```

Nên hỗ trợ override:

```bash
python src/generate_data.py --config config/base.yaml --seed 20260717 --format both
```

---

# 14. HANDOFF CONTRACT CHO CÁC TEAM KHÁC

## Layer 1 — Route & Cost Optimizer

Join/read:

- `orders` → `commodities`;
- `nodes` + `legs` để dựng route graph;
- `weather` theo timestamp và node/leg;
- `fuel_prices` theo nearest previous timestamp;
- `freight_rates` theo timestamp + leg + vehicle type;
- `fleet` để kiểm tra feasibility.

Layer 1 không được tự định nghĩa lại distance hoặc fuel price.

## Layer 2 — Forecast & Dispatch Agent

Join/read:

- orders đã được Layer 1 chuyển qua Cần Thơ;
- commodity urgency;
- fleet availability/capacity;
- outbound legs;
- weather risk;
- freight rate.

Layer 2 không được tự tạo một bảng cost riêng không tương thích với Layer 1.

## Frontend

- Dùng JSON output.
- Dùng `nodes.lat/lon` để vẽ map.
- Dùng scenario folder để chuyển dropdown mà không đổi schema.

## Business & Impact

- Dùng annual baseline + scenario packs.
- Chạy cùng data với `baseline_policy.yaml` và optimized policy.
- Mọi con số pitch phải truy ngược được về config hoặc anchor.

---

# 15. FORMAT PHẢN HỒI BẮT BUỘC CỦA AI

Khi thực thi task, phản hồi cuối phải theo đúng thứ tự:

1. **Status:** hoàn thành/partial và lý do.
2. **File tree:** liệt kê file đã tạo.
3. **Commands:** lệnh generate và validate.
4. **Validation summary:** pass/fail, row counts, warnings.
5. **Key assumptions:** tối đa 10 assumption quan trọng.
6. **Handoff notes:** điểm người làm Layer 1/2/frontend cần biết.
7. **Blockers còn lại:** chỉ liệt kê blocker thật; không kết thúc bằng câu hỏi mời làm tiếp.

Không lặp lại toàn bộ proposal. Không dành phần lớn phản hồi để giải thích kế hoạch đã rõ trong file này.

Nếu môi trường cho phép ghi file, phải tạo file thật.

Nếu môi trường không cho phép ghi file, phải xuất đầy đủ nội dung từng file trong code block có tên file rõ ràng; không chỉ đưa pseudo-code.

---

# 16. CÁC HÀNH VI BỊ CẤM

- Chỉ trả lời bằng plan hoặc checklist.
- Tạo vài dòng data mẫu rồi tuyên bố hoàn thành.
- Dùng random không seed.
- Tạo CSV và JSON bằng hai logic khác nhau.
- Dùng dấu tiếng Việt trong ID/enum.
- Tự thêm route recommendation vào orders.
- Dùng một giá trị khoảng cách mâu thuẫn mà không ghi provenance.
- Để weather của từng node hoàn toàn độc lập.
- Để fuel price biến động mượt từng giờ.
- Để mọi phương tiện luôn available.
- Làm water luôn rẻ nhất hoặc road luôn nhanh nhất trong mọi trường hợp.
- Ép AI downstream luôn khuyên đi qua Cần Thơ.
- Bịa nguồn hoặc nói dữ liệu “thật” khi chỉ là giả định.
- Hỏi người dùng có muốn tiếp tục sau khi chưa hoàn thành deliverable.

---

# 17. SUCCESS CRITERIA NGHIỆP VỤ

Bộ data đạt yêu cầu khi có thể chứng minh bằng simulation rằng:

1. Không phải hub nào cũng nên đi qua Cần Thơ.
2. Cùng một hub có thể đổi lựa chọn khi weather, price hoặc fleet thay đổi.
3. Hàng dễ hư có thể chọn tuyến nhanh hơn dù chi phí cao hơn.
4. Consolidation làm giảm cost/ton khi đủ tải nhưng có trade-off thời gian chờ.
5. Dispatch agent có thể quyết định “chạy ngay”, “chờ đủ tải” hoặc “chờ phương tiện”.
6. Impact được so sánh trên cùng dataset và cùng thời kỳ, không dùng hai bộ giả định khác nhau.
7. Judge có thể truy ngược các con số chính về `ANCHORS.md`, YAML config và validation report.

---

# 18. LỆNH KHỞI ĐỘNG

Bắt đầu ngay từ **Phase P0**.

Không viết lại proposal. Không hỏi thêm khi có thể dùng assumption có ghi nhãn. Không dừng trước khi đã tạo ít nhất schema, stubs, generator, scenarios, baseline policy và validator.
