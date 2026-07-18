export type Role = "business" | "logistics" | "admin";

export type User = {
  username: string;
  role: Role;
  name: string;
};

export type MenuItem = {
  id: string;
  label: string;
};

export type Priority = {
  tier: string;
  score: number;
  label: string;
};

export type CostBreakdown = {
  raw_transport_cost_vnd: number;
  spoilage_cost_vnd: number;
  transshipment_fee_vnd: number;
  total_cost_vnd: number;
  pricing_source?: string | null;
};

export type RouteOption = {
  ten: string;
  route_code: string;
  chi_phi_du_doan_vnd: number | null;
  thoi_gian_du_kien_gio: number | null;
  trang_thai: "available" | "currently_unavailable";
  ly_do?: string | null;
  cost_breakdown?: CostBreakdown | null;
};

export type OptimizeResult = {
  hub_id: string;
  priority: Priority;
  recommended_route: string | null;
  phuong_an: RouteOption[];
  khuyen_nghi: string | null;
  evidence: {
    weather_ts?: string | null;
    price_ts?: string | null;
  };
};

export type FleetRow = Record<string, string>;

export type Job = {
  job_id: string;
  hub_id: string;
  khoi_luong_tich_luy_hien_tai_kg: number;
  quyet_dinh: string;
  thoi_gian_de_xuat_chay: string;
  route_code: string;
};

export type Delivery = {
  delivery_id: string;
  route_code: string;
  status: string;
  eta: string;
};

export type Kpis = {
  processed: number;
  compared_orders: number;
  cost_savings: number;
  co2_savings_ton: number;
  time_delta_hours_abs: number;
  time_delta_pct_abs: number;
  time_direction: "faster" | "slower";
  reporting_start: string;
  reporting_end: string;
  route_counts: Record<string, number>;
};

export type TrackingItem = {
  created_at: string;
  input: {
    hub_id: string;
    khoi_luong_kg: number;
  };
  recommended_route: string | null;
  khuyen_nghi: string | null;
};

export type WeatherRow = {
  node_id: string;
  ts: string;
  road_factor: number;
  water_factor: number;
  alert_level: string;
};

export type MapPayload = {
  activeRoute?: string | null;
  nodes: Array<{ node_id: string; name: string; type: string; lat: number; lon: number; on_river: string }>;
  legs?: Array<{ leg_id: string; mode: string; distance_km: number; points: [number, number][] }>;
  fleet: Array<{ node_id: string; lat: number; lon: number; count: number; statuses: Record<string, number> }>;
  routes?: Record<string, Array<RouteSegment>>;
};

export type RouteSegment = {
  leg_id: string;
  mode: string;
  distance_km: number;
  origin: { lat: number; lon: number };
  destination: { lat: number; lon: number };
  points: [number, number][];
};

export type DashboardView = {
  user: User;
  role: Role;
  section: string;
  section_label: string;
  menu: MenuItem[];
  reason_labels: Record<string, string>;
  hub_options: Array<{ value: string; label: string }>;
  commodity_options: string[];
  result?: OptimizeResult;
  route_map?: MapPayload;
  map_payload?: MapPayload;
  kpis?: Kpis;
  tracking?: TrackingItem[];
  fleet?: FleetRow[];
  status_filter?: string;
  jobs?: Job[];
  ai2_live?: boolean;
  deliveries?: Delivery[];
  weather?: WeatherRow[];
  errors?: Array<Record<string, string>>;
};

export type ShipmentPayload = {
  hub_id: string;
  commodity_id: string;
  loai_hang: string;
  khoi_luong_kg: number;
  timestamp: string;
};
