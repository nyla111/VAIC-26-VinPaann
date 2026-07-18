# AI2 — Internal notes (không public)

> File này dành cho team nội bộ (AI1, Backend, Frontend, Data Lead, AI2). `README.md` trong
> cùng thư mục là bản public/professional, không có nội dung dưới đây — đừng copy ngược nội
> dung file này vào README.

## 1. Bối cảnh

`ai2_dispatch` được build ưu tiên "ra output nhanh": chạy đúng shape API trên **data canonical
thật** (không phải dataset simulate riêng của AI2) để Backend/Frontend cắm vào sớm, thay vì chờ
model forecast/priority score được tune hoàn chỉnh. Tham khảo thêm 2 file ngoài repo (không
push): `PROGRESS_REPORT.md` và `AI2_BUILD_PLAN.md` ở thư mục gốc `vaic/` — chứa phân tích chi
tiết hơn về lệch data giữa `AI2-plan.pdf` (draft không chính thức của Thảo Nhi) và data thật.

**2026-07-18 — cập nhật quan trọng:** đã gửi câu hỏi cho Phương/Nghiệp/Moi Ti/Data Lead (mục 5
cũ), **không ai phản hồi kịp**. Theo chỉ đạo, đã **tự chốt toàn bộ quyết định** thay vì chờ —
xem mục 6. Approach chung: chọn hướng nào **giảm rủi ro tích hợp nhất** (AI2 tự chịu phần việc
convert/validate, không bắt Backend/AI1 phải làm đúng 1 format cụ thể mới chạy được). Mọi quyết
định đều **có thể sửa lại** khi có phản hồi thật — không có gì là final tuyệt đối.

## 2. Điểm khác so với thông tin có sẵn chính thức (SCHEMA.md, INTEGRATION_LOP_AI_1.md, notebook Phase 1/2)

*(Không so với `AI2-plan.pdf` — file đó là draft không chính thức, không phải nguồn cần khớp
tuyệt đối.)*

1. **Cargo profile dùng `commodity_id` canonical, không dùng `cargo_type` tự do.** Notebook
   Phase 1 (`vaic_phase1_notebook_and_datasets`) sinh cargo như `mango`, `rambutan` — 2 loại
   này **không tồn tại** trong `commodities.csv` thật (10 commodity canonical). Nếu
   `commodity_id` gửi lên không khớp, AI2 giờ **không crash** — dùng fallback profile (xem mục
   6.2).
2. **Vehicle status dùng 4 giá trị canonical** (`available/en_route/maintenance/reserved`),
   không dùng 6 giá trị (`available/loading/dispatched/in_transit/maintenance/unavailable`)
   từng thấy ở dataset Phase 1 simulate. Lý do: đồng bộ với `fleet.csv` thật mà AI1 cũng đọc.
3. **`time_sensitivity`/`max_safe_wait_hours` là giá trị convert từ `commodities.csv`**
   (`perishability_level/5`, `max_hold_hours` giữ nguyên) — giả định do Thảo Nhi tự đặt, **chưa
   có ai xác nhận chính thức** (đã hỏi Data Lead, không có phản hồi — giữ nguyên công thức này
   làm chốt tạm, xem mục 6.6).
4. **Không có field nhiệt độ riêng theo commodity** (`temperature_min/max_celsius`) vì
   `commodities.csv` chỉ có `needs_reefer` boolean, không có range nhiệt độ.
5. **Lỗi validate route/mode trả 422 theo format Pydantic mặc định**, không phải envelope lỗi
   custom đầy đủ như 1 số thiết kế nội bộ từng phác thảo — chỉ 3 lỗi domain
   (`SHIPMENT_NOT_FOUND`, `INVALID_STATE_TRANSITION`, `ROUTE_NOT_APPLICABLE`) dùng envelope
   `{"error": {...}}`.
6. **State giờ có persist ra file local** (mục 6.3) — không còn thuần in-memory như bản đầu.
7. **Forecast "unknown future load" dùng rolling-mean tự tính từ event thật nhận được**, chưa
   cắm model đã train trong `VAIC_Phase2_Rolling_Forecaster.ipynb`
   (`HistGradientBoostingRegressor`) — notebook đó train trên dataset Phase 1 simulate, không
   phải canonical, nên **chưa thể dùng thẳng cho service này**. Xem mục 3.
8. **Weather risk (0..1) là `flood_risk_idx` thật từ `weather_bulletins.csv`**, không phải số
   tự chế. AI2 tự cộng dồn 2 node (CT_HUB, HCM_MARKET) theo hướng bảo thủ — quyết định thiết kế
   của Thảo Nhi, giữ nguyên làm chốt tạm (mục 6.7).
9. **Cấu trúc thư mục repo đã đổi tên** (ngoài phạm vi AI2, xảy ra 2026-07-18): thư mục AI1 từ
   `route_optimizer` → `ai1_route_optimizer`; data package từ
   `VAIC_Data_Simulation_Package_v3_2026-07-18` → `data_package`. `ai1_route_optimizer/data_loader.py`
   có `DEFAULT_DATA_DIR` trỏ vào tên thư mục cũ, đã tự sửa lại khi phát hiện lúc chạy test
   (không phải thay đổi chủ đích của AI2, nhưng cần AI1 biết để không bị ai đó revert nhầm).

## 3. Notebook Phase 1 / Phase 2 — giữ nguyên, chưa convert sang `.py`

Quyết định: **giữ nguyên 2 notebook Colab**
(`vaic_phase1_notebook_and_datasets/01_data_simulation_and_validation.ipynb` và
`VAIC_Phase2_Rolling_Forecaster.ipynb`) thay vì convert sang script `.py` chạy pipeline, vì:

- Cả 2 notebook hiện train/validate trên **dataset simulate riêng của AI2** (hub/cargo không
  khớp canonical, xem mục 2) — chưa finalize trên data thật, nên convert sang `.py` ngay bây
  giờ chỉ đóng băng một pipeline sẽ phải sửa lại.
- Giữ notebook giúp dễ reproduce trên Colab (mount Drive, cần thời gian train lâu hơn 1
  request), tách biệt hoàn toàn với API request-response latency thấp mà `ai2_dispatch/app`
  cần.
- `ai2_dispatch/app/forecasting.py` (rolling-mean v1) là **service code độc lập, viết mới**,
  không import gì từ 2 notebook này.

**Việc còn lại (không chặn Backend/Frontend, làm song song):** sau khi có đủ event log thật từ
demo (đi qua `ai2_dispatch/app`, không phải dataset simulate), build lại `arrival_buckets`
tương đương từ log đó, chạy lại pipeline Phase 1 → Phase 2 trên data thật, rồi swap model đã
train vào `forecasting.py::build_forecast()` — output shape không đổi nên không breaking
Backend/Frontend đã tích hợp trước đó.

## 4. Checklist trạng thái hiện tại

- [x] DONE — API chạy trên data canonical thật (commodities, fleet, weather_bulletins), path đã
      cập nhật theo cấu trúc thư mục mới (`ai1_route_optimizer/`, `data_package/`).
- [x] DONE — 5 event endpoint + idempotency theo `event_id`.
- [x] DONE — `GET /api/v1/forecast`, `GET /api/v1/dispatch-status` đúng shape thiết kế.
- [x] DONE — Hard constraint 1-5 + additive priority score.
- [x] DONE — Map/normalize route code AI1 (A-E) ↔ route enum AI2 (5 tên) ngay ở input layer;
      `direct_hcm_road` bị reject rõ ràng (`ROUTE_NOT_APPLICABLE`).
- [x] DONE — Fallback cargo profile khi `commodity_id` không khớp canonical (không crash).
- [x] DONE — State persist ra file local (pickle), sống sót qua restart process.
- [x] DONE — Test end-to-end (`tests/test_smoke.py`, 10 case) chạy qua data thật, pass — gồm
      case route code AI1 thô, commodity lạ, restart state.
- [x] DONE — Sample request/response thật trong `examples/`.
- [x] DONE — Event `dispatch-completed` — bù lỗ hổng bản đầu (shipment dispatch xong không bao
      giờ rời pending pool). `StateStore.mark_dispatched()`, test riêng.
- [x] DONE — Priority score weights (α=0.60/β=0.30/γ=0.10, threshold=0.65) đã tune bằng
      simulation trên data thật (157 shipment thật, 3 tháng, qua đúng `optimize_route()` AI1) —
      xem mục 8 và `reports/tuning_report.json`. Giảm proxy total_loss ~25% so với default cũ.
- [ ] NOT DONE — Chưa test end-to-end thật với service Backend — mới test nội bộ qua
      TestClient/curl.
- [ ] NOT DONE — `time_sensitivity`/`max_safe_wait_hours` convert từ canonical vẫn là giả định
      tự chốt (mục 6.6), chưa ai xác nhận.
- [ ] NOT DONE — Chưa cắm model forecast học máy thật (Phase 2 notebook hoặc train mới) — đang
      dùng rolling-mean; forecast baseline cũng chưa điều kiện theo hub/loại hàng/giờ (mục 8).
- [ ] NOT DONE — Persist state hiện là file pickle local, chưa phải shared store — nếu chạy
      nhiều instance sẽ không đồng bộ.
- [ ] NOT DONE — Chưa có auth/logging production.
- [ ] NOT DONE — Chưa xử lý concurrent request thật kỹ (mới có 1 lock chung, chưa test tải).
- [ ] NOT DONE — `total_loss` trong simulation là proxy tự đặt, chưa được Business Lead review
      (mục 8).

## 5. Câu hỏi đã gửi nhưng chưa có phản hồi (giữ lại để track)

- **Phương (AI1):** ai convert route code A-E → route enum AI2? `commodity_id` AI1 trả về có
  luôn khớp 10 mã canonical không?
- **Nghiệp (Backend):** nguồn `harvested_at`? State nên lưu ở AI2 hay Backend là source of
  truth? `decision_ts` có luôn được truyền tường minh không?
- **Data Lead:** công thức convert `time_sensitivity`/`max_safe_wait_hours` đúng ý đồ không?
  Cách cộng dồn weather 2 node có hợp lý không?

Nếu ai trả lời sau này và câu trả lời khác với quyết định tạm ở mục 6 → cập nhật code theo câu
trả lời thật, không giữ quyết định tạm chỉ vì đã lỡ code.

## 6. Quyết định tự chốt (2026-07-18, team chưa phản hồi kịp)

1. **`harvested_at`**: không bắt buộc ai phải gửi. Nếu thiếu, AI2 dùng `created_at` làm mốc
   tính urgency (đã là behavior mặc định từ bản đầu — `Shipment.urgency_reference_ts`). Không
   cần Backend/hub làm gì thêm để AI2 chạy được; nếu sau này có `harvested_at` thật thì độ chính
   xác urgency sẽ tốt hơn, nhưng không phải điều kiện bắt buộc.
2. **`commodity_id` không khớp canonical**: thay vì raise lỗi hoặc âm thầm bỏ qua shipment khỏi
   urgency check, dùng 1 fallback profile "an toàn vừa phải" —
   `time_sensitivity=0.6`, `max_safe_wait_hours=median(10 commodity thật)`, `needs_reefer=False`.
   Lý do chọn median thay vì min/max: tránh lệch quá xa về 1 hướng khi không biết gì về loại
   hàng. Xem `data_loader.get_fallback_cargo_profile()`.
3. **State persistence**: không chờ quyết định SQLite/Backend-as-source-of-truth — tự thêm
   persist state ra 1 file pickle local (`ai2_dispatch/.state/ai2_state.pkl`, gitignore, không
   commit). Ghi đè sau mỗi event được accept. Nếu sau này Backend trở thành source of truth,
   phần này bỏ thẳng không ảnh hưởng API bên ngoài — chỉ là an toàn tạm thời cho giai đoạn demo.
4. **Route code A-E ↔ route enum AI2**: AI2 tự nhận cả 2 format (xem `enums.normalize_route()`)
   — không cần Backend/AI1 làm bước convert trước khi gọi AI2. Nếu về sau AI1 chính thức trả
   route enum theo đúng 5 tên AI2 dùng thì không cần đổi gì (vẫn nhận được bình thường).
5. **`inbound_mode_to_can_tho`/`outbound_mode_from_can_tho`**: đổi từ bắt buộc sang optional,
   tự suy ra từ `selected_route` nếu không gửi. Nếu gửi mà sai so với route thì vẫn reject (để
   bắt lỗi thật, không nuốt im lặng).
6. **`time_sensitivity = perishability_level / 5`, `max_safe_wait_hours = max_hold_hours`**:
   giữ nguyên công thức ban đầu làm chốt tạm — không có thông tin gì tốt hơn để thay, và công
   thức này ít nhất có tính đơn điệu đúng hướng (perishability cao hơn → time_sensitivity cao
   hơn). Rủi ro đã biết: `max_hold_hours` có thể tính cho toàn hành trình chứ không riêng đoạn
   chờ ở Cần Thơ → urgency có thể bị đánh giá thấp hơn thực tế đối với hàng đã đi đường dài từ
   hub. Chưa sửa vì không có cách tính bù trừ nào chắc chắn hơn phỏng đoán.
7. **Cộng dồn weather 2 node (CT_HUB, HCM_MARKET)**: giữ nguyên hướng bảo thủ (blocked nếu 1
   trong 2 đóng, risk = max của 2 node) — đây là lựa chọn an toàn hơn (fail-safe), hợp lý để
   giữ làm default nếu không có thông tin ngược lại.
8. **`decision_ts` optional**: giữ nguyên default = giờ hiện tại nếu Backend không truyền — đây
   vốn không phải câu hỏi cần chặn, chỉ là khuyến nghị Backend nên truyền tường minh khi demo.

## 8. "Có AI ở đây không?" (2026-07-18, đã gửi output cho Backend, đổi ưu tiên sang "tốt nhất")

Câu hỏi được đặt ra sau khi đã gửi output đầu cho Backend — từ đây mục tiêu không còn là "nhanh
nhất" nữa. Trả lời thẳng, để không ai trong team hiểu nhầm khi bị hỏi lúc demo:

**Trước session này:** không có model học máy nào chạy trong pipeline live. Hard constraint là
rule-based thuần. Priority score là công thức cộng có trọng số, nhưng **trọng số là số tự đặt**
(0.55/0.35/0.10, threshold 0.75), không fit theo data nào. Forecast "unknown future load" là
1 con số rolling-mean **global** (không tách hub/loại hàng/giờ) — còn thô hơn cả "baseline bắt
buộc" AI2-plan.pdf mục 3.3 mô tả. Model ML thật duy nhất (`HistGradientBoostingRegressor`,
Phase 2 notebook) train trên dataset simulate sai hub/cargo, chưa nối vào service.

**Sau session này:**
- Priority score weights **đã tune bằng simulation trên data thật** — không phải ML, nhưng
  không còn là số tự đặt nữa. Xem `scripts/simulate_and_tune.py`: lấy 157 shipment thật "đi qua
  Cần Thơ" từ `orders.csv` (3 tháng 01/05/09-2026) bằng cách chạy đúng
  `ai1_route_optimizer.optimize_route()` thật, replay qua `decision_engine.evaluate()` thật
  (có mô phỏng xe quay vòng dựa trên `duration_hr_base` thật của leg CT_HUB↔HCM_MARKET, không
  mô phỏng thì fleet 13 xe road/14 phương tiện water cạn kiệt sau vài lượt — bug phát hiện và
  sửa trong lúc build harness), grid-search 55 tổ hợp α/β/γ/threshold theo đúng lưới AI2-plan.pdf
  mục 17, chọn bộ giảm proxy `total_loss` ~25% (164,025 → 122,866). Bộ mới:
  **α=0.60, β=0.30, γ=0.10, threshold=0.65**.
- Vẫn **không có model học máy nào chạy trong pipeline live** — forecast vẫn là rolling-mean
  global. Việc "có AI" hiện tại nằm ở tầng **tối ưu hoá có căn cứ data thật** (simulation-based
  tuning), không phải ở tầng **học từ data** (ML model). Đây là 2 khái niệm khác nhau, cần nói
  rõ với nhau trong team để không lỡ overclaim lúc pitch.
- `total_loss` dùng để tune là **proxy tự đặt** (wait cost/ton-giờ, underfill cost/ton, penalty
  safe-violation, penalty unresolved) — không phải VND thật, chưa có Business Lead review. Nếu
  pitch, phải nói "tune theo proxy chi phí tự định nghĩa", không nói "tối ưu chi phí thật".

## 9. Kế hoạch hoàn thiện phase tiếp theo

Đã làm trong session này (không còn trong list): fix `dispatch-completed`, build simulation
harness, tune priority score weights bằng data thật.

Còn lại, không cần chờ team khác:

1. **Forecast thống kê có điều kiện**: `rolling_mean_kg_per_bucket()` hiện là 1 số global toàn
   hệ thống — nên điều kiện theo `(outbound_mode, giờ trong ngày, ngày trong tuần)` như
   AI2-plan.pdf mục 3.3 mô tả. Có thể bootstrap từ chính simulation harness (đã có sẵn logic
   lấy shipment CT-bound thật) thay vì chỉ dựa vào event log runtime ít ỏi lúc mới start.
2. Externalize `DecisionConfig` ra `config/dispatch_config.json` — hiện hard-code trong
   `decision_engine.py`, dù đã có giá trị tune rồi vẫn nên tách để dễ chỉnh lại khi có info mới.
3. Thêm structured logging (mỗi event, mỗi decision) — cần cho việc debug lúc demo trực tiếp.
4. Viết script nhỏ replay `examples/sample_events.json` qua HTTP để demo nhanh không cần gõ
   curl tay.

Việc lớn, tốn công, đúng hướng "tốt nhất" nhưng chưa làm trong session này (cần quyết định có
làm tiếp không, xem mục còn lại của header conversation gốc — 3 hướng đã chọn: tune weights ✅,
forecast thống kê (mục 9.1, chưa làm), nối ML thật):

5. **Nối model ML thật**: retrain `HistGradientBoostingRegressor` (hoặc model khác) trên
   `arrival_buckets` build từ data canonical/event log thật — không dùng thẳng notebook Phase 2
   cũ (train sai hub/cargo). Cần: (a) sinh lại `arrival_buckets` tương đương nhưng đúng hub id
   + commodity_id canonical, (b) backtest so với rolling-mean hiện tại (MAE,
   `full_load_time_error_minutes` theo đúng AI2-plan.pdf mục 16), (c) chỉ swap vào
   `forecasting.py::build_forecast()` nếu thắng rõ ràng.
6. Nếu Data Lead xác nhận/sửa công thức `time_sensitivity`/`max_safe_wait_hours`: cập nhật
   `data_loader.build_cargo_profiles()`, chạy lại `simulate_and_tune.py` vì weight tune phụ
   thuộc công thức này.
7. Bàn với Backend về persistent state dài hạn (SQLite/Backend-as-source-of-truth) — pickle
   local hiện tại chỉ là giải pháp tạm cho 1 instance.
8. Đưa proxy objective (`total_loss` trong `simulate_and_tune.py`) cho Business Lead review —
   nếu có số chi phí chờ/penalty thật, chạy lại tuning với proxy chính xác hơn.

## 10. Checkpoint 2026-07-18 — thêm predictive model + agentic loop

Lý do: cần nộp checkpoint, cần show được "1 model predictive" và "agentic" cụ thể, không chỉ
nói suông là có AI. Làm bản đơn giản, KHÔNG fine-tune kỹ (theo đúng yêu cầu — ưu tiên có cái để
show trước).

**Predictive model** (mục 9.5 cũ, làm 1 phần rút gọn — không phải bản đầy đủ):
- `scripts/train_forecaster.py`: build bucket 30 phút từ **157 shipment thật** (cùng nguồn với
  `simulate_and_tune.py` — `orders.csv` canonical, qua đúng `optimize_route()` AI1, 3 tháng
  01/05/09-2026), feature: giờ/thứ/tháng/outbound_mode/lag+rolling count/weight. Train
  `GradientBoostingRegressor` (sklearn, cấu hình mặc định, KHÔNG grid-search).
- Kết quả thật (không phải claim): `mae_model_kg=2290.83` vs
  `mae_rolling_mean_baseline_kg=2432.23` — **thắng nhưng không rõ ràng** (~6%), không phải kiểu
  chênh lệch lớn có thể pitch mạnh. Lưu trong `models/training_metrics.json`, đọc kỹ trước khi
  quyết định có show con số này ra ngoài không — nếu giám khảo hỏi sâu, câu trả lời trung thực
  là "cải thiện nhẹ trên sample nhỏ, chưa đủ mạnh để khẳng định ML thắng rule-based rõ ràng".
- Wire vào `forecasting.py::build_forecast()` qua `app/ml_forecaster.py` — có fallback về
  rolling-mean nếu thiếu artifact/sklearn, không bao giờ crash service.
- **Việc 9.5 cũ (bản đầy đủ: sinh `arrival_buckets` đúng chuẩn, backtest kỹ, so với
  `full_load_time_error_minutes`) vẫn CHƯA làm** — đây chỉ là bản rút gọn đủ để có 1 model thật
  chạy trong pipeline, không phải bản hoàn chỉnh.

**Agentic loop** (chưa có trong plan cũ, bổ sung mới):
- `app/agent.py::periodic_tick_loop()` — background task chạy độc lập (FastAPI lifespan,
  `asyncio.create_task`), tick mỗi `AI2_AGENT_TICK_SECONDS` giây (default 30s), tự gọi
  `decision_engine.evaluate()` cho cả 2 outbound_mode, log khi decision đổi. Đây là phần đúng
  AI2-plan.pdf mục 3.6 (periodic safety tick) mà bản đầu chưa làm — trước đây service thuần
  reactive (chỉ tính khi có GET).
- Tách `run_single_tick()` (sync, test được) khỏi `periodic_tick_loop()` (async, chạy vô hạn) —
  có test riêng (`test_agent_run_single_tick_reflects_live_state`).
- **Chưa verify bằng live server chạy dài** — có 1 lần verify curl bị flaky do môi trường
  (Windows/network, không phải bug code, xem lịch sử tool call), nhưng automated test suite
  (12/12, gồm test agent) là bằng chứng chính. Nên tự chạy `uvicorn` + để 1-2 phút + xem log để
  tự mắt thấy trước khi demo, đừng chỉ tin lời assistant.

**Việc còn thiếu để "thật" hơn nữa** (không nằm trong checkpoint này):
- Model chưa backtest kỹ theo đúng metric AI2-plan.pdf mục 16 (`full_load_time_error_minutes`).
- Agent loop mới chỉ log ra console — chưa có nơi lưu lịch sử quyết định để show "agent đã tự
  hành động qua thời gian" một cách trực quan (VD dashboard xem lại log).
- Chưa test agent loop chạy khi service bị lỗi tạm thời (network, data load lỗi) — có try/except
  bọc ngoài mỗi tick nên không chết hẳn, nhưng chưa test case cụ thể.
