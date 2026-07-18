Kết luận ngắn
Bộ data đủ khả thi cho Layer 1 (Route & Cost Optimizer) và impact calc, nhưng hụt cho Layer 2 (Forecast Agent), cho grounding, và cho phần "AI-Native" của rubric. Nghịch lý: phần được làm tốt nhất (kỹ thuật, provenance) lại chỉ ăn 20/100 điểm; phần yếu nhất lại nằm đúng ở 35 điểm (AI-Native + Grounding).
Những gì tôi verify được (không phải tin theo doc)
Kiểm traKết quảRe-run generator, so canonical checksumTrùng bit-for-bit (annual + S2)validate_data.py423/423 pass, exit 0pytest tests/7 passedFuel/freight/fleet override của S3Áp dụng đúng (road available 0.62 → 0.36)S2 water penalty có thật khôngCó — mực nước 3.2–4.08 m, vượt band 3.35, water_factor 1.05–1.236
Reproducibility và provenance discipline ở đây là thật, không phải claim suông. ANCHORS.md với 4-nhãn taxonomy + conflict ledger là thứ hiếm gặp ở hackathon.
Test quan trọng nhất: data có sinh ra tín hiệu quyết định không?
Tôi chạy optimizer per-order (freight + hao hụt, deadline-feasible):
ScenarioA (thẳng)B (bộ qua CT)C (thủy qua CT)Bất khả thiS1_normal63170S2_flood510114S3_price_shock530180
Tín hiệu S1→S3 (C tăng 7→18) và S2 (4 đơn mất khả thi) có thật và đúng hướng. Đây là điểm mạnh lớn nhất.
Nhưng Route B chết về mặt hình học, không phải do model:
Vị Thanh    A=240.0km  B=251.0km   (+4.6%)
Long Xuyên  A=233.0km  B=278.8km   (+19.7%)
Sóc Trăng   A=231.0km  B=254.0km   (+10.0%)
Vĩnh Long   A=144.0km  B=270.2km   (+87.6%)   ← backtrack
B phải trả 2 fixed fee cho quãng đường dài hơn → không bao giờ thắng ở per-order. B chỉ sống nếu Layer 2 chia fixed fee qua consolidation. Nếu demo "so sánh 3 tuyến" mà B thua 71/71, giám khảo sẽ hỏi ngay tại sao có nó trong deck.
Impact number — chỗ pitch sẽ vỡ
ScenarioBaseline (always A)Route-optTiết kiệmS1_normal213.3 tr200.4 tr6.04%S2_flood282.4 tr268.0 tr5.10%S3_price_shock279.4 tr242.8 tr13.10%
Hai vấn đề:

Toàn bộ tiết kiệm S1 đến từ 7 đơn mía. 8/71 đơn được cải thiện, 7 trong đó là COM_SUGARCANE. Lý do: mía có value_vnd_per_kg = 1,300 → chi phí hao hụt gần bằng 0 → ghe chậm mà không bị phạt; cộng median 16 tấn → rate/ton-km (520 vs 1,500) áp đảo. Đây thực ra là insight kinh tế đúng (hàng bulk giá thấp mới đi thủy), nhưng nó có nghĩa: không được pitch "AI tiết kiệm X% cho nông sản ĐBSCL". Chỉ được pitch cho gạo + mía.
S2_flood tiết kiệm ÍT hơn S1 (5.10% < 6.04%). Nếu narrative là "khi lũ, AI cứu bạn" thì số liệu không đỡ được. Câu chuyện thật của S2 là 4 đơn mất khả thi — tức là reliability/feasibility, không phải cost. Phải đổi narrative S2 sang "AI phát hiện đơn không giao kịp deadline trước khi bạn xuất xe", nếu không phần Trình bày sẽ bị đâm.

Layer 2 Forecast Agent — đây là blocker nặng nhất
Tôi đo trần forecast trên annual pack:
Daily orders/hub: mean 6.42, var/mean = 1.19   (Poisson thuần = 1.00)
R² ceiling của model (hub, month, dow) hoàn hảo trên daily count = 0.323
Tonnage theo tháng: peak/trough chỉ 1.37x
Nghĩa là: generator sinh order bằng Poisson, mùa vụ chỉ thêm 19% excess variance trên nhiễu Poisson. Không model nào — LSTM, Prophet, XGBoost, LLM — vượt được R²≈0.32 trên data này. Còn lại là nhiễu bạn tự bơm vào.
Tệ hơn: seasonality per-commodity trong ANCHORS (tôm đỉnh T7 1.55x, mía đỉnh T11 1.55x, hành tím đỉnh T12 1.50x…) triệt tiêu lẫn nhau khi cộng gộp → đường tổng cầu gần phẳng (1.37x). Demo "Forecast Agent" sẽ vẽ ra một đường thẳng.
Và ở mức giờ: 78% ô (hub, giờ) là 0 đơn. Forecast theo giờ là vô nghĩa; buộc phải aggregate lên ngày, mà ở ngày thì trần là 0.32.
Đồng thời: không có ground truth outcome — không có realized travel time, không có delivery outcome. Nên "Forecast" chỉ còn là demand forecast, và demand forecast thì gần như không học được gì.
Consolidation density — barge là đồ trang trí
Tích lũy 24h hàng đủ điều kiện đi thủy tại mỗi hub (annual, median):
HUB_VITHANH    63.9 t     HUB_LONGXUYEN  41.2 t
HUB_VINHLONG   34.0 t     HUB_SOCTRANG   28.7 t
boat_50t (50t) → hợp lý, ~1 chuyến/hub/ngày. Nhưng barge_200t (7 chiếc) và barge_500t (3 chiếc) — 10/77 phương tiện, 13% đội — cần 3–7 ngày mới đầy tải tại 1 hub, trong khi max_hold_hours của phần lớn hàng thủy là 42–120h. Đặt 1 barge_500t ở Long Xuyên là bất khả thi về mặt số học. Chỉ ở CT_HUB (gom từ 4 hub, ~160t/ngày) barge mới có nghĩa.
Grounding — lỗ hổng cấu trúc
Hai vấn đề tôi đọc ra từ code:

fuel_prices không nối vào bất kỳ công thức chi phí nào. freight_vnd dùng rate_vnd_per_ton_km; vehicle_trip_vnd dùng cost_per_km_vnd. Fuel chỉ xuất hiện ở dòng ~753–777, tức chỉ trong compat dataset_price.json. Trong S3, diesel 1.18x và road rate 1.14x là hai override độc lập, không có quan hệ nhân quả. Giám khảo hỏi "dầu tăng 18% thì cước tăng 14% theo cơ chế nào?" → không có câu trả lời trong data.
Trong scenario, fuel_prices chỉ có 1 timestamp (3 rows = 3 loại nhiên liệu). Giá nhiên liệu là hằng số trong cửa sổ 72h. "Price shock" là một bậc thang tĩnh, không phải động lực học.

Và vấn đề lớn nhất cho rubric: bộ data không có một dòng text nào. 8 bảng đều là số/enum. Không có ghi chú đơn hàng, không có báo cáo tài xế, không có bản tin thời tiết, không có SOP. Một kiến trúc AI-Native cần grounding thì không có gì để ground vào. LLM trong hệ thống này chỉ có thể là lớp vỏ mỏng bọc một optimizer deterministic — và đó chính xác là điều rubric 20 điểm "AI-Native & Đổi mới" trừng phạt.
Cộng thêm: README cố tình không có recommended_route (đúng, tránh leakage) — nhưng cũng có nghĩa không có golden set để đo agent. Phần "Độ tin cậy" (15đ) không có bằng chứng định lượng.
Chấm theo rubric
Tiêu chíĐiểmƯớc tính data hỗ trợ đượcNhận địnhChất lượng triển khai kỹ thuật2017–19Reproducibility verified, validator 423 checks, config-driven, không magic number trong code. Đây là điểm mạnh.Kiến trúc AI-Native & Đổi mới208–11Data thuần số → LLM không có vai trò thật. Không có text, không có tool-use surface, không có gì để agent reason ngoài arithmetic.Khả thi kinh doanh & Pilot2013–156%/13% là số defensible và chạy được từ baseline_policy. Nhưng tiết kiệm dồn vào mía/gạo → TAM hẹp hơn pitch.UX AI-Native & Tư duy thiết kế1510–12compat/*.json + nodes.lat/lon cho FE là handoff tốt. Thiếu explainability payload (tại sao chọn tuyến này).An toàn AI, Grounding & Độ tin cậy157–9ANCHORS xuất sắc về provenance của data, nhưng grounding của AI không có nguồn text nào. Không golden set. Chỉ 2/~60 biến là verified_fact.Trình bày & Bảo vệ106–8Rủi ro cụ thể: B thua 71/71; S2 tiết kiệm < S1; VL–CT 79.2km.
Tổng ước tính: 61–74/100. Trần bị chặn bởi AI-Native + Grounding, không phải bởi chất lượng data.
Rủi ro bảo vệ cụ thể
LEG_VL_CT_ROAD = 79.2 km. Conflict ledger đã ghi nhận narrative nói ~35 km và chọn 79.2 vì "ưu tiên bảng người dùng". Thực tế Vĩnh Long–Cần Thơ khoảng 34–40 km qua QL1A. Tương tự Long Xuyên–Cần Thơ 87.8 km (thực tế ~62 km) và CT–HCM 191 km (thực tế ~169–174 km). Bất kỳ giám khảo nào ở ĐBSCL cũng biết con số này. Quy trình của bạn đúng (ledger đã flag), nhưng quyết định resolve lại chọn giá trị kém chính xác hơn — và nó khuếch đại thành detour +87.6% khiến Route B chết. Đây là một lỗi grounding có hậu quả xuống tận kết luận.
Rủi ro thứ hai: trong S2, road_factor max 2.62 còn water_factor max 1.236. Tỷ lệ phạt này là do bạn chọn hệ số (road penalty 1.25+0.25 vs water high penalty 0.85 trên phần vượt band hẹp), không phải phát hiện từ data. Kết luận "lũ thì đi thủy" đã được cài sẵn vào YAML. Và ANCHORS backlog thừa nhận tĩnh không cầu/mớn nước chưa model — tức là ở mực nước 4.08 m, sà lan thực tế có thể không chui qua cầu được, tức water_factor lẽ ra phải là ∞ chứ không phải 1.24.
6 việc nên làm, theo thứ tự ROI

Bơm text layer (~2h, cứu nhiều điểm nhất). Thêm 3 bảng: weather_bulletins (bản tin KTTV dạng text/ngày), ops_notes (ghi chú tài xế/HTX), policy_docs (SOP, quy định tải trọng). Đây là thứ cho LLM một việc thật để làm và cho grounding một nguồn để cite. Không có cái này thì 35 điểm AI-Native + Grounding bị chặn trần.
Sửa VL/LX/CT distance hoặc thêm dòng vào conflict ledger giải thích tại sao chọn 79.2 chứ không phải 35. Nếu không sửa được kịp, ít nhất phải chủ động nêu trong deck trước khi bị hỏi.
Nối fuel → freight. Thêm một hệ số pass-through công khai trong YAML: rate = base * (1 + β*(fuel_rel - 1)), β ~ 0.3–0.4. Vừa cứu grounding, vừa làm S3 thành một câu chuyện nhân quả thay vì hai override rời.
Đổi narrative S2 từ "tiết kiệm chi phí" sang "phát hiện đơn bất khả thi + reroute". Số liệu đỡ được cái sau (4 đơn), không đỡ được cái trước (5.10% < 6.04%).
Thêm golden set nhỏ: ~50 đơn với reference_optimal_route tính bằng brute-force, để riêng ở eval/. Không đưa vào training data. Đây là bằng chứng duy nhất cho "Độ tin cậy".
Hoặc bỏ barge_500t/200t ở spoke hub, hoặc gom về CT_HUB. Và dời E06.08*, V06.05*, PDF vào data/raw_sources/ — để chúng ở root làm handoff trông lộn xộn và mời gọi câu hỏi "sao có file này mà không dùng?".

Về Forecast Agent: nếu còn thời gian, nâng seasonal_volume amplitude và làm các commodity đỉnh cùng pha hơn để tổng cầu có biên độ ≥2x; hoặc thẳng thắn định vị lại Layer 2 là Dispatch/Consolidation Agent (nơi giá trị thật nằm) và bỏ chữ "Forecast". Với var/mean = 1.19 hiện tại, cố demo forecasting là tự đưa cổ vào máy chém.