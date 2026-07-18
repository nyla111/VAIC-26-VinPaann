# VAIC 2026 - Bộ dữ liệu mô phỏng logistics nông sản ĐBSCL

Bộ dữ liệu này là đầu vào semi-synthetic, có seed và có thể tái lập cho demo hai lớp:

1. Route & Cost Optimizer so sánh đi thẳng TP.HCM, đi bộ qua Cần Thơ, hoặc đi thủy qua Cần Thơ.
2. Dispatch & Consolidation Agent dự báo nhu cầu ở grain ngày, gom tải và điều phối chặng Cần Thơ - TP.HCM.

Đây là dữ liệu mô phỏng để phát triển và trình diễn, không phải dữ liệu vận hành hoặc báo giá thị trường. Tất cả tọa độ, khoảng cách đường thủy, thời lượng, tốc độ, cước, mùa vụ, hệ số thời tiết, hao hụt và cơ cấu đội xe hiện tại đều là giả định mô phỏng. Năm khoảng cách đường bộ lấy từ bảng người dùng cung cấp được ghi riêng là `user_provided_anchor`, chưa phải fact đã xác minh. Hai center anchor nhiên liệu ngày 09/07/2026 được xác minh từ Bộ Công Thương; tuy vậy, mọi row của chuỗi annual/scenario vẫn mang `source_type=simulated` vì là mô phỏng/extrapolation. Xem [ANCHORS.md](ANCHORS.md) trước khi dùng số liệu trong pitch hoặc ngoài demo.

## Data contract

Contract v3 gồm 6 logical pack và 11 bảng canonical:

| Pack | Bảng chuẩn | Vai trò |
|---|---|---|
| Reference Pack | `nodes`, `legs`, `commodities` | Graph tuyến, địa điểm, ràng buộc hàng hóa |
| Dataset 1 | `orders` | Đơn hàng theo hub |
| Dataset 2 | `weather` | Mưa, nước sông, rủi ro và hệ số bất lợi |
| Dataset 3 | `fleet` | Xe tải, xe lạnh, ghe và sà lan |
| Dataset 4 | `fuel_prices`, `freight_rates` | Giá nhiên liệu và giá cước |
| Grounding Pack | `weather_bulletins`, `ops_notes`, `policy_docs` | Text/evidence để agent trích dẫn, giải thích và áp constraint |

Mỗi bảng chuẩn được xuất cả CSV và JSON từ cùng một DataFrame trong một lần chạy. JSON dùng dạng mảng record; CSV và JSON không phải hai nguồn độc lập.

Ngoài contract chuẩn, mỗi pack có thể có 4 JSON tương thích, phục vụ giao diện/đội tích hợp muốn schema đơn giản:

- `compat/dataset_orders.json`
- `compat/dataset_weather.json`
- `compat/dataset_fleet.json`
- `compat/dataset_price.json`

Bốn file này là projection mất thông tin từ 11 bảng chuẩn, không thay thế canonical contract và không nên được dùng làm đầu vào duy nhất cho optimizer. Mapping đầy đủ nằm trong [SCHEMA.md](SCHEMA.md).

## Cài đặt

Yêu cầu Python 3.10+.

~~~bash
python -m pip install -r requirements.txt
~~~

Các dependency runtime chính là Pandas, NumPy và PyYAML; generator không cần dịch vụ ngoài hoặc kết nối mạng.

## Chạy nhanh

Sinh annual baseline 2026:

~~~bash
python src/generate_data.py --config config/base.yaml
~~~

Sinh ba pack scenario 72 giờ:

~~~bash
python src/generate_data.py --config config/scenarios/S1_normal.yaml
python src/generate_data.py --config config/scenarios/S2_flood.yaml
python src/generate_data.py --config config/scenarios/S3_price_shock.yaml
~~~

Override seed hoặc định dạng:

~~~bash
python src/generate_data.py --config config/base.yaml --seed 20260717 --format both
~~~

Các flag hữu ích:

| Flag | Ý nghĩa |
|---|---|
| `--format csv|json|both` | Chọn canonical serialization; 4 compatibility JSON vẫn luôn được xuất khi enabled |
| `--output-dir PATH` | Ghi chính xác một pack vào thư mục test/reproducibility |
| `--write-stubs` | Ghi 10 row đầu mỗi bảng vào `data/stubs` |
| `--no-stubs` | Tắt auto-stub khi chạy annual vào output mặc định |

Annual pack tự tạo stubs khi chạy vào output mặc định. Scenario không ghi đè stubs.

Validate toàn bộ output:

~~~bash
python src/validate_data.py --root data/generated --report reports/validation_report.json
python src/build_evaluation_set.py
python src/audit_synthetic_quality.py --multi-seed 5 --output reports/quality_after_v3.json
~~~

Validator trả exit code khác 0 khi hard check thất bại. Báo cáo gồm trạng thái, seed, số check pass/fail, row count, checksum, warning và thời điểm tạo.

Trong vòng lặp phát triển có thể dùng `--skip-reproducibility` để bỏ bốn lần chạy lại generator; validator sẽ ghi warning và vẫn chạy mọi hard check khác. Không dùng flag này cho handoff cuối.

## Cấu trúc output

~~~text
data/
├── raw_sources/                   # Input tham chiếu local; không auto-calibrate
├── stubs/                         # 11 CSV nhỏ để tích hợp sớm
└── generated/
    ├── annual/
    │   ├── csv/                   # 11 bảng chuẩn
    │   ├── json/                  # 11 bảng chuẩn, orientation=records
    │   ├── compat/                # 4 JSON schema đơn giản
    │   └── metadata.json
    └── scenarios/
        ├── S1_normal/{csv,json,compat,metadata.json}
        ├── S2_flood/{csv,json,compat,metadata.json}
        └── S3_price_shock/{csv,json,compat,metadata.json}
reports/
└── validation_report.json
eval/
├── reference_routes.csv
├── reference_routes.json
└── metadata.json
~~~

`metadata.json` là nơi kiểm tra version, seed, khoảng thời gian, pack/scenario, row count và checksum của lần sinh. Không suy luận provenance chỉ từ tên file; provenance của anchor nằm trong [ANCHORS.md](ANCHORS.md).

Row count của pack seed `20260717` hiện tại:

| Pack | orders | weather | fleet | fuel | freight | bulletins | ops notes | policies |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| annual | 9,054 | 52,560 | 77 | 81 | 122,640 | 2,190 | 1,537 | 10 |
| S1_normal | 64 | 432 | 77 | 3 | 1,008 | 18 | 89 | 10 |
| S2_flood | 51 | 432 | 77 | 3 | 1,008 | 18 | 89 | 10 |
| S3_price_shock | 64 | 432 | 77 | 7 | 1,008 | 18 | 89 | 10 |

Mỗi pack còn có 6 node, 14 leg và 10 commodity. S3 có 7 fuel rows vì diesel/marine diesel đi qua shock path ba bậc thay vì một mức tĩnh.

Row count là output deterministic của config/code hiện tại, không phải target nghiệp vụ cố định ngoại trừ annual orders phải nằm trong 6,000-12,000.

## Cấu hình và tính tái lập

`config/base.yaml` là nguồn sự thật cho mọi magic number: seed, thời gian, node/leg, commodity mix, mùa vụ, phân phối khối lượng, thời tiết, flood threshold, đội xe, giá nhiên liệu, cước, compatibility export và validation.

- Version contract: `3.0`
- Seed mặc định: `20260717`
- Múi giờ: `Asia/Bangkok`, timestamp xuất theo ISO 8601 với `+07:00`
- Annual: `2026-01-01T00:00:00+07:00` đến `2026-12-31T23:00:00+07:00`
- Scenario: cùng cửa sổ `2026-10-15T00:00:00+07:00` đến `2026-10-17T23:00:00+07:00`
- Mỗi miền ngẫu nhiên có stream riêng: orders `+101`, weather `+202`, fleet `+303`, fuel `+404`, freight `+505`

Cùng config đã resolve, cùng seed và cùng phiên bản code phải cho cùng PK, row count và canonical checksum. Scenario YAML dùng `extends: ../base.yaml`; chỉ override tín hiệu kịch bản, không đổi schema.

## Công thức generator

Các mảng multiplier theo giờ/ngày được chuẩn hóa về mean 1 trước khi dùng.

### Orders

~~~text
lambda(hub,day) =
  base_daily_orders
  * weekday_multiplier[day.weekday]
  * blended_shared_and_commodity_seasonality[day.month]
  * exp(regional_AR_state + hub_AR_state)
  * scenario.order_multiplier

count(hub,day) ~ Poisson(lambda)
arrival_hour ~ Categorical(hourly_arrival_profile)
commodity_weight[c] = base_mix[c] * monthly_multiplier[c,t.month]
weight_kg ~ clipped LogNormal(log(median_kg), log_sigma)
~~~

Count dùng Cox-style process: Poisson có điều kiện trên shared seasonality và latent AR(1) bị clip. Shared signal chiếm 80%, commodity-specific signal chiếm 20%, nên tổng cầu không còn bị các mùa vụ triệt tiêu nhưng vẫn giữ khác biệt mặt hàng. Forecast contract là **ngày × hub**, không phải giờ. Guardrail được kiểm tra trên nhiều seed: R² calendar không quá thấp/cao, peak/trough có biên độ và variance/mean không bị ép về một giá trị. Ready delay dùng gamma đã clip. Priority:

~~~text
priority_raw =
  perishability_level * 0.65
  + deadline_score([10,20,36,60] hours) * 0.35
priority_level = clip(round(priority_raw), 1, 5)
~~~

### Weather

Regional rain có persistence và innovation gamma theo mùa:

~~~text
regional_t = persistence * regional_(t-1)
           + (1-persistence) * innovation_t

rainfall_risk = min(rainfall_mm / rainfall_severe_mm, 1)
river_risk = clip(
  (river_level_m - river_risk_start_m)
  / (river_risk_severe_m - river_risk_start_m),
  0, 1
)
flood_risk = clip(
  rainfall_risk * 0.46 + river_risk * 0.54 + scenario_add,
  0, 1
)
road_factor =
  max(1, 1 + flood_risk*1.25 + rainfall_risk*0.25 + scenario_add)
~~~

Ở node không có sông, flood risk bằng rainfall risk. `water_factor` là hàm từng đoạn: bằng 1 trong dải 1.55-3.35 m; tăng tuyến tính khi thấp hơn/cao hơn dải, sau đó cộng scenario penalty. River level gồm base node, seasonality cosine đỉnh tháng 10, regional rain memory 24 giờ, event và local noise.

### Fuel

~~~text
relative_level_t =
  relative_level_(t-1)
  + clip(Normal(0, 0.025), -0.06, 0.06)
  - 0.22 * (relative_level_(t-1) - 1)

price_t = base_price * relative_level_t * scenario_multiplier_or_step_path[t]
~~~

Annual dùng kỳ 14 ngày. Scenario có thể thêm các breakpoint có timestamp; S3 dùng ba bậc trong 72 giờ để biểu diễn shock path, không còn là một hằng số toàn cửa sổ.

### Freight

~~~text
demand_idx =
  hourly_demand * weekday_demand * monthly_demand
  * scenario_mode_demand

noise = max(0.70, 1 + Normal(0, volatility_by_rate_type))
discount = 0.90 nếu contract, ngược lại 1.00

rate_vnd_per_ton_km =
  base_vehicle_rate * leg_multiplier * demand_idx
  * discount * noise * scenario_mode_rate * fuel_cost_factor

fuel_cost_factor = max(
  minimum_factor,
  1 + beta_mode * (fuel_price/base_fuel_price - 1)
)

fixed_fee_vnd =
  base_fixed_fee * leg_multiplier * discount * scenario_mode_rate
~~~

`beta_road=0.38`, `beta_water=0.25` là assumption công khai. Freight row lộ `fuel_type`, `fuel_price_vnd_per_liter` và `fuel_cost_factor`, nên validator có thể đối chiếu causal chain về `fuel_prices`. Consumer không nhân lại `demand_idx` hoặc `fuel_cost_factor`.

## Ý nghĩa ba scenario

| Scenario | Override chính | Tín hiệu cần thấy |
|---|---|---|
| `S1_normal` | Mưa `0.45x`, nước sông `-0.10 m` | Điều kiện bình thường, không extreme event nền |
| `S2_flood` | Mưa `2.20x`, nước `+0.65 m`, flood risk `+0.18`, road factor `+0.12` | Reliability/feasibility: bulletin có thể đóng luồng khi mực nước cực đoan; không pitch cost saving cao hơn S1 |
| `S3_price_shock` | Diesel path `1.05→1.12→1.18x`, fuel pass-through, road non-fuel rate `+5%`, demand `+10%`, availability giảm | Cước road tăng theo cơ chế có thể truy vết; consolidation/water hấp dẫn hơn với hàng phù hợp |

Các kỳ vọng trên là sanity check, không phải nhãn winner. Dataset không chứa `recommended_route`, `predicted_cost`, `selected_vehicle` hoặc quyết định dispatch.

## Join chuẩn

### Đơn hàng và ràng buộc hàng hóa

~~~text
orders.hub_id             -> nodes.node_id
orders.destination_node_id -> nodes.node_id
orders.commodity_id       -> commodities.commodity_id
~~~

`commodities` quyết định deadline/urgency, khả năng đi thủy, nhu cầu xe lạnh và loại phương tiện tương thích. Không suy ra các ràng buộc này từ tên tiếng Việt.

### Graph tuyến

~~~text
legs.from_node_id -> nodes.node_id
legs.to_node_id   -> nodes.node_id
~~~

- A: direct road `hub -> HCM_MARKET`.
- B: road `hub -> CT_HUB` + outbound `CT_HUB -> HCM_MARKET`.
- C: water `hub -> CT_HUB` + outbound phù hợp từ `CT_HUB`.

Road distance và water distance là hai leg độc lập. Không dùng road distance thay cho water distance.

### Time-series lookup

- Weather: chuẩn hóa thời điểm quyết định về giờ và join theo `node_id`; nếu event nằm giữa hai mốc, dùng mốc trước gần nhất, không dùng dữ liệu tương lai.
- Fuel: join theo `fuel_type` và nearest previous `ts`; giá là bậc thang theo kỳ điều chỉnh.
- Freight: join theo `leg_id + vehicle_type + rate_type` và nearest previous `ts`; tần suất chuẩn là 6 giờ.
- Fleet: lọc `status == available`, `available_from_ts <= decision_ts`, đúng mode, đủ capacity và thỏa reefer/commodity compatibility.
- Grounding: trích dẫn `bulletin_id`, `note_id` và `policy_id`; nếu bulletin có `road_status=closed` hoặc `water_navigation_status=closed`, loại route khỏi tập khả thi thay vì dùng finite penalty.

Với weather của một leg, downstream phải công bố cách tổng hợp hai đầu leg (ví dụ lấy max factor để bảo thủ). Generator không tự tạo một định nghĩa chi phí thứ hai.

Ví dụ Pandas:

~~~python
orders = orders.merge(
    commodities,
    on="commodity_id",
    how="left",
    validate="many_to_one",
)

rates = pd.merge_asof(
    decisions.sort_values("decision_ts"),
    freight_rates.sort_values("ts"),
    left_on="decision_ts",
    right_on="ts",
    by=["leg_id", "vehicle_type", "rate_type"],
    direction="backward",
)
~~~

## Công thức dùng chung cho downstream

Các bảng cung cấp primitive, không cung cấp winner. Một cost engine tối thiểu có thể dùng:

~~~text
weight_ton = weight_kg / 1000
travel_hr = duration_hr_base * weather_factor
freight_vnd = fixed_fee_vnd + rate_vnd_per_ton_km * weight_ton * distance_km
vehicle_trip_vnd = cost_fixed_vnd + cost_per_km_vnd * distance_km
estimated_loss_vnd =
    weight_kg * value_vnd_per_kg * loss_pct_per_hour/100 * total_elapsed_hr
~~~

`weather_factor` là `road_factor` hoặc `water_factor` theo mode. Các factor đã có quy ước thống nhất: `1.0` bình thường, lớn hơn `1.0` bất lợi hơn. Nếu cộng nhiều leg, cộng chi phí và thời gian từng leg; thêm thời gian chờ/consolidation một lần tại điểm trung chuyển. Không vừa dùng `freight_vnd` vừa cộng toàn bộ `vehicle_trip_vnd` nếu chúng đại diện hai mô hình mua dịch vụ khác nhau.

Hao hụt tuyến tính ở trên là proxy demo; cần cap tối đa 100% và ghi rõ nếu downstream dùng hàm khác. Mọi impact phải chạy baseline và optimized policy trên cùng data/time window. Baseline machine-readable nằm ở `config/baseline_policy.yaml`.

## Nguồn của 4 JSON tương thích

Compatibility export được tạo sau các bảng chuẩn, từ chính object/DataFrame canonical:

| File | Nguồn chuẩn |
|---|---|
| `dataset_orders.json` | `orders + nodes + commodities` |
| `dataset_weather.json` | `weather + nodes` |
| `dataset_fleet.json` | `fleet`, cùng mapping trong YAML |
| `dataset_price.json` | `fuel_prices + freight_rates + fleet` và các reference trong YAML |

Trong price projection, timestamp lấy theo nhịp freight 6 giờ; diesel được backward-asof theo kỳ giá, còn giá thuê/km lấy cost/km của reference vehicle nhân demand index và fuel factor trung bình của mode tại timestamp đó. Các field bị lược bỏ như deadline, priority, risk index, reefer, leg, rate type, demand index và grounding text vẫn phải đọc từ bảng chuẩn khi tối ưu. Không round-trip compatibility JSON để tái tạo 11 bảng.

## Quy tắc handoff

- Layer 1 và Layer 2 cùng đọc `legs`, `fleet`, `fuel_prices`, `freight_rates` và grounding tables; không hard-code distance/rate riêng.
- Forecast chỉ báo cáo ở grain ngày × hub. Giá trị Layer 2 chính là dispatch/consolidation; không gắn nhãn “AI forecast theo giờ”.
- Golden labels nằm riêng trong `eval/`; canonical input không chứa route winner.
- Frontend có thể đọc JSON canonical hoặc 4 file `compat`; map dùng `nodes.lat/lon`.
- Business chạy `habit_based_v1` và policy tối ưu trên cùng pack; không pitch phần trăm tiết kiệm được viết tay.
- ID/enum dùng ASCII; label hiển thị có thể dùng tiếng Việt.
- File UTF-8; nếu Excel hiển thị sai dấu, chọn import UTF-8 thay vì đổi encoding nguồn.

## Provenance và giới hạn

Audit local ngày 2026-07-17 không tìm thấy nguồn đủ truy vết để xác minh tọa độ, khoảng cách thủy, mùa vụ hoặc ngưỡng lũ. Các file tham chiếu đã được chuyển vào `data/raw_sources/`; `V06.05*` và `E06.08*` chỉ có số liệu tổng hợp cấp quốc gia, không có chiều hub, còn PDF logistics thiếu bibliography/URL hoàn chỉnh. Chúng không được dùng để nâng giả định thành fact. Riêng center anchor diesel 0.05S và E10RON95-III được kiểm tra từ thông báo chính thức của Bộ Công Thương; chi tiết và giới hạn áp dụng nằm trong `ANCHORS.md`.

Danh sách chi tiết, conflict và quyết định ưu tiên nằm trong [ANCHORS.md](ANCHORS.md). Mọi thay đổi contract/provenance được ghi trong [CHANGELOG.md](CHANGELOG.md).
