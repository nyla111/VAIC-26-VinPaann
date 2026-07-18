"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { ToastContainer, type ToastMessage } from "@/components/admin/Toast";
import { DISPATCH_QUEUE, ACTIVE_SHIPMENTS, EXCEPTIONS, PROVIDERS } from "@/data/adminMockData";
import type { DispatchItem, Shipment, Exception } from "@/data/adminMockData";

type Tab = "dispatch" | "shipments" | "exceptions" | "capacity";

function Progress({ pct, color = "#1d4ed8" }: { pct: number; color?: string }) {
  return (
    <div style={{ background: "#f1f5f9", borderRadius: 999, height: 8, width: "100%", minWidth: 120 }}>
      <div style={{ width: `${Math.min(100, pct)}%`, height: "100%", borderRadius: 999, background: color, transition: "width 0.3s" }} />
    </div>
  );
}

function CapacityBar({ label, used, total, unit = "t", color = "#1d4ed8" }: { label: string; used: number; total: number; unit?: string; color?: string }) {
  const pct = total > 0 ? Math.round((used / total) * 100) : 0;
  const barColor = pct >= 85 ? "#dc2626" : pct >= 65 ? "#d97706" : color;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span style={{ color: "#64748b" }}>{used}{unit} / {total}{unit} ({pct}%)</span>
      </div>
      <Progress pct={pct} color={barColor} />
    </div>
  );
}

function DispatchTab({ addToast }: { addToast: (msg: string, type: ToastMessage["type"]) => void }) {
  const [queue, setQueue] = useState<DispatchItem[]>(DISPATCH_QUEUE);
  const [processing, setProcessing] = useState<Set<string>>(new Set());

  function autoAssign(item: DispatchItem) {
    setProcessing((p) => new Set(p).add(item.order_id));
    setTimeout(() => {
      setQueue((prev) => prev.filter((d) => d.order_id !== item.order_id));
      setProcessing((p) => { const n = new Set(p); n.delete(item.order_id); return n; });
      addToast(`${item.order_id} auto-assigned to ${item.suggested_provider}.`, "success");
    }, 900);
  }

  function approveDispatch(item: DispatchItem) {
    setQueue((prev) => prev.filter((d) => d.order_id !== item.order_id));
    addToast(`Dispatch approved for ${item.order_id}.`, "success");
  }

  if (queue.length === 0) {
    return <div className="empty">No orders waiting for dispatch — queue is clear.</div>;
  }

  return (
    <div className="panel" style={{ padding: 0 }}>
      <div style={{ padding: "12px 16px", background: "#f8fafc", borderBottom: "1px solid #dbe2ea", display: "flex", gap: 8 }}>
        <button onClick={() => { queue.forEach((item) => autoAssign(item)); }} style={{ fontSize: 13, padding: "6px 14px" }}>
          Auto-Assign All
        </button>
        <span style={{ color: "#64748b", fontSize: 13, alignSelf: "center" }}>{queue.length} items pending</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Priority</th>
              <th>Order</th>
              <th>Business</th>
              <th>Commodity</th>
              <th>Deadline</th>
              <th>Rec. Route</th>
              <th>Capacity</th>
              <th>Suggested Provider</th>
              <th>Reason</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {queue.map((item) => (
              <tr key={item.order_id} className="table-row-hover">
                <td><StatusBadge status={item.priority} /></td>
                <td style={{ fontWeight: 600 }}>{item.order_id}</td>
                <td style={{ fontSize: 13 }}>{item.business_name}</td>
                <td>{item.commodity}</td>
                <td style={{ fontSize: 13, color: item.priority === "high" ? "#dc2626" : undefined, fontWeight: item.priority === "high" ? 600 : undefined }}>
                  {item.deadline}
                </td>
                <td style={{ fontSize: 12, color: "#64748b" }}>{item.recommended_route}</td>
                <td>{item.capacity_ton}t</td>
                <td style={{ fontSize: 13 }}>{item.suggested_provider}</td>
                <td style={{ fontSize: 12, color: "#64748b", maxWidth: 200 }}>{item.reason}</td>
                <td>
                  <div style={{ display: "flex", gap: 5 }}>
                    <button
                      style={{ fontSize: 11, padding: "4px 8px", background: "#047857" }}
                      onClick={() => autoAssign(item)}
                      disabled={processing.has(item.order_id)}
                    >
                      {processing.has(item.order_id) ? "Assigning…" : "Auto Assign"}
                    </button>
                    <button style={{ fontSize: 11, padding: "4px 8px" }} onClick={() => approveDispatch(item)}>
                      Approve
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ShipmentsTab({ addToast }: { addToast: (msg: string, type: ToastMessage["type"]) => void }) {
  const [shipments, setShipments] = useState<Shipment[]>(ACTIVE_SHIPMENTS);

  function reportIssue(id: string) {
    setShipments((prev) => prev.map((s) => s.id === id ? { ...s, status: "delayed" as const } : s));
    addToast("Issue reported and flagged for review.", "info");
  }

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
        {[
          { label: "On Track", value: shipments.filter((s) => s.status === "on_track").length, color: "#047857" },
          { label: "At Hub", value: shipments.filter((s) => s.status === "at_hub").length, color: "#1d4ed8" },
          { label: "Delayed", value: shipments.filter((s) => s.status === "delayed").length, color: "#dc2626" },
        ].map((c) => (
          <div key={c.label} style={{ background: "white", border: "1px solid #dbe2ea", borderRadius: 8, padding: 14, textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: c.color }}>{c.value}</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>{c.label}</div>
          </div>
        ))}
      </div>

      <div className="panel" style={{ padding: 0 }}>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Shipment</th>
                <th>Order</th>
                <th>Business</th>
                <th>Commodity</th>
                <th>Provider</th>
                <th>Route</th>
                <th>Progress</th>
                <th>ETA</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {shipments.map((s) => (
                <tr key={s.id} className="table-row-hover" style={{ background: s.status === "delayed" ? "#fff7f7" : undefined }}>
                  <td style={{ fontWeight: 600 }}>{s.id}</td>
                  <td style={{ fontSize: 13 }}>{s.order_id}</td>
                  <td style={{ fontSize: 13 }}>{s.business_name}</td>
                  <td>{s.commodity}</td>
                  <td style={{ fontSize: 13 }}>{s.provider_name}</td>
                  <td style={{ fontSize: 12, color: "#64748b" }}>{s.route}</td>
                  <td style={{ minWidth: 140 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Progress pct={s.progress} color={s.status === "delayed" ? "#dc2626" : s.status === "at_hub" ? "#1d4ed8" : "#047857"} />
                      <span style={{ fontSize: 12, minWidth: 32 }}>{s.progress}%</span>
                    </div>
                  </td>
                  <td style={{ fontSize: 13 }}>{s.eta}</td>
                  <td><StatusBadge status={s.status} /></td>
                  <td>
                    <div style={{ display: "flex", gap: 5 }}>
                      <button className="secondary" style={{ fontSize: 11, padding: "4px 8px" }}
                        onClick={() => addToast(`Tracking ${s.id} on map.`, "info")}>
                        Track
                      </button>
                      {s.status !== "delayed" && (
                        <button style={{ fontSize: 11, padding: "4px 8px", background: "#dc2626" }}
                          onClick={() => reportIssue(s.id)}>
                          Issue
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const EXCEPTION_TYPE_LABELS: Record<string, string> = {
  delayed: "Delayed Shipment",
  no_provider: "No Provider Available",
  capacity_shortage: "Capacity Shortage",
  route_unavailable: "Route Unavailable",
  weather_warning: "Weather Warning",
  high_cost: "High Cost Alert",
  provider_rejected: "Provider Rejected",
};

function ExceptionsTab({ addToast }: { addToast: (msg: string, type: ToastMessage["type"]) => void }) {
  const [exceptions, setExceptions] = useState<Exception[]>(EXCEPTIONS);
  const [showResolved, setShowResolved] = useState(false);

  const displayed = useMemo(() =>
    exceptions.filter((e) => showResolved ? true : !e.resolved),
    [exceptions, showResolved]
  );

  function resolve(id: string) {
    setExceptions((prev) => prev.map((e) => e.id === id ? { ...e, resolved: true } : e));
    addToast("Exception resolved.", "success");
  }

  const criticalCount = exceptions.filter((e) => e.severity === "critical" && !e.resolved).length;
  const warningCount = exceptions.filter((e) => e.severity === "warning" && !e.resolved).length;

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
        <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, padding: 14, textAlign: "center" }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#dc2626" }}>{criticalCount}</div>
          <div style={{ fontSize: 13, color: "#dc2626", fontWeight: 600 }}>Critical</div>
        </div>
        <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, padding: 14, textAlign: "center" }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#d97706" }}>{warningCount}</div>
          <div style={{ fontSize: 13, color: "#d97706", fontWeight: 600 }}>Warnings</div>
        </div>
        <div style={{ background: "#f8fafc", border: "1px solid #dbe2ea", borderRadius: 8, padding: 14, textAlign: "center" }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#047857" }}>{exceptions.filter((e) => e.resolved).length}</div>
          <div style={{ fontSize: 13, color: "#64748b" }}>Resolved</div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400, color: "#374151", fontSize: 14, cursor: "pointer" }}>
          <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
          Show resolved exceptions
        </label>
        <span style={{ marginLeft: "auto", color: "#64748b", fontSize: 13 }}>{displayed.length} shown</span>
      </div>

      <div style={{ display: "grid", gap: 12 }}>
        {displayed.length === 0 ? (
          <div className="empty">No exceptions to display.</div>
        ) : (
          displayed.map((ex) => (
            <div key={ex.id} style={{
              background: ex.resolved ? "#f8fafc" : ex.severity === "critical" ? "#fff7f7" : ex.severity === "warning" ? "#fffbeb" : "white",
              border: `1px solid ${ex.resolved ? "#e2e8f0" : ex.severity === "critical" ? "#fca5a5" : ex.severity === "warning" ? "#fcd34d" : "#dbeafe"}`,
              borderRadius: 8,
              padding: 16,
              opacity: ex.resolved ? 0.65 : 1,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 8 }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <StatusBadge status={ex.severity} />
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{EXCEPTION_TYPE_LABELS[ex.type]}</span>
                  <span style={{ fontSize: 12, color: "#64748b" }}>· {ex.order_id} · {ex.business_name}</span>
                </div>
                <span style={{ fontSize: 12, color: "#94a3b8", flexShrink: 0 }}>{ex.created_at}</span>
              </div>
              <p style={{ margin: "0 0 12px", color: "#374151", fontSize: 14 }}>{ex.description}</p>
              {!ex.resolved && (
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={{ fontSize: 12, padding: "5px 12px", background: "#047857" }} onClick={() => resolve(ex.id)}>
                    Resolve
                  </button>
                  <button className="secondary" style={{ fontSize: 12, padding: "5px 12px" }}
                    onClick={() => addToast("Reassignment queued.", "info")}>
                    Reassign Provider
                  </button>
                  <button className="secondary" style={{ fontSize: 12, padding: "5px 12px" }}
                    onClick={() => addToast("Business notified.", "info")}>
                    Contact Business
                  </button>
                </div>
              )}
              {ex.resolved && (
                <span style={{ fontSize: 12, color: "#047857", fontWeight: 600 }}>✓ Resolved</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function CapacityTab() {
  const totalRoad = PROVIDERS.filter((p) => p.modes.includes("road")).reduce((s, p) => s + p.fleet_size * 15, 0);
  const usedRoad = PROVIDERS.filter((p) => p.modes.includes("road")).reduce((s, p) => s + p.active_orders * 12, 0);
  const totalWater = PROVIDERS.filter((p) => p.modes.includes("waterway")).reduce((s, p) => s + p.fleet_size * 90, 0);
  const usedWater = PROVIDERS.filter((p) => p.modes.includes("waterway")).reduce((s, p) => s + p.active_orders * 70, 0);

  const waiting = 5;
  const ctCapacity = 450;
  const ctUsed = 320;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* Hub capacity */}
      <div className="panel">
        <h3 style={{ margin: "0 0 16px" }}>Can Tho Consolidation Hub</h3>
        <CapacityBar label="Hub Load" used={ctUsed} total={ctCapacity} />
        <div style={{ marginTop: 12, fontSize: 13, color: "#64748b" }}>
          {waiting} orders waiting for consolidation. Hub at {Math.round((ctUsed / ctCapacity) * 100)}% capacity.
        </div>
      </div>

      {/* Transport capacity */}
      <div className="panel">
        <h3 style={{ margin: "0 0 16px" }}>Transport Capacity Overview</h3>
        <div style={{ display: "grid", gap: 16 }}>
          <CapacityBar label="Road Transport" used={usedRoad} total={totalRoad} color="#1d4ed8" />
          <CapacityBar label="Waterway Transport" used={usedWater} total={totalWater} color="#0369a1" />
        </div>
      </div>

      {/* Provider vehicle availability */}
      <div className="panel">
        <h3 style={{ margin: "0 0 16px" }}>Vehicle Availability by Provider</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {PROVIDERS.map((p) => (
            <div key={p.id} style={{ display: "grid", gridTemplateColumns: "180px 1fr 120px", gap: 12, alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>{p.modes.join(", ")}</div>
              </div>
              <Progress pct={p.utilization} color={p.utilization >= 80 ? "#dc2626" : p.utilization >= 60 ? "#d97706" : "#047857"} />
              <div style={{ fontSize: 13, textAlign: "right" }}>
                <span style={{ fontWeight: 600 }}>{p.available_vehicles}</span>
                <span style={{ color: "#64748b" }}> / {p.fleet_size} avail.</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Orders waiting */}
      <div className="panel">
        <h3 style={{ margin: "0 0 8px" }}>Consolidation Queue</h3>
        <div style={{ display: "flex", gap: 24 }}>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#d97706" }}>{waiting}</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>Orders waiting</div>
          </div>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#1d4ed8" }}>168t</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>Total waiting volume</div>
          </div>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#047857" }}>12h</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>Est. until next dispatch</div>
          </div>
        </div>
      </div>
    </div>
  );
}

const TAB_LABELS: Record<Tab, string> = {
  dispatch: "Dispatch Queue",
  shipments: "Active Shipments",
  exceptions: "Exceptions",
  capacity: "Capacity",
};

function OperationsContent() {
  const searchParams = useSearchParams();
  const initTab = (searchParams.get("tab") as Tab) || "dispatch";

  const [tab, setTab] = useState<Tab>(["dispatch", "shipments", "exceptions", "capacity"].includes(initTab) ? initTab : "dispatch");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((msg: string, type: ToastMessage["type"] = "success") => {
    setToasts((p) => [...p, { id: `${Date.now()}-${Math.random()}`, message: msg, type }]);
  }, []);
  const dismissToast = useCallback((id: string) => setToasts((p) => p.filter((t) => t.id !== id)), []);

  const unresolved = EXCEPTIONS.filter((e) => !e.resolved).length;
  const critical = EXCEPTIONS.filter((e) => !e.resolved && e.severity === "critical").length;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>Operations</h1>
          <p className="page-subtitle">Real-time dispatch, shipments, exceptions and capacity</p>
        </div>
        {critical > 0 && (
          <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 16px", color: "#dc2626", fontWeight: 600, fontSize: 14 }}>
            ⚠️ {critical} critical exception{critical > 1 ? "s" : ""} require attention
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="ops-tabs">
        {(Object.entries(TAB_LABELS) as [Tab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`ops-tab${tab === key ? " active" : ""}`}
          >
            {label}
            {key === "exceptions" && unresolved > 0 && (
              <span style={{ marginLeft: 6, background: "#dc2626", color: "white", borderRadius: 999, fontSize: 11, padding: "1px 7px", fontWeight: 700 }}>
                {unresolved}
              </span>
            )}
          </button>
        ))}
      </div>

      {tab === "dispatch" && <DispatchTab addToast={addToast} />}
      {tab === "shipments" && <ShipmentsTab addToast={addToast} />}
      {tab === "exceptions" && <ExceptionsTab addToast={addToast} />}
      {tab === "capacity" && <CapacityTab />}

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

export default function OperationsPage() {
  return (
    <Suspense fallback={<div className="admin-page"><div className="empty">Loading…</div></div>}>
      <OperationsContent />
    </Suspense>
  );
}
