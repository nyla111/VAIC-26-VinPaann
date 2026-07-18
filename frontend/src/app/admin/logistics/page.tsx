"use client";

import { useCallback, useMemo, useState } from "react";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DetailDrawer } from "@/components/admin/DetailDrawer";
import { ToastContainer, type ToastMessage } from "@/components/admin/Toast";
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
  const [tab, setTab] = useState<"overview" | "fleet" | "orders" | "performance">("overview");
  const provOrders = ORDERS.filter((o) => o.provider_id === provider.id);
  const tabs = ["overview", "fleet", "orders", "performance"] as const;

  return (
    <DetailDrawer open onClose={onClose} title={provider.name} subtitle={`${provider.province} · ${provider.modes.join(", ")}`} width={640}>
      <div className="drawer-tabs">
        {tabs.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`drawer-tab${tab === t ? " active" : ""}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="drawer-section-grid">
          <DrawerField label="Company" value={provider.name} />
          <DrawerField label="Contact" value={provider.contact} />
          <DrawerField label="Email" value={provider.email} />
          <DrawerField label="Province" value={provider.province} />
          <DrawerField label="Transport Modes" value={provider.modes.map((m) => <StatusBadge key={m} status={m} />)} />
          <DrawerField label="Status" value={<StatusBadge status={provider.status} />} />
          <DrawerField label="Fleet Size" value={provider.fleet_size} />
          <DrawerField label="Available Vehicles" value={provider.available_vehicles} />
          <DrawerField label="Active Orders" value={provider.active_orders} />
          <DrawerField label="Available Capacity" value={`${provider.available_capacity_ton}t`} />
          <DrawerField label="On-time Rate" value={`${provider.ontime_rate}%`} />
          <DrawerField label="Utilization" value={<Progress pct={provider.utilization} />} />
        </div>
      )}

      {tab === "fleet" && (
        <table>
          <thead>
            <tr>
              <th>Vehicle ID</th>
              <th>Type</th>
              <th>Capacity</th>
              <th>Status</th>
              <th>Current Order</th>
            </tr>
          </thead>
          <tbody>
            {provider.fleet.map((v) => (
              <tr key={v.id}>
                <td style={{ fontWeight: 600 }}>{v.id}</td>
                <td style={{ textTransform: "capitalize" }}>{v.type}</td>
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
          <div className="empty">No orders assigned to this provider.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Business</th>
                <th>Commodity</th>
                <th>Route</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {provOrders.map((o) => (
                <tr key={o.id}>
                  <td style={{ fontWeight: 600 }}>{o.id}</td>
                  <td style={{ fontSize: 13 }}>{o.business_name}</td>
                  <td>{o.commodity}</td>
                  <td style={{ fontSize: 12, color: "#64748b" }}>{o.recommended_route}</td>
                  <td><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}

      {tab === "performance" && (
        <div className="drawer-section-grid">
          <DrawerField label="On-time Delivery Rate" value={`${provider.ontime_rate}%`} />
          <DrawerField label="Fleet Utilization" value={`${provider.utilization}%`} />
          <DrawerField label="Active Orders" value={provider.active_orders} />
          <DrawerField label="Avg Capacity per Order" value={`${Math.round(provider.available_capacity_ton / Math.max(1, provider.active_orders))}t`} />
        </div>
      )}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 24, paddingTop: 16, borderTop: "1px solid #dbe2ea" }}>
        {provider.status === "inactive" ? (
          <button onClick={() => onStatusChange(provider.id, "available")} style={{ background: "#047857" }}>
            Activate
          </button>
        ) : (
          <button onClick={() => onStatusChange(provider.id, "inactive")} style={{ background: "#dc2626" }}>
            Deactivate
          </button>
        )}
        <button className="secondary">Edit Capacity</button>
        <button className="secondary">Contact Provider</button>
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
    addToast(`Provider ${status === "inactive" ? "deactivated" : "activated"} successfully.`, status === "inactive" ? "info" : "success");
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
          <h1>Logistics Partners</h1>
          <p className="page-subtitle">Fleet, assignments, and partner performance</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="secondary">Export</button>
          <button>+ Add Partner</button>
        </div>
      </div>

      {/* Summary */}
      <div className="summary-strip" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
        {[
          { label: "Total Partners", value: totals.total },
          { label: "Available", value: totals.available, color: "#047857" },
          { label: "Active Deliveries", value: totals.activeDeliveries, color: "#1d4ed8" },
          { label: "Available Vehicles", value: totals.availVehicles, color: "#6366f1" },
          { label: "Avg On-time Rate", value: `${totals.avgOntime}%`, color: "#047857" },
        ].map((c) => (
          <div key={c.label} style={{ background: "white", border: "1px solid #dbe2ea", borderRadius: 8, padding: 14 }}>
            <span style={{ color: "#64748b", fontSize: 13 }}>{c.label}</span>
            <div style={{ fontSize: 24, fontWeight: 700, color: c.color ?? "#111827", marginTop: 4 }}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="admin-filters">
        <select value={modeFilter} onChange={(e) => setModeFilter(e.target.value)}>
          {MODES.map((m) => (
            <option key={m} value={m}>{m === "all" ? "All Modes" : m.charAt(0).toUpperCase() + m.slice(1)}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          <option value="available">Available</option>
          <option value="busy">Busy</option>
          <option value="inactive">Inactive</option>
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
                <th>Provider</th>
                <th>Modes</th>
                <th>Fleet</th>
                <th>Avail. Vehicles</th>
                <th>Active Orders</th>
                <th>Avail. Cap.</th>
                <th>On-time</th>
                <th>Utilization</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={10} style={{ textAlign: "center", padding: 32, color: "#64748b" }}>
                    No logistics partners match the selected filters.
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
                        <button className="secondary" style={{ padding: "5px 10px", fontSize: 12 }} onClick={() => setSelected(p)}>
                          Details
                        </button>
                        {p.status === "inactive" ? (
                          <button style={{ padding: "5px 10px", fontSize: 12, background: "#047857" }} onClick={() => handleStatusChange(p.id, "available")}>
                            Activate
                          </button>
                        ) : (
                          <button style={{ padding: "5px 10px", fontSize: 12, background: "#dc2626" }} onClick={() => handleStatusChange(p.id, "inactive")}>
                            Deactivate
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
