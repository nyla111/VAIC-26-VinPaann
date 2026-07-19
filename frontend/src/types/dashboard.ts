export type Role = "enterprise" | "logistics" | "admin";

export type User = {
  id: number;
  email: string;
  role: Role;
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
  mode?: string;
  status?: string;
  vehicle_plate?: string;
  total_weight_kg?: number;
  capacity_kg?: number;
  fill_ratio?: number;
  created_at?: string;
  shipments?: Array<{
    shipment_id: number;
    hub_id: string;
    commodity_id: string;
    loai_hang: string;
    weight_kg: number;
    deadline: string;
  }>;
};

export type ProviderVehicleOption = {
  vehicle_id: string;
  mode: string;
  capacity_kg: number;
  capacity_ton: number;
  status: string;
  location: string;
  available_for_order?: boolean;
};

export type ProviderOrder = {
  order_id: number;
  id: string;
  business_name: string;
  commodity: string;
  origin: string;
  destination: string;
  weight_ton: number;
  state_code: string;
  status: string;
  provider_assignment_status: string;
  assigned_vehicle_id?: string | null;
  required_outbound_mode: string;
  can_accept: boolean;
  transport_options: ProviderVehicleOption[];
};

export type LogisticsOrderQueue = {
  orders: ProviderOrder[];
  vehicles: ProviderVehicleOption[];
  summary: {
    open_orders: number;
    accepted_orders: number;
    waiting_weight_kg: number;
  };
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
  predictionReliabilityPct?: number;
  baseline_cost_vnd?: number;
  optimized_cost_vnd?: number;
  average_savings_vnd?: number;
  orders_with_savings?: number;
  savings_source?: string;
};

export type FleetDemandMode = {
  mode: "road" | "water";
  demand_kg: number;
  known_order_weight_kg: number;
  predicted_weight_kg: number;
  orders_count: number;
  vehicles_needed: number;
  available_vehicles: number;
  prepared_vehicle_count: number;
  available_capacity_kg: number;
  prepared_capacity_kg: number;
  enough_vehicles: boolean;
  capacity_gap_kg: number;
  confidence: number;
};

export type FleetDemandForecast = {
  forecast_date: string;
  generated_at: string;
  source: string;
  scope?: string;
  modes: Record<"road" | "water", FleetDemandMode>;
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
  operational?: boolean;
  vehicle_points?: VehicleMapPoint[];
  waiting_jobs?: JobMapPoint[];
  active_deliveries?: DeliveryMapItem[];
  summary?: LogisticsSummary;
};

export type VehicleMapPoint = {
  vehicle_id: string;
  vehicle_type: string;
  capacity_ton: string;
  source_status: string;
  display_status: "available" | "unavailable" | "in_delivery" | "arrived_waiting";
  current_node_id: string;
  delivery_id?: string | null;
  route_progress?: number | null;
  lat: number;
  lon: number;
  ai2_metrics?: {
    decision: string;
    explanation: string;
    reason_codes: string[];
    thoi_gian_de_xuat_chay?: string | null;
  } | null;
};

export type JobMapPoint = Job & { lat: number; lon: number };

export type DeliveryMapItem = Delivery & {
  hub_id: string;
  segments: RouteSegment[];
};

export type LogisticsSummary = {
  waiting_jobs: number;
  active_deliveries: number;
  available_vehicles: number;
  unavailable_vehicles: number;
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
  logistics_overview?: MapPayload;
  kpis?: Kpis;
  tracking?: TrackingItem[];
  fleet?: FleetRow[];
  status_filter?: string;
  jobs?: Job[];
  provider_orders?: LogisticsOrderQueue;
  ai2_live?: boolean;
  deliveries?: Delivery[];
  weather?: WeatherRow[];
  errors?: Array<Record<string, string>>;
  capacity?: OperationsCapacity;
  forecast?: Layer2ForecastPayload;
  fleet_forecast?: FleetDemandForecast;
  forecast_date?: string;
};

export type Layer2ForecastBucket = {
  timestamp: string;
  known_inbound_kg: number;
  predicted_unknown_kg: number;
  predicted_cumulative_load_kg: number;
};

export type Layer2ForecastMode = {
  mode: "road" | "water";
  available?: boolean;
  error?: string;
  decision?: string;
  reason_codes?: string[];
  explanation?: string;
  current_load_kg?: number;
  waiting_shipment_count?: number;
  fill_ratio?: number;
  selected_vehicle?: {
    vehicle_id: string;
    capacity_kg: number;
  } | null;
  priority_score?: {
    fill_component: number;
    urgency_component: number;
    weather_component: number;
    total_score: number;
  } | null;
  bucket_minutes?: number;
  horizon_hours?: number;
  predicted_full_load_time?: string | null;
  predicted_load_kg?: number | null;
  confidence?: number;
  buckets: Layer2ForecastBucket[];
};

export type Layer2ForecastPayload = {
  available: boolean;
  generated_at: string;
  modes: Partial<Record<"road" | "water", Layer2ForecastMode>>;
};

export type OperationsCapacity = {
  hub: {
    used_ton: number;
    capacity_ton: number | null;
    capacity_configured: boolean;
    waiting_orders: number;
  };
  transport: Record<"road" | "water", {
    used_ton: number;
    total_ton: number;
    available_ton: number;
  }>;
  queue: {
    waiting_orders: number;
    waiting_volume_ton: number;
    next_dispatch_hours: number | null;
  };
};

export type ShipmentPayload = {
  hub_id: string;
  commodity_id: string;
  loai_hang: string;
  khoi_luong_kg: number;
  timestamp: string;
};
