"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { StatusBadge } from "@/components/admin/StatusBadge";
import { ToastContainer, type ToastMessage } from "@/components/admin/Toast";
import { useLanguage } from "@/context/LanguageContext";
import { formatCurrency, formatDateTime, formatNumber, formatWeightKg, modeLabel, routeLabel } from "@/lib/labels";
import type { DispatchItem, Shipment, Exception } from "@/data/adminMockData";
import type { Kpis, Layer2ForecastMode, Layer2ForecastPayload, OperationsCapacity } from "@/types/dashboard";

type Tab = "dispatch" | "shipments" | "exceptions" | "capacity";

function Progress({ pct, color = "#1d4ed8" }: { pct: number; color?: string }) {
  return (
    <div style={{ background: "#f1f5f9", borderRadius: 999, height: 8, width: "100%", minWidth: 120 }}>
      <div style={{ width: `${Math.min(100, pct)}%`, height: "100%", borderRadius: 999, background: color, transition: "width 0.3s" }} />
    </div>
  );
}

function CapacityBar({ label, used, total, unit = "t", color = "#1d4ed8" }: { label: string; used: number; total: number | null; unit?: string; color?: string }) {
  const { language } = useLanguage();
  const pct = total !== null && total > 0 ? Math.round((used / total) * 100) : 0;
  const barColor = pct >= 85 ? "#dc2626" : pct >= 65 ? "#d97706" : color;
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span style={{ color: "#64748b" }}>
          {formatWeightKg(used * (unit === "t" ? 1000 : 1), language)}{total === null ? (language === "vi" ? " đã ghi nhận (chưa cấu hình sức chứa)" : " tracked (capacity not configured)") : ` / ${formatWeightKg(total * (unit === "t" ? 1000 : 1), language)} (${pct}%)`}
        </span>
      </div>
      <Progress pct={pct} color={total === null ? "#94a3b8" : barColor} />
    </div>
  );
}

function formatForecastTime(value: string | null | undefined, language: "vi" | "en") {
  return value ? formatDateTime(value, language) : language === "vi" ? "Chưa có dự báo" : "Not available";
}

function forecastDecisionLabel(decision: string | undefined, t: (key: string, fallback?: string) => string) {
  if (decision === "dispatch_now") return t("forecast.dispatch_now");
  if (decision === "wait_for_vehicle") return t("forecast.wait_for_vehicle");
  if (decision === "wait_for_load") return t("forecast.wait_for_load");
  return t("forecast.no_decision");
}

function Layer2ForecastPanel({ forecast }: { forecast?: Layer2ForecastPayload }) {
  const { language, t } = useLanguage();
  const modes: Array<["road" | "water", string, string]> = [
    ["road", t("admin.road_outbound"), "#1d4ed8"],
    ["water", t("admin.water_outbound"), "#0369a1"],
  ];

  return (
    <section className="panel" style={{ marginBottom: 16, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>{language === "vi" ? "Chi tiết forecast Layer 2" : "Layer 2 forecast detail"}</h2>
          <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>
            {language === "vi" ? "Forecast theo từng phương thức, bucket 30 phút trong horizon 6 giờ." : "Rolling forecast by mode, using 30-minute buckets over a 6-hour horizon."}
          </p>
        </div>
        <span style={{ color: forecast?.available ? "#047857" : "#b91c1c", fontSize: 12, fontWeight: 700 }}>
          {forecast?.available ? `${t("common.live")} · ${forecast.generated_at ? formatDateTime(forecast.generated_at, language) : ""}` : t("forecast.unavailable")}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 16 }}>
        {modes.map(([mode, label, color]) => {
          const item: Layer2ForecastMode | undefined = forecast?.modes?.[mode];
          const load = item?.current_load_kg || 0;
          const capacity = item?.selected_vehicle?.capacity_kg || 0;
          const fill = capacity > 0 ? Math.min(100, (load / capacity) * 100) : 0;
          const score = item?.priority_score;
          return (
            <div key={mode} style={{ border: "1px solid #dbe2ea", borderRadius: 10, overflow: "hidden", minWidth: 0 }}>
              <div style={{ background: `${color}10`, borderTop: `4px solid ${color}`, padding: "12px 14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <strong style={{ color }}>{label}</strong>
                  <span style={{ fontSize: 11, fontWeight: 800, color: item?.decision === "dispatch_now" ? "#047857" : "#92400e" }}>
                    {forecastDecisionLabel(item?.decision, t)}
                  </span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 12 }}>
                  <div><small style={{ color: "#64748b" }}>{language === "vi" ? "Hiện tại" : "Current"}</small><strong style={{ display: "block" }}>{formatWeightKg(load, language)}</strong></div>
                  <div><small style={{ color: "#64748b" }}>{language === "vi" ? "Xe" : "Vehicle"}</small><strong style={{ display: "block" }}>{capacity ? formatWeightKg(capacity, language) : "-"}</strong></div>
                  <div><small style={{ color: "#64748b" }}>{language === "vi" ? "Lấp đầy" : "Fill"}</small><strong style={{ display: "block" }}>{formatNumber(fill, language, 1)}%</strong></div>
                </div>
                <div style={{ background: "#e2e8f0", height: 8, borderRadius: 999, marginTop: 10 }}>
                  <div style={{ width: `${fill}%`, height: "100%", borderRadius: 999, background: color }} />
                </div>
              </div>

              <div style={{ padding: 14 }}>
                <div style={{ display: "grid", gap: 6, fontSize: 13 }}>
                  <div><span style={{ color: "#64748b" }}>{language === "vi" ? "Xe mục tiêu" : "Target vehicle"}: </span><strong>{item?.selected_vehicle?.vehicle_id || t("common.not_available")}</strong></div>
                  <div><span style={{ color: "#64748b" }}>{language === "vi" ? "Dự báo đầy tải" : "Predicted full load"}: </span><strong>{formatForecastTime(item?.predicted_full_load_time, language)}</strong></div>
                  <div><span style={{ color: "#64748b" }}>{t("fleet.confidence")}: </span><strong>{Math.round((item?.confidence || 0) * 100)}%</strong><span style={{ color: "#64748b" }}> · {item?.waiting_shipment_count ?? 0} {language === "vi" ? "đơn đang chờ" : "waiting orders"}</span></div>
                </div>
                {score ? (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginTop: 12, fontSize: 11 }}>
                    <div style={{ background: "#f8fafc", padding: 7, borderRadius: 6 }}>{language === "vi" ? "Lấp đầy" : "Fill"}<br /><strong>{score.fill_component.toFixed(2)}</strong></div>
                    <div style={{ background: "#f8fafc", padding: 7, borderRadius: 6 }}>{language === "vi" ? "Khẩn cấp" : "Urgency"}<br /><strong>{score.urgency_component.toFixed(2)}</strong></div>
                    <div style={{ background: "#f8fafc", padding: 7, borderRadius: 6 }}>{language === "vi" ? "Thời tiết" : "Weather"}<br /><strong>{score.weather_component.toFixed(2)}</strong></div>
                    <div style={{ background: "#eff6ff", padding: 7, borderRadius: 6 }}>{language === "vi" ? "Tổng" : "Total"}<br /><strong>{score.total_score.toFixed(2)}</strong></div>
                  </div>
                ) : null}
                <p style={{ margin: "12px 0", color: "#475569", fontSize: 12, lineHeight: 1.5 }}>{item?.explanation || item?.error || t("common.no_data")}</p>

                <div style={{ maxHeight: 230, overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: 6 }}>
                  <table style={{ width: "100%", fontSize: 11 }}>
                    <thead>
                      <tr>
                        <th style={{ padding: "7px 8px", textAlign: "left" }}>{language === "vi" ? "Mốc thời gian" : "Bucket"}</th>
                        <th style={{ padding: "7px 8px", textAlign: "right" }}>{language === "vi" ? "Đầu vào" : "Inbound"}</th>
                        <th style={{ padding: "7px 8px", textAlign: "right" }}>{language === "vi" ? "Chưa biết" : "Unknown"}</th>
                        <th style={{ padding: "7px 8px", textAlign: "right" }}>{language === "vi" ? "Tích lũy" : "Cumulative"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(item?.buckets || []).map((bucket) => (
                        <tr key={bucket.timestamp}>
                          <td style={{ padding: "6px 8px", whiteSpace: "nowrap" }}>{new Date(bucket.timestamp).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })}</td>
                          <td style={{ padding: "6px 8px", textAlign: "right" }}>{(bucket.known_inbound_kg / 1000).toFixed(1)}t</td>
                          <td style={{ padding: "6px 8px", textAlign: "right" }}>{(bucket.predicted_unknown_kg / 1000).toFixed(1)}t</td>
                          <td style={{ padding: "6px 8px", textAlign: "right", fontWeight: 700 }}>{(bucket.predicted_cumulative_load_kg / 1000).toFixed(1)}t</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function DispatchTab({
  queue,
  onAutoAssign,
  onApprove,
  addToast,
}: {
  queue: DispatchItem[];
  onAutoAssign: (item: DispatchItem) => void;
  onApprove: (item: DispatchItem) => void;
  addToast: (msg: string, type: ToastMessage["type"]) => void;
}) {
  const { language, t } = useLanguage();
  const [processing, setProcessing] = useState<Set<string>>(new Set());

  function autoAssign(item: DispatchItem) {
    setProcessing((p) => new Set(p).add(item.order_id));
    onAutoAssign(item);
    setTimeout(() => {
      setProcessing((p) => { const n = new Set(p); n.delete(item.order_id); return n; });
    }, 1000);
  }

  if (queue.length === 0) {
    return <div className="empty">{language === "vi" ? "Không có đơn chờ dispatch — hàng đợi đã trống." : "No orders waiting for dispatch — queue is clear."}</div>;
  }

  return (
    <div className="panel" style={{ padding: 0 }}>
      <div style={{ padding: "12px 16px", background: "#f8fafc", borderBottom: "1px solid #dbe2ea", display: "flex", gap: 8 }}>
        <button onClick={() => { queue.forEach((item) => autoAssign(item)); }} style={{ fontSize: 13, padding: "6px 14px" }}>
          {t("common.auto_assign_all")}
        </button>
        <span style={{ color: "#64748b", fontSize: 13, alignSelf: "center" }}>{queue.length} {t("common.items_pending")}</span>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{t("common.priority")}</th><th>{t("common.orders")}</th><th>{t("common.business")}</th><th>{t("common.commodity")}</th><th>{t("common.deadline")}</th><th>{t("common.recommended_route")}</th><th>{t("common.capacity")}</th><th>{t("common.suggested_provider")}</th><th>{t("common.reason")}</th><th>{t("common.actions")}</th>
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
                  <td style={{ fontSize: 12, color: "#64748b" }}>{routeLabel(item.recommended_route, language)}</td>
                <td>{item.capacity_ton}t</td>
                <td style={{ fontSize: 13 }}>{item.suggested_provider}</td>
                <td style={{ fontSize: 12, color: "#64748b", maxWidth: 200 }}>{item.reason}</td>
                <td>
                  <div style={{ display: "flex", gap: 5 }}>
                    <button
                      className="admin-btn-action"
                      style={{ fontSize: 11, padding: "4px 8px", background: "#047857" }}
                      onClick={() => autoAssign(item)}
                      disabled={processing.has(item.order_id)}
                    >
                      {processing.has(item.order_id) ? t("common.assigning") : t("common.assign")}
                    </button>
                    <button className="admin-btn-action" style={{ fontSize: 11, padding: "4px 8px" }} onClick={() => onApprove(item)}>
                      {t("common.approve")}
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

function ShipmentsTab({
  shipments,
  addToast,
}: {
  shipments: Shipment[];
  addToast: (msg: string, type: ToastMessage["type"]) => void;
}) {
  const { language, t } = useLanguage();
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
        {[
          { label: t("common.on_track"), value: shipments.filter((s) => s.status === "on_track").length, color: "#047857" },
          { label: t("common.at_hub"), value: shipments.filter((s) => s.status === "at_hub").length, color: "#1d4ed8" },
          { label: t("common.delayed"), value: shipments.filter((s) => s.status === "delayed").length, color: "#dc2626" },
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
                <th>{t("common.shipment")}</th><th>{t("common.orders")}</th><th>{t("common.business")}</th><th>{t("common.commodity")}</th><th>{t("common.provider")}</th><th>{t("common.route")}</th><th>{t("common.progress")}</th><th>{t("common.eta")}</th><th>{t("common.status")}</th><th>{t("common.actions")}</th>
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
                  <td style={{ fontSize: 12, color: "#64748b" }}>{routeLabel(s.route, language)}</td>
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
                        onClick={() => addToast(`${t("common.track")} ${s.id}.`, "info")}>
                        {t("common.track")}
                      </button>
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

function ExceptionsTab({
  exceptions,
  onResolve,
  addToast,
}: {
  exceptions: Exception[];
  onResolve: (id: string) => void;
  addToast: (msg: string, type: ToastMessage["type"]) => void;
}) {
  const { language, t } = useLanguage();
  const [showResolved, setShowResolved] = useState(false);

  const displayed = useMemo(() =>
    exceptions.filter((e) => showResolved ? true : !e.resolved),
    [exceptions, showResolved]
  );

  const criticalCount = exceptions.filter((e) => e.severity === "critical" && !e.resolved).length;
  const warningCount = exceptions.filter((e) => e.severity === "warning" && !e.resolved).length;

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 16 }}>
        <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, padding: 14, textAlign: "center" }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#dc2626" }}>{criticalCount}</div>
          <div style={{ fontSize: 13, color: "#dc2626", fontWeight: 600 }}>{t("common.critical")}</div>
        </div>
        <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", borderRadius: 8, padding: 14, textAlign: "center" }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#d97706" }}>{warningCount}</div>
          <div style={{ fontSize: 13, color: "#d97706", fontWeight: 600 }}>{t("common.warnings")}</div>
        </div>
        <div style={{ background: "#f8fafc", border: "1px solid #dbe2ea", borderRadius: 8, padding: 14, textAlign: "center" }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#047857" }}>{exceptions.filter((e) => e.resolved).length}</div>
          <div style={{ fontSize: 13, color: "#64748b" }}>{t("common.resolved")}</div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 400, color: "#374151", fontSize: 14, cursor: "pointer" }}>
          <input type="checkbox" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} />
          {t("common.show_resolved")}
        </label>
        <span style={{ marginLeft: "auto", color: "#64748b", fontSize: 13 }}>{displayed.length} {t("common.shown")}</span>
      </div>

      <div style={{ display: "grid", gap: 12 }}>
        {displayed.length === 0 ? (
          <div className="empty">{t("admin.no_exceptions")}</div>
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
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{t(`exceptions.${ex.type}`, EXCEPTION_TYPE_LABELS[ex.type])}</span>
                  <span style={{ fontSize: 12, color: "#64748b" }}>· {ex.order_id} · {ex.business_name}</span>
                </div>
                <span style={{ fontSize: 12, color: "#94a3b8", flexShrink: 0 }}>{ex.created_at}</span>
              </div>
              <p style={{ margin: "0 0 12px", color: "#374151", fontSize: 14 }}>{ex.description}</p>
              {!ex.resolved && (
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={{ fontSize: 12, padding: "5px 12px", background: "#047857" }} onClick={() => onResolve(ex.id)}>
                    {t("common.resolve")}
                  </button>
                  <button className="secondary" style={{ fontSize: 12, padding: "5px 12px" }}
                    onClick={() => addToast("Reassignment queued.", "info")}>
                    {t("common.reassign")}
                  </button>
                  <button className="secondary" style={{ fontSize: 12, padding: "5px 12px" }}
                    onClick={() => addToast("Business notified.", "info")}>
                    {t("common.contact_business")}
                  </button>
                </div>
              )}
              {ex.resolved && (
                <span style={{ fontSize: 12, color: "#047857", fontWeight: 600 }}>✓ {t("common.resolved")}</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function CapacityTab({ providers = [], capacity }: { providers?: any[]; capacity?: OperationsCapacity }) {
  const { language, t } = useLanguage();
  const road = capacity?.transport?.road ?? { used_ton: 0, total_ton: 0, available_ton: 0 };
  const water = capacity?.transport?.water ?? { used_ton: 0, total_ton: 0, available_ton: 0 };
  const hub = capacity?.hub ?? { used_ton: 0, capacity_ton: null, capacity_configured: false, waiting_orders: 0 };
  const queue = capacity?.queue ?? { waiting_orders: 0, waiting_volume_ton: 0, next_dispatch_hours: null };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* Hub capacity */}
      <div className="panel">
        <h3 style={{ margin: "0 0 16px" }}>{language === "vi" ? "Hub trung chuyển Cần Thơ" : "Can Tho consolidation hub"}</h3>
        <CapacityBar label={language === "vi" ? "Tải hub" : "Hub load"} used={hub.used_ton} total={hub.capacity_ton} />
        <div style={{ marginTop: 12, fontSize: 13, color: "#64748b" }}>
          {hub.waiting_orders} {language === "vi" ? "đơn đang chờ gom. Đây là volume từ database; sức chứa vật lý của hub chưa được cấu hình." : "orders waiting for consolidation. This is tracked DB volume; physical hub capacity is not configured."}
        </div>
      </div>

      {/* Transport capacity */}
      <div className="panel">
        <h3 style={{ margin: "0 0 16px" }}>{language === "vi" ? "Tổng quan sức chứa vận chuyển" : "Transport capacity overview"}</h3>
        <div style={{ display: "grid", gap: 16 }}>
          <CapacityBar label={t("admin.road_outbound")} used={road.used_ton} total={road.total_ton} color="#1d4ed8" />
          <CapacityBar label={t("admin.water_outbound")} used={water.used_ton} total={water.total_ton} color="#0369a1" />
        </div>
      </div>

      {/* Provider vehicle availability */}
      <div className="panel">
        <h3 style={{ margin: "0 0 16px" }}>{language === "vi" ? "Phương tiện sẵn sàng theo provider" : "Vehicle availability by provider"}</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {providers.map((p) => (
            <div key={p.id} style={{ display: "grid", gridTemplateColumns: "180px 1fr 190px", gap: 12, alignItems: "center" }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>{p.modes?.map((mode: string) => modeLabel(mode, language)).join(", ") || "—"}</div>
              </div>
              <Progress pct={p.utilization} color={p.utilization >= 80 ? "#dc2626" : p.utilization >= 60 ? "#d97706" : "#047857"} />
              <div style={{ fontSize: 13, textAlign: "right" }}>
                <span style={{ fontWeight: 600 }}>{p.available_vehicles}</span>
                <span style={{ color: "#64748b" }}> / {p.fleet_size} {language === "vi" ? "xe" : "vehicles"} · {p.available_capacity_ton ?? 0}t {language === "vi" ? "trống" : "free"}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Orders waiting */}
      <div className="panel">
        <h3 style={{ margin: "0 0 8px" }}>{language === "vi" ? "Hàng đợi gom hàng" : "Consolidation queue"}</h3>
        <div style={{ display: "flex", gap: 24 }}>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#d97706" }}>{queue.waiting_orders}</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>{language === "vi" ? "Đơn đang chờ" : "Orders waiting"}</div>
          </div>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#1d4ed8" }}>{queue.waiting_volume_ton}t</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>{language === "vi" ? "Tổng volume chờ" : "Total waiting volume"}</div>
          </div>
          <div>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#047857" }}>{queue.next_dispatch_hours === null ? "—" : `${queue.next_dispatch_hours}h`}</div>
            <div style={{ fontSize: 13, color: "#64748b" }}>{language === "vi" ? "Ước tính đến dispatch tiếp theo" : "Est. until next dispatch"}</div>
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
  const { language, t, sectionDescription } = useLanguage();
  const searchParams = useSearchParams();
  const initTab = (searchParams.get("tab") as Tab) || "dispatch";

  const [tab, setTab] = useState<Tab>(["dispatch", "shipments", "exceptions", "capacity"].includes(initTab) ? initTab : "dispatch");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [queue, setQueue] = useState<DispatchItem[]>([]);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [exceptions, setExceptions] = useState<Exception[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [capacity, setCapacity] = useState<OperationsCapacity | undefined>();
  const [forecast, setForecast] = useState<Layer2ForecastPayload | undefined>();
  const [kpis, setKpis] = useState<Kpis | undefined>();

  const addToast = useCallback((msg: string, type: ToastMessage["type"] = "success") => {
    setToasts((p) => [...p, { id: `${Date.now()}-${Math.random()}`, message: msg, type }]);
  }, []);
  const dismissToast = useCallback((id: string) => setToasts((p) => p.filter((t) => t.id !== id)), []);

  const fetchData = useCallback(async () => {
    try {
      const { getDashboardView } = await import("@/lib/api");
      const res = await getDashboardView("admin_operations") as any;
      if (res) {
        setQueue(res.queue || []);
        setShipments(res.active_shipments || []);
        setExceptions(res.exceptions || []);
        setProviders(res.providers || []);
        setCapacity(res.capacity);
        setForecast(res.forecast);
        setKpis(res.kpis);
      }
    } catch (e) {
      console.error("Failed to load operations data:", e);
    }
  }, []);

  useEffect(() => {
    fetchData();

    const apiBase = process.env.NEXT_PUBLIC_VAIC_API_BASE_URL || "http://127.0.0.1:8000";
    const socket = new WebSocket(apiBase.replace(/^http/, "ws") + "/ws/status");
    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === "TIME_TICK" || msg.event === "STATE_UPDATE") {
          fetchData();
        }
      } catch (e) {
        console.error(e);
      }
    };
    return () => socket.close();
  }, [fetchData]);

  async function handleAutoAssign(item: DispatchItem) {
    try {
      const res = await fetch(`/api/vaic/approve-route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: item.order_id }),
      });
      if (res.ok) {
        addToast(`${item.order_id} auto-assigned.`, "success");
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function handleApproveDispatch(item: DispatchItem) {
    try {
      const res = await fetch(`/api/vaic/approve-route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: item.order_id }),
      });
      if (res.ok) {
        addToast(`Dispatch approved for ${item.order_id}.`, "success");
        fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  }

  function handleResolveException(id: string) {
    addToast("Exception resolved.", "success");
    setExceptions((prev) => prev.map((e) => e.id === id ? { ...e, resolved: true } : e));
  }

  const unresolved = exceptions.filter((e) => !e.resolved).length;
  const critical = exceptions.filter((e) => !e.resolved && e.severity === "critical").length;

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>{t("admin.operations_title", "Operations")}</h1>
          <p className="page-subtitle">{sectionDescription("admin_operations")}</p>
        </div>
        {critical > 0 && (
          <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 16px", color: "#dc2626", fontWeight: 600, fontSize: 14 }}>
            ⚠️ {critical} {language === "vi" ? "ngoại lệ nghiêm trọng cần xử lý" : `critical exception${critical > 1 ? "s" : ""} require attention`}
          </div>
        )}
      </div>

      <div className="admin-two-column-layout">
        {/* Left Column: Forecast details, Tabs and content panels */}
        <div style={{ display: "grid", gap: 20, minWidth: 0 }}>
          <Layer2ForecastPanel forecast={forecast} />

          {/* Tabs */}
          <div className="ops-tabs" style={{ marginTop: 8 }}>
            {(Object.entries(TAB_LABELS) as [Tab, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`ops-tab${tab === key ? " active" : ""}`}
              >
                {key === "dispatch" ? t("admin.dispatch_queue") : key === "shipments" ? t("admin.active_shipments") : key === "exceptions" ? t("admin.exceptions") : t("admin.capacity")}
                {key === "exceptions" && unresolved > 0 && (
                  <span style={{ marginLeft: 6, background: "#dc2626", color: "white", borderRadius: 999, fontSize: 11, padding: "1px 7px", fontWeight: 700 }}>
                    {unresolved}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div>
            {tab === "dispatch" && <DispatchTab queue={queue} onAutoAssign={handleAutoAssign} onApprove={handleApproveDispatch} addToast={addToast} />}
            {tab === "shipments" && <ShipmentsTab shipments={shipments} addToast={addToast} />}
            {tab === "exceptions" && <ExceptionsTab exceptions={exceptions} onResolve={handleResolveException} addToast={addToast} />}
            {tab === "capacity" && <CapacityTab providers={providers} capacity={capacity} />}
          </div>
        </div>

        {/* Right Column: KPIs stacked vertically */}
        <div className="admin-summary-column">
          <h2 className="section-title" style={{ margin: 0 }}>{language === "vi" ? "Thống kê vận hành" : "Operational KPIs"}</h2>
          {kpis ? (
            <div style={{ display: "grid", gap: 12 }}>
              <div className="admin-kpi-card admin-kpi-card--success" style={{ padding: "16px 20px" }}>
                <span>{t("admin.cost_savings")}</span>
                <strong>{formatCurrency(Number(kpis.cost_savings), language)}</strong>
                <small>{kpis.orders_with_savings ?? kpis.compared_orders} {language === "vi" ? "đơn có đủ baseline để so sánh" : "orders have a comparable baseline"}</small>
              </div>
              <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                <span>{language === "vi" ? "Chi phí baseline" : "Baseline cost"}</span>
                <strong>{formatCurrency(Number(kpis.baseline_cost_vnd || 0), language)}</strong>
              </div>
              <div className="admin-kpi-card" style={{ padding: "16px 20px" }}>
                <span>{language === "vi" ? "Chi phí sau tối ưu" : "Optimized cost"}</span>
                <strong>{formatCurrency(Number(kpis.optimized_cost_vnd || 0), language)}</strong>
              </div>
            </div>
          ) : (
            <div className="empty" style={{ padding: 20 }}>{t("common.loading")}</div>
          )}
        </div>
      </div>

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
