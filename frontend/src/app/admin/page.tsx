"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
const AdminLogisticsMap = dynamic(() => import("@/components/admin/AdminLogisticsMap").then((m) => m.AdminLogisticsMap), {
  ssr: false,
});

import { StatusBadge } from "@/components/admin/StatusBadge";
import { getDashboardView } from "@/lib/api";
import { getAdminKpis, RECENT_ACTIVITY } from "@/data/adminMockData";
import type { DashboardView } from "@/types/dashboard";

function fmtVnd(n: number) {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B VND`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(0)}M VND`;
  return `${n.toLocaleString()} VND`;
}

const kpis = getAdminKpis();

const ACTION_CENTER = [
  {
    title: "Pending Business Approvals",
    count: 2,
    color: "#f59e0b",
    bgColor: "#fffbeb",
    label: "New applications waiting review",
    action: "Review Applications",
    href: "/admin/businesses?filter=pending",
    icon: "🏢",
  },
  {
    title: "Unassigned Orders",
    count: kpis.unassigned,
    color: "#dc2626",
    bgColor: "#fef2f2",
    label: "Orders without a logistics provider",
    action: "Assign Orders",
    href: "/admin/orders?filter=awaiting_assignment",
    icon: "📦",
  },
  {
    title: "Delayed Shipments",
    count: kpis.delayed,
    color: "#b91c1c",
    bgColor: "#fef2f2",
    label: "Shipments past estimated ETA",
    action: "View Delays",
    href: "/admin/operations?tab=exceptions",
    icon: "⚠️",
  },
  {
    title: "Capacity Alerts",
    count: 1,
    color: "#1d4ed8",
    bgColor: "#eff6ff",
    label: "Hub or vehicle capacity warnings",
    action: "Review Capacity",
    href: "/admin/operations?tab=capacity",
    icon: "📊",
  },
];

export default function AdminOverviewPage() {
  const [backendView, setBackendView] = useState<DashboardView | null>(null);
  const [activityExpanded, setActivityExpanded] = useState(false);

  useEffect(() => {
    getDashboardView("admin_inventory")
      .then(setBackendView)
      .catch(() => {/* graceful fallback — no backend KPIs */});
  }, []);

  const backendKpis = backendView?.kpis;
  const displayActivity = activityExpanded ? RECENT_ACTIVITY : RECENT_ACTIVITY.slice(0, 5);

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>Admin Overview</h1>
          <p className="page-subtitle">Platform health, pending actions &amp; recent activity</p>
        </div>
        <div style={{ color: "#64748b", fontSize: 13 }}>
          Last updated: {new Date().toLocaleString("en-GB")}
        </div>
      </div>

      {/* KPI Grid */}
      <section>
        <h2 className="section-title">Platform KPIs</h2>
        <div className="admin-kpi-grid">
          <div className="admin-kpi-card">
            <span>Total Businesses</span>
            <strong>{kpis.totalBusinesses}</strong>
          </div>
          <div className="admin-kpi-card">
            <span>Active Logistics Partners</span>
            <strong>{kpis.activeProviders}</strong>
          </div>
          <div className="admin-kpi-card">
            <span>Total Orders</span>
            <strong>{kpis.totalOrders}</strong>
          </div>
          <div className="admin-kpi-card">
            <span>Active Shipments</span>
            <strong>{kpis.activeShipments}</strong>
          </div>
          <div className="admin-kpi-card admin-kpi-card--warn">
            <span>Unassigned Orders</span>
            <strong>{kpis.unassigned}</strong>
          </div>
          <div className="admin-kpi-card admin-kpi-card--danger">
            <span>Delayed Orders</span>
            <strong>{kpis.delayed}</strong>
          </div>
          <div className="admin-kpi-card admin-kpi-card--success">
            <span>On-time Delivery Rate</span>
            <strong>{kpis.ontimeRate}%</strong>
          </div>
          <div className="admin-kpi-card admin-kpi-card--blue">
            <span>Est. Cost Savings (All Time)</span>
            <strong>{fmtVnd(kpis.savings)}</strong>
          </div>
        </div>
      </section>

      {/* Backend KPIs (when available) */}
      {backendKpis ? (
        <section>
          <h2 className="section-title">AI Route Optimizer Metrics (Live)</h2>
          <div className="admin-kpi-grid">
            <div className="admin-kpi-card admin-kpi-card--success">
              <span>30-day Cost Savings (AI1)</span>
              <strong>{Number(backendKpis.cost_savings).toLocaleString("vi-VN")} VND</strong>
            </div>
            <div className="admin-kpi-card">
              <span>CO₂ Reduction vs Direct Road</span>
              <strong>{backendKpis.co2_savings_ton?.toFixed(2)} tonnes</strong>
            </div>
            <div className="admin-kpi-card">
              <span>Orders Processed</span>
              <strong>{backendKpis.processed}</strong>
            </div>
            <div className="admin-kpi-card">
              <span>Prediction Reliability</span>
              <strong>
                {backendKpis.predictionReliabilityPct !== undefined
                  ? `${backendKpis.predictionReliabilityPct.toFixed(1)}%`
                  : "87.4%"}
              </strong>
              <small style={{ color: "#64748b", fontSize: 11 }}>
                Predictions within accepted error tolerance
              </small>
              {backendKpis.predictionReliabilityPct === undefined && (
                <span style={{
                  display: "inline-block",
                  marginTop: 4,
                  fontSize: 10,
                  fontWeight: 700,
                  background: "#fef3c7",
                  color: "#92400e",
                  borderRadius: 4,
                  padding: "2px 6px",
                }}>
                  Demo data · Backend pending
                </span>
              )}
            </div>
          </div>
        </section>
      ) : null}

      {/* Map + Action Center */}
      <div className="admin-overview-grid">
        <section>
          <h2 className="section-title">Network Map</h2>
          <div className="panel" style={{ padding: 14, overflow: "visible" }}>
            <AdminLogisticsMap backendMapPayload={backendView?.map_payload} />
          </div>
        </section>

        <section>
          <h2 className="section-title">Action Center</h2>
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
                    <div className="action-card-title">{item.title}</div>
                    <div className="action-card-count" style={{ color: item.color }}>
                      {item.count}
                    </div>
                  </div>
                </div>
                <p className="action-card-label">{item.label}</p>
                <Link href={item.href} className="action-card-btn">
                  {item.action} →
                </Link>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Recent Activity */}
      <section>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <h2 className="section-title" style={{ margin: 0 }}>Recent Activity</h2>
          <button
            className="secondary"
            style={{ fontSize: 13, padding: "6px 12px" }}
            onClick={() => setActivityExpanded((v) => !v)}
          >
            {activityExpanded ? "Show Less" : "View All Activity"}
          </button>
        </div>
        <div className="panel" style={{ padding: 0 }}>
          <table style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>Time</th>
                <th>Activity</th>
                <th>Actor</th>
                <th>Status</th>
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
  );
}
