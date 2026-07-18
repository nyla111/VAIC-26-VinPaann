// Frontend-only logistics map data for the Admin Overview.
// Coordinates are approximate but geographically accurate for the
// Mekong Delta transport network (WGS-84, decimal degrees).
// No backend changes required to display this layer.

export type LogisticsMapPoint = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  type: "origin" | "hub" | "destination" | "transfer";
  province?: string;
};

export type LogisticsRouteSegment = {
  id: string;
  mode: "road" | "waterway";
  fromId: string;
  toId: string;
  label: string;
  distance_km: number;
  // [lat, lon] pairs forming the polyline
  points: [number, number][];
};

// ─── Operating-area map configuration ────────────────────────────────────────
// Single source of truth for all view/zoom/bounds constants used by
// AdminLogisticsMap. Keeps geo constants out of JSX.

export const ADMIN_MAP_VIEW = {
  center: [10.15, 105.75] as [number, number],
  zoom: 8,
  minZoom: 8,
  maxZoom: 13,
  // SW corner → NE corner of the permitted operating area.
  // Covers the Mekong Delta provinces + TP. HCM; excludes the East Sea.
  maxBounds: [
    [8.35, 104.35],
    [11.25, 106.95],
  ] as [[number, number], [number, number]],
};

// ─── Logistics network nodes ───────────────────────────────────────────────────

export const LOGISTICS_MAP_POINTS: LogisticsMapPoint[] = [
  {
    id: "HUB_VITHANH",
    name: "Hub Vị Thanh",
    latitude: 9.7756,
    longitude: 105.4703,
    type: "origin",
    province: "Hậu Giang",
  },
  {
    id: "HUB_LONGXUYEN",
    name: "Hub Long Xuyên",
    latitude: 10.3845,
    longitude: 105.4357,
    type: "origin",
    province: "An Giang",
  },
  {
    id: "HUB_SOCTRANG",
    name: "Hub Sóc Trăng",
    latitude: 9.6047,
    longitude: 105.9741,
    type: "origin",
    province: "Sóc Trăng",
  },
  {
    id: "HUB_VINHLONG",
    name: "Hub Vĩnh Long",
    latitude: 10.2528,
    longitude: 105.9722,
    type: "origin",
    province: "Vĩnh Long",
  },
  {
    id: "CT_HUB",
    name: "Cần Thơ Hub",
    latitude: 10.0341,
    longitude: 105.79,
    type: "hub",
    province: "Cần Thơ",
  },
  {
    id: "HCM_MARKET",
    name: "TP. Hồ Chí Minh",
    latitude: 10.7769,
    longitude: 106.7009,
    type: "destination",
    province: "TP. HCM",
  },
];

// ─── Road segments ────────────────────────────────────────────────────────────
// Approximate QL91 / QL61 / QL1A corridors in the Mekong Delta.

export const ROAD_SEGMENTS: LogisticsRouteSegment[] = [
  {
    id: "ROAD_LX_CT",
    mode: "road",
    fromId: "HUB_LONGXUYEN",
    toId: "CT_HUB",
    label: "Long Xuyên → Cần Thơ (QL91)",
    distance_km: 62,
    points: [
      [10.3845, 105.4357],
      [10.3500, 105.5100],
      [10.3000, 105.6000],
      [10.2200, 105.6700],
      [10.1400, 105.7200],
      [10.0800, 105.7600],
      [10.0341, 105.79],
    ],
  },
  {
    id: "ROAD_VT_CT",
    mode: "road",
    fromId: "HUB_VITHANH",
    toId: "CT_HUB",
    label: "Vị Thanh → Cần Thơ (QL61)",
    distance_km: 55,
    points: [
      [9.7756, 105.4703],
      [9.8400, 105.5200],
      [9.9100, 105.6000],
      [9.9700, 105.6700],
      [10.0100, 105.7300],
      [10.0250, 105.7600],
      [10.0341, 105.79],
    ],
  },
  {
    id: "ROAD_ST_CT",
    mode: "road",
    fromId: "HUB_SOCTRANG",
    toId: "CT_HUB",
    label: "Sóc Trăng → Cần Thơ (QL1A)",
    distance_km: 61,
    points: [
      [9.6047, 105.9741],
      [9.7100, 105.9400],
      [9.8300, 105.9000],
      [9.9300, 105.8600],
      [9.99, 105.8300],
      [10.0200, 105.8100],
      [10.0341, 105.79],
    ],
  },
  {
    id: "ROAD_VL_CT",
    mode: "road",
    fromId: "HUB_VINHLONG",
    toId: "CT_HUB",
    label: "Vĩnh Long → Cần Thơ (QL1A/QL54)",
    distance_km: 35,
    points: [
      [10.2528, 105.9722],
      [10.2300, 105.9400],
      [10.2100, 105.9100],
      [10.1800, 105.8800],
      [10.1300, 105.8400],
      [10.0800, 105.8100],
      [10.0500, 105.79],
      [10.0341, 105.79],
    ],
  },
  {
    id: "ROAD_CT_HCM",
    mode: "road",
    fromId: "CT_HUB",
    toId: "HCM_MARKET",
    label: "Cần Thơ → TP. HCM (QL1A)",
    distance_km: 165,
    points: [
      [10.0341, 105.79],
      [10.1000, 105.8400],
      [10.2000, 105.9500],
      [10.3200, 106.0600],
      [10.4300, 106.1500],
      [10.5200, 106.2400],
      [10.6100, 106.3700],
      [10.6700, 106.5000],
      [10.7200, 106.6000],
      [10.7769, 106.7009],
    ],
  },
];

// ─── Waterway segments ────────────────────────────────────────────────────────
// Sông Hậu, Kênh Xáng Xà No, and coastal canal corridors.

export const WATERWAY_SEGMENTS: LogisticsRouteSegment[] = [
  {
    id: "WATER_LX_CT",
    mode: "waterway",
    fromId: "HUB_LONGXUYEN",
    toId: "CT_HUB",
    label: "Long Xuyên → Cần Thơ (Sông Hậu)",
    distance_km: 75,
    points: [
      [10.3845, 105.4357],
      [10.3300, 105.4800],
      [10.2800, 105.5400],
      [10.2200, 105.6100],
      [10.1600, 105.6700],
      [10.1100, 105.7200],
      [10.0600, 105.7600],
      [10.0341, 105.79],
    ],
  },
  {
    id: "WATER_VT_CT",
    mode: "waterway",
    fromId: "HUB_VITHANH",
    toId: "CT_HUB",
    label: "Vị Thanh → Cần Thơ (Kênh Xáng Xà No)",
    distance_km: 68,
    points: [
      [9.7756, 105.4703],
      [9.8200, 105.5100],
      [9.8800, 105.5800],
      [9.9400, 105.6500],
      [9.9800, 105.7000],
      [10.0100, 105.7400],
      [10.0270, 105.7700],
      [10.0341, 105.79],
    ],
  },
  {
    id: "WATER_ST_CT",
    mode: "waterway",
    fromId: "HUB_SOCTRANG",
    toId: "CT_HUB",
    label: "Sóc Trăng → Cần Thơ (Sông Hậu east)",
    distance_km: 78,
    points: [
      [9.6047, 105.9741],
      [9.6800, 105.9200],
      [9.7800, 105.8900],
      [9.8700, 105.8600],
      [9.9500, 105.8300],
      [9.99, 105.8100],
      [10.0200, 105.8000],
      [10.0341, 105.79],
    ],
  },
  {
    id: "WATER_VL_CT",
    mode: "waterway",
    fromId: "HUB_VINHLONG",
    toId: "CT_HUB",
    label: "Vĩnh Long → Cần Thơ (Sông Cổ Chiên)",
    distance_km: 42,
    points: [
      [10.2528, 105.9722],
      [10.2200, 105.9400],
      [10.1900, 105.9000],
      [10.1500, 105.8600],
      [10.1100, 105.8300],
      [10.0700, 105.8100],
      [10.0500, 105.79],
      [10.0341, 105.79],
    ],
  },
  {
    id: "WATER_CT_HCM",
    mode: "waterway",
    fromId: "CT_HUB",
    toId: "HCM_MARKET",
    label: "Cần Thơ → TP. HCM (Sông Hậu → cảng)",
    distance_km: 195,
    points: [
      [10.0341, 105.79],
      [10.0700, 105.8300],
      [10.1500, 105.9200],
      [10.2500, 106.0100],
      [10.3700, 106.1200],
      [10.4800, 106.2100],
      [10.5700, 106.3100],
      [10.6300, 106.4300],
      [10.6900, 106.5500],
      [10.7400, 106.6400],
      [10.7769, 106.7009],
    ],
  },
];
