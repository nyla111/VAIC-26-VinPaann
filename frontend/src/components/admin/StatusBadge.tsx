"use client";

import { useLanguage } from "@/context/LanguageContext";

type Variant =
  | "active"
  | "pending"
  | "suspended"
  | "available"
  | "busy"
  | "inactive"
  | "assigned"
  | "in_transit"
  | "delivered"
  | "delayed"
  | "cancelled"
  | "optimizing"
  | "awaiting_assignment"
  | "on_track"
  | "at_hub"
  | "success"
  | "warning"
  | "info"
  | "high"
  | "medium"
  | "low"
  | "critical"
  | string;

const CONFIG: Record<string, { bg: string; color: string; label?: string }> = {
  active: { bg: "#dcfce7", color: "#166534", label: "Active" },
  pending: { bg: "#fef3c7", color: "#92400e", label: "Pending" },
  suspended: { bg: "#fee2e2", color: "#991b1b", label: "Suspended" },
  available: { bg: "#dcfce7", color: "#166534", label: "Available" },
  busy: { bg: "#fef9c3", color: "#713f12", label: "Busy" },
  inactive: { bg: "#f1f5f9", color: "#475569", label: "Inactive" },
  assigned: { bg: "#ede9fe", color: "#4c1d95", label: "Assigned" },
  in_transit: { bg: "#dbeafe", color: "#1e40af", label: "In Transit" },
  delivered: { bg: "#dcfce7", color: "#166534", label: "Delivered" },
  delayed: { bg: "#fee2e2", color: "#991b1b", label: "Delayed" },
  cancelled: { bg: "#f1f5f9", color: "#475569", label: "Cancelled" },
  optimizing: { bg: "#e0f2fe", color: "#0369a1", label: "Optimizing" },
  awaiting_assignment: { bg: "#fef3c7", color: "#92400e", label: "Awaiting" },
  on_track: { bg: "#dcfce7", color: "#166534", label: "On Track" },
  at_hub: { bg: "#dbeafe", color: "#1e40af", label: "At Hub" },
  success: { bg: "#dcfce7", color: "#166534" },
  warning: { bg: "#fef3c7", color: "#92400e" },
  info: { bg: "#dbeafe", color: "#1e40af" },
  high: { bg: "#fee2e2", color: "#991b1b", label: "High" },
  medium: { bg: "#fef3c7", color: "#92400e", label: "Medium" },
  low: { bg: "#f0fdf4", color: "#166534", label: "Low" },
  critical: { bg: "#fee2e2", color: "#991b1b", label: "Critical" },
  road: { bg: "#dbeafe", color: "#1e40af", label: "Road" },
  waterway: { bg: "#e0f2fe", color: "#0369a1", label: "Waterway" },
  multimodal: { bg: "#ede9fe", color: "#4c1d95", label: "Multimodal" },
};

export function StatusBadge({ status, label }: { status: Variant; label?: string }) {
  const { language } = useLanguage();
  const cfg = CONFIG[status] ?? { bg: "#f1f5f9", color: "#475569" };
  const translated: Record<string, string> = language === "vi" ? {
    active: "Đang hoạt động", pending: "Đang chờ", suspended: "Tạm dừng", available: "Sẵn sàng",
    busy: "Đang bận", inactive: "Không hoạt động", assigned: "Đã phân công", in_transit: "Đang vận chuyển",
    delivered: "Đã giao", delayed: "Trễ", cancelled: "Đã hủy", optimizing: "Đang tối ưu",
    awaiting_assignment: "Chờ phân công", on_track: "Đúng tiến độ", at_hub: "Tại hub", road: "Đường bộ",
    waterway: "Đường thủy", multimodal: "Đa phương thức", high: "Cao", medium: "Trung bình", low: "Thấp",
    critical: "Nghiêm trọng",
  } : {
    active: "Active", pending: "Pending", suspended: "Suspended", available: "Available", busy: "Busy",
    inactive: "Inactive", assigned: "Assigned", in_transit: "In transit", delivered: "Delivered",
    delayed: "Delayed", cancelled: "Cancelled", optimizing: "Optimizing", awaiting_assignment: "Awaiting assignment",
    on_track: "On track", at_hub: "At hub", road: "Road", waterway: "Waterway", multimodal: "Multimodal",
    high: "High", medium: "Medium", low: "Low", critical: "Critical",
  };
  const text = label ?? translated[status] ?? cfg.label ?? status.replace(/_/g, " ");
  return (
    <span
      style={{
        background: cfg.bg,
        color: cfg.color,
        padding: "3px 9px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: "nowrap",
        display: "inline-block",
      }}
    >
      {text}
    </span>
  );
}
