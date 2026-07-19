"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Language = "vi" | "en";

type Dictionary = {
  brand: string;
  language: string;
  logout: string;
  login: string;
  email: string;
  password: string;
  enterprise: string;
  logistics: string;
  admin: string;
  enterpriseSubtitle: string;
  logisticsSubtitle: string;
  adminSubtitle: string;
  loginDescription: string;
  demoAccounts: string;
  loading: string;
  sections: Record<string, string>;
  sectionDescriptions: Record<string, string>;
  messages: Record<string, string>;
};

const dictionaries: Record<Language, Dictionary> = {
  vi: {
    brand: "DeltaFlow AI",
    language: "Ngôn ngữ",
    logout: "Đăng xuất",
    login: "Đăng nhập",
    email: "Email",
    password: "Mật khẩu",
    enterprise: "Doanh nghiệp",
    logistics: "Đơn vị logistics",
    admin: "Quản trị viên",
    enterpriseSubtitle: "Quản lý đơn hàng và theo dõi hành trình",
    logisticsSubtitle: "Điều phối đội xe và trung chuyển",
    adminSubtitle: "Giám sát vận hành và phân tích toàn mạng lưới",
    loginDescription: "Hệ thống điều phối logistics nông sản Đồng bằng sông Cửu Long.",
    demoAccounts: "Tài khoản demo",
    loading: "Đang tải...",
    sections: {
      business_shipment_form: "Tạo đơn hàng",
      business_recommendations: "Phân tích tuyến đường",
      business_tracking: "Theo dõi đơn hàng",
      logistics_overview: "Tổng quan",
      logistics_orders: "Đơn chờ nhận",
      logistics_fleet: "Đội xe",
      logistics_jobs: "Chuyến vận chuyển",
      logistics_deliveries: "Lịch sử giao hàng",
      admin_inventory: "Tổng quan",
      admin_weather: "Thời tiết",
      admin_dispatch: "Điều phối",
      admin_simulation: "Mô phỏng",
      admin_logs: "Phân tích hệ thống",
      admin_orders: "Đơn hàng",
      admin_operations: "Vận hành",
      admin_logistics: "Đối tác logistics",
      businesses: "Doanh nghiệp",
    },
    sectionDescriptions: {
      business_shipment_form: "Tạo và gửi yêu cầu vận chuyển nông sản.",
      business_recommendations: "So sánh các phương án tuyến đường do Layer 1 đề xuất.",
      business_tracking: "Theo dõi trạng thái, phương tiện và hành trình đơn hàng.",
      logistics_overview: "Giám sát đội xe, chuyến vận chuyển và hàng đang trung chuyển.",
      logistics_orders: "Nhận đơn, chọn phương tiện và gom hàng tại Cần Thơ.",
      logistics_fleet: "Theo dõi sức chứa và dự báo nhu cầu phương tiện theo ngày.",
      logistics_jobs: "Xem các chuyến vận chuyển đã nhận và đang thực hiện.",
      logistics_deliveries: "Lịch sử giao hàng và trạng thái hoàn tất.",
      admin_inventory: "Sức khỏe mạng lưới, KPI và luồng hàng theo thời gian thực.",
      admin_weather: "Theo dõi điều kiện thời tiết và thủy văn trên các hub.",
      admin_dispatch: "Theo dõi quyết định gom hàng và điều phối phương tiện.",
      admin_simulation: "Điều chỉnh dữ liệu mô phỏng phục vụ trình diễn vận hành.",
      admin_logs: "Phân tích hiệu quả tuyến đường và lịch sử sự kiện hệ thống.",
      admin_orders: "Theo dõi toàn bộ đơn hàng và đơn vị logistics phụ trách.",
      admin_operations: "Điều hành dispatch, capacity, exceptions và Layer 2 forecast.",
      admin_logistics: "Đánh giá năng lực và hiệu suất các đối tác vận chuyển.",
    },
    messages: {
      "common.all": "Tất cả", "common.cancel": "Hủy", "common.close": "Đóng", "common.confirm": "Xác nhận",
      "common.save": "Lưu", "common.refresh": "Làm mới", "common.search": "Tìm kiếm", "common.filter": "Bộ lọc",
      "common.loading": "Đang tải...", "common.no_data": "Chưa có dữ liệu", "common.no_results": "Không tìm thấy kết quả",
      "common.unknown": "Chưa rõ", "common.not_available": "Chưa có", "common.live": "Trực tiếp",
      "common.view_details": "Xem chi tiết", "common.back": "Quay lại", "common.next": "Tiếp theo",
      "common.previous": "Trước", "common.date": "Ngày", "common.status": "Trạng thái", "common.actions": "Thao tác",
      "common.route": "Tuyến đường", "common.mode": "Phương thức", "common.vehicle": "Phương tiện",
      "common.orders": "Đơn hàng", "common.weight": "Khối lượng", "common.capacity": "Sức chứa",
      "common.cost": "Chi phí", "common.time": "Thời gian", "common.eta": "Thời gian dự kiến",
      "common.provider": "Đơn vị vận chuyển", "common.hub": "Hub", "common.source": "Nguồn dữ liệu",
      "common.overview": "Tổng quan", "common.fleet": "Đội xe", "common.performance": "Hiệu suất", "common.multimodal": "Đa phương thức", "common.edit": "Chỉnh sửa", "common.reset": "Đặt lại", "common.view_by_role": "Xem theo góc nhìn", "common.origin": "Điểm xuất phát", "common.destination": "Điểm đến", "common.created": "Ngày tạo", "common.deadline": "Hạn giao", "common.progress": "Tiến độ", "common.shipment": "Lô hàng", "common.business": "Doanh nghiệp", "common.commodity": "Nông sản", "common.type": "Loại", "common.reason": "Lý do", "common.priority": "Mức ưu tiên", "common.suggested_provider": "Provider đề xuất", "common.recommended_route": "Tuyến đề xuất", "common.assign": "Phân công", "common.approve": "Duyệt", "common.track": "Theo dõi", "common.resolve": "Xử lý", "common.reassign": "Phân công lại", "common.contact_business": "Liên hệ doanh nghiệp", "common.show_resolved": "Hiển thị ngoại lệ đã xử lý", "common.shown": "đang hiển thị", "common.total": "Tổng số", "common.on_track": "Đúng tiến độ", "common.at_hub": "Tại hub", "common.delayed": "Bị trễ", "common.critical": "Nghiêm trọng", "common.warnings": "Cảnh báo", "common.resolved": "Đã xử lý", "common.assigning": "Đang phân công...", "common.auto_assign_all": "Tự động phân công tất cả", "common.items_pending": "mục đang chờ",
      "auth.invalid_credentials": "Email hoặc mật khẩu không đúng.", "auth.login_failed": "Đăng nhập thất bại.",
      "auth.demo_accounts": "Tài khoản demo", "auth.email": "Email", "auth.password": "Mật khẩu",
      "fleet.available": "Sẵn sàng", "fleet.in_transit": "Đang vận chuyển", "fleet.maintenance": "Bảo trì",
      "fleet.en_route": "Đang di chuyển", "fleet.vehicle_truck": "Xe tải", "fleet.vehicle_vessel": "Tàu",
      "fleet.forecast_date": "Ngày forecast", "fleet.demand": "Nhu cầu dự báo", "fleet.vehicles_needed": "Xe cần chuẩn bị",
      "fleet.available_vehicles": "Xe đang sẵn sàng", "fleet.available_capacity": "Sức chứa sẵn sàng",
      "fleet.enough": "Đủ xe", "fleet.shortage": "Thiếu {value} tấn", "fleet.confidence": "Độ tin cậy",
      "orders.awaiting_assignment": "Chờ phân công", "orders.arrived_waiting": "Đang chờ gom tại hub",
      "orders.dispatched": "Đã dispatch", "orders.completed": "Hoàn tất", "orders.cancelled": "Đã hủy",
      "orders.created": "Mới tạo", "orders.routed_to_can_tho": "Đang về Cần Thơ",
      "orders.provider_accepted": "Provider đã nhận", "orders.provider_rejected": "Provider từ chối",
      "map.available": "Sẵn sàng", "map.unavailable": "Không sẵn sàng", "map.in_delivery": "Đang giao hàng",
      "map.arrived_at_hub": "Đã đến hub", "map.waiting_jobs": "Đơn chờ gom", "map.active_routes": "Tuyến đang chạy",
      "map.waiting_consolidation": "Đang chờ gom hàng tại Cần Thơ", "map.unassigned": "Chưa gán",
      "forecast.live": "Forecast trực tiếp", "forecast.unavailable": "Forecast chưa khả dụng",
      "forecast.dispatch_now": "Sẵn sàng dispatch", "forecast.wait_for_load": "Đang gom thêm hàng",
      "forecast.wait_for_vehicle": "Đang chờ phương tiện", "forecast.no_decision": "Chưa có quyết định",
      "errors.generic": "Đã xảy ra lỗi. Vui lòng thử lại.", "errors.network": "Không thể kết nối tới máy chủ.",
      "errors.order_not_found": "Không tìm thấy đơn hàng.", "errors.vehicle_capacity": "Sức chứa phương tiện không đủ.",
      "errors.vehicle_unavailable": "Phương tiện hiện không sẵn sàng.", "errors.unauthorized": "Bạn không có quyền thực hiện thao tác này.",
      "errors.invalid_date": "Ngày không hợp lệ.", "errors.required": "Vui lòng nhập thông tin này.",
      "admin.platform_management": "Quản trị nền tảng", "admin.last_updated": "Cập nhật lần cuối",
      "admin.platform_kpis": "KPI nền tảng", "admin.live_metrics": "Chỉ số vận hành trực tiếp",
      "admin.cost_savings": "Tiền tiết kiệm từ đơn thực", "admin.orders_processed": "Đơn đã xử lý",
      "admin.operations_description": "Điều hành dispatch, capacity, exceptions và Layer 2 forecast.",
      "admin.dispatch_queue": "Hàng đợi dispatch", "admin.active_shipments": "Đơn đang vận chuyển",
      "admin.exceptions": "Ngoại lệ", "admin.capacity": "Capacity", "admin.no_exceptions": "Không có ngoại lệ cần xử lý.",
      "admin.road_outbound": "Đường bộ", "admin.water_outbound": "Đường thủy",
      "admin.pending_business_approvals": "Hồ sơ doanh nghiệp chờ duyệt", "admin.unassigned_orders": "Đơn chưa phân công",
      "admin.delayed_shipments": "Đơn vận chuyển bị trễ", "admin.capacity_alerts": "Cảnh báo sức chứa",
      "admin.review_applications": "Xem hồ sơ", "admin.assign_orders": "Phân công đơn", "admin.view_delays": "Xem đơn trễ",
      "admin.review_capacity": "Kiểm tra sức chứa", "admin.recent_activity": "Hoạt động gần đây", "admin.view_all_activity": "Xem toàn bộ hoạt động",
      "admin.show_less": "Thu gọn", "admin.time": "Thời điểm", "admin.activity": "Hoạt động", "admin.actor": "Người thực hiện",
      "route.optimize": "Tối ưu tuyến", "route.ai_recommendation": "Route AI khuyến nghị", "route.priority": "Mức ưu tiên",
      "route.weather_timestamp": "Thời điểm thời tiết", "route.price_timestamp": "Thời điểm giá", "route.recommended": "Khuyến nghị",
      "route.unavailable": "Tuyến chưa khả dụng.", "fleet.search": "Tìm kiếm biển số...",
      "jobs.waiting_for_pickup": "Chờ lấy hàng tại Hub", "jobs.moving_to_can_tho": "Đang chuyển về Cần Thơ",
      "jobs.consolidating_at_can_tho": "Đang gom hàng tại Cần Thơ", "jobs.dispatching_to_hcm": "Đang đi TP.HCM",
      "jobs.completed": "Giao hàng hoàn tất", "jobs.title": "Chuyến vận chuyển", "jobs.description": "Danh sách chuyến và chi tiết lô hàng đi kèm.",
      "jobs.no_jobs": "Hiện chưa có chuyến vận chuyển nào.", "jobs.details": "Chi tiết", "jobs.collapse": "Thu gọn",
      "orders.accept": "Nhận đơn", "orders.dispatch": "Xuất bến", "orders.select_vehicle": "Chọn xe phù hợp",
      "orders.open": "Đang mở", "orders.accepted": "Đã nhận", "orders.no_queue": "Chưa có đơn chờ nhận.",
      "orders.accept_failed": "Không thể nhận đơn.", "orders.dispatch_failed": "Không thể xuất bến.", "orders.waiting_title": "Đơn chờ nhận", "orders.waiting_description": "Chọn xe phù hợp, nhận đơn rồi gom nhiều đơn trước khi xuất bến.", "orders.accepted_summary": "Đã nhận {count} đơn. Có thể gom các đơn cùng xe và cùng phương thức.", "orders.select_dispatch_vehicle": "Chọn xe xuất bến", "orders.held_for_vehicle": "Đã giữ đơn cho xe {vehicle}. Chọn đơn ở trên để gom và xuất bến.", "orders.no_waiting": "Chưa có đơn chờ nhận.", "orders.selected_vehicle": "Xe đã chọn", "orders.provider_assigned_success": "Đã phân công provider thành công.", "orders.select_provider": "Chọn provider", "orders.change_assignment": "Đổi phân công", "orders.reoptimization_queued": "Đã đưa yêu cầu tối ưu lại vào hàng đợi.",
      "route.transfers": "Điểm trung chuyển", "route.accept_recommendation": "Chấp nhận gợi ý", "route.select_route": "Chọn tuyến này",
      "admin.overview_title": "Tổng quan quản trị", "admin.new_applications_waiting": "hồ sơ mới đang chờ", "admin.orders_without_provider": "đơn chưa có provider", "admin.shipments_past_eta": "lô hàng quá ETA", "admin.capacity_warnings": "cảnh báo sức chứa", "admin.total_businesses": "Tổng doanh nghiệp", "admin.active_logistics_partners": "Đối tác logistics hoạt động", "admin.delayed_orders": "Đơn bị trễ", "admin.ontime_rate": "Tỷ lệ đúng hạn", "admin.operations_title": "Vận hành", "admin.due_today": "Hạn hôm nay", "admin.search_orders": "Tìm mã đơn hoặc doanh nghiệp...", "admin.all_commodities": "Tất cả nông sản",
      "businesses.overview": "Tổng quan", "businesses.performance": "Hiệu suất", "businesses.activity": "Hoạt động", "businesses.address": "Địa chỉ", "businesses.registered": "Ngày đăng ký", "businesses.ton": "tấn", "businesses.no_orders": "Doanh nghiệp này chưa có đơn hàng.", "businesses.commodity": "Nông sản", "businesses.created": "Ngày tạo", "businesses.no_performance": "Chưa có dữ liệu hiệu suất — chưa có đơn hàng.", "businesses.activity_hint": "Hoạt động gần đây của doanh nghiệp hiển thị trong mục Tổng quan → Hoạt động gần đây.", "businesses.view_orders": "Xem đơn hàng", "businesses.confirm_suspend": "Xác nhận tạm dừng",
      "logistics.modes": "Phương thức vận tải", "logistics.fleet_size": "Quy mô đội xe", "logistics.no_orders": "Chưa có đơn được phân công cho provider này.", "logistics.fleet_utilization": "Mức sử dụng đội xe", "logistics.ontime": "Tỷ lệ giao đúng hạn", "logistics.utilization": "Mức sử dụng", "logistics.active_orders": "Đơn đang hoạt động", "logistics.avg_capacity": "Sức chứa trung bình mỗi đơn", "logistics.vehicle_id": "Mã phương tiện", "logistics.edit_capacity": "Chỉnh sức chứa", "logistics.contact": "Liên hệ", "logistics.activated": "Đã kích hoạt", "logistics.deactivated": "Đã vô hiệu hóa", "logistics.busy": "Bận", "logistics.inactive": "Không hoạt động",
      "events.route_optimized": "Đã tối ưu tuyến", "events.provider_assigned": "Đã phân công provider", "events.picked_up": "Đã lấy hàng", "events.arrived_at_hub": "Đã đến hub", "events.departed_from_hub": "Đã rời hub", "events.expected_pickup": "Dự kiến lấy hàng", "events.estimated_delivery": "Dự kiến giao hàng", "events.order_created": "Đã tạo đơn", "events.awaiting_assignment": "Đang chờ phân công",
      "map.route_selector": "Chọn tuyến", "map.fallback_geometry": "Hình học dự phòng", "map.layer2_decision": "Quyết định AI Layer 2", "map.explanation": "Giải thích", "map.departure": "Khởi hành", "map.type": "Loại", "map.status": "Trạng thái", "map.eta": "ETA",
      "exceptions.delayed": "Lô hàng bị trễ", "exceptions.no_provider": "Không có provider", "exceptions.capacity_shortage": "Thiếu sức chứa", "exceptions.route_unavailable": "Tuyến không khả dụng", "exceptions.weather_warning": "Cảnh báo thời tiết", "exceptions.high_cost": "Cảnh báo chi phí cao", "exceptions.provider_rejected": "Provider từ chối",
      "enterprise.manager": "Quản lý đơn hàng", "enterprise.heading": "Doanh nghiệp nông sản", "enterprise.subtitle": "Tạo đơn và theo dõi hành trình theo thời gian thực", "enterprise.create_order": "Tạo đơn vận chuyển", "enterprise.validation_error": "Lỗi nhập liệu", "enterprise.hub_origin": "Hub xuất phát", "enterprise.commodity": "Nông sản", "enterprise.custom_commodity": "Tên nông sản khác", "enterprise.custom_placeholder": "ví dụ: Cua Cà Mau, Nhãn xuồng...", "enterprise.weight": "Khối lượng (kg)", "enterprise.harvest_time": "Thời điểm thu hoạch", "enterprise.shipment_time": "Thời điểm xuất hàng", "enterprise.delivery_deadline": "Hạn giao hàng", "enterprise.submit": "Tối ưu tuyến", "enterprise.route_heading": "Tuyến đường AI đề xuất", "enterprise.route_description": "Chọn phương án phù hợp và xác nhận để bắt đầu vận chuyển.", "enterprise.ai_recommended": "Gợi ý AI", "enterprise.predicted_cost": "Chi phí dự đoán", "enterprise.preview_map": "Bản đồ xem trước hành trình", "enterprise.tracking_map": "Bản đồ theo dõi hành trình", "enterprise.progress": "Tiến trình di chuyển", "enterprise.shipment_id": "Mã lô hàng", "enterprise.transport_provider": "Đơn vị vận tải", "enterprise.vehicle": "Phương tiện", "enterprise.status": "Trạng thái", "enterprise.route_progress": "Tiến độ hành trình", "enterprise.timeline": "Nhật ký hành trình", "enterprise.back_to_form": "Tạo đơn mới", "enterprise.confirm_route": "Xác nhận tuyến đường", "enterprise.back": "Quay lại",
      "businesses.title": "Doanh nghiệp", "businesses.subtitle": "Quản lý doanh nghiệp và đơn hàng trên nền tảng",
      "businesses.total": "Tổng doanh nghiệp", "businesses.active": "Đang hoạt động", "businesses.pending": "Chờ duyệt", "businesses.suspended": "Tạm dừng",
      "businesses.search": "Tìm theo tên hoặc người liên hệ...", "businesses.all_statuses": "Tất cả trạng thái", "businesses.all_provinces": "Tất cả tỉnh thành",
      "businesses.clear_filters": "Xóa bộ lọc", "businesses.no_match": "Không có doanh nghiệp phù hợp.", "businesses.details": "Chi tiết",
      "businesses.approve": "Duyệt doanh nghiệp", "businesses.suspend": "Tạm dừng", "businesses.reactivate": "Kích hoạt lại", "businesses.export": "Xuất dữ liệu", "businesses.add": "Thêm doanh nghiệp",
      "businesses.company": "Doanh nghiệp", "businesses.contact": "Người liên hệ", "businesses.province": "Tỉnh thành", "businesses.total_orders": "Tổng đơn", "businesses.active_orders": "Đơn đang chạy", "businesses.volume": "Sản lượng", "businesses.spend": "Tổng chi tiêu", "businesses.last_active": "Hoạt động gần nhất", "businesses.actions": "Thao tác",
      "logistics.title": "Đối tác logistics", "logistics.subtitle": "Đội xe, phân công và hiệu suất đối tác", "logistics.total": "Tổng đối tác", "logistics.available": "Sẵn sàng", "logistics.active_deliveries": "Đơn đang giao", "logistics.available_vehicles": "Xe sẵn sàng", "logistics.avg_ontime": "Tỷ lệ đúng hạn TB", "logistics.all_modes": "Tất cả phương thức", "logistics.all_statuses": "Tất cả trạng thái", "logistics.no_match": "Không có đối tác phù hợp.", "logistics.details": "Chi tiết", "logistics.activate": "Kích hoạt", "logistics.deactivate": "Vô hiệu hóa", "logistics.export": "Xuất dữ liệu", "logistics.add": "Thêm đối tác",
      "admin.orders_title": "Đơn hàng", "admin.orders_subtitle": "Theo dõi, phân công và quản lý toàn bộ đơn hàng", "admin.total": "Tổng", "admin.pending": "Chờ xử lý", "admin.unassigned": "Chưa phân công", "admin.in_transit": "Đang vận chuyển", "admin.delivered_today": "Đã giao hôm nay", "admin.all": "Tất cả", "admin.clear_filters": "Xóa bộ lọc", "admin.create_order": "Tạo đơn hàng", "admin.export": "Xuất dữ liệu", "admin.assign_selected": "Phân công đã chọn", "admin.cancel_selected": "Hủy đã chọn", "admin.no_orders_match": "Không có đơn hàng phù hợp.", "admin.view": "Xem", "admin.assign": "Phân công", "admin.route_options": "Các phương án tuyến", "admin.assignment": "Phân công", "admin.timeline": "Dòng thời gian", "admin.order_info": "Thông tin đơn", "admin.reoptimize": "Tối ưu lại",
    },
  },
  en: {
    brand: "DeltaFlow AI",
    language: "Language",
    logout: "Log out",
    login: "Log in",
    email: "Email",
    password: "Password",
    enterprise: "Enterprise",
    logistics: "Logistics provider",
    admin: "Administrator",
    enterpriseSubtitle: "Order management and shipment tracking",
    logisticsSubtitle: "Fleet and transshipment operations",
    adminSubtitle: "Network-wide operations and analytics",
    loginDescription: "Agricultural logistics orchestration for the Mekong Delta.",
    demoAccounts: "Demo accounts",
    loading: "Loading...",
    sections: {
      business_shipment_form: "Create order",
      business_recommendations: "Route analytics",
      business_tracking: "Order tracking",
      logistics_overview: "Overview",
      logistics_orders: "Orders to accept",
      logistics_fleet: "Fleet",
      logistics_jobs: "Transport jobs",
      logistics_deliveries: "Delivery history",
      admin_inventory: "Overview",
      admin_weather: "Weather",
      admin_dispatch: "Dispatch",
      admin_simulation: "Simulation",
      admin_logs: "System analytics",
      admin_orders: "Orders",
      admin_operations: "Operations",
      admin_logistics: "Logistics partners",
      businesses: "Businesses",
    },
    sectionDescriptions: {
      business_shipment_form: "Create and submit an agricultural shipment request.",
      business_recommendations: "Compare route options recommended by Layer 1.",
      business_tracking: "Track order status, vehicle and shipment progress.",
      logistics_overview: "Monitor fleet, transport jobs and transshipment flows.",
      logistics_orders: "Accept orders, select vehicles and consolidate at Can Tho.",
      logistics_fleet: "Track capacity and forecast vehicle demand by date.",
      logistics_jobs: "Review accepted and active transport jobs.",
      logistics_deliveries: "Delivery history and completion status.",
      admin_inventory: "Network health, KPIs and live shipment flows.",
      admin_weather: "Monitor weather and water conditions across hubs.",
      admin_dispatch: "Review consolidation and dispatch decisions.",
      admin_simulation: "Adjust simulation data for operational demonstrations.",
      admin_logs: "Analyze route performance and system event history.",
      admin_orders: "Track all orders and their logistics providers.",
      admin_operations: "Run dispatch, capacity, exception and Layer 2 forecast operations.",
      admin_logistics: "Evaluate logistics partner capacity and performance.",
    },
    messages: {
      "common.all": "All", "common.cancel": "Cancel", "common.close": "Close", "common.confirm": "Confirm",
      "common.save": "Save", "common.refresh": "Refresh", "common.search": "Search", "common.filter": "Filter",
      "common.loading": "Loading...", "common.no_data": "No data available", "common.no_results": "No results found",
      "common.unknown": "Unknown", "common.not_available": "Not available", "common.live": "Live",
      "common.view_details": "View details", "common.back": "Back", "common.next": "Next", "common.previous": "Previous",
      "common.date": "Date", "common.status": "Status", "common.actions": "Actions", "common.route": "Route",
      "common.mode": "Mode", "common.vehicle": "Vehicle", "common.orders": "Orders", "common.weight": "Weight",
      "common.capacity": "Capacity", "common.cost": "Cost", "common.time": "Time", "common.eta": "ETA",
      "common.provider": "Provider", "common.hub": "Hub", "common.source": "Data source",
      "common.overview": "Overview", "common.fleet": "Fleet", "common.performance": "Performance", "common.multimodal": "Multimodal", "common.edit": "Edit", "common.reset": "Reset", "common.view_by_role": "View by role", "common.origin": "Origin", "common.destination": "Destination", "common.created": "Created", "common.deadline": "Deadline", "common.progress": "Progress", "common.shipment": "Shipment", "common.business": "Business", "common.commodity": "Commodity", "common.type": "Type", "common.reason": "Reason", "common.priority": "Priority", "common.suggested_provider": "Suggested provider", "common.recommended_route": "Recommended route", "common.assign": "Assign", "common.approve": "Approve", "common.track": "Track", "common.resolve": "Resolve", "common.reassign": "Reassign", "common.contact_business": "Contact business", "common.show_resolved": "Show resolved exceptions", "common.shown": "shown", "common.total": "Total", "common.on_track": "On track", "common.at_hub": "At hub", "common.delayed": "Delayed", "common.critical": "Critical", "common.warnings": "Warnings", "common.resolved": "Resolved", "common.assigning": "Assigning...", "common.auto_assign_all": "Auto-assign all", "common.items_pending": "items pending",
      "auth.invalid_credentials": "The email or password is incorrect.", "auth.login_failed": "Login failed.",
      "auth.demo_accounts": "Demo accounts", "auth.email": "Email", "auth.password": "Password",
      "fleet.available": "Available", "fleet.in_transit": "In transit", "fleet.maintenance": "Maintenance",
      "fleet.en_route": "En route", "fleet.vehicle_truck": "Truck", "fleet.vehicle_vessel": "Vessel",
      "fleet.forecast_date": "Forecast date", "fleet.demand": "Forecast demand", "fleet.vehicles_needed": "Vehicles needed",
      "fleet.available_vehicles": "Available vehicles", "fleet.available_capacity": "Available capacity",
      "fleet.enough": "Enough vehicles", "fleet.shortage": "Short by {value} tons", "fleet.confidence": "Confidence",
      "orders.awaiting_assignment": "Awaiting assignment", "orders.arrived_waiting": "Waiting for consolidation",
      "orders.dispatched": "Dispatched", "orders.completed": "Completed", "orders.cancelled": "Cancelled",
      "orders.created": "Created", "orders.routed_to_can_tho": "Moving to Can Tho",
      "orders.provider_accepted": "Accepted by provider", "orders.provider_rejected": "Rejected by provider",
      "map.available": "Available", "map.unavailable": "Unavailable", "map.in_delivery": "In delivery",
      "map.arrived_at_hub": "Arrived at hub", "map.waiting_jobs": "Waiting jobs", "map.active_routes": "Active routes",
      "map.waiting_consolidation": "Waiting for consolidation at Can Tho", "map.unassigned": "Unassigned",
      "forecast.live": "Live forecast", "forecast.unavailable": "Forecast unavailable",
      "forecast.dispatch_now": "Ready to dispatch", "forecast.wait_for_load": "Waiting for load",
      "forecast.wait_for_vehicle": "Waiting for vehicle", "forecast.no_decision": "No decision",
      "errors.generic": "Something went wrong. Please try again.", "errors.network": "Unable to connect to the server.",
      "errors.order_not_found": "Order not found.", "errors.vehicle_capacity": "Vehicle capacity is insufficient.",
      "errors.vehicle_unavailable": "The vehicle is not currently available.", "errors.unauthorized": "You are not authorized to perform this action.",
      "errors.invalid_date": "Invalid date.", "errors.required": "This field is required.",
      "admin.platform_management": "Platform management", "admin.last_updated": "Last updated",
      "admin.platform_kpis": "Platform KPIs", "admin.live_metrics": "Live operations metrics",
      "admin.cost_savings": "Savings from live orders", "admin.orders_processed": "Orders processed",
      "admin.operations_description": "Run dispatch, capacity, exception and Layer 2 forecast operations.",
      "admin.dispatch_queue": "Dispatch queue", "admin.active_shipments": "Active shipments",
      "admin.exceptions": "Exceptions", "admin.capacity": "Capacity", "admin.no_exceptions": "No exceptions require attention.",
      "admin.road_outbound": "Road outbound", "admin.water_outbound": "Waterway outbound",
      "admin.pending_business_approvals": "Pending business approvals", "admin.unassigned_orders": "Unassigned orders",
      "admin.delayed_shipments": "Delayed shipments", "admin.capacity_alerts": "Capacity alerts",
      "admin.review_applications": "Review applications", "admin.assign_orders": "Assign orders", "admin.view_delays": "View delays",
      "admin.review_capacity": "Review capacity", "admin.recent_activity": "Recent activity", "admin.view_all_activity": "View all activity",
      "admin.show_less": "Show less", "admin.time": "Time", "admin.activity": "Activity", "admin.actor": "Actor",
      "route.optimize": "Optimize route", "route.ai_recommendation": "AI recommended route", "route.priority": "Priority",
      "route.weather_timestamp": "Weather timestamp", "route.price_timestamp": "Price timestamp", "route.recommended": "Recommended",
      "route.unavailable": "Route unavailable.", "fleet.search": "Search license plate...",
      "jobs.waiting_for_pickup": "Waiting for pickup", "jobs.moving_to_can_tho": "Moving to Can Tho",
      "jobs.consolidating_at_can_tho": "Consolidating at Can Tho", "jobs.dispatching_to_hcm": "Moving to Ho Chi Minh City",
      "jobs.completed": "Delivery completed", "jobs.title": "Transport jobs", "jobs.description": "Transport jobs and shipment details.",
      "jobs.no_jobs": "No transport jobs yet.", "jobs.details": "Details", "jobs.collapse": "Collapse",
      "orders.accept": "Accept order", "orders.dispatch": "Dispatch", "orders.select_vehicle": "Select compatible vehicle",
      "orders.open": "Open", "orders.accepted": "Accepted", "orders.no_queue": "No orders waiting for acceptance.",
      "orders.accept_failed": "Unable to accept the order.", "orders.dispatch_failed": "Unable to dispatch the orders.", "orders.waiting_title": "Orders waiting for acceptance", "orders.waiting_description": "Select a compatible vehicle, accept orders, then consolidate multiple orders before dispatch.", "orders.accepted_summary": "{count} orders accepted. Orders using the same vehicle and mode can be consolidated.", "orders.select_dispatch_vehicle": "Select dispatch vehicle", "orders.held_for_vehicle": "Order held for vehicle {vehicle}. Select orders above to consolidate and dispatch.", "orders.no_waiting": "No orders waiting for acceptance.", "orders.selected_vehicle": "Selected vehicle", "orders.provider_assigned_success": "Provider assigned successfully.", "orders.select_provider": "Select provider", "orders.change_assignment": "Change assignment", "orders.reoptimization_queued": "Re-optimization request queued.",
      "route.transfers": "Transfer points", "route.accept_recommendation": "Accept recommendation", "route.select_route": "Select this route",
      "admin.overview_title": "Admin overview", "admin.new_applications_waiting": "new applications waiting", "admin.orders_without_provider": "orders without a provider", "admin.shipments_past_eta": "shipments past ETA", "admin.capacity_warnings": "capacity warnings", "admin.total_businesses": "Total businesses", "admin.active_logistics_partners": "Active logistics partners", "admin.delayed_orders": "Delayed orders", "admin.ontime_rate": "On-time rate", "admin.operations_title": "Operations", "admin.due_today": "Due today", "admin.search_orders": "Search order ID or business...", "admin.all_commodities": "All commodities",
      "businesses.overview": "Overview", "businesses.performance": "Performance", "businesses.activity": "Activity", "businesses.address": "Address", "businesses.registered": "Registered", "businesses.ton": "tons", "businesses.no_orders": "No orders from this business yet.", "businesses.commodity": "Commodity", "businesses.created": "Created", "businesses.no_performance": "No performance data — no orders placed yet.", "businesses.activity_hint": "Recent business activity is shown in the Overview → Recent Activity feed.", "businesses.view_orders": "View orders", "businesses.confirm_suspend": "Confirm suspend",
      "logistics.modes": "Transport modes", "logistics.fleet_size": "Fleet size", "logistics.no_orders": "No orders assigned to this provider.", "logistics.fleet_utilization": "Fleet utilization", "logistics.ontime": "On-time delivery rate", "logistics.utilization": "Utilization", "logistics.active_orders": "Active orders", "logistics.avg_capacity": "Average capacity per order", "logistics.vehicle_id": "Vehicle ID", "logistics.edit_capacity": "Edit capacity", "logistics.contact": "Contact", "logistics.activated": "Activated", "logistics.deactivated": "Deactivated", "logistics.busy": "Busy", "logistics.inactive": "Inactive",
      "events.route_optimized": "Route optimized", "events.provider_assigned": "Provider assigned", "events.picked_up": "Picked up", "events.arrived_at_hub": "Arrived at hub", "events.departed_from_hub": "Departed from hub", "events.expected_pickup": "Expected pickup", "events.estimated_delivery": "Estimated delivery", "events.order_created": "Order created", "events.awaiting_assignment": "Awaiting assignment",
      "map.route_selector": "Route selector", "map.fallback_geometry": "Fallback geometry", "map.layer2_decision": "AI Layer 2 decision", "map.explanation": "Explanation", "map.departure": "Departure", "map.type": "Type", "map.status": "Status", "map.eta": "ETA",
      "exceptions.delayed": "Delayed shipment", "exceptions.no_provider": "No provider available", "exceptions.capacity_shortage": "Capacity shortage", "exceptions.route_unavailable": "Route unavailable", "exceptions.weather_warning": "Weather warning", "exceptions.high_cost": "High cost alert", "exceptions.provider_rejected": "Provider rejected",
      "enterprise.manager": "Order manager", "enterprise.heading": "Agricultural enterprise", "enterprise.subtitle": "Create orders and track shipments in real time", "enterprise.create_order": "Create shipment order", "enterprise.validation_error": "Validation error", "enterprise.hub_origin": "Origin hub", "enterprise.commodity": "Commodity", "enterprise.custom_commodity": "Other commodity name", "enterprise.custom_placeholder": "e.g. Ca Mau crab, longan...", "enterprise.weight": "Weight (kg)", "enterprise.harvest_time": "Harvest time", "enterprise.shipment_time": "Shipment time", "enterprise.delivery_deadline": "Delivery deadline", "enterprise.submit": "Optimize route", "enterprise.route_heading": "AI recommended routes", "enterprise.route_description": "Choose an option and confirm to start transportation.", "enterprise.ai_recommended": "AI recommendation", "enterprise.predicted_cost": "Predicted cost", "enterprise.preview_map": "Route preview map", "enterprise.tracking_map": "Shipment tracking map", "enterprise.progress": "Shipment progress", "enterprise.shipment_id": "Shipment ID", "enterprise.transport_provider": "Transport provider", "enterprise.vehicle": "Vehicle", "enterprise.status": "Status", "enterprise.route_progress": "Route progress", "enterprise.timeline": "Shipment timeline", "enterprise.back_to_form": "Create new order", "enterprise.confirm_route": "Confirm route", "enterprise.back": "Back",
      "businesses.title": "Businesses", "businesses.subtitle": "Manage platform businesses and their orders",
      "businesses.total": "Total businesses", "businesses.active": "Active", "businesses.pending": "Pending approval", "businesses.suspended": "Suspended",
      "businesses.search": "Search by name or contact...", "businesses.all_statuses": "All statuses", "businesses.all_provinces": "All provinces",
      "businesses.clear_filters": "Clear filters", "businesses.no_match": "No businesses match the selected filters.", "businesses.details": "Details",
      "businesses.approve": "Approve business", "businesses.suspend": "Suspend", "businesses.reactivate": "Reactivate", "businesses.export": "Export", "businesses.add": "Add business",
      "businesses.company": "Company", "businesses.contact": "Contact", "businesses.province": "Province", "businesses.total_orders": "Total orders", "businesses.active_orders": "Active orders", "businesses.volume": "Volume", "businesses.spend": "Total spend", "businesses.last_active": "Last active", "businesses.actions": "Actions",
      "logistics.title": "Logistics partners", "logistics.subtitle": "Fleet, assignments and partner performance", "logistics.total": "Total partners", "logistics.available": "Available", "logistics.active_deliveries": "Active deliveries", "logistics.available_vehicles": "Available vehicles", "logistics.avg_ontime": "Average on-time rate", "logistics.all_modes": "All modes", "logistics.all_statuses": "All statuses", "logistics.no_match": "No logistics partners match the selected filters.", "logistics.details": "Details", "logistics.activate": "Activate", "logistics.deactivate": "Deactivate", "logistics.export": "Export", "logistics.add": "Add partner",
      "admin.orders_title": "Orders", "admin.orders_subtitle": "Track, assign and manage all platform orders", "admin.total": "Total", "admin.pending": "Pending", "admin.unassigned": "Unassigned", "admin.in_transit": "In transit", "admin.delivered_today": "Delivered today", "admin.all": "All", "admin.clear_filters": "Clear filters", "admin.create_order": "Create order", "admin.export": "Export", "admin.assign_selected": "Assign selected", "admin.cancel_selected": "Cancel selected", "admin.no_orders_match": "No orders match the selected filters.", "admin.view": "View", "admin.assign": "Assign", "admin.route_options": "Route options", "admin.assignment": "Assignment", "admin.timeline": "Timeline", "admin.order_info": "Order info", "admin.reoptimize": "Re-optimize",
    },
  },
};

type LanguageContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  dictionary: Dictionary;
  sectionLabel: (section: string, fallback?: string) => string;
  sectionDescription: (section: string, fallback?: string) => string;
  t: (key: string, fallback?: string, params?: Record<string, string | number>) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguage] = useState<Language>("vi");

  useEffect(() => {
    const stored = window.localStorage.getItem("vaic-language");
    if (stored === "vi" || stored === "en") setLanguage(stored);
  }, []);

  useEffect(() => {
    window.localStorage.setItem("vaic-language", language);
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => ({
    language,
    setLanguage,
    dictionary: dictionaries[language],
    sectionLabel: (section, fallback) => dictionaries[language].sections[section] || fallback || section,
    sectionDescription: (section, fallback) => dictionaries[language].sectionDescriptions[section] || fallback || "",
    t: (key, fallback, params) => {
      const template = dictionaries[language].messages[key] || fallback || key.split(".").at(-1)?.replaceAll("_", " ") || key;
      return Object.entries(params || {}).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), template);
    },
  }), [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage must be used inside LanguageProvider");
  return context;
}
