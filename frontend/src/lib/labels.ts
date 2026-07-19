import type { Language } from "@/context/LanguageContext";

const ROUTES: Record<string, { vi: string; en: string }> = {
  A_DIRECT_ROAD: { vi: "A · Đường bộ trực tiếp", en: "A · Direct road" },
  B_ROAD_VIA_CT: { vi: "B · Đường bộ qua Cần Thơ", en: "B · Road via Can Tho" },
  C_WATER_ROAD_VIA_CT: { vi: "C · Đường thủy + bộ qua Cần Thơ", en: "C · Water + road via Can Tho" },
  D_WATER_VIA_CT: { vi: "D · Đường thủy qua Cần Thơ", en: "D · Waterway via Can Tho" },
  E_ROAD_WATER_VIA_CT: { vi: "E · Bộ + thủy qua Cần Thơ", en: "E · Road + water via Can Tho" },
};

export function routeLabel(code: string | null | undefined, language: Language) {
  if (!code) return language === "vi" ? "Chưa chọn tuyến" : "No route selected";
  return ROUTES[code]?.[language] || code.replaceAll("_", " ");
}

export function modeLabel(mode: string | null | undefined, language: Language) {
  if (mode === "water" || mode === "waterway") return language === "vi" ? "Đường thủy (Tàu)" : "Waterway (Vessel)";
  if (mode === "road") return language === "vi" ? "Đường bộ (Xe tải)" : "Road (Truck)";
  return mode || (language === "vi" ? "Chưa rõ" : "Unknown");
}

export const ORDER_STATES: Record<string, { vi: string; en: string }> = {
  created: { vi: "Mới tạo", en: "Created" },
  routed_to_can_tho: { vi: "Đang về Cần Thơ", en: "Moving to Can Tho" },
  arrived_waiting: { vi: "Đang chờ gom tại hub", en: "Waiting for consolidation" },
  dispatched: { vi: "Đã dispatch", en: "Dispatched" },
  completed: { vi: "Hoàn tất", en: "Completed" },
  cancelled: { vi: "Đã hủy", en: "Cancelled" },
};

export const LAYER2_DECISIONS: Record<string, { vi: string; en: string }> = {
  dispatch_now: { vi: "Sẵn sàng dispatch", en: "Ready to dispatch" },
  wait_for_load: { vi: "Đang gom thêm hàng", en: "Waiting for load" },
  wait_for_vehicle: { vi: "Đang chờ phương tiện", en: "Waiting for vehicle" },
};

export function enumLabel(value: string | null | undefined, language: Language, labels: Record<string, { vi: string; en: string }>, fallback?: string) {
  if (!value) return fallback || (language === "vi" ? "Chưa rõ" : "Unknown");
  return labels[value]?.[language] || value.replaceAll("_", " ");
}

export function orderStateLabel(value: string | null | undefined, language: Language) {
  return enumLabel(value, language, ORDER_STATES);
}

export function layer2DecisionLabel(value: string | null | undefined, language: Language) {
  return enumLabel(value, language, LAYER2_DECISIONS);
}

export function formatNumber(value: number | null | undefined, language: Language, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat(language === "vi" ? "vi-VN" : "en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatCurrency(value: number | null | undefined, language: Language) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${formatNumber(value, language)} VND`;
}

export function formatDate(value: string | Date | null | undefined, language: Language) {
  if (!value) return "-";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(language === "vi" ? "vi-VN" : "en-US", {
    year: "numeric", month: "2-digit", day: "2-digit",
  }).format(date);
}

export function formatDateTime(value: string | Date | null | undefined, language: Language) {
  if (!value) return "-";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(language === "vi" ? "vi-VN" : "en-US", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

export function formatWeightKg(value: number | null | undefined, language: Language, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const unit = language === "vi" ? "tấn" : "tons";
  return `${formatNumber(value / 1000, language, digits)} ${unit}`;
}

export function formatDurationHours(value: number | null | undefined, language: Language, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${formatNumber(value, language, digits)} ${language === "vi" ? "giờ" : "hours"}`;
}
