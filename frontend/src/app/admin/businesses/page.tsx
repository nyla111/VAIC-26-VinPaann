"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useMemo, useState } from "react";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DetailDrawer } from "@/components/admin/DetailDrawer";
import { ToastContainer, type ToastMessage } from "@/components/admin/Toast";
import { BUSINESSES, ORDERS, type Business, type BusinessStatus } from "@/data/adminMockData";

function fmtVnd(n: number) {
  if (n === 0) return "—";
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(0)}M`;
  return n.toLocaleString();
}

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  danger,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <>
      <div
        onClick={onCancel}
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 300 }}
      />
      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%,-50%)",
          background: "white",
          borderRadius: 12,
          padding: 28,
          zIndex: 301,
          width: 420,
          boxShadow: "0 20px 60px rgba(0,0,0,0.2)",
        }}
      >
        <h2 style={{ margin: "0 0 8px", fontSize: 18 }}>{title}</h2>
        <p style={{ margin: "0 0 20px", color: "#64748b" }}>{message}</p>
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            style={danger ? { background: "#dc2626" } : {}}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </>
  );
}

function BusinessDrawer({
  biz,
  onClose,
  onStatusChange,
}: {
  biz: Business;
  onClose: () => void;
  onStatusChange: (id: string, status: BusinessStatus) => void;
}) {
  const [tab, setTab] = useState<"overview" | "orders" | "performance" | "activity">("overview");
  const orders = ORDERS.filter((o) => o.business_id === biz.id);

  const tabs = ["overview", "orders", "performance", "activity"] as const;
  const tabLabels: Record<typeof tabs[number], string> = {
    overview: "Overview",
    orders: "Orders",
    performance: "Performance",
    activity: "Activity",
  };

  return (
    <DetailDrawer open onClose={onClose} title={biz.name} subtitle={`${biz.province} · ${biz.status}`} width={600}>
      {/* Tabs */}
      <div className="drawer-tabs">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`drawer-tab${tab === t ? " active" : ""}`}
          >
            {tabLabels[t]}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="drawer-section-grid">
          <DrawerField label="Company" value={biz.name} />
          <DrawerField label="Contact" value={biz.contact} />
          <DrawerField label="Email" value={biz.email} />
          <DrawerField label="Phone" value={biz.phone} />
          <DrawerField label="Province" value={biz.province} />
          <DrawerField label="Address" value={biz.address} />
          <DrawerField label="Status" value={<StatusBadge status={biz.status} />} />
          <DrawerField label="Registered" value={biz.registered_at} />
          <DrawerField label="Total Orders" value={biz.total_orders} />
          <DrawerField label="Active Orders" value={biz.active_orders} />
          <DrawerField label="Total Volume" value={`${biz.total_volume_ton} ton`} />
          <DrawerField label="Total Spend" value={`${fmtVnd(biz.total_spend_vnd)} VND`} />
          <DrawerField label="Last Active" value={biz.last_active} />
        </div>
      )}

      {tab === "orders" && (
        orders.length === 0 ? (
          <div className="empty">No orders from this business yet.</div>
        ) : (
          <div style={{ overflow: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Commodity</th>
                  <th>Weight</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td style={{ fontWeight: 600 }}>{o.id}</td>
                    <td>{o.commodity}</td>
                    <td>{o.weight_ton}t</td>
                    <td><StatusBadge status={o.status} /></td>
                    <td style={{ color: "#64748b", fontSize: 13 }}>{o.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {tab === "performance" && (
        biz.total_orders === 0 ? (
          <div className="empty">No performance data — no orders placed yet.</div>
        ) : (
          <div className="drawer-section-grid">
            <DrawerField label="Avg Transport Cost" value={`${fmtVnd(biz.avg_cost_vnd)} VND`} />
            <DrawerField label="Avg Delivery Time" value={`${biz.avg_delivery_hours}h`} />
            <DrawerField label="On-time Delivery Rate" value={`${biz.ontime_rate}%`} />
            <DrawerField label="Savings from AI Routing" value={`${fmtVnd(biz.savings_vnd)} VND`} />
          </div>
        )
      )}

      {tab === "activity" && (
        <div className="empty" style={{ fontSize: 14, color: "#64748b" }}>
          Recent business activity is shown in the Overview → Recent Activity feed.
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 24, paddingTop: 16, borderTop: "1px solid #dbe2ea" }}>
        {biz.status === "pending" && (
          <button onClick={() => onStatusChange(biz.id, "active")} style={{ background: "#047857" }}>
            Approve Business
          </button>
        )}
        {biz.status === "active" && (
          <button onClick={() => onStatusChange(biz.id, "suspended")} style={{ background: "#dc2626" }}>
            Suspend
          </button>
        )}
        {biz.status === "suspended" && (
          <button onClick={() => onStatusChange(biz.id, "active")} style={{ background: "#047857" }}>
            Reactivate
          </button>
        )}
        <button className="secondary">Edit</button>
        <button className="secondary">View Orders →</button>
      </div>
    </DetailDrawer>
  );
}

function DrawerField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gap: 2 }}>
      <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>{label}</span>
      <div style={{ fontWeight: 500 }}>{value}</div>
    </div>
  );
}

const PROVINCES = [...new Set(BUSINESSES.map((b) => b.province))].sort();

function BusinessesContent() {
  const searchParams = useSearchParams();
  const initialFilter = searchParams.get("filter") || "all";

  const [businesses, setBusinesses] = useState<Business[]>(BUSINESSES);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>(initialFilter === "pending" ? "pending" : "all");
  const [provinceFilter, setProvinceFilter] = useState("all");
  const [selected, setSelected] = useState<Business | null>(null);
  const [confirm, setConfirm] = useState<{ biz: Business; next: BusinessStatus } | null>(null);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((message: string, type: ToastMessage["type"] = "success") => {
    const id = `${Date.now()}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const filtered = useMemo(() => {
    return businesses.filter((b) => {
      if (search && !b.name.toLowerCase().includes(search.toLowerCase()) && !b.contact.toLowerCase().includes(search.toLowerCase())) return false;
      if (statusFilter !== "all" && b.status !== statusFilter) return false;
      if (provinceFilter !== "all" && b.province !== provinceFilter) return false;
      return true;
    });
  }, [businesses, search, statusFilter, provinceFilter]);

  const counts = {
    total: businesses.length,
    active: businesses.filter((b) => b.status === "active").length,
    pending: businesses.filter((b) => b.status === "pending").length,
    suspended: businesses.filter((b) => b.status === "suspended").length,
  };

  function handleStatusChange(id: string, next: BusinessStatus) {
    const biz = businesses.find((b) => b.id === id);
    if (!biz) return;
    if (next === "suspended") {
      setConfirm({ biz, next });
    } else {
      applyStatusChange(id, next);
    }
  }

  function applyStatusChange(id: string, next: BusinessStatus) {
    setBusinesses((prev) => prev.map((b) => b.id === id ? { ...b, status: next } : b));
    if (selected?.id === id) setSelected((prev) => prev ? { ...prev, status: next } : null);
    const labels: Record<BusinessStatus, string> = {
      active: "approved",
      pending: "set to pending",
      suspended: "suspended",
    };
    addToast(`Business ${labels[next]} successfully.`, next === "suspended" ? "error" : "success");
    setConfirm(null);
  }

  const actionLabels: Record<BusinessStatus, string> = { active: "Approve", pending: "Reset", suspended: "Confirm Suspend" };

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>Businesses</h1>
          <p className="page-subtitle">Manage platform businesses and their orders</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="secondary">Export</button>
          <button>+ Add Business</button>
        </div>
      </div>

      {/* Summary strip */}
      <div className="summary-strip" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <SummaryCard label="Total Businesses" value={counts.total} />
        <SummaryCard label="Active" value={counts.active} color="#047857" />
        <SummaryCard label="Pending Approval" value={counts.pending} color="#d97706" />
        <SummaryCard label="Suspended" value={counts.suspended} color="#dc2626" />
      </div>

      {/* Filters */}
      <div className="admin-filters">
        <input
          className="filter-input"
          placeholder="Search by name or contact…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="pending">Pending</option>
          <option value="suspended">Suspended</option>
        </select>
        <select value={provinceFilter} onChange={(e) => setProvinceFilter(e.target.value)}>
          <option value="all">All Provinces</option>
          {PROVINCES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        {(search || statusFilter !== "all" || provinceFilter !== "all") && (
          <button className="secondary" onClick={() => { setSearch(""); setStatusFilter("all"); setProvinceFilter("all"); }}>
            Clear Filters
          </button>
        )}
        <span style={{ marginLeft: "auto", color: "#64748b", fontSize: 13 }}>
          {filtered.length} of {businesses.length}
        </span>
      </div>

      {/* Table */}
      <div className="panel" style={{ padding: 0 }}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Business</th>
                <th>Contact</th>
                <th>Province</th>
                <th>Orders (Total / Active)</th>
                <th>Volume</th>
                <th>Total Spend</th>
                <th>Last Active</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: "center", padding: 32, color: "#64748b" }}>
                    No businesses match the selected filters.
                  </td>
                </tr>
              ) : (
                filtered.map((biz) => (
                  <tr key={biz.id} className="table-row-hover">
                    <td>
                      <div style={{ fontWeight: 600 }}>{biz.name}</div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>{biz.id}</div>
                    </td>
                    <td>
                      <div>{biz.contact}</div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>{biz.email}</div>
                    </td>
                    <td>{biz.province}</td>
                    <td>{biz.total_orders} / {biz.active_orders}</td>
                    <td>{biz.total_volume_ton}t</td>
                    <td>{fmtVnd(biz.total_spend_vnd)} VND</td>
                    <td style={{ color: "#64748b", fontSize: 13 }}>{biz.last_active}</td>
                    <td><StatusBadge status={biz.status} /></td>
                    <td>
                      <div style={{ display: "flex", gap: 6, flexWrap: "nowrap" }}>
                        <button
                          className="secondary"
                          style={{ padding: "5px 10px", fontSize: 12 }}
                          onClick={() => setSelected(biz)}
                        >
                          Details
                        </button>
                        {biz.status === "pending" && (
                          <button
                            style={{ padding: "5px 10px", fontSize: 12, background: "#047857" }}
                            onClick={() => handleStatusChange(biz.id, "active")}
                          >
                            Approve
                          </button>
                        )}
                        {biz.status === "active" && (
                          <button
                            style={{ padding: "5px 10px", fontSize: 12, background: "#dc2626" }}
                            onClick={() => handleStatusChange(biz.id, "suspended")}
                          >
                            Suspend
                          </button>
                        )}
                        {biz.status === "suspended" && (
                          <button
                            style={{ padding: "5px 10px", fontSize: 12, background: "#047857" }}
                            onClick={() => handleStatusChange(biz.id, "active")}
                          >
                            Reactivate
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

      {/* Drawer */}
      {selected && (
        <BusinessDrawer
          biz={businesses.find((b) => b.id === selected.id) ?? selected}
          onClose={() => setSelected(null)}
          onStatusChange={handleStatusChange}
        />
      )}

      {/* Confirm dialog */}
      <ConfirmDialog
        open={!!confirm}
        title="Suspend Business"
        message={`Are you sure you want to suspend "${confirm?.biz.name}"? They will lose access to the platform.`}
        confirmLabel={confirm ? actionLabels[confirm.next] : "Confirm"}
        danger
        onConfirm={() => confirm && applyStatusChange(confirm.biz.id, confirm.next)}
        onCancel={() => setConfirm(null)}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ background: "white", border: "1px solid #dbe2ea", borderRadius: 8, padding: 14 }}>
      <span style={{ color: "#64748b", fontSize: 13 }}>{label}</span>
      <div style={{ fontSize: 28, fontWeight: 700, color: color ?? "#111827", marginTop: 4 }}>{value}</div>
    </div>
  );
}

export default function BusinessesPage() {
  return (
    <Suspense fallback={<div className="admin-page"><div className="empty">Loading…</div></div>}>
      <BusinessesContent />
    </Suspense>
  );
}
