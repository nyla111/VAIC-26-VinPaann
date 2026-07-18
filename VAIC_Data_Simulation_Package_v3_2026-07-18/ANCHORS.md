# Anchors, assumptions và provenance

Ngày audit: **2026-07-18**  
Contract: **3.0**  
Kết luận: **không có `verified_fact` trong các file nguồn local; có hai center anchor nhiên liệu được xác minh từ nguồn chính thức online**.

Bộ data là semi-synthetic. Một số giá trị do người dùng cung cấp được giữ làm provisional anchor; chúng chưa trở thành fact chỉ vì xuất hiện trong config. Các nguồn local còn lại không đủ metadata để xác minh các biến mô hình theo hub/tuyến.

## Taxonomy bắt buộc

Chỉ dùng bốn nhãn sau trong tài liệu provenance:

| Loại | Nghĩa |
|---|---|
| `verified_fact` | Có nguồn truy vết được, đúng phạm vi/đơn vị/thời điểm và đã kiểm tra |
| `user_provided_anchor` | Người dùng hoặc file người dùng cung cấp; chưa xác minh độc lập |
| `simulation_assumption` | Giá trị thiết kế để mô phỏng/demo |
| `derived_value` | Giá trị tính được từ anchor/assumption bằng công thức công khai |

Mapping sang enum vật lý:

| Trong CSV | Trong tài liệu này |
|---|---|
| `verified` | `verified_fact` |
| `user_provided` | `user_provided_anchor` |
| `assumption` hoặc `simulated` | `simulation_assumption` |

Không được đổi một row từ `assumption` sang `verified` nếu chỉ tìm thấy một nguồn kể chuyện, một search snippet hoặc một file không có provenance.

## Tọa độ node

Tất cả tọa độ hiện tại là điểm đại diện cấp địa danh, không phải vị trí HTX, kho, cảng hoặc chợ đích đã khảo sát.

| Biến/nhóm biến | Giá trị | Loại | Nguồn/giải thích | Ngày kiểm tra | Dùng ở đâu |
|---|---|---|---|---|---|
| `HUB_VITHANH` | 9.7840, 105.4701 | `simulation_assumption` | Điểm đại diện Vị Thanh trong `base.yaml` | 2026-07-17 | map, weather |
| `HUB_LONGXUYEN` | 10.3864, 105.4352 | `simulation_assumption` | Điểm đại diện Long Xuyên | 2026-07-17 | map, weather |
| `HUB_SOCTRANG` | 9.6025, 105.9739 | `simulation_assumption` | Điểm đại diện Sóc Trăng | 2026-07-17 | map, weather |
| `HUB_VINHLONG` | 10.2537, 105.9722 | `simulation_assumption` | Điểm đại diện Vĩnh Long | 2026-07-17 | map, weather |
| `CT_HUB` | 10.0452, 105.7469 | `simulation_assumption` | Điểm đại diện Cần Thơ; vị trí hub thật chưa được cung cấp | 2026-07-17 | transshipment, map |
| `HCM_MARKET` | 10.7769, 106.7009 | `simulation_assumption` | Điểm đại diện trung tâm TP.HCM; chợ/kho đích thật chưa xác định | 2026-07-17 | destination, map |
| `HUB_CAMAU` | 9.1769, 105.1524 | `simulation_assumption` | Node optional, inactive mặc định | 2026-07-17 | stub/extra hub |
| `HUB_DONGTHAP` | 10.4938, 105.6882 | `simulation_assumption` | Node optional, inactive mặc định | 2026-07-17 | stub/extra hub |
| `HUB_TAYNINH` | 11.3352, 106.1099 | `simulation_assumption` | Node optional, inactive mặc định | 2026-07-17 | stub/extra hub |
| `HUB_BENTRE` | 10.2434, 106.3756 | `simulation_assumption` | Node optional, inactive mặc định | 2026-07-17 | stub/extra hub |

`on_river=true` cho bốn hub demo và `CT_HUB`, `false` cho `HCM_MARKET`, cũng là `simulation_assumption`.

## Khoảng cách và thời lượng road

Bảng người dùng cung cấp không ghi mode; trong demo các cặp dưới đây được **diễn giải là road**. Khoảng cách giữ nhãn `user_provided_anchor`; duration vẫn là `simulation_assumption`.

| Leg | Distance km | Duration hr | Loại distance | Ghi chú |
|---|---:|---:|---|---|
| `LEG_LX_HCM_ROAD` | 190.0 | 4.4 | `user_provided_anchor` | Corrective review anchor; chưa xác minh theo endpoint |
| `LEG_VL_HCM_ROAD` | 144.0 | 3.2 | `user_provided_anchor` | Vĩnh Long - TP.HCM |
| `LEG_LX_CT_ROAD` | 62.0 | 1.6 | `user_provided_anchor` | Corrective review anchor; chưa xác minh theo endpoint |
| `LEG_VL_CT_ROAD` | 38.0 | 1.0 | `user_provided_anchor` | Corrective review anchor; chưa xác minh theo endpoint |
| `LEG_CT_HCM_ROAD` | 172.0 | 3.7 | `user_provided_anchor` | Corrective review anchor; chưa xác minh theo endpoint |
| `LEG_VT_HCM_ROAD` | 240.0 | 5.2 | `simulation_assumption` | Narrative cũ, chưa xác minh |
| `LEG_ST_HCM_ROAD` | 231.0 | 5.1 | `simulation_assumption` | Narrative cũ, chưa xác minh |
| `LEG_VT_CT_ROAD` | 60.0 | 1.5 | `simulation_assumption` | Narrative cũ, chưa xác minh |
| `LEG_ST_CT_ROAD` | 63.0 | 1.6 | `simulation_assumption` | Narrative cũ, chưa xác minh |

Nguồn: bảng provisional trong spec và `config/base.yaml`; kiểm tra ngày 2026-07-17. Tất cả duration, `bidirectional=true` và weather sensitivity là giả định mô phỏng.

## Khoảng cách và thời lượng water

Water distance không được copy từ road distance. Toàn bộ các leg dưới đây được thiết kế riêng cho simulation.

| Leg | Distance km | Duration hr | Loại | Dùng ở đâu |
|---|---:|---:|---|---|
| `LEG_VT_CT_WATER` | 72.0 | 6.5 | `simulation_assumption` | Route C |
| `LEG_LX_CT_WATER` | 105.0 | 9.0 | `simulation_assumption` | Route C |
| `LEG_ST_CT_WATER` | 82.0 | 7.5 | `simulation_assumption` | Route C |
| `LEG_VL_CT_WATER` | 65.0 | 5.8 | `simulation_assumption` | Route C |
| `LEG_CT_HCM_WATER` | 220.0 | 19.0 | `simulation_assumption` | Outbound water |

Nguồn/giải thích: calibration demo trong `base.yaml`; chưa map theo luồng/kênh thực tế, bến, tĩnh không cầu, mớn nước hay hạn chế luồng.

## Commodity, mùa vụ và hao hụt

Mọi commodity property, phân phối khối lượng và monthly multiplier hiện tại là `simulation_assumption`. Các file thống kê local không có chiều hub/tháng để hiệu chỉnh các pattern này.

| Commodity | Hold hr | Loss %/hr | Value VND/kg | Weight median [min,max] kg | Seasonality mô phỏng |
|---|---:|---:|---:|---:|---|
| `COM_RICE` | 120 | 0.010 | 16,000 | 7,500 [500,45,000] | Đỉnh T2-T3, T7-T8, T11-T12 |
| `COM_PANGASIUS` | 18 | 0.180 | 32,000 | 4,200 [500,8,000] | Gần phẳng quanh năm, 0.95-1.05 |
| `COM_SHRIMP` | 12 | 0.220 | 125,000 | 3,000 [300,8,000] | Đỉnh T5-T9, max 1.55 ở T7 |
| `COM_POMELO` | 48 | 0.055 | 36,000 | 5,200 [400,18,000] | Tăng T8-T12, max 1.55 ở T10 |
| `COM_SWEET_POTATO` | 72 | 0.030 | 15,000 | 6,500 [500,24,000] | Nhiều đợt: T1-T2, T5-T6, T9-T10 |
| `COM_SUGARCANE` | 72 | 0.025 | 1,300 | 16,000 [1,500,85,000] | Tăng cuối năm, max 1.55 ở T11 |
| `COM_PINEAPPLE` | 42 | 0.060 | 10,000 | 5,500 [400,20,000] | Gần phẳng, 0.90-1.15 |
| `COM_PURPLE_ONION` | 72 | 0.035 | 28,000 | 4,200 [300,16,000] | Đỉnh T12-T3, max 1.50 ở T12 |
| `COM_ORANGE` | 42 | 0.065 | 22,000 | 4,800 [350,18,000] | Tăng T10-T2, max 1.35 ở T11 |
| `COM_VEGETABLE` | 24 | 0.100 | 18,000 | 2,600 [200,9,000] | Tăng T11-T2, 0.80-1.20 |

Ràng buộc reefer/water cũng là assumption:

- `COM_PANGASIUS`, `COM_SHRIMP`: cần reefer, không đi water.
- `COM_VEGETABLE`: không bắt buộc reefer nhưng `water_ok=false`.
- Các commodity còn lại `water_ok=true`; compatibility vehicle lấy đúng list trong YAML.

Hao hụt downstream đề xuất:

~~~text
estimated_loss_vnd =
  weight_kg * value_vnd_per_kg
  * (loss_pct_per_hour / 100)
  * elapsed_hours
~~~

Đây là `derived_value`; phải cap 100% và ghi rõ nếu dùng hàm phi tuyến khác.

## Order generation

Tất cả tham số dưới đây là `simulation_assumption`.

| Hub | Base orders/day | Commodity mix |
|---|---:|---|
| `HUB_LONGXUYEN` | 6.4 | rice 0.48, pangasius 0.27, vegetable 0.10, sweet potato 0.15 |
| `HUB_SOCTRANG` | 6.2 | shrimp 0.32, rice 0.28, purple onion 0.25, vegetable 0.15 |
| `HUB_VINHLONG` | 6.0 | pomelo 0.28, orange 0.26, sweet potato 0.28, vegetable 0.18 |
| `HUB_VITHANH` | 6.3 | sugarcane 0.28, pineapple 0.27, rice 0.27, pangasius 0.10, vegetable 0.08 |

Các assumption bổ sung:

- Annual target: 6,000-12,000 orders.
- Forecast grain: ngày × hub; không dùng hour-level forecast làm KPI.
- Shared monthly profile: `[0.65,0.70,0.82,0.98,1.16,1.34,1.50,1.62,1.48,1.20,0.88,0.67]`, weight 0.80.
- Daily latent AR(1): persistence 0.65, regional/hub log std 0.08/0.06, clip 0.75-1.35.
- Multi-seed guardrail: calendar-oracle R² 0.40-0.75, monthly tonnage peak/trough 1.75-3.00, variance/mean 1.10-2.50. Đây là range chống underfit/overfit, không phải target cho một seed.
- Hourly multiplier thấp ban đêm, tăng từ 06:00, max 1.80 lúc 07:00.
- Weekday multiplier: `[1.05,1.05,1.05,1.05,1.10,0.90,0.80]`.
- Ready delay: gamma shape 1.8, scale 0.7, clip 0-4 giờ.
- Deadline dùng 55%-90% của `max_hold_hours`, floor 4 giờ.
- Status mix: new 0.30, ready 0.66, cancelled 0.04.
- Priority kết hợp perishability 0.65 và deadline 0.35.

## Weather/flood

Toàn bộ weather parameter là `simulation_assumption`, không phải ngưỡng KTTV hoặc mực báo động pháp lý.

| Nhóm | Giá trị/range | Giải thích |
|---|---|---|
| Wet months | T5-T11 | Mùa mưa mô phỏng |
| Rain probability | dry 0.10; wet 0.34 | Xác suất regional event |
| Regional rainfall | gamma shape 1.7; scale 2.5/8.5 mm | Dry/wet |
| Persistence | 0.62 | Tương quan theo giờ |
| Local noise | 1.6 mm; local weight 0.18 | Tạo khác biệt nhỏ giữa node |
| River seasonality | peak T10; amplitude 0.62 m | Chu kỳ mô phỏng |
| Rain memory | 24 giờ; 0.010 m/mm | Tác động mưa tích lũy |
| River local noise | 0.035 m | |
| Flood rainfall severe | 65 mm | Ngưỡng scale mô phỏng |
| River risk start/severe | 2.60/3.75 m | Không phải báo động thật |
| Flood weights | rain 0.46; river 0.54 | Risk composite |
| Alert thresholds | 0.35/0.60/0.82 | watch/warning/severe |
| Road penalties | risk 1.25; rain 0.25 | Factor >= 1 |
| Water optimal band | 1.55-3.35 m | Nước thấp/cao đều bất lợi |
| Water penalties | low 0.70; high 0.85 | |

River level base theo node: Vị Thanh 2.15 m, Long Xuyên 2.45 m, Sóc Trăng 1.95 m, Vĩnh Long 2.25 m, Cần Thơ 2.35 m; TP.HCM để null. Đây đều là simulation baseline.

Annual có hai extreme event giả lập:

- 2026-09-20 06:00 đến 2026-09-21 18:00: +18 mm, +0.25 m tại Vị Thanh, Sóc Trăng, Cần Thơ.
- 2026-10-28 12:00 đến 2026-10-29 23:00: +15 mm, +0.22 m tại Long Xuyên, Vĩnh Long, Cần Thơ.

## Fleet

Mọi capacity, cost, speed, allocation và status mix là `simulation_assumption`.

| Vehicle | Capacity t | Fixed VND | VND/km | Speed km/h | Reefer | Số xe |
|---|---:|---:|---:|---:|---:|---:|
| `truck_5t` | 5 | 250,000 | 12,000 | 45 | no | 24 |
| `truck_15t` | 15 | 420,000 | 18,500 | 42 | no | 17 |
| `reefer_8t` | 8 | 650,000 | 21,000 | 43 | yes | 14 |
| `boat_50t` | 50 | 900,000 | 6,000 | 12 | no | 12 |
| `barge_200t` | 200 | 2,500,000 | 9,000 | 10 | no | 7 |
| `barge_500t` | 500 | 5,200,000 | 13,000 | 8.5 | no | 3 |

Tổng allocation: 77 phương tiện tại bốn hub và Cần Thơ. Cả 7 barge 200 tấn và 3 barge 500 tấn nằm tại `CT_HUB`; spoke hub chỉ giữ boat 50 tấn cho gom tuyến đầu. Baseline status mix là available 0.54, en_route 0.25, maintenance 0.11, reserved 0.10. Delay availability theo status cũng là assumption: available 0-2h, en_route 3-18h, maintenance 18-72h, reserved 4-30h.

## Fuel price

| Biến | Giá trị | Loại | Nguồn/giải thích | Dùng ở đâu |
|---|---:|---|---|---|
| Diesel 0.05S | 21,745 VND/l | `verified_fact` | Mức giá bán lẻ tối đa, hiệu lực từ 15:00 ngày 09/07/2026; truy cập 2026-07-17 | Center của `fuel_prices` |
| Gasoline | 20,003 VND/l | `verified_fact` | Anchor gốc là E10RON95-III cùng kỳ; enum canonical rút gọn thành `gasoline`; truy cập 2026-07-17 | Center của `fuel_prices` |
| Marine diesel | 18,500 VND/l | `simulation_assumption` | Base mô phỏng | `fuel_prices` |
| Adjustment interval | 14 ngày | `simulation_assumption` | Tạo bậc thang | generator |
| Volatility/clip | std 0.025; max 0.060 | `simulation_assumption` | Biến động mỗi kỳ | generator |
| Mean reversion | 0.22 | `simulation_assumption` | Giữ chuỗi quanh base | generator |
| Fuel pass-through beta | road 0.38; water 0.25 | `simulation_assumption` | `1 + beta*(fuel/base-1)` | `freight_rates` |
| Compat fuel/km | diesel price * 0.35 l/km | `derived_value` | Backward-asof theo mốc freight | `dataset_price.json` |
| Compat road rent/km | median truck_5t cost/km * mean road demand_idx | `derived_value` | Reference cost 12,000 VND/km | `dataset_price.json` |
| Compat water rent/km | median boat_50t cost/km * mean water demand_idx | `derived_value` | Reference cost 6,000 VND/km | `dataset_price.json` |

Nguồn chính thức:

- [Bộ Công Thương - Một số thông tin về việc điều hành giá xăng dầu ngày 09/7/2026](https://minhbach.moit.gov.vn/tin-tuc/mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-09-7-2026.html)
- [Metadata văn bản 5280/BCT-TTTN](https://moit.gov.vn/van-ban-phap-luat/van-ban-dieu-hanh/thong-bao-dieu-hanh-gia-ban-xang-dau-ngay-09-7-2026.html)

Phạm vi xác minh chỉ là **center anchor tại một kỳ điều hành**. `source_type` của mọi fuel row vẫn là `simulated`, vì generator tạo chuỗi bậc thang annual/scenario bằng innovation, mean reversion và multiplier; các row đó không phải lịch sử giá quan sát. S3 dùng shock path có timestamp; rate row lưu chính giá as-of và `fuel_cost_factor` để causal chain có thể audit.

## Freight rate và vehicle cost

Tất cả rate/fixed fee, discount, multiplier và noise là `simulation_assumption`.

| Vehicle | Base VND/ton-km | Freight fixed VND |
|---|---:|---:|
| `truck_5t` | 1,500 | 260,000 |
| `truck_15t` | 1,050 | 430,000 |
| `reefer_8t` | 1,950 | 680,000 |
| `boat_50t` | 520 | 950,000 |
| `barge_200t` | 310 | 2,600,000 |
| `barge_500t` | 235 | 5,300,000 |

- Frequency: 6 giờ.
- Contract discount: 0.90.
- Spot volatility std: 0.075; contract: 0.020.
- Demand multiplier theo giờ/ngày/tháng và leg multiplier đều là calibration demo trong YAML.
- Freight quote là `derived_value`: `fixed_fee + rate * ton * km`.
- Vehicle trip cost là mô hình khác: `cost_fixed + cost_per_km * km`. Không cộng trùng hai mô hình.

## Consolidation và baseline policy

| Biến | Giá trị | Loại | Dùng ở đâu |
|---|---:|---|---|
| Baseline route | always direct road to HCM | `simulation_assumption` | `baseline_policy.yaml` |
| Min load factor | 0.60 | `simulation_assumption` | baseline dispatch |
| Max wait | 24 giờ | `simulation_assumption` | baseline dispatch |
| Weather/price awareness | false/false | `simulation_assumption` | baseline |
| Vehicle rule | first compatible available | `simulation_assumption` | baseline |
| Split large orders | true | `simulation_assumption` | baseline |

Lợi ích consolidation không được hard-code thành một phần trăm tiết kiệm. Nó phải xuất hiện từ fixed fee, rate/ton-km, capacity, load factor và thời gian chờ. Kết quả impact là `derived_value`.

## Scenario overrides

Mọi override là `simulation_assumption`.

| Scenario | Override chính |
|---|---|
| `S1_normal` | rainfall 0.45x; river -0.10 m; suppress extreme nền |
| `S2_flood` | rainfall 2.20x; river +0.65 m; risk +0.18; road factor +0.12; water factor +0.05; road rate +8%; road demand +12%; targeted extreme event |
| `S3_price_shock` | diesel 1.05→1.12→1.18x; marine diesel 1.01→1.02→1.04x; non-fuel road rate 1.05x; road demand 1.10x; water demand 1.03x; road available mix 0.30 |

Giá/factor sau override là `derived_value`, không phải quan sát thị trường.

## Grounding text và golden evaluation

- `weather_bulletins` và `ops_notes` là `simulation_assumption`/derived text từ canonical weather, fleet và orders; chúng cho phép agent cite evidence nhưng không biến dữ liệu mô phỏng thành quan sát thật.
- `policy_docs` là SOP demo có `citation_ref`; không phải văn bản pháp lý.
- `eval/reference_routes.*` là `derived_value` từ brute-force evaluator. Nhãn chỉ dùng để đánh giá, không được join vào feature hoặc ghi ngược vào `orders`.
- Closure threshold road/water, pass-through beta và route cost formula đều là assumption công khai và phải được recalibrate khi có pilot data.

## Audit nguồn local

| File | Nội dung audit được | Hạn chế provenance | Phân loại nếu trích | Có dùng calibrate generator? |
|---|---|---|---|---:|
| `data/raw_sources/E06.08.xlsx`, `E06.08 (1).xlsx`, `E06.08.htm` | Bảng quốc gia về diện tích/sản lượng ngũ cốc 1990-2024; 2024 sơ bộ lúa 7,127.1 nghìn ha, 43,451.6 nghìn tấn | Không có chiều hub/tháng; local artifact không kèm URL/source note đủ truy vết | `user_provided_anchor` | no |
| `data/raw_sources/V06.05.json` | Selection mía 2024: 185.48 nghìn ha | `source: null`, trailing NUL, không có vùng/hub | `user_provided_anchor` | no |
| `data/raw_sources/V06.05 (1).json` | Diện tích cây hàng năm quốc gia 2000-2024 | `source: null`, trailing NUL; không có chiều vùng/hub/tháng | `user_provided_anchor` | no |
| `data/raw_sources/Cần-Thơs-Multimodal-Logistics-Landscape-and-Challenges.pdf` | Bối cảnh định tính logistics đa phương thức, 5 trang | Tài liệu Deep Research; citation marker dạng nội bộ/bị gãy, không có bibliography/URL hoàn chỉnh | `user_provided_anchor` cho context, không cho số | no |

Hai file XLSX có cùng workbook/sheet/shared-string payload nghiệp vụ nhưng binary hash khác do relationship/core metadata. Không coi đây là hai nguồn độc lập.

Các số quốc gia trong E/V có thể dùng để mô tả bối cảnh sau khi tìm lại nguồn gốc chính thức, nhưng không suy ra commodity mix, số order, weight hay seasonality của từng hub.

## Conflict ledger

Quy tắc v3: technical review được dùng để sửa các provisional distance gây sai hình học; mọi số vẫn giữ nhãn `user_provided_anchor` cho đến khi đo lại bằng cùng routing provider và endpoint thật.

| Biến | Giá trị đang dùng | Giá trị xung đột | Quyết định |
|---|---:|---:|---|
| CT - HCM road | 172 km | 191 km provisional; khoảng 169-174 km trong review | Dùng midpoint 172 làm corrective anchor |
| Long Xuyên - CT road | 62 km | 87.8 km provisional; khoảng 62 km trong review | Dùng 62; không trộn với water |
| Vĩnh Long - CT road | 38 km | 79.2 km provisional; khoảng 34-40 km trong review | Dùng midpoint 38 |
| Long Xuyên - HCM road | 190 km | 233 km provisional; khoảng 190 km trong review | Dùng 190 |
| Vĩnh Long - HCM road | 144 km | khoảng 136 km trong narrative | Dùng 144 |
| CT - HCM water | 220 km | có nơi dùng road distance cho ví dụ route | Giữ water leg riêng, assumption |
| Diesel center | 21,745 VND/l tại kỳ 09/07/2026 | narrative cũ nêu 21,866 rồi khoảng 21,200 | Dùng 21,745 làm `verified_fact` center; annual rows vẫn simulated |
| River risk thresholds | 2.60/3.75 m | narrative cũ nhắc báo động III khoảng 2.0 m và peak >2.2 m | Giữ threshold mô phỏng; không gọi là ngưỡng pháp lý |
| PDF numeric claims | Không dùng | 70-80%, 30-40%, 18 triệu tấn... | Không dùng vì citation không truy vết được |

## Temporal anchors và địa lý hài hòa v4

| Hạng mục | Giá trị v4 | Phân loại | Phạm vi/giới hạn |
|---|---|---|---|
| Annual demand index | 2024 `1.00`, 2025 `1.04`, 2026 `1.08` | `simulation_assumption` | Trend nhỏ, không phải số tăng trưởng thị trường quan sát |
| Seasonality blend | shared `0.35`, commodity `0.50`, hub `0.15` | `simulation_assumption` | Giữ pattern có thể học nhưng không lặp cứng giữa các năm |
| Demand year noise | seeded, clipped quanh 1 | `derived_value` | Giá trị đã resolve được lưu trong metadata để audit |
| Weather year anomaly | seeded, clipped quanh 1 | `derived_value` | Tạo khác biệt giữa năm, không dùng dữ liệu thời tiết lịch sử |
| Weather lag | rain/flood 3 ngày; salinity 14 ngày | `simulation_assumption` | Chỉ mô phỏng causal delay hợp lý, cần calibrate bằng pilot data |
| Administrative names | chỉ tên tỉnh/thành sau sáp nhập cho 2024-2026 | `user_requested_harmonization` | Phục vụ consistent join; không đại diện tên pháp lý lịch sử tại event time |
| Merger demand shock | không áp dụng | `simulation_assumption` | Ngăn bước nhảy giả tạo tháng 7/2025 do đổi nhãn địa lý |

Nguồn chính thức xác nhận Nghị quyết 202/2025/QH15 và mốc chính quyền địa phương sau sắp xếp hoạt động từ 01/07/2025: <https://baochinhphu.vn/nghi-quyet-cua-quoc-hoi-ve-sap-xep-don-vi-hanh-chinh-cap-tinh-102250612191145158.htm>. MRC được dùng làm context định tính cho nhịp mùa mưa/lũ và salinity, không dùng để gán weather row quan sát: <https://www.mrcmekong.org/publications/annual-mekong-hydrology-flood-and-drought-report-2018/>.

Quyết định áp dụng tên sau sáp nhập ngược cho 2024 là **analytical harmonization do người dùng yêu cầu**. Vì vậy `valid_from=2024-01-01` trong reference table mô tả phạm vi dataset, không khẳng định đơn vị hành chính đó đã tồn tại pháp lý từ ngày này.

## Verification backlog trước khi dùng ngoài demo

1. Chốt địa chỉ cụ thể của bốn HTX/hub, `CT_HUB` và market/kho TP.HCM.
2. Tính road distance bằng cùng một routing provider, cùng vehicle profile và ngày đo.
3. Map waterway theo bến thật, luồng, cầu, mớn nước, chiều dòng và restriction.
4. Xác minh mực nước/ngưỡng cảnh báo theo trạm và datum cụ thể; không dùng threshold simulation như cảnh báo thật.
5. Lấy giá nhiên liệu theo kỳ điều hành có URL/ngày hiệu lực.
6. Lấy báo giá freight có mode, vehicle, tải, leg, thời điểm, VAT/toll và fixed fee rõ ràng.
7. Xác minh mùa vụ, sản lượng và hao hụt theo hub/commodity thay vì số quốc gia.
8. Đo fleet/capacity/status từ đơn vị vận hành thực tế.

Khi hoàn tất một mục, cập nhật đồng thời `base.yaml`, `source_type`, file này và `CHANGELOG.md`; không sửa CSV output bằng tay.
