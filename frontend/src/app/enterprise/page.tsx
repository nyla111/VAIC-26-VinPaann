"use client";

import { useEffect, useRef, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Brand } from "@/components/Brand";
import { LanguageToggle } from "@/components/LanguageToggle";
import { getScopedMapData } from "@/lib/api";
import { formatCurrency, formatDurationHours, orderStateLabel, routeLabel } from "@/lib/labels";
import dynamic from "next/dynamic";
const VaicMap = dynamic(() => import("@/components/VaicMap").then((m) => m.VaicMap), {
  ssr: false,
});

import type { OptimizeResult, RouteOption, MapPayload } from "@/types/dashboard";

const HUBS = [
  { value: "HUB_VITHANH", label: "Hub Vị Thanh" },
  { value: "HUB_LONGXUYEN", label: "Hub Long Xuyên" },
  { value: "HUB_SOCTRANG", label: "Hub Sóc Trăng" },
  { value: "HUB_VINHLONG", label: "Hub Vĩnh Long" },
];

const CARGO_PRESETS = [
  { value: "COM_RICE", label: "Lúa gạo", loaiHang: "lúa gạo" },
  { value: "COM_PANGASIUS", label: "Cá tra", loaiHang: "cá tra" },
  { value: "COM_SHRIMP", label: "Tôm (Thủy sản)", loaiHang: "tôm" },
  { value: "COM_POMELO", label: "Bưởi", loaiHang: "bưởi" },
  { value: "COM_PURPLE_ONION", label: "Hành tím", loaiHang: "hành tím" },
  { value: "COM_VEGETABLE", label: "Rau xanh / Hoa quả", loaiHang: "rau xanh" },
  { value: "COM_SUGARCANE", label: "Mía đường", loaiHang: "mía đường" },
  { value: "COM_PINEAPPLE", label: "Khóm (Dứa)", loaiHang: "khóm dứa" },
  { value: "COM_ORANGE", label: "Cam sành", loaiHang: "cam sành" },
  { value: "other", label: "Khác (Tự nhập...)", loaiHang: "" },
];

const REASON_LABELS: Record<string, string> = {
  "hang_khong_phu_hop_duong_thuy": "Loại hàng không phù hợp vận chuyển đường thủy.",
  "muc_nuoc_khong_an_toan": "Mực nước hoặc điều kiện thủy văn chưa an toàn.",
  "khong_co_phuong_tien_phu_hop": "Chưa có phương tiện phù hợp về tải trọng/trạng thái.",
  "vuot_deadline": "Không đáp ứng được hạn giao hàng.",
  "missing_weather": "Thiếu dữ liệu thời tiết gần thời điểm quyết định.",
};

function formatLocalDatetime(date: Date): string {
  const localOffset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - localOffset).toISOString().slice(0, 16);
}

function getVehicleType(state: string, routeId: string | null, language: "vi" | "en"): string {
  if (!routeId) return language === "vi" ? "🚚 Xe tải bộ" : "🚚 Road truck";
  if (state === "routed_to_can_tho" || state === "in_transit_to_can_tho") {
    if (routeId.includes("WATER")) {
      return language === "vi" ? "🚢 Tàu đường thủy" : "🚢 Waterway vessel";
    }
    return language === "vi" ? "🚚 Xe tải bộ" : "🚚 Road truck";
  }
  if (state === "dispatched") {
    if (routeId === "D_WATER_VIA_CT" || routeId === "E_ROAD_WATER_VIA_CT") {
      return language === "vi" ? "🚢 Tàu đường thủy" : "🚢 Waterway vessel";
    }
    return language === "vi" ? "🚚 Xe tải bộ" : "🚚 Road truck";
  }
  return language === "vi" ? "🚚 Phương tiện" : "🚚 Vehicle";
}

export default function EnterpriseDashboard() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const { dictionary, language, t } = useLanguage();
  const [step, setStep] = useState<"form" | "routes" | "tracking">("form");

  // Form states
  const [selectedPreset, setSelectedPreset] = useState("COM_RICE");
  const [customCargoName, setCustomCargoName] = useState("");
  
  // Datetimes default states
  const [harvestedAt, setHarvestedAt] = useState("");
  const [shipmentAt, setShipmentAt] = useState("");
  const [deliveryDeadline, setDeliveryDeadline] = useState("");

  const [validationError, setValidationError] = useState<string | null>(null);

  // States
  const [orderId, setOrderId] = useState<number | null>(null);
  const [routeOptions, setRouteOptions] = useState<OptimizeResult | null>(null);
  const [routeMap, setRouteMap] = useState<MapPayload | null>(null);
  const [liveMap, setLiveMap] = useState<MapPayload | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<string | null>(null);
  const [trackingState, setTrackingState] = useState<{
    state: string;
    location: { lat: number; lon: number } | null;
    progress: number;
    provider_name?: string | null;
    timeline?: Array<{ event: string; time: string; done: boolean }> | null;
  } | null>(null);

  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const now = new Date();
    const harvestDate = new Date(now.getTime() - 6 * 60 * 60 * 1000);
    setHarvestedAt(formatLocalDatetime(harvestDate));
    
    const shipmentDate = new Date(now.getTime() + 45 * 60 * 1000);
    setShipmentAt(formatLocalDatetime(shipmentDate));
    
    const deadlineDate = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);
    setDeliveryDeadline(formatLocalDatetime(deadlineDate));
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== "enterprise") {
      router.replace(`/${user.role}`);
      return;
    }

    const backendBaseUrl = process.env.NEXT_PUBLIC_VAIC_API_BASE_URL || "http://127.0.0.1:8000";
    const wsUrl = backendBaseUrl.replace(/^http/, "ws") + "/ws";
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log("WebSocket connected.");
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log("Received event:", message);

        if (message.event === "ROUTE_OPTIONS") {
          setRouteOptions(message.data);
          setRouteMap(message.route_map);
          setOrderId(message.order_id);
          setLiveMap(null);
          // Pre-select the recommended route
          setSelectedRoute(message.data.recommended_route);
          setStep("routes");
        } else if (message.event === "ROUTE_CONFIRMED") {
          socket.send(
            JSON.stringify({
              action: "TRACK_CARGO",
              order_id: message.order_id,
            })
          );
          setStep("tracking");
        } else if (message.event === "CARGO_TRACKING") {
          setTrackingState({
            state: message.state,
            location: message.location,
            progress: message.progress,
            provider_name: message.provider_name,
            timeline: message.timeline,
          });
        }
      } catch (err) {
        console.error("Error parsing message:", err);
      }
    };

    socket.onclose = () => {
      console.log("WebSocket disconnected.");
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [loading, router, user]);

  useEffect(() => {
    if (step !== "tracking" || !orderId) return;
    getScopedMapData()
      .then((payload) => {
        if (payload) {
          setLiveMap({
            ...payload,
            routes: routeMap?.routes || payload.routes,
            activeRoute: selectedRoute || payload.activeRoute,
          });
        }
      })
      .catch(() => {
        // The tracking WebSocket remains authoritative if the map API is unavailable.
      });
  }, [orderId, routeMap, selectedRoute, step]);

  if (loading || !user || user.role !== "enterprise") {
    return <main className="loading-screen">{dictionary.loading}</main>;
  }

  const handleFormSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setValidationError(null);

    const now = new Date();
    const harvestDate = new Date(harvestedAt);
    const shipmentDate = new Date(shipmentAt);
    const deadlineDate = new Date(deliveryDeadline);

    if (shipmentDate < harvestDate) {
      setValidationError("Thời điểm xuất hàng không thể sớm hơn thời điểm thu hoạch.");
      return;
    }

    if (deadlineDate < shipmentDate) {
      setValidationError("Hạn giao hàng không thể sớm hơn thời điểm xuất hàng.");
      return;
    }

    const minFutureTime = new Date(now.getTime() + 30 * 60 * 1000);
    
    if (shipmentDate < minFutureTime) {
      setValidationError("Thời điểm xuất hàng phải lớn hơn thời điểm tạo đơn ít nhất 30 phút.");
      return;
    }

    if (deadlineDate < minFutureTime) {
      setValidationError("Hạn giao hàng phải lớn hơn thời điểm tạo đơn ít nhất 30 phút.");
      return;
    }

    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      setValidationError("Kết nối máy chủ (WebSocket) chưa sẵn sàng. Vui lòng kiểm tra xem Backend đã được khởi chạy chưa.");
      return;
    }

    let loaiHang = "";
    if (selectedPreset === "other") {
      loaiHang = customCargoName.trim();
      if (!loaiHang) {
        setValidationError("Vui lòng nhập tên loại hàng cụ thể.");
        return;
      }
    } else {
      const preset = CARGO_PRESETS.find((p) => p.value === selectedPreset);
      loaiHang = preset ? preset.loaiHang : "";
    }

    const data = new FormData(e.currentTarget);
    const payload = {
      action: "CREATE_ORDER",
      hub_id: String(data.get("hub_id")),
      loai_hang: loaiHang,
      khoi_luong_kg: Number(data.get("khoi_luong_kg")),
      timestamp: `${shipmentAt}:00+07:00`,
      delivery_deadline: `${deliveryDeadline}:00+07:00`,
      harvested_at: `${harvestedAt}:00+07:00`,
    };

    socketRef.current.send(JSON.stringify(payload));
  };

  const handleConfirmRoute = () => {
    if (!socketRef.current || !orderId || !selectedRoute) return;
    socketRef.current.send(
      JSON.stringify({
        action: "CONFIRM_ROUTE",
        order_id: orderId,
        selected_route_id: selectedRoute,
      })
    );
  };

  const getMapPayload = (): MapPayload => {
    return {
      nodes: [
        { node_id: "HUB_VITHANH", name: "Hub Vị Thanh", type: "farm_hub", lat: 9.784, lon: 105.4701, on_river: "True" },
        { node_id: "HUB_LONGXUYEN", name: "Hub Long Xuyên", type: "farm_hub", lat: 10.3864, lon: 105.4352, on_river: "True" },
        { node_id: "HUB_SOCTRANG", name: "Hub Sóc Trăng", type: "farm_hub", lat: 9.6025, lon: 105.9739, on_river: "True" },
        { node_id: "HUB_VINHLONG", name: "Hub Vĩnh Long", type: "farm_hub", lat: 10.2537, lon: 105.9722, on_river: "True" },
        { node_id: "CT_HUB", name: "Trung tâm trung chuyển Cần Thơ", type: "transshipment", lat: 10.0452, lon: 105.7469, on_river: "True" },
        { node_id: "HCM_MARKET", name: "Thị trường TP.HCM", type: "market", lat: 10.7769, lon: 106.7009, on_river: "False" },
      ],
      fleet: [],
    };
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand role="enterprise" />
        <nav>
          <a className="active" href="#">{t("enterprise.manager")}</a>
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{t("enterprise.heading")}</h1>
            <p>{t("enterprise.subtitle")}</p>
          </div>
          <div className="user-box">
            <LanguageToggle />
            <span>{user.email}</span>
            <button className="secondary" type="button" onClick={() => logout().then(() => router.replace("/login"))}>
              {dictionary.logout}
            </button>
          </div>
        </header>

        <section className="content">
          {step === "form" && (
            <div className="panel">
              <h2 style={{ marginBottom: "16px" }}>{t("enterprise.create_order")}</h2>
              {validationError && (
                <div className="alert" style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b", marginBottom: "16px" }}>
                  <strong>{t("enterprise.validation_error")}:</strong> {validationError}
                </div>
              )}
              <form onSubmit={handleFormSubmit} className="grid-form">
                <label>
                  {t("enterprise.hub_origin")}
                  <select name="hub_id" defaultValue="HUB_VITHANH">
                    {HUBS.map((h) => (
                      <option key={h.value} value={h.value}>{h.label}</option>
                    ))}
                  </select>
                </label>

                <label>
                  {t("enterprise.commodity")}
                  <select value={selectedPreset} onChange={(e) => setSelectedPreset(e.target.value)}>
                    {CARGO_PRESETS.map((p) => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                </label>

                {selectedPreset === "other" ? (
                  <label>
                    {t("enterprise.custom_commodity")}
                    <input
                      value={customCargoName}
                      onChange={(e) => setCustomCargoName(e.target.value)}
                      placeholder={t("enterprise.custom_placeholder")}
                      required
                    />
                  </label>
                ) : (
                  <div />
                )}

                <label>
                  {t("enterprise.weight")}
                  <input name="khoi_luong_kg" type="number" min="100" defaultValue="5000" required />
                </label>

                <label>
                  {t("enterprise.harvest_time")}
                  <input
                    type="datetime-local"
                    value={harvestedAt}
                    onChange={(e) => setHarvestedAt(e.target.value)}
                    required
                  />
                </label>

                <label>
                  {t("enterprise.shipment_time")}
                  <input
                    type="datetime-local"
                    value={shipmentAt}
                    onChange={(e) => setShipmentAt(e.target.value)}
                    required
                  />
                </label>

                <label>
                  {t("enterprise.delivery_deadline")}
                  <input
                    type="datetime-local"
                    value={deliveryDeadline}
                    onChange={(e) => setDeliveryDeadline(e.target.value)}
                    required
                  />
                </label>

                <button type="submit" style={{ gridColumn: "span 3", marginTop: "12px" }}>
                  {t("enterprise.submit")}
                </button>
              </form>
            </div>
          )}

          {step === "routes" && routeOptions && (
            <div>
              <div className="panel" style={{ marginBottom: "16px" }}>
                <h2 style={{ marginBottom: "8px" }}>{t("enterprise.route_heading")}</h2>
                <p style={{ color: "#64748b", marginBottom: "16px" }}>{t("enterprise.route_description")}</p>
                <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))" }}>
                  {routeOptions.phuong_an.map((route: RouteOption) => {
                    const isRecommended = route.route_code === routeOptions.recommended_route;
                    const isSelected = selectedRoute === route.route_code;
                    const disabled = route.trang_thai !== "available";
                    return (
                      <article
                        key={route.route_code}
                        onClick={() => !disabled && setSelectedRoute(route.route_code)}
                        className={`route-card ${isRecommended ? "recommended" : ""} ${isSelected ? "selected-highlight" : ""} ${disabled ? "disabled" : ""}`}
                        style={{ cursor: disabled ? "not-allowed" : "pointer", border: isSelected ? "2px solid #1d4ed8" : "" }}
                      >
                        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <strong>{routeLabel(route.route_code, language)}</strong>
                          {isRecommended && <span className="badge">{t("enterprise.ai_recommended")}</span>}
                        </header>
                        <p>{route.ten}</p>
                        {route.trang_thai === "available" ? (
                          <>
                            <div className="metric">
                              <span>{t("enterprise.predicted_cost")}</span>
                              <strong>{formatCurrency(route.chi_phi_du_doan_vnd, language)}</strong>
                            </div>
                            <div className="metric">
                              <span>{t("common.time")}</span>
                              <strong>{formatDurationHours(route.thoi_gian_du_kien_gio, language)}</strong>
                            </div>
                          </>
                        ) : (
                          <div className="unavailable" style={{ color: "#b91c1c", fontSize: "14px", marginTop: "8px" }}>
                            {REASON_LABELS[route.ly_do || ""] || "Tuyến chưa khả dụng."}
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
                <div style={{ marginTop: "20px", display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                  <button className="secondary" onClick={() => setStep("form")}>{t("enterprise.back")}</button>
                  <button onClick={handleConfirmRoute} disabled={!selectedRoute}>{t("enterprise.confirm_route")}</button>
                </div>
              </div>

              {routeMap && (
                <div className="panel" style={{ height: "450px", position: "relative", marginTop: "16px" }}>
                  <h3 style={{ marginBottom: "12px" }}>{t("enterprise.preview_map")}</h3>
                  <VaicMap
                    data={routeMap}
                    selectedRoute={selectedRoute}
                    onSelectedRouteChange={setSelectedRoute}
                  />
                </div>
              )}
            </div>
          )}

          {step === "tracking" && (
            <div style={{ display: "flex", gap: "20px", alignItems: "stretch" }}>
              {/* Nửa trái (70%) */}
              <div className="panel" style={{ flex: 7, display: "flex", flexDirection: "column", height: "550px" }}>
                <h2 style={{ marginBottom: "12px" }}>{t("enterprise.tracking_map")}</h2>
                <div style={{ flex: 1, position: "relative" }}>
                  <VaicMap
                    data={liveMap || routeMap || getMapPayload()}
                    trackingMarker={
                      trackingState?.location
                        ? {
                            lat: trackingState.location.lat,
                            lon: trackingState.location.lon,
                            label: `${getVehicleType(trackingState.state, selectedRoute, language)} - ${t("enterprise.shipment_id")} #${orderId}`,
                          }
                        : null
                    }
                  />
                </div>
              </div>

              {/* Nửa phải (30%) */}
              <div className="panel" style={{ flex: 3, display: "flex", flexDirection: "column", justifyContent: "space-between", height: "550px" }}>
                <div>
                  <h2 style={{ marginBottom: "16px" }}>{t("enterprise.progress")}</h2>
                  
                  <div className="metric" style={{ marginBottom: "20px" }}>
                    <span>{t("enterprise.shipment_id")}:</span>
                    <strong>#{orderId}</strong>
                  </div>
                  
                  <div className="metric" style={{ marginBottom: "20px" }}>
                    <span>{t("enterprise.transport_provider")}:</span>
                    <strong>{trackingState?.provider_name || t("orders.awaiting_assignment")}</strong>
                  </div>

                  <div className="metric" style={{ marginBottom: "20px" }}>
                    <span>{t("enterprise.vehicle")}:</span>
                    <strong>{getVehicleType(trackingState?.state || "", selectedRoute, language)}</strong>
                  </div>

                  <div className="metric" style={{ marginBottom: "20px" }}>
                    <span>{t("enterprise.status")}:</span>
                    <strong style={{ color: "#2563eb" }}>
                      {orderStateLabel(trackingState?.state, language)}
                    </strong>
                  </div>

                  <div className="metric" style={{ marginBottom: "12px" }}>
                    <span>{t("enterprise.route_progress")}:</span>
                    <strong>{trackingState ? Math.round(trackingState.progress * 100) : 0}%</strong>
                  </div>
                  
                  <div style={{ height: "8px", background: "#e2e8f0", borderRadius: "4px", overflow: "hidden", marginBottom: "20px" }}>
                    <div style={{ height: "100%", width: `${(trackingState?.progress || 0) * 100}%`, background: "#2563eb", transition: "width 0.5s ease" }} />
                  </div>

                  {/* Nhật ký hành trình */}
                  <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "14px", overflowY: "auto", maxHeight: "190px" }}>
                    <h3 style={{ fontSize: "13px", fontWeight: 700, marginBottom: "10px", color: "#475569" }}>{t("enterprise.timeline")}</h3>
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {trackingState?.timeline?.map((step, idx) => (
                        <div key={idx} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
                          <div style={{
                            width: "10px", height: "10px", borderRadius: "50%",
                            background: step.done ? "#10b981" : "#cbd5e1",
                            marginTop: "4px", flexShrink: 0
                          }} />
                          <div>
                            <div style={{ fontSize: "12px", fontWeight: step.done ? 600 : 400, color: step.done ? "#0f172a" : "#64748b" }}>
                              {step.event}
                            </div>
                            <div style={{ fontSize: "10px", color: "#94a3b8" }}>{step.time}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <button className="secondary" style={{ width: "100%" }} onClick={() => setStep("form")}>
                  {t("enterprise.back_to_form")}
                </button>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
