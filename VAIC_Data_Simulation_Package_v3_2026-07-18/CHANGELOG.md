# Changelog

## [4.0.0] - 2026-07-18

### Added

- Thêm pack `three_year` bao phủ 2024-2026, annual CSV partitions và hai bảng analytics `monthly_trends`/`weather_logistics_impacts`.
- Thêm config riêng cho tăng trưởng năm, mùa vụ commodity, thời tiết theo tháng, anomaly từng năm và causal lag weather → orders/freight.
- Thêm đánh giá forecast theo temporal holdout: train 2024-2025, test 2026; tuyệt đối không random split hoặc tune trên test.
- Thêm quality audit 15 tiêu chí, validator 78 tiêu chí, test contract ba năm và multi-seed guardrail.
- Thêm bảng tham chiếu địa lý `admin_units.csv` và `node_admin_history.csv`.

### Changed

- Khóa geography ở chế độ `harmonized_post_2025`: toàn bộ record 2024-2026 chỉ dùng tên tỉnh/thành sau sáp nhập; không sinh tên cũ theo event time.
- Override `dataset_weather.json.region` thành mã tỉnh/thành sau sáp nhập; không còn `vi_thanh`, `soc_trang` hoặc `long_xuyen` trong field region của pack ba năm.
- Order ID chứa năm (`ORD_2024_*`, `ORD_2025_*`, `ORD_2026_*`) và sequence khởi động lại theo năm.
- Seasonality tổng hợp dùng trọng số shared/commodity/hub `0.35/0.50/0.15`; thêm annual index `1.00/1.04/1.08` và seeded clipped year noise.
- Weather ảnh hưởng orders theo lag mưa/lũ 3 ngày và salinity 14 ngày; freight lưu hệ số thời tiết đã resolve.

### Validation

- Seed chuẩn đạt quality `15/15`, full validation `78/78` và legacy validation `534/534`.
- Ba seed độc lập đều đạt bốn guardrail; output khác checksum/row count giữa seed nhưng cùng giữ contract và dải tín hiệu.
- Forecast cho thấy daily grain còn nhiễu: calendar-trend ridge có WAPE `0.328459`, R² `0.070885`; rolling-28d tốt nhất ở monthly grain với WAPE `0.053960`, R² `0.669019`. Kết quả âm này được giữ lại để tránh tuyên bố learnability quá mức.

### Compatibility

- 11 bảng canonical v3 giữ nguyên tên cột; v4 là temporal data/config extension. Bốn compatibility JSON tiếp tục được sinh từ canonical tables.

Mọi thay đổi contract, generator rule, scenario, anchor hoặc compatibility projection phải được ghi ở đây. Format theo hướng Keep a Changelog; version dataset hiện tại là `3.0`.

## [3.0.0] - 2026-07-18

### Added

- Thêm ba bảng canonical cho AI grounding: `weather_bulletins`, `ops_notes`, `policy_docs`.
- Thêm hard closure `road_status`/`water_navigation_status` trong bulletin; route đóng bị loại khỏi feasibility set.
- Thêm causal fields vào `freight_rates`: `fuel_type`, `fuel_price_vnd_per_liter`, `fuel_cost_factor`.
- Thêm shock path có timestamp cho S3: diesel `1.05 → 1.12 → 1.18x`, marine diesel `1.01 → 1.02 → 1.04x`.
- Thêm `eval/reference_routes.{csv,json}` gồm 50 golden cases được brute-force và tách khỏi canonical input.
- Thêm `src/audit_synthetic_quality.py` và multi-seed guardrails cho learnability.

### Changed

- Chuyển order arrival từ Poisson độc lập theo giờ sang daily conditional Poisson với shared seasonality, latent AR(1) bị clip và categorical arrival hour.
- Chốt forecast contract ở grain `day × hub`; Layer 2 được định vị chính là Dispatch & Consolidation Agent.
- Shared seasonality chiếm 80% volume signal; commodity-specific seasonality vẫn quyết định mix. Trên 5 seed audit, calendar-oracle R² nằm `0.415–0.474`, monthly tonnage peak/trough `1.855–2.143x`.
- Sửa provisional road distance: Long Xuyên–HCM `190 km`, Long Xuyên–Cần Thơ `62 km`, Vĩnh Long–Cần Thơ `38 km`, Cần Thơ–HCM `172 km`.
- Dồn toàn bộ 7 barge 200 tấn và 3 barge 500 tấn về `CT_HUB`; spoke hub giữ boat 50 tấn.
- S3 non-fuel road rate/demand multiplier giảm còn `1.05/1.10`; phần fuel tăng được giải thích riêng qua beta road `0.38`.
- Chuyển input tham chiếu local vào `data/raw_sources/`.

### Validation

- Validator kiểm tra 11 schemas, grounding text/evidence, daily bulletin reconciliation, ops-note coverage, fuel as-of/pass-through, explicit S2 water closure, staged S3 fuel shock và held-out eval integrity.
- Pytest thêm kiểm tra demand signal trên nhiều seed và leakage control của eval set.

### Breaking

- Canonical contract tăng từ 8 lên 11 bảng; `freight_rates` thêm ba cột bắt buộc. Consumer khóa exact schema v2 phải migrate lên v3.
- Bốn compatibility JSON giữ nguyên field contract để frontend cũ tiếp tục đọc được, nhưng không chứa grounding/eval fields.

## [2.0.0] - 2026-07-17

### Added

- Thiết lập 5 logical data pack và 8 bảng canonical:
  - Reference: `nodes`, `legs`, `commodities`
  - Dynamic: `orders`, `weather`, `fleet`, `fuel_prices`, `freight_rates`
- Thêm annual baseline 2026, seed mặc định `20260717`, timezone `Asia/Bangkok`.
- Thêm RNG stream độc lập cho orders/weather/fleet/fuel/freight để giữ tính tái lập khi một module đổi row count.
- Thêm ba scenario dùng chung schema/codebase:
  - `S1_normal`
  - `S2_flood`
  - `S3_price_shock`
- Thêm baseline policy `habit_based_v1` để so sánh impact trên cùng dataset.
- Thêm CSV stub, CSV/JSON canonical, metadata/checksum và validation report.
- Thêm bốn compatibility JSON theo expected output mới của team:
  - `dataset_orders.json`
  - `dataset_weather.json`
  - `dataset_fleet.json`
  - `dataset_price.json`
- Thêm tài liệu join, lookup thời gian, công thức chi phí, provenance và handoff.

### Compatibility mapping

Compatibility export là projection không breaking; schema canonical không đổi.

| File | Thay đổi/projection |
|---|---|
| `dataset_orders.json` | `orders` join `nodes` và commodity config; xuất `hub_id`, `hub_name`, `timestamp`, `loai_hang`, `khoi_luong_kg` |
| `dataset_weather.json` | Map node thành region; map alert về `thap/trung_binh/cao`; đổi m sang cm |
| `dataset_fleet.json` | Map road/water thành `xe_tai/sa_lan`; đổi ton sang kg; map status/location |
| `dataset_price.json` | Project diesel thành VND/km theo 0.35 l/km; reference cost/km của `truck_5t`, `boat_50t` được nhân demand index trung bình theo mode ở mỗi mốc 6 giờ |

Quyết định compatibility:

- `dataset_orders.hub_id` giữ ID canonical `HUB_*` để join ổn định. Chuỗi `hg_01` trong ví dụ brief không được dùng vì không có mapping khai báo và mâu thuẫn với ASCII key contract hiện hành.
- `weather.region` và `fleet.vi_tri_hien_tai` dùng `location_codes` như `vi_thanh`, `long_xuyen`, `can_tho`.
- Timestamp compatibility vẫn có offset `+07:00`, dù ví dụ brief bỏ offset.
- Fleet status `reserved` được giữ qua giá trị `da_dat`; không ép về `ranh`.
- Bốn file chỉ là JSON. CSV canonical vẫn là interface cho Pandas/data science.

### Provenance

- Xác định không có `verified_fact` trong input local ở thời điểm release.
- Thêm hai `verified_fact` từ thông báo chính thức Bộ Công Thương kỳ 09/07/2026:
  - diesel 0.05S tối đa 21,745 VND/l
  - E10RON95-III tối đa 20,003 VND/l, dùng làm center cho enum `gasoline`
- Giữ `source_type=simulated` cho mọi fuel row vì annual/scenario curve là mô phỏng quanh center, không phải chuỗi lịch sử.
- Ghi nhãn năm khoảng cách road là `user_provided_anchor`:
  - CT - HCM: 191.0 km
  - Long Xuyên - CT: 87.8 km
  - Vĩnh Long - CT: 79.2 km
  - Long Xuyên - HCM: 233.0 km
  - Vĩnh Long - HCM: 144.0 km
- Mode `road` là diễn giải của demo vì bảng provisional không ghi mode.
- Ghi nhãn toàn bộ tọa độ, water distance, duration/speed, capacity/mix, price/rate, commodity seasonality/perishability/loss và weather/flood parameter là `simulation_assumption`.
- Không dùng `E06.08*`, `V06.05*` để calibrate hub:
  - E06.08 là bảng ngũ cốc quốc gia 1990-2024.
  - V06.05 là diện tích cây hàng năm cấp quốc gia, `source: null`, có trailing NUL.
- Không dùng số trong PDF logistics làm anchor định lượng vì citation marker bị gãy và thiếu bibliography/URL truy vết.

### Conflict resolution

Ưu tiên provisional table trong spec hơn narrative cũ:

| Biến | Giá trị giữ | Narrative bị loại |
|---|---:|---:|
| CT - HCM road | 191 km | 169 km |
| Long Xuyên - CT road | 87.8 km | khoảng 62-65 km |
| Vĩnh Long - CT road | 79.2 km | khoảng 35 km |
| Long Xuyên - HCM road | 233 km | khoảng 190 km |
| Vĩnh Long - HCM road | 144 km | khoảng 136 km |

Giữ water leg riêng; không tái sử dụng road distance. Diesel center 21,745 VND/l được xác minh cho đúng kỳ 09/07/2026 nhưng các row sinh ra vẫn là simulation. River threshold 2.60/3.75 m tiếp tục là assumption, không phải ngưỡng pháp lý.

### Validation contract

- Hard fail khi thiếu bảng/cột, PK duplicate, FK orphan, null required, range/time invalid, thiếu coverage hoặc scenario signal sai.
- Kiểm tra annual orders trong 6,000-12,000 row và phủ 12 tháng.
- Kiểm tra weather hourly, fuel/freight có thể backward-asof/forward-fill hợp lệ.
- Kiểm tra S2 bất lợi road rõ hơn S1; S3 diesel tăng đúng 18% và tín hiệu road fleet/demand xấu hơn.
- Kiểm tra reproducibility bằng row count, PK và checksum canonical.

### Backward compatibility

- Bốn compatibility JSON được thêm mà không đổi tên/cột/enum của 8 bảng canonical.
- Consumer đã dùng canonical v2.0 không cần migration.
- Consumer chỉ dùng compatibility JSON chấp nhận mất deadline, priority, risk/factor, reefer, leg, rate type và demand index.
- Không hỗ trợ round-trip từ 4 JSON compatibility về 8 bảng canonical.

## Quy tắc cho release tiếp theo

- Sửa value assumption mà không đổi schema: tăng patch, ghi lý do và tác động scenario.
- Thêm field optional/projection: tăng minor.
- Đổi tên/xóa field, enum, đơn vị hoặc nghĩa factor: tăng major.
- Khi một anchor được xác minh, lưu nguồn/URL, ngày truy cập, phạm vi và method; cập nhật đồng thời `base.yaml`, `ANCHORS.md`, `SCHEMA.md` nếu contract thay đổi.
