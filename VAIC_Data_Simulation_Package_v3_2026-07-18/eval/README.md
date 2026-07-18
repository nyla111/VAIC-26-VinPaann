# Held-out evaluation set

`eval/` chứa nhãn tham chiếu để đo Route & Cost Agent; đây không phải input huấn luyện và không được join vào canonical tables khi tạo feature.

## Files

- `reference_routes.csv` và `reference_routes.json`: 50 đơn được chọn deterministic, phân tầng theo hub/commodity và chia giữa S1/S2/S3.
- `metadata.json`: algorithm version, phân bố nhãn và checksum.
- Generator: `src/build_evaluation_set.py`.

## Reference algorithm

Mỗi đơn được brute-force ba candidate cố định:

- `A_DIRECT_ROAD`: hub → TP.HCM bằng đường bộ.
- `B_ROAD_VIA_CT`: hub → Cần Thơ → TP.HCM bằng đường bộ.
- `C_WATER_VIA_CT`: hub → Cần Thơ → TP.HCM bằng đường thủy.

Chi phí tham chiếu gồm freight quote nearest-previous, fixed fee theo số chuyến, và linear spoilage proxy. Feasibility kiểm tra commodity compatibility, explicit route closure trong `weather_bulletins`, và deadline. Nhãn không được ghi ngược vào `orders`.

Golden set này đo tính đúng của tool/agent trên dữ liệu mô phỏng; nó không chứng minh route thực tế tối ưu ngoài pilot. Khi thay đổi cost model, contract hoặc route geometry, phải tăng `evaluation.algorithm_version` và tái sinh toàn bộ eval set.
