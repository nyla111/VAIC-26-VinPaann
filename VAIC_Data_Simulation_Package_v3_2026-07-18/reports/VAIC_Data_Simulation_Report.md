# Báo cáo cải thiện dữ liệu mô phỏng logistics VAIC 2026

**Dataset contract:** 3.0  
**Seed mặc định:** `20260717`  
**Múi giờ:** `Asia/Bangkok` (`+07:00`)  
**Ngày cập nhật:** 2026-07-18  
**Phạm vi:** annual 2026, ba scenario 72 giờ, 11 bảng canonical, 4 compatibility JSON và held-out evaluation set  

## Kết luận

Phiên bản 3.0 xử lý trực tiếp sáu nhóm rủi ro trong technical review: demand khó học, route geometry lệch, fuel và freight tách rời, barge đặt sai tầng mạng, thiếu text grounding, và không có golden set. Thay đổi được áp ở generator/config/validator thay vì chỉnh tay output.

Kết quả quan trọng nhất:

- Demand forecast ở grain ngày × hub có signal vừa đủ: qua 5 seed, calendar-oracle R² nằm **0,415–0,474**, monthly tonnage peak/trough **1,86–2,14×**. Range này mạnh hơn v2 nhưng chưa gần 1, giúp tránh cả underfitting lẫn synthetic overfitting.
- `freight_rates` lưu trực tiếp fuel price as-of và `fuel_cost_factor`; S3 dùng diesel path `1,05 → 1,12 → 1,18×` thay vì một shock tĩnh.
- Bốn corrective road anchors giảm detour qua Cần Thơ; Route B đã xuất hiện trong held-out optimum nhưng không bị ép thành winner hàng loạt.
- Toàn bộ barge 200/500 tấn được đặt tại `CT_HUB`; spoke hub dùng boat 50 tấn.
- Ba bảng text grounding cung cấp **3.737 rows annual** và machine-readable evidence reference.
- Golden set gồm **50 cases**, nằm riêng trong `eval/`, không rò nhãn vào canonical input.

## 1. Đối chiếu trước và sau

| Vấn đề review | v2 | v3 | Cách chống overfit |
|---|---|---|---|
| Learnability demand | R² ceiling khoảng 0,32; peak/trough 1,37× | R² 0,415–0,474; peak/trough 1,86–2,14× | Đo trên 5 seed, dùng range guardrail thay vì target một seed |
| Forecast grain | Hourly, 78% ô bằng 0 | Contract ở ngày × hub | Không giả vờ dự báo hourly; hourly zero share chỉ là diagnostic |
| Route geometry | VL→CT 79,2 km; CT→HCM 191 km | 38 km và 172 km, vẫn gắn nhãn provisional | Không đổi thành `verified`; backlog yêu cầu routing provider |
| Route B | Thua per-order do detour/fixed fee | Có thể thắng nhưng chỉ 1/50 golden case | Không tune rate để B thắng; consolidation vẫn là use case chính |
| Fuel→freight | Hai override độc lập | Formula pass-through với beta theo mode | Validator đối chiếu từng quote với fuel as-of và YAML beta |
| S3 dynamics | Một mức giá tĩnh 72 giờ | Ba breakpoint có timestamp | Shock path là config, không hard-code trong code |
| Barge | Barge lớn nằm ở spoke hub | 10/10 barge lớn tại `CT_HUB` | Allocation dựa trên tầng mạng, không theo output winner |
| AI grounding | Không có text | Bulletin, ops notes, policy docs | Text có `evidence_ref` và `source_type`; không giả làm observed fact |
| Reliability | Không có golden set | 50 held-out brute-force cases | Nhãn chỉ nằm trong `eval/`; canonical cấm optimizer output |

## 2. Kích thước dữ liệu v3

### Annual canonical

| Bảng | Dòng | Cột | CSV bytes | JSON bytes | Grain |
|---|---:|---:|---:|---:|---|
| `nodes` | 6 | 9 | 641 | 1.183 | node |
| `legs` | 14 | 11 | 2.546 | 4.630 | route leg |
| `commodities` | 10 | 11 | 1.303 | 2.939 | commodity |
| `orders` | 9.054 | 10 | 1.359.822 | 2.725.633 | order |
| `weather` | 52.560 | 8 | 4.542.843 | 10.230.865 | node × hour |
| `fleet` | 77 | 12 | 10.667 | 23.511 | vehicle snapshot |
| `fuel_prices` | 81 | 5 | 5.866 | 12.345 | fuel adjustment |
| `freight_rates` | 122.640 | 11 | 16.378.684 | 36.472.923 | quote × time × leg × vehicle × rate type |
| `weather_bulletins` | 2.190 | 14 | 1.365.340 | 1.863.993 | node × day |
| `ops_notes` | 1.537 | 11 | 582.939 | 837.807 | vehicle snapshot hoặc hub × day |
| `policy_docs` | 10 | 7 | 2.776 | 3.794 | policy/SOP |

Annual pack chiếm **80,10 MiB**; annual và ba scenario chiếm **82,39 MiB** trước khi nén.

### Scenario row counts

| Pack | Orders | Weather | Fuel | Freight | Bulletins | Ops notes | Policies |
|---|---:|---:|---:|---:|---:|---:|---:|
| `S1_normal` | 64 | 432 | 3 | 1.008 | 18 | 89 | 10 |
| `S2_flood` | 51 | 432 | 3 | 1.008 | 18 | 89 | 10 |
| `S3_price_shock` | 64 | 432 | 7 | 1.008 | 18 | 89 | 10 |

S1 và S3 giữ cùng order stream; S2 thay đổi count qua `order_multiplier=0.95`. S3 có 7 fuel rows vì diesel và marine diesel có ba breakpoint, gasoline có một.

## 3. Preview các bảng mới

### `weather_bulletins`

| Field | Ví dụ |
|---|---|
| `bulletin_id` | `WX_20261015_CT_HUB` |
| `severity` | `none/watch/warning/severe` |
| `road_status` | `open/restricted/closed` |
| `water_navigation_status` | `open/caution/closed/not_applicable` |
| `evidence_ref` | `weather:2026-10-15:CT_HUB` |
| `bulletin_text` | Bản tin tiếng Việt nêu mưa cực đại, flood risk và constraint cho từng mode |

Bulletin được aggregate từ weather row trong cùng ngày. Validator đối chiếu `max_rainfall_mm` và `max_flood_risk_idx` ngược về bảng `weather`. Khi status là `closed`, evaluator loại route khỏi tập khả thi; không thay bằng penalty hữu hạn.

### `ops_notes`

| note_type | Grain | Nội dung |
|---|---|---|
| `vehicle_status` | vehicle | Status, vị trí, capacity và mốc khả dụng |
| `daily_intake` | hub × day | Số đơn, tổng tấn, tấn phù hợp đường thủy và số đơn priority 4–5 |

Mỗi note có `constraint_code`, `is_blocking`, `valid_until` và `evidence_ref`. Note không chứa route winner.

### `policy_docs`

Mười policy bao phủ forecast grain, cold chain, water compatibility, closure, fuel pass-through, barge allocation, consolidation, leakage control và provenance. `policy_docs` là SOP demo có thể cite, không phải văn bản pháp lý.

### `freight_rates` v3

| Cột causal mới | Ý nghĩa |
|---|---|
| `fuel_type` | `diesel_005s` cho road, `marine_diesel` cho water |
| `fuel_price_vnd_per_liter` | Giá nearest-previous thực sự dùng cho quote |
| `fuel_cost_factor` | Pass-through factor đã nhân vào variable rate |

```text
fuel_cost_factor = max(
  minimum_factor,
  1 + beta_mode * (fuel_price/base_fuel_price - 1)
)
```

Beta road/water hiện là `0,38/0,25`, đều mang nhãn simulation assumption. `fixed_fee_vnd` không nhận fuel factor.

## 4. Demand signal và kiểm soát overfit/underfit

Generator v3 sinh daily count có điều kiện:

```text
lambda(hub, day)
  = base_daily
  × weekday
  × blended shared/commodity seasonality
  × clipped exp(regional_AR + hub_AR)
  × scenario multiplier

daily_count ~ Poisson(lambda)
arrival_hour ~ Categorical(hour profile)
```

Shared monthly signal chiếm 80%, commodity-specific signal chiếm 20%. Commodity-specific multipliers vẫn quyết định mix, nên không làm mất khác biệt mùa vụ từng mặt hàng.

### Audit trên 5 seed

| Metric | Min | Median | Max | Guardrail |
|---|---:|---:|---:|---|
| Annual rows | 9.054 | 9.150 | 9.238 | 6.000–12.000 |
| Calendar-oracle R² | 0,415 | 0,453 | 0,474 | 0,40–0,75 |
| Daily variance/mean | 1,406 | 1,456 | 1,507 | 1,10–2,50 |
| Monthly tonnage peak/trough | 1,855 | 2,022 | 2,143 | 1,75–3,00 |
| Hourly zero share | 0,784 | 0,784 | 0,787 | diagnostic ≤0,82 |

Guardrail là khoảng rộng có ý nghĩa, không phải tối ưu để khớp một con số. R² không được ép quá cao vì dữ liệu synthetic gần-deterministic sẽ tạo kỳ vọng sai khi pilot gặp noise thật. Forecast demo phải dùng time split và báo cáo against seasonal-naive baseline.

## 5. Route geometry và fleet

| Hub | Direct road | Road qua CT v2 | Road qua CT v3 | Detour v3 |
|---|---:|---:|---:|---:|
| Vị Thanh | 240 km | 251 km | 232 km | −3,3% |
| Long Xuyên | 190 km | 278,8 km | 234 km | +23,2% |
| Sóc Trăng | 231 km | 254 km | 235 km | +1,7% |
| Vĩnh Long | 144 km | 270,2 km | 210 km | +45,8% |

Route B vẫn không mặc định tốt hơn direct route. Giá trị chính của B là chia fixed fee sau consolidation; per-order evaluator chỉ tìm thấy 1/50 case B tối ưu. Điều này tốt hơn việc cố tune rate để cả ba route thắng ngang nhau.

Fleet v3 giữ 77 phương tiện nhưng chuyển toàn bộ **7 barge 200 tấn** và **3 barge 500 tấn** về Cần Thơ. Bốn spoke hub vẫn có boat 50 tấn để gom tuyến đầu.

## 6. Scenario narrative đúng với dữ liệu

### S1 – normal

Baseline cho cost/route comparison. Không nên quảng bá phần trăm tiết kiệm ra ngoài commodity/scenario đã chạy.

### S2 – flood reliability

Narrative chính là phát hiện route/đơn bất khả thi và explicit closure. Water không mặc định thắng: high-water closure có thể loại tuyến thủy hoàn toàn. Không dùng câu chuyện “lũ làm tiết kiệm chi phí nhiều hơn”.

### S3 – staged price shock

Diesel đi qua ba mức `22.832,25 → 24.354,40 → 25.659,10 VND/lít`. Fuel factor road tương ứng tăng theo beta và được ghi trên từng freight quote. Non-fuel multiplier vẫn tồn tại nhưng tách riêng, giúp giải thích phần nào do nhiên liệu và phần nào do scarcity/demand.

## 7. Held-out reliability evidence

`eval/reference_routes.csv` có 50 rows:

| Reference label | Cases |
|---|---:|
| `A_DIRECT_ROAD` | 46 |
| `B_ROAD_VIA_CT` | 1 |
| `C_WATER_VIA_CT` | 2 |
| `INFEASIBLE` | 1 |

Mỗi case brute-force ba route với quote nearest-previous, fixed fee theo số chuyến, spoilage proxy, commodity compatibility, deadline và explicit closure. Label chỉ nằm trong `eval/`. Golden set đo tính đúng của agent trên simulation, không chứng minh tối ưu ngoài thực địa.

## 8. Validation và reproducibility

Validation kiểm tra:

- Exact schema/order cho 11 bảng CSV và JSON.
- PK, FK, enum, null, range, timezone và coverage.
- CSV/JSON equivalence và checksum metadata.
- Grounding text length, evidence reference và daily weather reconciliation.
- Fuel nearest-previous và pass-through formula.
- S2 explicit navigation closure; S3 staged fuel path đi vào freight.
- Demand learnability guardrails.
- Eval source checksum và leakage isolation.
- Re-generation byte-for-byte của annual + S1 + S2 + S3.

Kết quả cuối: **534 kiểm tra đạt, 0 lỗi** trong `reports/validation_report.json`; **9/9 pytest đạt**. Validator cũng đã tái sinh annual + S1 + S2 + S3 và xác nhận byte-for-byte, nên output hiện tại có thể tái lập từ seed/config đã công bố.

## 9. Provenance và giới hạn

- Tọa độ, water distance, weather threshold, seasonality, fleet/rate và beta vẫn là assumption.
- Bốn road distance sửa theo technical review vẫn là provisional `user_provided_anchor`, chưa phải verified fact.
- Hai center fuel anchor có nguồn Bộ Công Thương; curve và shock path là simulated.
- Bulletin/ops note là derived synthetic text; chúng tạo grounding surface nhưng không biến simulation thành dữ liệu thực.
- Raw references nằm trong `data/raw_sources/` và không tự động calibrate generator.
- Cần pilot data để đo travel outcome, delivery status, actual consolidation wait và causal fuel pass-through.

## 10. File tham chiếu

- Contract: [`README.md`](../README.md), [`SCHEMA.md`](../SCHEMA.md).
- Provenance: [`ANCHORS.md`](../ANCHORS.md).
- Version history: [`CHANGELOG.md`](../CHANGELOG.md).
- Generator/audit/eval: [`generate_data.py`](../src/generate_data.py), [`audit_synthetic_quality.py`](../src/audit_synthetic_quality.py), [`build_evaluation_set.py`](../src/build_evaluation_set.py).
- Evidence: [`quality_baseline_v2.json`](quality_baseline_v2.json), [`quality_after_v3.json`](quality_after_v3.json), [`validation_report.json`](validation_report.json).
- Held-out set: [`eval/`](../eval/).

---

**Kết luận sử dụng:** v3 phù hợp cho hackathon demo, integration test, agent grounding và controlled evaluation. Khi pitch, định vị Layer 2 là Dispatch & Consolidation Agent có daily demand planning; S2 là reliability story; mọi con số impact phải chỉ rõ scenario và commodity coverage.
