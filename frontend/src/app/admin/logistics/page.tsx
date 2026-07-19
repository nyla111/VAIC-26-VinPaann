"use client";

import { useCallback, useMemo, useState } from "react";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DetailDrawer } from "@/components/admin/DetailDrawer";
import { ToastContainer, type ToastMessage } from "@/components/admin/Toast";
import { useLanguage } from "@/context/LanguageContext";
import { modeLabel, routeLabel } from "@/lib/labels";
import { PROVIDERS, ORDERS, type LogisticsProvider, type ProviderStatus } from "@/data/adminMockData";

function Progress({ pct, color = "#1d4ed8" }: { pct: number; color?: string }) {
  return (
    <div style={{ background: "#f1f5f9", borderRadius: 999, height: 8, width: "100%", minWidth: 80 }}>
      <div style={{ width: `${Math.min(100, pct)}%`, height: "100%", borderRadius: 999, background: color }} />
    </div>
  );
}

function ProviderDrawer({
  provider,
  onClose,
  onStatusChange,
}: {
  provider: LogisticsProvider;
  onClose: () => void;
  onStatusChange: (id: string, status: ProviderStatus) => void;
}) {
  const { language, t } = useLanguage();
  const [tab, setTab] = useState<"overview" | "fleet" | "orders" | "performance">("overview");
  const provOrders = ORDERS.filter((o) => o.provider_id === provider.id);
  const tabs = ["overview", "fleet", "orders", "performance"] as const;

  return (
    <DetailDrawer open onClose={onClose} title={provider.name} subtitle={`${provider.province} · ${provider.modes.map((mode) => modeLabel(mode, language)).join(", ")}`} width={640}>
      <div className="drawer-tabs">
        {tabs.map((tabKey) => (
          <button key={tabKey} onClick={() => setTab(tabKey)} className={`drawer-tab${tab === tabKey ? " active" : ""}`}>
            {tabKey === "overview" ? t("common.overview", "Overview") : tabKey === "fleet" ? t("common.fleet", "Fleet") : tabKey === "orders" ? t("common.orders") : t("common.performance", "Performance")}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="drawer-section-grid">
          <DrawerField label={t("businesses.company")} value={provider.name} />
          <DrawerField label={t("logistics.contact")} value={provider.contact} />
          <DrawerField label="Email" value={provider.email} />
          <DrawerField label={t("businesses.province")} value={provider.province} />
          <DrawerField label={t("logistics.modes", "Transport modes")} value={provider.modes.map((m) => <StatusBadge key={m} status={m} />)} />
          <DrawerField label={t("common.status")} value={<StatusBadge status={provider.status} />} />
          <DrawerField label={t("logistics.fleet_size", "Fleet size")} value={provider.fleet_size} />
          <DrawerField label={t("logistics.available_vehicles")} value={provider.available_vehicles} />
          <DrawerField label={t("common.orders")} value={provider.active_orders} />
          <DrawerField label={t("common.capacity")} value={`${provider.available_capacity_ton}t`} />
          <DrawerField label={t("logistics.ontime", "On-time rate")} value={`${provider.ontime_rate}%`} />
          <DrawerField label={t("logistics.utilization", "Utilization")} value={<Progress pct={provider.utilization} />} />
        </div>
      )}

      {tab === "fleet" && (
        <table>
          <thead>
            <tr>
              <th>{t("logistics.vehicle_id")}</th><th>{t("common.type", "Type")}</th><th>{t("common.capacity")}</th><th>{t("common.status")}</th><th>{language === "vi" ? "Đơn hiện tại" : "Current order"}</th>
            </tr>
          </thead>
          <tbody>
            {provider.fleet.map((v) => (
              <tr key={v.id}>
                <td style={{ fontWeight: 600 }}>{v.id}</td>
                <td style={{ textTransform: "capitalize" }}>{modeLabel(v.type, language)}</td>
                <td>{v.capacity_ton}t</td>
                <td><StatusBadge status={v.status} /></td>
                <td style={{ color: "#64748b", fontSize: 13 }}>{v.current_order ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "orders" && (
        provOrders.length === 0 ? (
          <div className="empty">{t("logistics.no_orders", "No orders assigned to this provider.")}</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t("common.orders")}</th><th>{t("common.business")}</th><th>{t("common.commodity")}</th><th>{t("common.route")}</th><th>{t("common.status")}</th>
              </tr>
            </thead>
            <tbody>
              {provOrders.map((o) => (
                <tr key={o.id}>
                  <td style={{ fontWeight: 600 }}>{o.id}</td>
                  <td style={{ fontSize: 13 }}>{o.business_name}</td>
                  <td>{o.commodity}</td>
                  <td style={{ fontSize: 12, color: "#64748b" }}>{routeLabel(o.recommended_route, language)}</td>
                  <td><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}

      {tab === "performance" && (
        <div className="drawer-section-grid">
          <DrawerField label={t("logistics.ontime")} value={`${provider.ontime_rate}%`} />
          <DrawerField label={t("logistics.fleet_utilization")} value={`${provider.utilization}%`} />
          <DrawerField label={t("logistics.active_orders")} value={provider.active_orders} />
          <DrawerField label={t("logistics.avg_capacity")} value={`${Math.round(provider.available_capacity_ton / Math.max(1, provider.active_orders))}t`} />
        </div>
      )}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 24, paddingTop: 16, borderTop: "1px solid #dbe2ea" }}>
        {provider.status === "inactive" ? (
          <button onClick={() => onStatusChange(provider.id, "available")} style={{ background: "#047857" }}>
            {t("logistics.activate")}
          </button>
        ) : (
          <button onClick={() => onStatusChange(provider.id, "inactive")} style={{ background: "#dc2626" }}>
            {t("logistics.deactivate")}
          </button>
        )}
        <button className="secondary">{t("logistics.edit_capacity", "Edit capacity")}</button>
        <button className="secondary">{t("logistics.contact", "Contact provider")}</button>
      </div>
    </DetailDrawer>
  );
}

function DrawerField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gap: 3 }}>
      <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>{label}</span>
      <div style={{ fontWeight: 500 }}>{value}</div>
    </div>
  );
}

const MODES = ["all", "road", "waterway", "multimodal"];

export default function LogisticsPage() {
  const { language, t } = useLanguage();
  const [providers, setProviders] = useState<LogisticsProvider[]>(PROVIDERS);
  const [selected, setSelected] = useState<LogisticsProvider | null>(null);
  const [modeFilter, setModeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((message: string, type: ToastMessage["type"] = "success") => {
    const id = `${Date.now()}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);
  const dismissToast = useCallback((id: string) => setToasts((p) => p.filter((t) => t.id !== id)), []);

  const filtered = useMemo(() => {
    return providers.filter((p) => {
      if (modeFilter !== "all" && !p.modes.includes(modeFilter as "road" | "waterway" | "multimodal")) return false;
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      return true;
    });
  }, [providers, modeFilter, statusFilter]);

  function handleStatusChange(id: string, status: ProviderStatus) {
    setProviders((prev) => prev.map((p) => p.id === id ? { ...p, status } : p));
    if (selected?.id === id) setSelected((prev) => prev ? { ...prev, status } : null);
    addToast(`${status === "inactive" ? t("logistics.deactivated") : t("logistics.activated")}.`, status === "inactive" ? "info" : "success");
  }

  const totals = {
    total: providers.length,
    available: providers.filter((p) => p.status === "available").length,
    activeDeliveries: providers.reduce((s, p) => s + p.active_orders, 0),
    availVehicles: providers.reduce((s, p) => s + p.available_vehicles, 0),
    avgOntime: Math.round(providers.reduce((s, p) => s + p.ontime_rate, 0) / providers.length),
  };

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>{t("logistics.title")}</h1>
          <p className="page-subtitle">{t("logistics.subtitle")}</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="secondary">{t("logistics.export")}</button>
          <button>+ {t("logistics.add")}</button>
        </div>
      </div>

      <div className="admin-two-column-layout">
        {/* Left Column: Filters and Table */}
        <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
          {/* Filters */}
          <div className="admin-filters">
            <select value={modeFilter} onChange={(e) => setModeFilter(e.target.value)}>
              {MODES.map((m) => (
                <option key={m} value={m}>{m === "all" ? t("logistics.all_modes") : modeLabel(m, language)}</option>
              ))}
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="all">{t("logistics.all_statuses")}</option><option value="available">{t("fleet.available")}</option><option value="busy">{t("logistics.busy")}</option><option value="inactive">{t("logistics.inactive")}</option>
            </select>
            <span style={{ marginLeft: "auto", color: "#64748b", fontSize: 13 }}>
              {filtered.length} of {providers.length}
            </span>
          </div>

          {/* Table */}
          <div className="panel" style={{ padding: 0 }}>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("common.provider")}</th><th>{t("common.mode")}</th><th>{t("common.fleet")}</th><th>{t("fleet.available_vehicles")}</th><th>{t("logistics.active_orders")}</th><th>{t("common.capacity")}</th><th>{t("logistics.ontime")}</th><th>{t("logistics.fleet_utilization")}</th><th>{t("common.status")}</th><th>{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ textAlign: "center", padding: 32, color: "#64748b" }}>
                        {t("logistics.no_match")}
                      </td>
                    </tr>
                  ) : (
                    filtered.map((p) => (
                      <tr key={p.id} className="table-row-hover">
                        <td>
                          <div style={{ fontWeight: 600 }}>{p.name}</div>
                          <div style={{ fontSize: 12, color: "#64748b" }}>{p.province}</div>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                            {p.modes.map((m) => <StatusBadge key={m} status={m} />)}
                          </div>
                        </td>
                        <td>{p.fleet_size}</td>
                        <td>{p.available_vehicles}</td>
                        <td>{p.active_orders}</td>
                        <td>{p.available_capacity_ton}t</td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <Progress pct={p.ontime_rate} color={p.ontime_rate >= 90 ? "#047857" : p.ontime_rate >= 80 ? "#d97706" : "#dc2626"} />
                            <span style={{ fontSize: 12, fontWeight: 600, minWidth: 36 }}>{p.ontime_rate}%</span>
                          </div>
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <Progress pct={p.utilization} color={p.utilization >= 80 ? "#dc2626" : "#1d4ed8"} />
                            <span style={{ fontSize: 12, fontWeight: 600, minWidth: 36 }}>{p.utilization}%</span>
                          </div>
                        </td>
                        <td><StatusBadge status={p.status} /></td>
                        <td>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button className="secondary admin-btn-details" style={{ padding: "5px 10px", fontSize: 12 }} onClick={() => setSelected(p)}>
                              {t("logistics.details")}
                            </button>
                            {p.status === "inactive" ? (
                              <button className="admin-btn-action" style={{ padding: "5px 10px", fontSize: 12, background: "#047857" }} onClick={() => handleStatusChange(p.id, "available")}>
                                {t("logistics.activate")}
                              </button>
                            ) : (
                              <button className="admin-btn-action" style={{ padding: "5px 10px", fontSize: 12, background: "#dc2626" }} onClick={() => handleStatusChange(p.id, "inactive")}>
                                {t("logistics.deactivate")}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column: Summaries stacked vertically */}
        <div className="admin-summary-column">
          <h2 className="section-title" style={{ margin: 0 }}>{language === "vi" ? "Thống kê" : "Summary"}</h2>
          {[
            { label: t("logistics.total"), value: totals.total },
            { label: t("logistics.available"), value: totals.available, color: "#047857" },
            { label: t("logistics.active_deliveries"), value: totals.activeDeliveries, color: "#1d4ed8" },
            { label: t("logistics.available_vehicles"), value: totals.availVehicles, color: "#6366f1" },
            { label: t("logistics.avg_ontime"), value: `${totals.avgOntime}%`, color: "#047857" },
          ].map((c) => (
            <div key={c.label} style={{ background: "white", border: "1px solid #dbe2ea", borderRadius: 8, padding: 14 }}>
              <span style={{ color: "#64748b", fontSize: 13 }}>{c.label}</span>
              <div style={{ fontSize: 24, fontWeight: 700, color: c.color ?? "#111827", marginTop: 4 }}>{c.value}</div>
            </div>
          ))}
        </div>
      </div>

      {selected && (
        <ProviderDrawer
          provider={providers.find((p) => p.id === selected.id) ?? selected}
          onClose={() => setSelected(null)}
          onStatusChange={handleStatusChange}
        />
      )}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
