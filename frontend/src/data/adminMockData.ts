// Shared mock data for all Admin pages.
// Keep IDs consistent – pages cross-reference businesses, providers, and orders.

export type BusinessStatus = "active" | "pending" | "suspended";
export type ProviderStatus = "available" | "busy" | "inactive";
export type TransportMode = "road" | "waterway" | "multimodal";
export type OrderStatus =
  | "pending"
  | "optimizing"
  | "awaiting_assignment"
  | "assigned"
  | "in_transit"
  | "delivered"
  | "delayed"
  | "cancelled";
export type VehicleStatus = "available" | "en_route" | "maintenance";
export type VehicleType = "truck" | "barge";
export type ExceptionType =
  | "delayed"
  | "no_provider"
  | "capacity_shortage"
  | "route_unavailable"
  | "weather_warning"
  | "high_cost"
  | "provider_rejected";
export type DispatchDecision = "dispatch_now" | "wait_for_load" | "wait_for_vehicle";

export interface Business {
  id: string;
  name: string;
  contact: string;
  email: string;
  phone: string;
  province: string;
  address: string;
  total_orders: number;
  active_orders: number;
  total_volume_ton: number;
  total_spend_vnd: number;
  last_active: string;
  status: BusinessStatus;
  registered_at: string;
  avg_cost_vnd: number;
  avg_delivery_hours: number;
  ontime_rate: number;
  savings_vnd: number;
}

export interface Vehicle {
  id: string;
  type: VehicleType;
  capacity_ton: number;
  status: VehicleStatus;
  current_order: string | null;
}

export interface LogisticsProvider {
  id: string;
  name: string;
  modes: TransportMode[];
  fleet_size: number;
  available_vehicles: number;
  active_orders: number;
  available_capacity_ton: number;
  ontime_rate: number;
  utilization: number;
  status: ProviderStatus;
  province: string;
  contact: string;
  email: string;
  fleet: Vehicle[];
}

export interface RouteOption {
  code: string;
  name: string;
  cost_vnd: number;
  duration_hours: number;
  modes: string[];
  transfers: number;
  risk: "low" | "medium" | "high";
  available: boolean;
  recommended: boolean;
}

export interface TimelineEvent {
  time: string;
  event: string;
  done: boolean;
}

export interface Order {
  id: string;
  business_id: string;
  business_name: string;
  commodity: string;
  origin: string;
  destination: string;
  weight_ton: number;
  deadline: string;
  recommended_route: string | null;
  provider_id: string | null;
  provider_name: string | null;
  estimated_cost_vnd: number;
  status: OrderStatus;
  created_at: string;
  route_options: RouteOption[];
  timeline: TimelineEvent[];
}

export interface DispatchItem {
  priority: "high" | "medium" | "low";
  order_id: string;
  business_name: string;
  commodity: string;
  deadline: string;
  recommended_route: string;
  capacity_ton: number;
  suggested_provider: string;
  reason: string;
}

export interface Shipment {
  id: string;
  order_id: string;
  business_name: string;
  commodity: string;
  provider_name: string;
  route: string;
  origin: string;
  destination: string;
  departed: string;
  eta: string;
  status: "on_track" | "delayed" | "at_hub";
  progress: number;
}

export interface Exception {
  id: string;
  type: ExceptionType;
  order_id: string;
  business_name: string;
  description: string;
  severity: "critical" | "warning" | "info";
  created_at: string;
  resolved: boolean;
}

export interface ActivityItem {
  time: string;
  activity: string;
  actor: string;
  status: "success" | "warning" | "info";
}

// ─── Businesses ────────────────────────────────────────────────────────────────

export const BUSINESSES: Business[] = [
  {
    id: "BIZ001",
    name: "Cửu Long Rice Co.",
    contact: "Nguyễn Văn Hùng",
    email: "hung@cuulongrice.vn",
    phone: "0292 123 456",
    province: "Cần Thơ",
    address: "Khu CN Trà Nóc, Ô Môn, Cần Thơ",
    total_orders: 48,
    active_orders: 5,
    total_volume_ton: 1240,
    total_spend_vnd: 3_840_000_000,
    last_active: "2026-07-17",
    status: "active",
    registered_at: "2024-02-10",
    avg_cost_vnd: 80_000_000,
    avg_delivery_hours: 14.2,
    ontime_rate: 91,
    savings_vnd: 420_000_000,
  },
  {
    id: "BIZ002",
    name: "Tiền Giang Fruit Farm",
    contact: "Trần Thị Lan",
    email: "lan@tgfarm.vn",
    phone: "0273 234 567",
    province: "Tiền Giang",
    address: "QL1A, Cai Lậy, Tiền Giang",
    total_orders: 32,
    active_orders: 3,
    total_volume_ton: 680,
    total_spend_vnd: 2_150_000_000,
    last_active: "2026-07-17",
    status: "active",
    registered_at: "2024-04-15",
    avg_cost_vnd: 67_000_000,
    avg_delivery_hours: 12.8,
    ontime_rate: 88,
    savings_vnd: 280_000_000,
  },
  {
    id: "BIZ003",
    name: "Đồng Tháp Seafood Ltd",
    contact: "Lê Minh Tuấn",
    email: "tuan@dtseafood.vn",
    phone: "0277 345 678",
    province: "Đồng Tháp",
    address: "Khu CN Sa Đéc, Đồng Tháp",
    total_orders: 27,
    active_orders: 4,
    total_volume_ton: 540,
    total_spend_vnd: 2_560_000_000,
    last_active: "2026-07-16",
    status: "active",
    registered_at: "2024-06-01",
    avg_cost_vnd: 94_000_000,
    avg_delivery_hours: 16.5,
    ontime_rate: 85,
    savings_vnd: 310_000_000,
  },
  {
    id: "BIZ004",
    name: "An Giang Organic Farm",
    contact: "Phạm Thị Hoa",
    email: "hoa@agorganic.vn",
    phone: "0296 456 789",
    province: "An Giang",
    address: "Châu Phú, An Giang",
    total_orders: 19,
    active_orders: 2,
    total_volume_ton: 320,
    total_spend_vnd: 1_240_000_000,
    last_active: "2026-07-15",
    status: "active",
    registered_at: "2024-08-20",
    avg_cost_vnd: 65_000_000,
    avg_delivery_hours: 18.0,
    ontime_rate: 79,
    savings_vnd: 140_000_000,
  },
  {
    id: "BIZ005",
    name: "Kiên Giang Export Co.",
    contact: "Vũ Hoàng Nam",
    email: "nam@kgexport.vn",
    phone: "0297 567 890",
    province: "Kiên Giang",
    address: "Rạch Giá, Kiên Giang",
    total_orders: 0,
    active_orders: 0,
    total_volume_ton: 0,
    total_spend_vnd: 0,
    last_active: "—",
    status: "pending",
    registered_at: "2026-07-10",
    avg_cost_vnd: 0,
    avg_delivery_hours: 0,
    ontime_rate: 0,
    savings_vnd: 0,
  },
  {
    id: "BIZ006",
    name: "Vĩnh Long Agri Coop",
    contact: "Đỗ Thị Mai",
    email: "mai@vlagricopp.vn",
    phone: "0270 678 901",
    province: "Vĩnh Long",
    address: "Long Hồ, Vĩnh Long",
    total_orders: 14,
    active_orders: 1,
    total_volume_ton: 280,
    total_spend_vnd: 890_000_000,
    last_active: "2026-07-14",
    status: "active",
    registered_at: "2025-01-05",
    avg_cost_vnd: 63_000_000,
    avg_delivery_hours: 13.5,
    ontime_rate: 93,
    savings_vnd: 95_000_000,
  },
  {
    id: "BIZ007",
    name: "Sóc Trăng Veg Co.",
    contact: "Hoàng Minh Đức",
    email: "duc@stveg.vn",
    phone: "0299 789 012",
    province: "Sóc Trăng",
    address: "Mỹ Xuyên, Sóc Trăng",
    total_orders: 0,
    active_orders: 0,
    total_volume_ton: 0,
    total_spend_vnd: 0,
    last_active: "—",
    status: "pending",
    registered_at: "2026-07-12",
    avg_cost_vnd: 0,
    avg_delivery_hours: 0,
    ontime_rate: 0,
    savings_vnd: 0,
  },
  {
    id: "BIZ008",
    name: "Bến Tre Coconut Ltd",
    contact: "Ngô Thị Thu",
    email: "thu@btcoconut.vn",
    phone: "0275 890 123",
    province: "Bến Tre",
    address: "Châu Thành, Bến Tre",
    total_orders: 8,
    active_orders: 0,
    total_volume_ton: 160,
    total_spend_vnd: 420_000_000,
    last_active: "2026-05-20",
    status: "suspended",
    registered_at: "2024-11-15",
    avg_cost_vnd: 52_000_000,
    avg_delivery_hours: 15.0,
    ontime_rate: 62,
    savings_vnd: 30_000_000,
  },
];

// ─── Logistics Providers ───────────────────────────────────────────────────────

export const PROVIDERS: LogisticsProvider[] = [
  {
    id: "LP001",
    name: "Mekong Logistics",
    modes: ["road", "waterway"],
    fleet_size: 24,
    available_vehicles: 9,
    active_orders: 7,
    available_capacity_ton: 320,
    ontime_rate: 92,
    utilization: 63,
    status: "available",
    province: "Cần Thơ",
    contact: "Nguyễn Thanh Sơn",
    email: "son@mekonglogistics.vn",
    fleet: [
      { id: "ML-T01", type: "truck", capacity_ton: 15, status: "en_route", current_order: "ORD007" },
      { id: "ML-T02", type: "truck", capacity_ton: 15, status: "available", current_order: null },
      { id: "ML-T03", type: "truck", capacity_ton: 20, status: "available", current_order: null },
      { id: "ML-T04", type: "truck", capacity_ton: 10, status: "maintenance", current_order: null },
      { id: "ML-B01", type: "barge", capacity_ton: 80, status: "en_route", current_order: "ORD011" },
      { id: "ML-B02", type: "barge", capacity_ton: 80, status: "available", current_order: null },
    ],
  },
  {
    id: "LP002",
    name: "Cần Thơ Trans",
    modes: ["road"],
    fleet_size: 18,
    available_vehicles: 12,
    active_orders: 4,
    available_capacity_ton: 180,
    ontime_rate: 88,
    utilization: 44,
    status: "available",
    province: "Cần Thơ",
    contact: "Trần Quốc Việt",
    email: "viet@canthotrans.vn",
    fleet: [
      { id: "CT-T01", type: "truck", capacity_ton: 15, status: "en_route", current_order: "ORD003" },
      { id: "CT-T02", type: "truck", capacity_ton: 15, status: "available", current_order: null },
      { id: "CT-T03", type: "truck", capacity_ton: 15, status: "available", current_order: null },
      { id: "CT-T04", type: "truck", capacity_ton: 20, status: "available", current_order: null },
    ],
  },
  {
    id: "LP003",
    name: "Delta Waterway",
    modes: ["waterway"],
    fleet_size: 10,
    available_vehicles: 2,
    active_orders: 6,
    available_capacity_ton: 160,
    ontime_rate: 79,
    utilization: 80,
    status: "busy",
    province: "Cần Thơ",
    contact: "Lý Thị Hằng",
    email: "hang@deltawaterway.vn",
    fleet: [
      { id: "DW-B01", type: "barge", capacity_ton: 100, status: "en_route", current_order: "ORD005" },
      { id: "DW-B02", type: "barge", capacity_ton: 100, status: "en_route", current_order: "ORD009" },
      { id: "DW-B03", type: "barge", capacity_ton: 80, status: "available", current_order: null },
      { id: "DW-B04", type: "barge", capacity_ton: 80, status: "maintenance", current_order: null },
    ],
  },
  {
    id: "LP004",
    name: "Southern Freight",
    modes: ["road", "multimodal"],
    fleet_size: 30,
    available_vehicles: 18,
    active_orders: 5,
    available_capacity_ton: 540,
    ontime_rate: 95,
    utilization: 40,
    status: "available",
    province: "TP. Hồ Chí Minh",
    contact: "Bùi Văn Khoa",
    email: "khoa@southernfreight.vn",
    fleet: [
      { id: "SF-T01", type: "truck", capacity_ton: 25, status: "en_route", current_order: "ORD015" },
      { id: "SF-T02", type: "truck", capacity_ton: 25, status: "available", current_order: null },
      { id: "SF-T03", type: "truck", capacity_ton: 15, status: "available", current_order: null },
      { id: "SF-T04", type: "truck", capacity_ton: 20, status: "available", current_order: null },
      { id: "SF-T05", type: "truck", capacity_ton: 20, status: "maintenance", current_order: null },
    ],
  },
  {
    id: "LP005",
    name: "An Giang Transport",
    modes: ["road"],
    fleet_size: 12,
    available_vehicles: 3,
    active_orders: 5,
    available_capacity_ton: 75,
    ontime_rate: 82,
    utilization: 75,
    status: "busy",
    province: "An Giang",
    contact: "Đinh Văn Long",
    email: "long@agtransport.vn",
    fleet: [
      { id: "AG-T01", type: "truck", capacity_ton: 15, status: "en_route", current_order: "ORD018" },
      { id: "AG-T02", type: "truck", capacity_ton: 15, status: "en_route", current_order: "ORD020" },
      { id: "AG-T03", type: "truck", capacity_ton: 10, status: "available", current_order: null },
    ],
  },
];

// ─── Route Options (5 fixed VAIC routes) ──────────────────────────────────────

function buildRouteOptions(baseMultiplier = 1): RouteOption[] {
  return [
    {
      code: "A_DIRECT_ROAD",
      name: "Direct Road to HCM",
      cost_vnd: Math.round(75_000_000 * baseMultiplier),
      duration_hours: 8,
      modes: ["Road"],
      transfers: 0,
      risk: "low",
      available: true,
      recommended: false,
    },
    {
      code: "B_ROAD_VIA_CT",
      name: "Road via Can Tho Hub",
      cost_vnd: Math.round(68_000_000 * baseMultiplier),
      duration_hours: 10,
      modes: ["Road"],
      transfers: 1,
      risk: "low",
      available: true,
      recommended: false,
    },
    {
      code: "C_WATER_ROAD_VIA_CT",
      name: "Water to Can Tho, then Road",
      cost_vnd: Math.round(55_000_000 * baseMultiplier),
      duration_hours: 14,
      modes: ["Waterway", "Road"],
      transfers: 1,
      risk: "medium",
      available: true,
      recommended: true,
    },
    {
      code: "D_WATER_VIA_CT",
      name: "Full Waterway via Can Tho",
      cost_vnd: Math.round(48_000_000 * baseMultiplier),
      duration_hours: 20,
      modes: ["Waterway"],
      transfers: 1,
      risk: "medium",
      available: true,
      recommended: false,
    },
    {
      code: "E_ROAD_WATER_VIA_CT",
      name: "Road to Can Tho, then Water",
      cost_vnd: Math.round(52_000_000 * baseMultiplier),
      duration_hours: 18,
      modes: ["Road", "Waterway"],
      transfers: 1,
      risk: "medium",
      available: true,
      recommended: false,
    },
  ];
}

// ─── Orders ────────────────────────────────────────────────────────────────────

export const ORDERS: Order[] = [
  {
    id: "ORD001",
    business_id: "BIZ001",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    weight_ton: 25,
    deadline: "2026-07-20",
    recommended_route: "C_WATER_ROAD_VIA_CT",
    provider_id: "LP001",
    provider_name: "Mekong Logistics",
    estimated_cost_vnd: 55_000_000,
    status: "in_transit",
    created_at: "2026-07-15",
    route_options: buildRouteOptions(1.0),
    timeline: [
      { time: "2026-07-15 08:00", event: "Order created", done: true },
      { time: "2026-07-15 08:05", event: "Route optimized by AI1", done: true },
      { time: "2026-07-15 10:30", event: "Provider assigned: Mekong Logistics", done: true },
      { time: "2026-07-16 07:00", event: "Picked up at Cần Thơ", done: true },
      { time: "2026-07-16 14:00", event: "Arrived at Can Tho Hub", done: true },
      { time: "2026-07-17 06:00", event: "Departed from hub", done: false },
      { time: "2026-07-20 10:00", event: "Estimated delivery at TP. HCM", done: false },
    ],
  },
  {
    id: "ORD002",
    business_id: "BIZ002",
    business_name: "Tiền Giang Fruit Farm",
    commodity: "Mango",
    origin: "Tiền Giang",
    destination: "TP. HCM",
    weight_ton: 12,
    deadline: "2026-07-19",
    recommended_route: "A_DIRECT_ROAD",
    provider_id: "LP004",
    provider_name: "Southern Freight",
    estimated_cost_vnd: 75_000_000,
    status: "assigned",
    created_at: "2026-07-16",
    route_options: buildRouteOptions(0.8),
    timeline: [
      { time: "2026-07-16 09:00", event: "Order created", done: true },
      { time: "2026-07-16 09:05", event: "Route optimized by AI1", done: true },
      { time: "2026-07-16 14:00", event: "Provider assigned: Southern Freight", done: true },
      { time: "2026-07-18 08:00", event: "Expected pickup", done: false },
      { time: "2026-07-19 16:00", event: "Estimated delivery", done: false },
    ],
  },
  {
    id: "ORD003",
    business_id: "BIZ003",
    business_name: "Đồng Tháp Seafood Ltd",
    commodity: "Seafood",
    origin: "Đồng Tháp",
    destination: "TP. HCM",
    weight_ton: 8,
    deadline: "2026-07-18",
    recommended_route: "B_ROAD_VIA_CT",
    provider_id: "LP002",
    provider_name: "Cần Thơ Trans",
    estimated_cost_vnd: 68_000_000,
    status: "delayed",
    created_at: "2026-07-14",
    route_options: buildRouteOptions(1.1),
    timeline: [
      { time: "2026-07-14 07:00", event: "Order created", done: true },
      { time: "2026-07-14 07:05", event: "Route optimized by AI1", done: true },
      { time: "2026-07-14 11:00", event: "Provider assigned: Cần Thơ Trans", done: true },
      { time: "2026-07-15 06:00", event: "Picked up at Đồng Tháp", done: true },
      { time: "2026-07-16 00:00", event: "Arrived at Can Tho Hub", done: true },
      { time: "2026-07-17 06:00", event: "Departed hub — DELAYED", done: false },
      { time: "2026-07-18 18:00", event: "Estimated delivery (revised)", done: false },
    ],
  },
  {
    id: "ORD004",
    business_id: "BIZ001",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    weight_ton: 40,
    deadline: "2026-07-25",
    recommended_route: "D_WATER_VIA_CT",
    provider_id: null,
    provider_name: null,
    estimated_cost_vnd: 48_000_000,
    status: "awaiting_assignment",
    created_at: "2026-07-17",
    route_options: buildRouteOptions(1.3),
    timeline: [
      { time: "2026-07-17 10:00", event: "Order created", done: true },
      { time: "2026-07-17 10:05", event: "Route optimized by AI1", done: true },
      { time: "—", event: "Awaiting provider assignment", done: false },
    ],
  },
  {
    id: "ORD005",
    business_id: "BIZ003",
    business_name: "Đồng Tháp Seafood Ltd",
    commodity: "Seafood",
    origin: "Đồng Tháp",
    destination: "TP. HCM",
    weight_ton: 15,
    deadline: "2026-07-22",
    recommended_route: "D_WATER_VIA_CT",
    provider_id: "LP003",
    provider_name: "Delta Waterway",
    estimated_cost_vnd: 48_000_000,
    status: "in_transit",
    created_at: "2026-07-16",
    route_options: buildRouteOptions(1.0),
    timeline: [
      { time: "2026-07-16 11:00", event: "Order created", done: true },
      { time: "2026-07-16 11:06", event: "Route optimized by AI1", done: true },
      { time: "2026-07-16 15:00", event: "Provider assigned: Delta Waterway", done: true },
      { time: "2026-07-17 05:30", event: "Departed by barge", done: true },
      { time: "2026-07-22 14:00", event: "Estimated arrival at TP. HCM port", done: false },
    ],
  },
  {
    id: "ORD006",
    business_id: "BIZ004",
    business_name: "An Giang Organic Farm",
    commodity: "Vegetables",
    origin: "An Giang",
    destination: "TP. HCM",
    weight_ton: 6,
    deadline: "2026-07-19",
    recommended_route: "C_WATER_ROAD_VIA_CT",
    provider_id: null,
    provider_name: null,
    estimated_cost_vnd: 55_000_000,
    status: "awaiting_assignment",
    created_at: "2026-07-17",
    route_options: buildRouteOptions(0.7),
    timeline: [
      { time: "2026-07-17 14:00", event: "Order created", done: true },
      { time: "2026-07-17 14:06", event: "Route optimized by AI1", done: true },
      { time: "—", event: "Awaiting provider assignment", done: false },
    ],
  },
  {
    id: "ORD007",
    business_id: "BIZ006",
    business_name: "Vĩnh Long Agri Coop",
    commodity: "Dragon Fruit",
    origin: "Vĩnh Long",
    destination: "TP. HCM",
    weight_ton: 10,
    deadline: "2026-07-20",
    recommended_route: "A_DIRECT_ROAD",
    provider_id: "LP001",
    provider_name: "Mekong Logistics",
    estimated_cost_vnd: 75_000_000,
    status: "in_transit",
    created_at: "2026-07-16",
    route_options: buildRouteOptions(0.9),
    timeline: [
      { time: "2026-07-16 08:00", event: "Order created", done: true },
      { time: "2026-07-16 08:05", event: "Route optimized by AI1", done: true },
      { time: "2026-07-16 12:00", event: "Provider assigned: Mekong Logistics", done: true },
      { time: "2026-07-17 07:00", event: "Picked up at Vĩnh Long", done: true },
      { time: "2026-07-20 16:00", event: "Estimated delivery", done: false },
    ],
  },
  {
    id: "ORD008",
    business_id: "BIZ002",
    business_name: "Tiền Giang Fruit Farm",
    commodity: "Durian",
    origin: "Tiền Giang",
    destination: "TP. HCM",
    weight_ton: 20,
    deadline: "2026-07-21",
    recommended_route: "C_WATER_ROAD_VIA_CT",
    provider_id: null,
    provider_name: null,
    estimated_cost_vnd: 55_000_000,
    status: "optimizing",
    created_at: "2026-07-18",
    route_options: buildRouteOptions(1.2),
    timeline: [
      { time: "2026-07-18 09:00", event: "Order created", done: true },
      { time: "2026-07-18 09:01", event: "AI1 route optimization running…", done: false },
    ],
  },
  {
    id: "ORD009",
    business_id: "BIZ001",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    weight_ton: 60,
    deadline: "2026-07-28",
    recommended_route: "D_WATER_VIA_CT",
    provider_id: "LP003",
    provider_name: "Delta Waterway",
    estimated_cost_vnd: 48_000_000,
    status: "in_transit",
    created_at: "2026-07-14",
    route_options: buildRouteOptions(1.5),
    timeline: [
      { time: "2026-07-14 10:00", event: "Order created", done: true },
      { time: "2026-07-14 10:05", event: "Route optimized by AI1", done: true },
      { time: "2026-07-14 16:00", event: "Provider assigned: Delta Waterway", done: true },
      { time: "2026-07-15 06:00", event: "Loaded onto barge", done: true },
      { time: "2026-07-28 10:00", event: "Estimated arrival", done: false },
    ],
  },
  {
    id: "ORD010",
    business_id: "BIZ002",
    business_name: "Tiền Giang Fruit Farm",
    commodity: "Mango",
    origin: "Tiền Giang",
    destination: "TP. HCM",
    weight_ton: 8,
    deadline: "2026-07-17",
    recommended_route: "A_DIRECT_ROAD",
    provider_id: "LP004",
    provider_name: "Southern Freight",
    estimated_cost_vnd: 75_000_000,
    status: "delivered",
    created_at: "2026-07-13",
    route_options: buildRouteOptions(0.8),
    timeline: [
      { time: "2026-07-13 07:00", event: "Order created", done: true },
      { time: "2026-07-13 07:05", event: "Route optimized", done: true },
      { time: "2026-07-13 11:00", event: "Provider assigned: Southern Freight", done: true },
      { time: "2026-07-14 07:00", event: "Picked up at Tiền Giang", done: true },
      { time: "2026-07-15 14:00", event: "Delivered to TP. HCM", done: true },
    ],
  },
  {
    id: "ORD011",
    business_id: "BIZ003",
    business_name: "Đồng Tháp Seafood Ltd",
    commodity: "Seafood",
    origin: "Đồng Tháp",
    destination: "TP. HCM",
    weight_ton: 5,
    deadline: "2026-07-20",
    recommended_route: "B_ROAD_VIA_CT",
    provider_id: "LP001",
    provider_name: "Mekong Logistics",
    estimated_cost_vnd: 68_000_000,
    status: "assigned",
    created_at: "2026-07-17",
    route_options: buildRouteOptions(0.9),
    timeline: [
      { time: "2026-07-17 13:00", event: "Order created", done: true },
      { time: "2026-07-17 13:05", event: "Route optimized", done: true },
      { time: "2026-07-17 17:00", event: "Provider assigned: Mekong Logistics", done: true },
      { time: "2026-07-18 07:00", event: "Expected pickup", done: false },
    ],
  },
  {
    id: "ORD012",
    business_id: "BIZ004",
    business_name: "An Giang Organic Farm",
    commodity: "Vegetables",
    origin: "An Giang",
    destination: "TP. HCM",
    weight_ton: 4,
    deadline: "2026-07-18",
    recommended_route: "A_DIRECT_ROAD",
    provider_id: "LP005",
    provider_name: "An Giang Transport",
    estimated_cost_vnd: 75_000_000,
    status: "delayed",
    created_at: "2026-07-15",
    route_options: buildRouteOptions(0.6),
    timeline: [
      { time: "2026-07-15 09:00", event: "Order created", done: true },
      { time: "2026-07-15 09:05", event: "Route optimized", done: true },
      { time: "2026-07-15 14:00", event: "Provider assigned: An Giang Transport", done: true },
      { time: "2026-07-16 06:00", event: "Picked up at An Giang", done: true },
      { time: "2026-07-17 06:00", event: "Delayed – vehicle breakdown", done: false },
    ],
  },
  {
    id: "ORD013",
    business_id: "BIZ006",
    business_name: "Vĩnh Long Agri Coop",
    commodity: "Dragon Fruit",
    origin: "Vĩnh Long",
    destination: "TP. HCM",
    weight_ton: 7,
    deadline: "2026-07-22",
    recommended_route: "E_ROAD_WATER_VIA_CT",
    provider_id: "LP002",
    provider_name: "Cần Thơ Trans",
    estimated_cost_vnd: 52_000_000,
    status: "assigned",
    created_at: "2026-07-17",
    route_options: buildRouteOptions(0.85),
    timeline: [
      { time: "2026-07-17 08:00", event: "Order created", done: true },
      { time: "2026-07-17 08:05", event: "Route optimized", done: true },
      { time: "2026-07-17 11:00", event: "Provider assigned: Cần Thơ Trans", done: true },
    ],
  },
  {
    id: "ORD014",
    business_id: "BIZ001",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    weight_ton: 30,
    deadline: "2026-07-30",
    recommended_route: "D_WATER_VIA_CT",
    provider_id: null,
    provider_name: null,
    estimated_cost_vnd: 48_000_000,
    status: "pending",
    created_at: "2026-07-18",
    route_options: buildRouteOptions(1.2),
    timeline: [{ time: "2026-07-18 11:00", event: "Order created", done: true }],
  },
  {
    id: "ORD015",
    business_id: "BIZ002",
    business_name: "Tiền Giang Fruit Farm",
    commodity: "Mango",
    origin: "Tiền Giang",
    destination: "TP. HCM",
    weight_ton: 18,
    deadline: "2026-07-23",
    recommended_route: "C_WATER_ROAD_VIA_CT",
    provider_id: "LP004",
    provider_name: "Southern Freight",
    estimated_cost_vnd: 55_000_000,
    status: "in_transit",
    created_at: "2026-07-15",
    route_options: buildRouteOptions(1.1),
    timeline: [
      { time: "2026-07-15 10:00", event: "Order created", done: true },
      { time: "2026-07-15 10:05", event: "Route optimized", done: true },
      { time: "2026-07-15 15:00", event: "Provider assigned: Southern Freight", done: true },
      { time: "2026-07-16 08:00", event: "Picked up at Tiền Giang", done: true },
      { time: "2026-07-17 12:00", event: "Arrived at Can Tho Hub", done: true },
      { time: "2026-07-18 08:00", event: "Expected departure from hub", done: false },
    ],
  },
  {
    id: "ORD016",
    business_id: "BIZ003",
    business_name: "Đồng Tháp Seafood Ltd",
    commodity: "Seafood",
    origin: "Đồng Tháp",
    destination: "TP. HCM",
    weight_ton: 9,
    deadline: "2026-07-10",
    recommended_route: "A_DIRECT_ROAD",
    provider_id: "LP004",
    provider_name: "Southern Freight",
    estimated_cost_vnd: 75_000_000,
    status: "delivered",
    created_at: "2026-07-07",
    route_options: buildRouteOptions(0.9),
    timeline: [
      { time: "2026-07-07 09:00", event: "Order created", done: true },
      { time: "2026-07-07 09:05", event: "Route optimized", done: true },
      { time: "2026-07-07 13:00", event: "Provider assigned", done: true },
      { time: "2026-07-08 07:00", event: "Picked up", done: true },
      { time: "2026-07-09 15:00", event: "Delivered to TP. HCM", done: true },
    ],
  },
  {
    id: "ORD017",
    business_id: "BIZ004",
    business_name: "An Giang Organic Farm",
    commodity: "Vegetables",
    origin: "An Giang",
    destination: "TP. HCM",
    weight_ton: 5,
    deadline: "2026-07-19",
    recommended_route: "B_ROAD_VIA_CT",
    provider_id: null,
    provider_name: null,
    estimated_cost_vnd: 68_000_000,
    status: "awaiting_assignment",
    created_at: "2026-07-18",
    route_options: buildRouteOptions(0.7),
    timeline: [
      { time: "2026-07-18 10:00", event: "Order created", done: true },
      { time: "2026-07-18 10:05", event: "Route optimized", done: true },
      { time: "—", event: "Awaiting assignment", done: false },
    ],
  },
  {
    id: "ORD018",
    business_id: "BIZ001",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    weight_ton: 20,
    deadline: "2026-07-24",
    recommended_route: "B_ROAD_VIA_CT",
    provider_id: "LP005",
    provider_name: "An Giang Transport",
    estimated_cost_vnd: 68_000_000,
    status: "in_transit",
    created_at: "2026-07-16",
    route_options: buildRouteOptions(1.0),
    timeline: [
      { time: "2026-07-16 12:00", event: "Order created", done: true },
      { time: "2026-07-16 12:05", event: "Route optimized", done: true },
      { time: "2026-07-16 16:00", event: "Provider assigned", done: true },
      { time: "2026-07-17 06:00", event: "Picked up at Cần Thơ", done: true },
      { time: "2026-07-24 12:00", event: "Estimated delivery", done: false },
    ],
  },
  {
    id: "ORD019",
    business_id: "BIZ006",
    business_name: "Vĩnh Long Agri Coop",
    commodity: "Dragon Fruit",
    origin: "Vĩnh Long",
    destination: "TP. HCM",
    weight_ton: 11,
    deadline: "2026-07-21",
    recommended_route: "C_WATER_ROAD_VIA_CT",
    provider_id: null,
    provider_name: null,
    estimated_cost_vnd: 55_000_000,
    status: "awaiting_assignment",
    created_at: "2026-07-18",
    route_options: buildRouteOptions(0.95),
    timeline: [
      { time: "2026-07-18 13:00", event: "Order created", done: true },
      { time: "2026-07-18 13:05", event: "Route optimized", done: true },
      { time: "—", event: "Awaiting assignment", done: false },
    ],
  },
  {
    id: "ORD020",
    business_id: "BIZ001",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    weight_ton: 35,
    deadline: "2026-07-26",
    recommended_route: "D_WATER_VIA_CT",
    provider_id: "LP005",
    provider_name: "An Giang Transport",
    estimated_cost_vnd: 48_000_000,
    status: "in_transit",
    created_at: "2026-07-15",
    route_options: buildRouteOptions(1.4),
    timeline: [
      { time: "2026-07-15 08:00", event: "Order created", done: true },
      { time: "2026-07-15 08:05", event: "Route optimized", done: true },
      { time: "2026-07-15 12:00", event: "Provider assigned", done: true },
      { time: "2026-07-16 06:00", event: "Loaded onto barge", done: true },
      { time: "2026-07-26 14:00", event: "Estimated delivery", done: false },
    ],
  },
];

// ─── Operations: Dispatch Queue ───────────────────────────────────────────────

export const DISPATCH_QUEUE: DispatchItem[] = [
  {
    priority: "high",
    order_id: "ORD006",
    business_name: "An Giang Organic Farm",
    commodity: "Vegetables",
    deadline: "2026-07-19",
    recommended_route: "C_WATER_ROAD_VIA_CT",
    capacity_ton: 6,
    suggested_provider: "Mekong Logistics",
    reason: "Deadline in 1 day, no assignment yet",
  },
  {
    priority: "high",
    order_id: "ORD017",
    business_name: "An Giang Organic Farm",
    commodity: "Vegetables",
    deadline: "2026-07-19",
    recommended_route: "B_ROAD_VIA_CT",
    capacity_ton: 5,
    suggested_provider: "Cần Thơ Trans",
    reason: "Deadline in 1 day, no assignment yet",
  },
  {
    priority: "medium",
    order_id: "ORD004",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    deadline: "2026-07-25",
    recommended_route: "D_WATER_VIA_CT",
    capacity_ton: 40,
    suggested_provider: "Delta Waterway",
    reason: "Large volume – waiting for waterway consolidation",
  },
  {
    priority: "medium",
    order_id: "ORD019",
    business_name: "Vĩnh Long Agri Coop",
    commodity: "Dragon Fruit",
    deadline: "2026-07-21",
    recommended_route: "C_WATER_ROAD_VIA_CT",
    capacity_ton: 11,
    suggested_provider: "Mekong Logistics",
    reason: "Provider not yet confirmed",
  },
  {
    priority: "low",
    order_id: "ORD014",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    deadline: "2026-07-30",
    recommended_route: "D_WATER_VIA_CT",
    capacity_ton: 30,
    suggested_provider: "Delta Waterway",
    reason: "Pending route optimization confirm",
  },
];

// ─── Operations: Active Shipments ─────────────────────────────────────────────

export const ACTIVE_SHIPMENTS: Shipment[] = [
  {
    id: "SHP001",
    order_id: "ORD001",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    provider_name: "Mekong Logistics",
    route: "C_WATER_ROAD_VIA_CT",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    departed: "2026-07-16 07:00",
    eta: "2026-07-20 10:00",
    status: "at_hub",
    progress: 65,
  },
  {
    id: "SHP002",
    order_id: "ORD005",
    business_name: "Đồng Tháp Seafood Ltd",
    commodity: "Seafood",
    provider_name: "Delta Waterway",
    route: "D_WATER_VIA_CT",
    origin: "Đồng Tháp",
    destination: "TP. HCM",
    departed: "2026-07-17 05:30",
    eta: "2026-07-22 14:00",
    status: "on_track",
    progress: 30,
  },
  {
    id: "SHP003",
    order_id: "ORD007",
    business_name: "Vĩnh Long Agri Coop",
    commodity: "Dragon Fruit",
    provider_name: "Mekong Logistics",
    route: "A_DIRECT_ROAD",
    origin: "Vĩnh Long",
    destination: "TP. HCM",
    departed: "2026-07-17 07:00",
    eta: "2026-07-20 16:00",
    status: "on_track",
    progress: 55,
  },
  {
    id: "SHP004",
    order_id: "ORD003",
    business_name: "Đồng Tháp Seafood Ltd",
    commodity: "Seafood",
    provider_name: "Cần Thơ Trans",
    route: "B_ROAD_VIA_CT",
    origin: "Đồng Tháp",
    destination: "TP. HCM",
    departed: "2026-07-15 06:00",
    eta: "2026-07-18 18:00",
    status: "delayed",
    progress: 70,
  },
  {
    id: "SHP005",
    order_id: "ORD009",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    provider_name: "Delta Waterway",
    route: "D_WATER_VIA_CT",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    departed: "2026-07-15 06:00",
    eta: "2026-07-28 10:00",
    status: "on_track",
    progress: 20,
  },
  {
    id: "SHP006",
    order_id: "ORD015",
    business_name: "Tiền Giang Fruit Farm",
    commodity: "Mango",
    provider_name: "Southern Freight",
    route: "C_WATER_ROAD_VIA_CT",
    origin: "Tiền Giang",
    destination: "TP. HCM",
    departed: "2026-07-16 08:00",
    eta: "2026-07-23 12:00",
    status: "at_hub",
    progress: 50,
  },
  {
    id: "SHP007",
    order_id: "ORD012",
    business_name: "An Giang Organic Farm",
    commodity: "Vegetables",
    provider_name: "An Giang Transport",
    route: "A_DIRECT_ROAD",
    origin: "An Giang",
    destination: "TP. HCM",
    departed: "2026-07-16 06:00",
    eta: "2026-07-18 18:00",
    status: "delayed",
    progress: 45,
  },
  {
    id: "SHP008",
    order_id: "ORD018",
    business_name: "Cửu Long Rice Co.",
    commodity: "Rice",
    provider_name: "An Giang Transport",
    route: "B_ROAD_VIA_CT",
    origin: "Cần Thơ",
    destination: "TP. HCM",
    departed: "2026-07-17 06:00",
    eta: "2026-07-24 12:00",
    status: "on_track",
    progress: 18,
  },
];

// ─── Operations: Exceptions ────────────────────────────────────────────────────

export const EXCEPTIONS: Exception[] = [
  {
    id: "EXC001",
    type: "delayed",
    order_id: "ORD003",
    business_name: "Đồng Tháp Seafood Ltd",
    description: "Vehicle CT-T01 reported 3-hour delay due to traffic on QL91. ETA revised to 18:00.",
    severity: "critical",
    created_at: "2026-07-17 14:30",
    resolved: false,
  },
  {
    id: "EXC002",
    type: "delayed",
    order_id: "ORD012",
    business_name: "An Giang Organic Farm",
    description: "Truck AG-T01 mechanical breakdown near Long Xuyên. Vegetables at risk. Needs reassignment.",
    severity: "critical",
    created_at: "2026-07-17 11:00",
    resolved: false,
  },
  {
    id: "EXC003",
    type: "capacity_shortage",
    order_id: "ORD004",
    business_name: "Cửu Long Rice Co.",
    description: "No barge with 40t capacity available for waterway route. Delta Waterway fully committed.",
    severity: "warning",
    created_at: "2026-07-17 09:00",
    resolved: false,
  },
  {
    id: "EXC004",
    type: "no_provider",
    order_id: "ORD006",
    business_name: "An Giang Organic Farm",
    description: "Order ORD006 unassigned for 18 hours. Deadline is 2026-07-19. Auto-assign recommended.",
    severity: "warning",
    created_at: "2026-07-17 08:00",
    resolved: false,
  },
  {
    id: "EXC005",
    type: "weather_warning",
    order_id: "ORD009",
    business_name: "Cửu Long Rice Co.",
    description: "Heavy rain forecast on Mekong river July 19–20. Water factor may drop below safety threshold.",
    severity: "info",
    created_at: "2026-07-17 06:00",
    resolved: false,
  },
  {
    id: "EXC006",
    type: "high_cost",
    order_id: "ORD002",
    business_name: "Tiền Giang Fruit Farm",
    description: "Estimated cost for ORD002 is 28% above monthly average. Review route selection.",
    severity: "info",
    created_at: "2026-07-16 16:00",
    resolved: true,
  },
];

// ─── Recent Activity ───────────────────────────────────────────────────────────

export const RECENT_ACTIVITY: ActivityItem[] = [
  {
    time: "2026-07-18 13:05",
    activity: "Route optimized for ORD019",
    actor: "AI1 Optimizer",
    status: "success",
  },
  {
    time: "2026-07-18 11:00",
    activity: "Order ORD014 created",
    actor: "Cửu Long Rice Co.",
    status: "info",
  },
  {
    time: "2026-07-18 10:05",
    activity: "Route optimized for ORD017",
    actor: "AI1 Optimizer",
    status: "success",
  },
  {
    time: "2026-07-18 09:05",
    activity: "Route optimization started for ORD008",
    actor: "AI1 Optimizer",
    status: "info",
  },
  {
    time: "2026-07-17 17:00",
    activity: "Mekong Logistics assigned to ORD011",
    actor: "admin1",
    status: "success",
  },
  {
    time: "2026-07-17 14:30",
    activity: "DELAYED alert raised for ORD003",
    actor: "System",
    status: "warning",
  },
  {
    time: "2026-07-17 13:00",
    activity: "Order ORD011 created",
    actor: "Đồng Tháp Seafood Ltd",
    status: "info",
  },
  {
    time: "2026-07-17 11:00",
    activity: "Breakdown alert for ORD012",
    actor: "System",
    status: "warning",
  },
  {
    time: "2026-07-17 08:00",
    activity: "Business BIZ007 applied – pending review",
    actor: "Sóc Trăng Veg Co.",
    status: "info",
  },
  {
    time: "2026-07-17 07:00",
    activity: "ORD007 picked up by Mekong Logistics",
    actor: "Mekong Logistics",
    status: "success",
  },
  {
    time: "2026-07-16 15:00",
    activity: "Delta Waterway assigned to ORD005",
    actor: "admin1",
    status: "success",
  },
  {
    time: "2026-07-15 10:05",
    activity: "Route optimized for ORD015",
    actor: "AI1 Optimizer",
    status: "success",
  },
];

// ─── Analytics time-series data ────────────────────────────────────────────────

export const ORDERS_OVER_TIME = [
  { month: "Jan 2026", total: 18, delivered: 16 },
  { month: "Feb 2026", total: 22, delivered: 20 },
  { month: "Mar 2026", total: 19, delivered: 17 },
  { month: "Apr 2026", total: 27, delivered: 25 },
  { month: "May 2026", total: 31, delivered: 28 },
  { month: "Jun 2026", total: 35, delivered: 31 },
  { month: "Jul 2026", total: 20, delivered: 4 },
];

export const VOLUME_BY_MODE = [
  { month: "Jan", road: 210, waterway: 180, multimodal: 90 },
  { month: "Feb", road: 240, waterway: 210, multimodal: 110 },
  { month: "Mar", road: 200, waterway: 190, multimodal: 80 },
  { month: "Apr", road: 280, waterway: 240, multimodal: 130 },
  { month: "May", road: 310, waterway: 270, multimodal: 145 },
  { month: "Jun", road: 340, waterway: 300, multimodal: 160 },
  { month: "Jul", road: 185, waterway: 140, multimodal: 75 },
];

export const COST_OVER_TIME = [
  { month: "Jan 2026", cost: 1_240 },
  { month: "Feb 2026", cost: 1_480 },
  { month: "Mar 2026", cost: 1_310 },
  { month: "Apr 2026", cost: 1_820 },
  { month: "May 2026", cost: 2_090 },
  { month: "Jun 2026", cost: 2_350 },
  { month: "Jul 2026", cost: 1_120 },
];

export const ROUTE_MIX = [
  { route: "A_DIRECT_ROAD", count: 28, pct: 18 },
  { route: "B_ROAD_VIA_CT", count: 34, pct: 22 },
  { route: "C_WATER_ROAD_VIA_CT", count: 45, pct: 29 },
  { route: "D_WATER_VIA_CT", count: 35, pct: 23 },
  { route: "E_ROAD_WATER_VIA_CT", count: 12, pct: 8 },
];

export const SAVINGS_BY_ROUTE = [
  { route: "B_ROAD_VIA_CT", savings: 238 },
  { route: "C_WATER_ROAD_VIA_CT", savings: 900 },
  { route: "D_WATER_VIA_CT", savings: 945 },
  { route: "E_ROAD_WATER_VIA_CT", savings: 276 },
];

export const DISPATCH_MIX = [
  { name: "Dispatch Now", value: 62, color: "#047857" },
  { name: "Wait for Load", value: 24, color: "#1d4ed8" },
  { name: "Wait for Vehicle", value: 14, color: "#92400e" },
];

export const FORECAST_VS_ACTUAL = [
  { month: "Jan", forecast: 20, actual: 18 },
  { month: "Feb", forecast: 21, actual: 22 },
  { month: "Mar", forecast: 22, actual: 19 },
  { month: "Apr", forecast: 25, actual: 27 },
  { month: "May", forecast: 29, actual: 31 },
  { month: "Jun", forecast: 33, actual: 35 },
  { month: "Jul", forecast: 22, actual: 20 },
];

export const STATUS_DISTRIBUTION = [
  { name: "Delivered", value: 4, color: "#047857" },
  { name: "In Transit", value: 6, color: "#1d4ed8" },
  { name: "Assigned", value: 3, color: "#6366f1" },
  { name: "Awaiting", value: 4, color: "#f59e0b" },
  { name: "Delayed", value: 2, color: "#b91c1c" },
  { name: "Pending", value: 1, color: "#64748b" },
];

// ─── Computed summaries ────────────────────────────────────────────────────────

export function getAdminKpis() {
  const totalBusinesses = BUSINESSES.length;
  const activeProviders = PROVIDERS.filter((p) => p.status !== "inactive").length;
  const totalOrders = ORDERS.length;
  const activeShipments = ORDERS.filter((o) => o.status === "in_transit" || o.status === "assigned").length;
  const unassigned = ORDERS.filter((o) => o.status === "awaiting_assignment").length;
  const delayed = ORDERS.filter((o) => o.status === "delayed").length;
  const delivered = ORDERS.filter((o) => o.status === "delivered").length;
  const ontimeRate = Math.round((delivered / Math.max(1, totalOrders - activeShipments)) * 100);
  const savings = BUSINESSES.reduce((sum, b) => sum + b.savings_vnd, 0);
  return {
    totalBusinesses,
    activeProviders,
    totalOrders,
    activeShipments,
    unassigned,
    delayed,
    ontimeRate,
    savings,
  };
}
