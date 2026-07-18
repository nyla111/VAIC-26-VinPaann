"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { DetailDrawer } from "@/components/admin/DetailDrawer";
import { ToastContainer, type ToastMessage } from "@/components/admin/Toast";
import { ORDERS, PROVIDERS, type Order, type OrderStatus } from "@/data/adminMockData";

const ROUTE_NAMES: Record<string, string> = {
  A_DIRECT_ROAD: "A – Direct Road",
  B_ROAD_VIA_CT: "B – Road via Can Tho",
  C_WATER_ROAD_VIA_CT: "C – Water → Road via CT",
  D_WATER_VIA_CT: "D – Full Waterway via CT",
  E_ROAD_WATER_VIA_CT: "E – Road → Water via CT",
};

function fmtVnd(n: number) {
  return (n / 1_000_000).toFixed(0) + "M";
}

const QUICK_FILTERS = [
  { key: "awaiting_assignment", label: "Unassigned" },
  { key: "delayed", label: "Delayed" },
  { key: "due_today", label: "Due Today" },
  { key: "in_transit", label: "In Transit" },
];

const ALL_STATUSES: OrderStatus[] = [
  "pending", "optimizing", "awaiting_assignment", "assigned",
  "in_transit", "delivered", "delayed", "cancelled",
];

function OrderTimeline({ events }: { events: Order["timeline"] }) {
  return (
    <div style={{ display: "grid", gap: 0 }}>
      {events.map((ev, i) => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", paddingBottom: 12, position: "relative" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
            <div style={{
              width: 16, height: 16, borderRadius: "50%",
              background: ev.done ? "#047857" : "#dbe2ea",
              border: `2px solid ${ev.done ? "#047857" : "#94a3b8"}`,
              zIndex: 1, flexShrink: 0,
            }} />
            {i < events.length - 1 && (
              <div style={{ width: 2, flex: 1, minHeight: 20, background: ev.done ? "#bbf7d0" : "#e2e8f0", marginTop: 2 }} />
            )}
          </div>
          <div style={{ paddingBottom: 4 }}>
            <div style={{ fontWeight: ev.done ? 600 : 400, color: ev.done ? "#111827" : "#64748b", fontSize: 14 }}>
              {ev.event}
            </div>
            <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>{ev.time}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function RouteOptionsPanel({ order, onAccept }: { order: Order; onAccept: (code: string) => void }) {
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {order.route_options.map((r) => (
        <div key={r.code} style={{
          border: `1.5px solid ${r.recommended ? "#047857" : "#dbe2ea"}`,
          borderRadius: 8,
          padding: 14,
          background: r.recommended ? "#f0fdf4" : "white",
          opacity: r.available ? 1 : 0.5,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8, marginBottom: 6 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>{r.code}</div>
              <div style={{ fontSize: 13, color: "#64748b" }}>{r.name}</div>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
              {r.recommended && (
                <span style={{
                  background: "#dcfce7", color: "#166534",
                  fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 999,
                }}>
                  ✓ AI Recommended
                </span>
              )}
              <StatusBadge status={r.risk === "low" ? "available" : r.risk === "medium" ? "pending" : "delayed"} label={r.risk + " risk"} />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, fontSize: 13 }}>
            <div><span style={{ color: "#64748b" }}>Cost</span><div style={{ fontWeight: 600 }}>{fmtVnd(r.cost_vnd)}M VND</div></div>
            <div><span style={{ color: "#64748b" }}>Duration</span><div style={{ fontWeight: 600 }}>{r.duration_hours}h</div></div>
            <div><span style={{ color: "#64748b" }}>Modes</span><div style={{ fontWeight: 600 }}>{r.modes.join(" + ")}</div></div>
            <div><span style={{ color: "#64748b" }}>Transfers</span><div style={{ fontWeight: 600 }}>{r.transfers}</div></div>
          </div>
          {r.available && (
            <div style={{ marginTop: 10 }}>
              <button
                onClick={() => onAccept(r.code)}
                style={{
                  padding: "6px 14px", fontSize: 12,
                  background: r.recommended ? "#047857" : "#1d4ed8",
                }}
              >
                {r.recommended ? "Accept Recommendation" : "Select This Route"}
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function AssignmentPanel({
  order,
  onAssign,
  onToast,
}: {
  order: Order;
  onAssign: (orderId: string, providerId: string) => void;
  onToast: (msg: string, type: ToastMessage["type"]) => void;
}) {
  const [selectingProvider, setSelectingProvider] = useState(false);
  const [selectedPid, setSelectedPid] = useState("");
  const available = PROVIDERS.filter((p) => p.status !== "inactive");

  function doAssign() {
    if (!selectedPid) return;
    onAssign(order.id, selectedPid);
    setSelectingProvider(false);
    onToast("Provider assigned successfully.", "success");
  }

  if (selectingProvider) {
    return (
      <div>
        <h4 style={{ marginBottom: 12 }}>Select Provider</h4>
        <div style={{ display: "grid", gap: 8 }}>
          {available.map((p) => (
            <label key={p.id} style={{ display: "flex", gap: 10, alignItems: "center", cursor: "pointer", padding: "10px 14px", border: `1.5px solid ${selectedPid === p.id ? "#1d4ed8" : "#dbe2ea"}`, borderRadius: 8, background: selectedPid === p.id ? "#eff6ff" : "white" }}>
              <input type="radio" name="provider" value={p.id} checked={selectedPid === p.id} onChange={() => setSelectedPid(p.id)} />
              <div>
                <div style={{ fontWeight: 600 }}>{p.name}</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>{p.modes.join(", ")} · {p.available_vehicles} available · {p.ontime_rate}% on-time</div>
              </div>
              <StatusBadge status={p.status} />
            </label>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <button onClick={doAssign} disabled={!selectedPid}>Confirm Assignment</button>
          <button className="secondary" onClick={() => setSelectingProvider(false)}>Cancel</button>
        </div>
      </div>
    );
  }

  return (
    <div className="drawer-section-grid">
      <div>
        <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>Assigned Provider</span>
        <div style={{ fontWeight: 600, marginTop: 3 }}>{order.provider_name ?? <span style={{ color: "#64748b" }}>Not assigned</span>}</div>
      </div>
      <div>
        <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>Route</span>
        <div style={{ fontWeight: 600, marginTop: 3 }}>{ROUTE_NAMES[order.recommended_route ?? ""] ?? order.recommended_route ?? "—"}</div>
      </div>
      <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, marginTop: 8 }}>
        {!order.provider_id ? (
          <button onClick={() => setSelectingProvider(true)}>Assign Provider</button>
        ) : (
          <button onClick={() => setSelectingProvider(true)} className="secondary">Change Assignment</button>
        )}
        {order.provider_id && <button className="secondary">Contact Provider</button>}
      </div>
    </div>
  );
}

function OrderDrawer({
  order,
  onClose,
  onAssign,
  onRouteAccept,
  onToast,
}: {
  order: Order;
  onClose: () => void;
  onAssign: (orderId: string, providerId: string) => void;
  onRouteAccept: (orderId: string, route: string) => void;
  onToast: (msg: string, type: ToastMessage["type"]) => void;
}) {
  const [tab, setTab] = useState<"info" | "route" | "assignment" | "timeline">("info");
  const tabs = ["info", "route", "assignment", "timeline"] as const;
  const labels = { info: "Order Info", route: "Route Options", assignment: "Assignment", timeline: "Timeline" };

  return (
    <DetailDrawer open onClose={onClose} title={order.id} subtitle={`${order.business_name} · ${order.commodity}`} width={680}>
      <div className="drawer-tabs">
        {tabs.map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`drawer-tab${tab === t ? " active" : ""}`}>
            {labels[t]}
          </button>
        ))}
      </div>

      {tab === "info" && (
        <div className="drawer-section-grid">
          <Field label="Business" value={order.business_name} />
          <Field label="Commodity" value={order.commodity} />
          <Field label="Weight" value={`${order.weight_ton}t`} />
          <Field label="Origin" value={order.origin} />
          <Field label="Destination" value={order.destination} />
          <Field label="Deadline" value={order.deadline} />
          <Field label="Created" value={order.created_at} />
          <Field label="Status" value={<StatusBadge status={order.status} />} />
          <Field label="Est. Cost" value={`${fmtVnd(order.estimated_cost_vnd)} VND`} />
          <Field label="Recommended Route" value={ROUTE_NAMES[order.recommended_route ?? ""] ?? order.recommended_route ?? "—"} />
        </div>
      )}

      {tab === "route" && (
        <RouteOptionsPanel
          order={order}
          onAccept={(code) => {
            onRouteAccept(order.id, code);
            onToast(`Route ${code} accepted for ${order.id}.`, "success");
          }}
        />
      )}

      {tab === "assignment" && (
        <AssignmentPanel order={order} onAssign={onAssign} onToast={onToast} />
      )}

      {tab === "timeline" && <OrderTimeline events={order.timeline} />}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 24, paddingTop: 16, borderTop: "1px solid #dbe2ea" }}>
        <button className="secondary" onClick={() => setTab("route")}>View Route Options</button>
        <button className="secondary" onClick={() => setTab("assignment")}>Assign Provider</button>
        <button className="secondary" onClick={() => { onToast("Re-optimization queued.", "info"); }}>Re-optimize</button>
      </div>
    </DetailDrawer>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gap: 3 }}>
      <span style={{ fontSize: 12, color: "#64748b", fontWeight: 600, textTransform: "uppercase" }}>{label}</span>
      <div style={{ fontWeight: 500 }}>{value}</div>
    </div>
  );
}

function OrdersContent() {
  const searchParams = useSearchParams();
  const initFilter = searchParams.get("filter") ?? "all";

  const [orders, setOrders] = useState<Order[]>(ORDERS);
  const [selected, setSelected] = useState<Order | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState(ALL_STATUSES.includes(initFilter as OrderStatus) ? initFilter : "all");
  const [commodityFilter, setCommodityFilter] = useState("all");
  const [quickFilter, setQuickFilter] = useState(
    initFilter === "awaiting_assignment" ? "awaiting_assignment" : ""
  );
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((message: string, type: ToastMessage["type"] = "success") => {
    setToasts((p) => [...p, { id: `${Date.now()}-${Math.random()}`, message, type }]);
  }, []);
  const dismissToast = useCallback((id: string) => setToasts((p) => p.filter((t) => t.id !== id)), []);

  const commodities = useMemo(() => [...new Set(ORDERS.map((o) => o.commodity))].sort(), []);

  const filtered = useMemo(() => {
    return orders.filter((o) => {
      if (search && !o.id.toLowerCase().includes(search.toLowerCase()) && !o.business_name.toLowerCase().includes(search.toLowerCase())) return false;
      if (statusFilter !== "all" && o.status !== statusFilter) return false;
      if (commodityFilter !== "all" && o.commodity !== commodityFilter) return false;
      if (quickFilter === "awaiting_assignment" && o.status !== "awaiting_assignment") return false;
      if (quickFilter === "delayed" && o.status !== "delayed") return false;
      if (quickFilter === "due_today" && o.deadline !== "2026-07-18") return false;
      if (quickFilter === "in_transit" && o.status !== "in_transit") return false;
      return true;
    });
  }, [orders, search, statusFilter, commodityFilter, quickFilter]);

  const counts = {
    total: orders.length,
    pending: orders.filter((o) => o.status === "pending").length,
    unassigned: orders.filter((o) => o.status === "awaiting_assignment").length,
    in_transit: orders.filter((o) => o.status === "in_transit").length,
    delayed: orders.filter((o) => o.status === "delayed").length,
    delivered_today: orders.filter((o) => o.status === "delivered" && o.deadline === "2026-07-17").length,
  };

  function toggleRow(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function toggleAll() {
    if (selectedIds.size === filtered.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(filtered.map((o) => o.id)));
  }

  function handleAssign(orderId: string, providerId: string) {
    const prov = PROVIDERS.find((p) => p.id === providerId);
    setOrders((prev) => prev.map((o) =>
      o.id === orderId
        ? { ...o, provider_id: providerId, provider_name: prov?.name ?? null, status: "assigned" }
        : o
    ));
    if (selected?.id === orderId) {
      setSelected((prev) => prev ? { ...prev, provider_id: providerId, provider_name: prov?.name ?? null, status: "assigned" } : null);
    }
  }

  function handleRouteAccept(orderId: string, route: string) {
    setOrders((prev) => prev.map((o) =>
      o.id === orderId ? { ...o, recommended_route: route } : o
    ));
  }

  function bulkStatusUpdate(status: OrderStatus) {
    setOrders((prev) => prev.map((o) =>
      selectedIds.has(o.id) ? { ...o, status } : o
    ));
    addToast(`${selectedIds.size} order(s) updated to "${status}".`, "success");
    setSelectedIds(new Set());
  }

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>Orders</h1>
          <p className="page-subtitle">Track, assign, and manage all platform orders</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {selectedIds.size > 0 && (
            <>
              <button className="secondary" onClick={() => bulkStatusUpdate("assigned")}>
                Assign Selected ({selectedIds.size})
              </button>
              <button className="secondary" onClick={() => bulkStatusUpdate("cancelled")} style={{ color: "#dc2626" }}>
                Cancel Selected
              </button>
            </>
          )}
          <button className="secondary">Export</button>
          <button>+ Create Order</button>
        </div>
      </div>

      {/* Summary */}
      <div className="summary-strip" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
        <SummaryCard label="Total" value={counts.total} />
        <SummaryCard label="Pending" value={counts.pending} color="#64748b" />
        <SummaryCard label="Unassigned" value={counts.unassigned} color="#d97706" />
        <SummaryCard label="In Transit" value={counts.in_transit} color="#1d4ed8" />
        <SummaryCard label="Delayed" value={counts.delayed} color="#dc2626" />
        <SummaryCard label="Delivered Today" value={counts.delivered_today} color="#047857" />
      </div>

      {/* Quick filters */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          onClick={() => setQuickFilter("")}
          style={{
            padding: "6px 14px",
            fontSize: 13,
            background: quickFilter === "" ? "#1d4ed8" : "#e5e7eb",
            color: quickFilter === "" ? "white" : "#374151",
            borderRadius: 999,
          }}
        >
          All
        </button>
        {QUICK_FILTERS.map((qf) => (
          <button
            key={qf.key}
            onClick={() => setQuickFilter(quickFilter === qf.key ? "" : qf.key)}
            style={{
              padding: "6px 14px",
              fontSize: 13,
              background: quickFilter === qf.key ? "#1d4ed8" : "#e5e7eb",
              color: quickFilter === qf.key ? "white" : "#374151",
              borderRadius: 999,
            }}
          >
            {qf.label}
          </button>
        ))}
      </div>

      {/* Advanced filters */}
      <div className="admin-filters">
        <input className="filter-input" placeholder="Search order ID or business…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          {ALL_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select value={commodityFilter} onChange={(e) => setCommodityFilter(e.target.value)}>
          <option value="all">All Commodities</option>
          {commodities.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {(search || statusFilter !== "all" || commodityFilter !== "all" || quickFilter) && (
          <button className="secondary" onClick={() => { setSearch(""); setStatusFilter("all"); setCommodityFilter("all"); setQuickFilter(""); }}>
            Clear Filters
          </button>
        )}
        <span style={{ marginLeft: "auto", color: "#64748b", fontSize: 13 }}>
          {filtered.length} of {orders.length}
          {selectedIds.size > 0 && ` · ${selectedIds.size} selected`}
        </span>
      </div>

      {/* Table */}
      <div className="panel" style={{ padding: 0 }}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox" checked={selectedIds.size === filtered.length && filtered.length > 0} onChange={toggleAll} />
                </th>
                <th>Order ID</th>
                <th>Business</th>
                <th>Commodity</th>
                <th>Origin → Dest.</th>
                <th>Weight</th>
                <th>Deadline</th>
                <th>Route</th>
                <th>Provider</th>
                <th>Cost</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={12} style={{ textAlign: "center", padding: 32, color: "#64748b" }}>
                    {quickFilter === "delayed" ? "No delayed orders — all shipments on schedule." :
                     quickFilter === "awaiting_assignment" ? "No unassigned orders." :
                     "No orders match the selected filters."}
                  </td>
                </tr>
              ) : (
                filtered.map((o) => {
                  const isDelayed = o.status === "delayed";
                  const isUnassigned = o.status === "awaiting_assignment";
                  return (
                    <tr
                      key={o.id}
                      className="table-row-hover"
                      style={{ background: selectedIds.has(o.id) ? "#eff6ff" : isDelayed ? "#fff7f7" : undefined }}
                    >
                      <td>
                        <input type="checkbox" checked={selectedIds.has(o.id)} onChange={() => toggleRow(o.id)} />
                      </td>
                      <td>
                        <button
                          onClick={() => setSelected(o)}
                          style={{ background: "none", color: "#1d4ed8", fontWeight: 700, padding: 0, textDecoration: "underline", cursor: "pointer", fontSize: "inherit" }}
                        >
                          {o.id}
                        </button>
                      </td>
                      <td style={{ fontSize: 13 }}>{o.business_name}</td>
                      <td>{o.commodity}</td>
                      <td style={{ fontSize: 12, color: "#64748b" }}>{o.origin} → {o.destination}</td>
                      <td>{o.weight_ton}t</td>
                      <td style={{ color: isDelayed ? "#dc2626" : undefined, fontWeight: isDelayed ? 600 : undefined, fontSize: 13 }}>
                        {o.deadline}
                      </td>
                      <td style={{ fontSize: 12, color: "#64748b" }}>{o.recommended_route ?? "—"}</td>
                      <td style={{ fontSize: 13 }}>
                        {o.provider_name ?? <span style={{ color: "#d97706", fontWeight: 600, fontSize: 12 }}>Unassigned</span>}
                      </td>
                      <td style={{ fontSize: 13 }}>{fmtVnd(o.estimated_cost_vnd)}M</td>
                      <td><StatusBadge status={o.status} /></td>
                      <td>
                        <div style={{ display: "flex", gap: 5 }}>
                          <button className="secondary" style={{ padding: "4px 8px", fontSize: 11 }} onClick={() => setSelected(o)}>
                            View
                          </button>
                          {isUnassigned && (
                            <button style={{ padding: "4px 8px", fontSize: 11, background: "#047857" }} onClick={() => { setSelected(o); }}>
                              Assign
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <OrderDrawer
          order={orders.find((o) => o.id === selected.id) ?? selected}
          onClose={() => setSelected(null)}
          onAssign={handleAssign}
          onRouteAccept={handleRouteAccept}
          onToast={addToast}
        />
      )}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ background: "white", border: "1px solid #dbe2ea", borderRadius: 8, padding: 14 }}>
      <span style={{ color: "#64748b", fontSize: 12 }}>{label}</span>
      <div style={{ fontSize: 26, fontWeight: 700, color: color ?? "#111827", marginTop: 4 }}>{value}</div>
    </div>
  );
}

export default function OrdersPage() {
  return (
    <Suspense fallback={<div className="admin-page"><div className="empty">Loading…</div></div>}>
      <OrdersContent />
    </Suspense>
  );
}
