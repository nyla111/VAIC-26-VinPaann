"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
const AdminLogisticsMap = dynamic(() => import("@/components/VaicMap").then((m) => m.VaicMap), {
  ssr: false,
});

import { StatusBadge } from "@/components/admin/StatusBadge";
import { useLanguage } from "@/context/LanguageContext";
import { getDashboardView } from "@/lib/api";
import { getAdminKpis, RECENT_ACTIVITY } from "@/data/adminMockData";
import { formatCurrency, formatDateTime, formatNumber, formatWeightKg } from "@/lib/labels";
import type { DashboardView, Layer2ForecastMode, Layer2ForecastPayload } from "@/types/dashboard";

const kpis = getAdminKpis();

const ACTION_CENTER = [
  {
    title: "admin.pending_business_approvals",
    count: 2,
    color: "#f59e0b",
    bgColor: "#fffbeb",
    label: "admin.new_applications_waiting",
    action: "admin.review_applications",
    href: "/admin/businesses?filter=pending",
    icon: "🏢",
  },
  {
    title: "admin.unassigned_orders",
    count: kpis.unassigned,
    color: "#dc2626",
    bgColor: "#fef2f2",
    label: "admin.orders_without_provider",
    action: "admin.assign_orders",
    href: "/admin/orders?filter=awaiting_assignment",
    icon: "📦",
  },
  {
    title: "admin.delayed_shipments",
    count: kpis.delayed,
    color: "#b91c1c",
    bgColor: "#fef2f2",
    label: "admin.shipments_past_eta",
    action: "admin.view_delays",
    href: "/admin/operations?tab=exceptions",
    icon: "⚠️",
  },
  {
    title: "admin.capacity_alerts",
    count: 1,
    color: "#1d4ed8",
    bgColor: "#eff6ff",
    label: "admin.capacity_warnings",
    action: "admin.review_capacity",
    href: "/admin/operations?tab=capacity",
    icon: "📊",
  },
];

function formatForecastTime(value: string | null | undefined, language: "vi" | "en", fallback: string) {
  return value ? formatDateTime(value, language) : fallback;
}

function forecastDecisionLabel(decision: string | undefined, t: (key: string, fallback?: string) => string) {
  if (decision === "dispatch_now") return t("forecast.dispatch_now");
  if (decision === "wait_for_vehicle") return t("forecast.wait_for_vehicle");
  if (decision === "wait_for_load") return t("forecast.wait_for_load");
  return t("forecast.no_decision");
}

function ForecastOverviewCard({ forecast }: { forecast?: Layer2ForecastPayload }) {
  const { language, t } = useLanguage();
  const modes: Array<["road" | "water", string, string]> = [
    ["road", t("admin.road_outbound"), "#1d4ed8"],
    ["water", t("admin.water_outbound"), "#0369a1"],
  ];

  return (
    <section>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 12 }}>
        <div>
          <h2 className="section-title" style={{ margin: 0 }}>{language === "vi" ? "Forecast Layer 2" : "Layer 2 forecast"}</h2>
          <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>
            {language === "vi" ? "Dự báo thời điểm hàng tại Cần Thơ đầy phương tiện mục tiêu." : "Forecast when the Can Tho queue fills the target vehicle."}
          </p>
        </div>
        <span style={{ fontSize: 12, color: forecast?.available ? "#047857" : "#b91c1c", fontWeight: 700 }}>
          {forecast?.available ? `${t("common.live")} · SQLite` : t("forecast.unavailable")}
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
        {modes.map(([mode, label, color]) => {
          const item: Layer2ForecastMode | undefined = forecast?.modes?.[mode];
          const capacity = item?.selected_vehicle?.capacity_kg || 0;
          const load = item?.current_load_kg || 0;
          const fill = capacity > 0 ? Math.min(100, (load / capacity) * 100) : 0;
          return (
            <div key={mode} className="panel" style={{ borderTop: `4px solid ${color}`, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <strong style={{ color }}>{label}</strong>
                <span style={{ fontSize: 12, color: "#64748b" }}>{forecastDecisionLabel(item?.decision, t)}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 14, fontSize: 13 }}>
                <span>{language === "vi" ? "Queue hiện tại" : "Current queue"}</span>
                <strong>{formatWeightKg(load, language)}{capacity ? ` / ${formatWeightKg(capacity, language)}` : ""}</strong>
              </div>
              <div style={{ background: "#e2e8f0", height: 8, borderRadius: 999, marginTop: 7 }}>
                <div style={{ width: `${fill}%`, height: "100%", borderRadius: 999, background: color }} />
              </div>
              <div style={{ marginTop: 12, fontSize: 13 }}>
                <span style={{ color: "#64748b" }}>{language === "vi" ? "Dự báo đầy tải" : "Predicted full load"}: </span>
                <strong>{formatForecastTime(item?.predicted_full_load_time, language, language === "vi" ? "Chưa có" : "Not available")}</strong>
              </div>
              <div style={{ marginTop: 6, color: "#64748b", fontSize: 12 }}>
                {item?.waiting_shipment_count ?? 0} {language === "vi" ? "đơn chờ" : "waiting orders"} · {t("fleet.confidence")} {Math.round((item?.confidence || 0) * 100)}%
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function AdminOverviewPage() {
  const { language, t, sectionDescription } = useLanguage();
  const [backendView, setBackendView] = useState<DashboardView | null>(null);
  const [activityExpanded, setActivityExpanded] = useState(false);

  useEffect(() => {
    const refresh = () => {
      getDashboardView("admin_inventory")
        .then(setBackendView)
        .catch(() => {/* graceful fallback — no backend KPIs */});
    };

    refresh();
    const apiBase = process.env.NEXT_PUBLIC_VAIC_API_BASE_URL || "http://127.0.0.1:8000";
    const socket = new WebSocket(apiBase.replace(/^http/, "ws") + "/ws/status");
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.event === "TIME_TICK" || message.event === "STATE_UPDATE") refresh();
      } catch {
        // The next authoritative REST refresh will recover from malformed frames.
      }
    };
    return () => socket.close();
  }, []);

  const backendKpis = backendView?.kpis;
  const displayActivity = activityExpanded ? RECENT_ACTIVITY : RECENT_ACTIVITY.slice(0, 5);

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>{t("admin.overview_title", "Admin Overview")}</h1>
          <p className="page-subtitle">{sectionDescription("admin_inventory")}</p>
        </div>
        <div style={{ color: "#64748b", fontSize: 13 }}>
          {t("admin.last_updated")}: {formatDateTime(new Date(), language)}
        </div>
      </div>

      <div className="admin-two-column-layout">
        {/* Left Column: Interactive content, forecast, map, action center, and activity */}
        <div style={{ display: "grid", gap: 24, minWidth: 0 }}>
          <ForecastOverviewCard forecast={backendView?.forecast} />

          {/* Map */}
          <section>
            <h2 className="section-title">{language === "vi" ? "Bản đồ Đồng bằng sông Cửu Long" : "Mekong Delta map view"}</h2>
            <div className="panel" style={{ padding: 14, overflow: "visible" }}>
              {backendView?.map_payload ? (
                <AdminLogisticsMap data={backendView.map_payload} />
              ) : (
                <div className="empty">{t("common.loading")}</div>
              )}
            </div>
          </section>

          {/* Action Center */}
          <section>
            <h2 className="section-title">{language === "vi" ? "Trung tâm hành động" : "Action center"}</h2>
            <div className="action-center-grid">
              {ACTION_CENTER.map((item) => (
                <div
                  key={item.title}
                  className="action-card"
                  style={{ borderLeftColor: item.color, background: item.bgColor }}
                >
                  <div className="action-card-header">
                    <span style={{ fontSize: 22 }}>{item.icon}</span>
                    <div>
                      <div className="action-card-title">{t(item.title)}</div>
                      <div className="action-card-count" style={{ color: item.color }}>
                        {item.count}
                      </div>
                    </div>
                  </div>
                  <p className="action-card-label">{t(item.label, item.label)}</p>
                  <Link href={item.href} className="action-card-btn">
                    {t(item.action, item.action)} →
                  </Link>
                </div>
              ))}
            </div>
          </section>

          {/* Recent Activity */}
          <section style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <h2 className="section-title" style={{ margin: 0 }}>{t("admin.recent_activity")}</h2>
              <button
                className="secondary"
                style={{ fontSize: 13, padding: "6px 12px" }}
                onClick={() => setActivityExpanded((v) => !v)}
              >
                {activityExpanded ? t("admin.show_less") : t("admin.view_all_activity")}
              </button>
            </div>
            <div className="panel" style={{ padding: 0 }}>
              <table style={{ width: "100%" }}>
                <thead>
                  <tr>
                    <th>{t("admin.time")}</th>
                    <th>{t("admin.activity")}</th>
                    <th>{t("admin.actor")}</th>
                    <th>{t("common.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {displayActivity.map((item, i) => (
                    <tr key={i}>
                      <td style={{ whiteSpace: "nowrap", color: "#64748b", fontSize: 13 }}>{item.time}</td>
                      <td>{item.activity}</td>
                      <td style={{ color: "#64748b", fontSize: 13 }}>{item.actor}</td>
                      <td>
                        <StatusBadge status={item.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* Right Column: Platform and Live KPIs stacked vertically */}
        <div className="admin-summary-column" style={{ gap: 24 }}>
          {/* Platform KPIs */}
          <section>
            <h2 className="section-title">{t("admin.platform_kpis")}</h2>
            <div style={{ display: "grid", gap: 12 }}>
              <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                <span>{t("admin.total_businesses", "Total Businesses")}</span>
                <strong>{kpis.totalBusinesses}</strong>
              </div>
              <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                <span>{t("admin.active_logistics_partners", "Active Logistics Partners")}</span>
                <strong>{kpis.activeProviders}</strong>
              </div>
              <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                <span>{t("common.orders", "Total Orders")}</span>
                <strong>{kpis.totalOrders}</strong>
              </div>
              <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                <span>{t("admin.active_shipments", "Active Shipments")}</span>
                <strong>{kpis.activeShipments}</strong>
              </div>
              <div className="admin-kpi-card admin-kpi-card--warn" style={{ padding: "16px 20px" }}>
                <span>{t("admin.unassigned_orders")}</span>
                <strong>{kpis.unassigned}</strong>
              </div>
              <div className="admin-kpi-card admin-kpi-card--danger" style={{ padding: "16px 20px" }}>
                <span>{t("admin.delayed_orders", "Delayed Orders")}</span>
                <strong>{kpis.delayed}</strong>
              </div>
              <div className="admin-kpi-card admin-kpi-card--success" style={{ padding: "16px 20px" }}>
                <span>{t("admin.ontime_rate", "On-time Delivery Rate")}</span>
                <strong>{kpis.ontimeRate}%</strong>
              </div>
              <div className="admin-kpi-card admin-kpi-card--blue" style={{ padding: "16px 20px" }}>
                <span>{t("admin.cost_savings")}</span>
                <strong>{backendKpis ? formatCurrency(Number(backendKpis.cost_savings), language) : t("common.loading")}</strong>
                <small>{backendKpis ? `${backendKpis.orders_with_savings ?? backendKpis.compared_orders} ${language === "vi" ? "đơn đã so sánh" : "orders compared"}` : t("common.source")}</small>
              </div>
            </div>
          </section>

          {/* Live Metrics */}
          {backendKpis ? (
            <section>
              <h2 className="section-title">{t("admin.live_metrics")}</h2>
              <div style={{ display: "grid", gap: 12 }}>
                <div className="admin-kpi-card admin-kpi-card--success" style={{ padding: "16px 20px" }}>
                  <span>{t("admin.cost_savings")}</span>
                  <strong>{formatCurrency(Number(backendKpis.cost_savings), language)}</strong>
                  <small>{backendKpis.savings_source === "live_orders" ? (language === "vi" ? "Nguồn: database" : "Source: database") : t("common.source")}</small>
                </div>
                <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                  <span>CO₂ {language === "vi" ? "giảm so với đường thẳng" : "reduction vs direct road"}</span>
                  <strong>{formatWeightKg(Number(backendKpis.co2_savings_ton || 0) * 1000, language, 2)}</strong>
                </div>
                <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                  <span>{t("admin.orders_processed")}</span>
                  <strong>{formatNumber(backendKpis.processed, language)}</strong>
                </div>
                <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                  <span>{language === "vi" ? "Độ tin cậy dự báo" : "Prediction reliability"}</span>
                  <strong>
                    {backendKpis.predictionReliabilityPct !== undefined
                      ? `${backendKpis.predictionReliabilityPct.toFixed(1)}%`
                      : "87.4%"}
                  </strong>
                  <small style={{ color: "#64748b", fontSize: 11 }}>
                    {language === "vi" ? "Dự báo nằm trong ngưỡng sai số chấp nhận được" : "Predictions within accepted error tolerance"}
                  </small>
                </div>
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
