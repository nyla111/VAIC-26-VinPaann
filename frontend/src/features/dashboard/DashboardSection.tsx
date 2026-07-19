"use client";

import React, { FormEvent, useState } from "react";
import dynamic from "next/dynamic";
const VaicMap = dynamic(() => import("@/components/VaicMap").then((m) => m.VaicMap), {
  ssr: false,
});

import {
  acceptLogisticsOrder,
  dispatchLogisticsOrders,
  getLogisticsOrders,
  submitShipment,
} from "@/lib/api";
import type { DashboardView, OptimizeResult, ProviderOrder, RouteOption, ShipmentPayload } from "@/types/dashboard";
import { useLanguage } from "@/context/LanguageContext";
import { formatCurrency, formatNumber, formatWeightKg, formatDurationHours, modeLabel, routeLabel } from "@/lib/labels";

type Props = {
  view: DashboardView;
  onViewChange: (view: DashboardView) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  forecastDate: string;
  onForecastDateChange: (value: string) => void;
};

const statuses = ["available", "en_route", "maintenance"];

function fmtNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

function ShipmentForm({ view, onViewChange }: Pick<Props, "view" | "onViewChange">) {
  const { t } = useLanguage();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    const payload: ShipmentPayload = {
      hub_id: String(form.get("hub_id")),
      commodity_id: String(form.get("commodity_id")),
      loai_hang: String(form.get("loai_hang") || ""),
      khoi_luong_kg: Number(form.get("khoi_luong_kg")),
      timestamp: String(form.get("timestamp")),
    };
    try {
      onViewChange(await submitShipment(payload));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("errors.generic"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="panel">
        {error ? <div className="alert">{error}</div> : null}
        <form onSubmit={onSubmit} className="grid-form">
          <label>
            {t("common.hub", "Hub xuất phát")}
            <select name="hub_id" defaultValue="HUB_VITHANH">
              {view.hub_options.map((hub) => (
                <option key={hub.value} value={hub.value}>
                  {hub.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("common.commodity", "Commodity")}
            <select name="commodity_id" defaultValue="COM_RICE">
              {view.commodity_options.map((commodity) => (
                <option key={commodity} value={commodity}>
                  {commodity}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("common.commodity", "Commodity")}
            <input name="loai_hang" placeholder={t("enterprise.custom_placeholder", "e.g. rice, catfish, pomelo...")} />
          </label>
          <label>
            {t("common.weight", "Khối lượng (kg)")}
            <input name="khoi_luong_kg" type="number" min="1" step="0.1" defaultValue="5000" required />
          </label>
          <label>
            {t("common.date", "Thời điểm tạo đơn")}
            <input name="timestamp" defaultValue="2026-01-15T08:00:00+07:00" required />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? t("common.loading") : t("route.optimize", "Tối ưu tuyến")}
          </button>
        </form>
      </div>
      {view.result ? <Recommendations view={view} result={view.result} /> : null}
    </>
  );
}

function Recommendations({ view, result }: { view: DashboardView; result: OptimizeResult }) {
  const { language, t } = useLanguage();
  return (
    <>
      <div className="summary-strip">
        <div>
          <span>{t("route.ai_recommendation", "Route AI khuyến nghị")}</span>
          <strong>{routeLabel(result.recommended_route, language)}</strong>
        </div>
        <div>
          <span>{t("route.priority", "Priority")}</span>
          <strong>{result.priority.tier}</strong>
        </div>
        <div>
          <span>{t("route.weather_timestamp", "Weather timestamp")}</span>
          <strong>{result.evidence.weather_ts || "-"}</strong>
        </div>
        <div>
          <span>{t("route.price_timestamp", "Price timestamp")}</span>
          <strong>{result.evidence.price_ts || "-"}</strong>
        </div>
      </div>
      {view.route_map ? (
        <div className="panel">
          <VaicMap data={view.route_map} selectedRoute={result.recommended_route} />
        </div>
      ) : null}
      <div className="route-grid">
        {result.phuong_an.map((route) => (
          <RouteCard
            key={route.route_code}
            route={route}
            recommendedRoute={result.recommended_route}
            reasonLabels={view.reason_labels}
          />
        ))}
      </div>
    </>
  );
}

function RouteCard({
  route,
  recommendedRoute,
  reasonLabels,
}: {
  route: RouteOption;
  recommendedRoute: string | null;
  reasonLabels: Record<string, string>;
}) {
  const { language, t } = useLanguage();
  const isRecommended = route.route_code === recommendedRoute;
  const disabled = route.trang_thai !== "available";
  return (
    <article className={`route-card ${isRecommended ? "recommended" : ""} ${disabled ? "disabled" : ""}`}>
      <header>
        <strong>{routeLabel(route.route_code, language)}</strong>
        {isRecommended ? <span className="badge">{t("route.recommended", "Khuyến nghị")}</span> : null}
      </header>
      <p>{route.ten}</p>
      {route.trang_thai === "available" ? (
        <>
          <div className="metric">
            <span>{t("common.cost", "Chi phí")}</span>
            <strong>{formatCurrency(route.chi_phi_du_doan_vnd, language)}</strong>
          </div>
          <div className="metric">
            <span>{t("common.time", "Thời gian")}</span>
            <strong>{formatDurationHours(route.thoi_gian_du_kien_gio, language)}</strong>
          </div>
        </>
      ) : (
        <div className="unavailable">{reasonLabels[route.ly_do || ""] || t("route.unavailable", "Tuyến chưa khả dụng.")}</div>
      )}
    </article>
  );
}

function Tracking({ view }: { view: DashboardView }) {
  const { language, t } = useLanguage();
  const rows = view.tracking || [];
  if (!rows.length) return <div className="empty">{language === "vi" ? "Chưa có đơn nào trong phiên của người dùng này." : "No orders in this user's session yet."}</div>;
  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>{t("common.time")}</th><th>{t("common.hub")}</th><th>{t("common.weight")}</th><th>{t("common.route")}</th><th>{language === "vi" ? "Khuyến nghị" : "Recommendation"}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => (
            <tr key={`${item.created_at}-${item.input.hub_id}`}>
              <td>{item.created_at}</td>
              <td>{item.input.hub_id}</td>
              <td>{formatWeightKg(item.input.khoi_luong_kg, language)}</td>
              <td>{routeLabel(item.recommended_route, language)}</td>
              <td>{item.khuyen_nghi || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Fleet({ view, statusFilter, onStatusFilterChange, forecastDate, onForecastDateChange }: Props) {
  const [searchTerm, setSearchTerm] = useState("");
  const { language, t } = useLanguage();

  const statusColors: Record<string, string> = {
    available: "bg-green-100 text-green-800 border-green-200",
    in_transit: "bg-blue-100 text-blue-800 border-blue-200",
    en_route: "bg-blue-100 text-blue-800 border-blue-200",
    maintenance: "bg-gray-100 text-gray-600 border-gray-200"
  };

  const fleet = view.fleet || [];

  // Filter vehicles on client side based on search
  const filteredFleet = fleet.filter((vehicle) => {
    const vehicleId = vehicle.vehicle_id || "";
    const plateMatches = vehicleId.toLowerCase().includes(searchTerm.toLowerCase());
    return plateMatches;
  });

  return (
    <div className="panel flex flex-col gap-6">
      {/* Search and Filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-100 pb-4">
        <div className="flex-1 max-w-sm">
          <input
            type="text"
            placeholder={t("fleet.search", "Tìm kiếm biển số...")}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-500 mr-2">{t("common.status", "Trạng thái")}:</span>
          {["", "available", "in_transit", "maintenance"].map((status) => (
            <button
              key={status}
              type="button"
              className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${
                statusFilter === status
                  ? "bg-blue-600 text-white border-blue-600 shadow"
                  : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
              }`}
              onClick={() => onStatusFilterChange(status)}
            >
              {status === "" ? t("common.all") : t(`fleet.${status}`, status.replaceAll("_", " "))}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm font-semibold text-gray-500">
          {t("fleet.forecast_date", "Ngày forecast")}
          <input
            type="date"
            value={forecastDate}
            onChange={(event) => onForecastDateChange(event.target.value)}
            className="border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm text-gray-700"
          />
        </label>
      </div>

      {view.fleet_forecast ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {(["road", "water"] as const).map((mode) => {
            const forecast = view.fleet_forecast?.modes[mode];
            if (!forecast) return null;
            const label = modeLabel(mode, language);
            return (
              <div key={mode} className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-bold text-gray-900">{label}</h3>
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${forecast.enough_vehicles ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    {forecast.enough_vehicles ? t("fleet.enough", "Đủ xe") : t("fleet.shortage", "Thiếu {value} tấn", { value: formatNumber(forecast.capacity_gap_kg / 1000, language, 1) })}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                  <div><span className="text-gray-500 block">{t("fleet.demand", "Nhu cầu dự báo")}</span><strong>{formatWeightKg(forecast.demand_kg, language)}</strong></div>
                  <div><span className="text-gray-500 block">{t("fleet.vehicles_needed", "Xe cần chuẩn bị")}</span><strong>{formatNumber(forecast.vehicles_needed, language)} {language === "vi" ? "xe" : "vehicles"}</strong></div>
                  <div><span className="text-gray-500 block">{t("fleet.available_vehicles", "Xe đang sẵn sàng")}</span><strong>{formatNumber(forecast.available_vehicles, language)} {language === "vi" ? "xe" : "vehicles"}</strong></div>
                  <div><span className="text-gray-500 block">{t("fleet.available_capacity", "Sức chứa sẵn sàng")}</span><strong>{formatWeightKg(forecast.available_capacity_kg, language)}</strong></div>
                </div>
                <p className="mt-3 text-xs text-gray-500">
                  {formatNumber(forecast.orders_count, language)} {language === "vi" ? "đơn đã biết" : "known orders"} · {formatWeightKg(forecast.predicted_weight_kg, language)} {language === "vi" ? "dự kiến bổ sung" : "predicted additional demand"} · {t("fleet.confidence", "Độ tin cậy")} {formatNumber(forecast.confidence * 100, language)}%
                </p>
              </div>
            );
          })}
        </div>
      ) : null}

      {/* Fleet Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{language === "vi" ? "Biển số / ký hiệu" : "License plate / ID"}</th>
              <th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{language === "vi" ? "Loại phương tiện" : "Vehicle type"}</th>
              <th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{language === "vi" ? "Tải trọng" : "Capacity"}</th>
              <th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{language === "vi" ? "Vị trí hiện tại" : "Current location"}</th>
              <th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{t("common.status")}</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredFleet.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400 text-sm">
                  {t("common.no_results")}
                </td>
              </tr>
            ) : (
              filteredFleet.map((vehicle) => (
                <tr key={vehicle.vehicle_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3.5 whitespace-nowrap text-sm font-bold text-gray-900">
                    {vehicle.vehicle_id}
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap text-sm text-gray-500">
                    {modeLabel(vehicle.vehicle_type, language)}
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap text-sm text-gray-900 font-medium">
                    {formatWeightKg(Number(vehicle.capacity_ton) * 1000, language)}
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap text-sm text-gray-500">
                    {vehicle.current_node_id === "CT_HUB" ? "Cần Thơ Hub" : vehicle.current_node_id}
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-bold border ${
                      statusColors[vehicle.status] || "bg-gray-100 text-gray-800"
                    }`}>
                    {t(`fleet.${vehicle.status}`, vehicle.status.replaceAll("_", " "))}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Jobs({ view, admin = false }: { view: DashboardView; admin?: boolean }) {
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const { language, t } = useLanguage();

  const statusLabels: Record<string, string> = {
    waiting_for_pickup: t("jobs.waiting_for_pickup"),
    moving_to_can_tho: t("jobs.moving_to_can_tho"),
    consolidating_at_can_tho: t("jobs.consolidating_at_can_tho"),
    dispatching_to_hcm: t("jobs.dispatching_to_hcm"),
    completed: t("jobs.completed"),
  };

  const statusColors: Record<string, string> = {
    waiting_for_pickup: "bg-amber-100 text-amber-800 border-amber-200",
    moving_to_can_tho: "bg-blue-100 text-blue-800 border-blue-200",
    consolidating_at_can_tho: "bg-purple-100 text-purple-800 border-purple-200",
    dispatching_to_hcm: "bg-indigo-100 text-indigo-800 border-indigo-200",
    completed: "bg-green-100 text-green-800 border-green-200",
  };

  const jobs = view.jobs || [];

  return (
    <div className="panel flex flex-col gap-4">
      <div className="flex justify-between items-center border-b border-gray-100 pb-3">
        <div>
          <h2 className="text-lg font-bold">{t("jobs.title")}</h2>
          <p className="text-xs text-gray-500">{t("jobs.description")}</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{language === "vi" ? "Mã chuyến" : "Job ID"}</th><th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{language === "vi" ? "Biển số xe" : "Vehicle ID"}</th><th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{t("common.mode")}</th><th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{t("common.weight")}</th><th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{language === "vi" ? "Lấp đầy" : "Fill"}</th><th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{t("common.status")}</th><th className="px-4 py-3 bg-gray-50 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">{t("common.view_details")}</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">
                  {t("jobs.no_jobs")}
                </td>
              </tr>
            ) : (
              jobs.map((job) => {
                const isExpanded = expandedJobId === job.job_id;
                return (
                  <React.Fragment key={job.job_id}>
                    <tr
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => setExpandedJobId(isExpanded ? null : job.job_id)}
                    >
                      <td className="px-4 py-4 whitespace-nowrap text-sm font-bold text-blue-700">
                        {job.job_id}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                        {(job as any).vehicle_plate || "N/A"}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                        {modeLabel(job.mode, language)}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {formatWeightKg((job as any).total_weight_kg ?? job.khoi_luong_tich_luy_hien_tai_kg, language)}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-600 font-bold">
                        {fmtNumber(((job as any).fill_ratio ?? 0) * 100, 1)}%
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-bold border ${
                          statusColors[job.status || ""] || "bg-gray-100 text-gray-800"
                        }`}>
                          {statusLabels[job.status || ""] || job.status || "Chưa rõ"}
                        </span>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-xs text-blue-600 font-bold">
                        {isExpanded ? `${t("jobs.collapse")} ▲` : `${t("jobs.details")} ▼`}
                      </td>
                    </tr>
                    
                    {isExpanded && (
                      <tr className="bg-gray-50">
                        <td colSpan={7} className="px-6 py-4">
                          <div className="border border-gray-200 rounded-lg bg-white p-4 flex flex-col gap-3 shadow-inner">
                            <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider border-b border-gray-100 pb-2">
                              {language === "vi" ? "Danh sách đơn hàng vận chuyển" : "Shipment orders"} ({((job as any).shipments || []).length})
                            </h4>
                            {(!((job as any).shipments) || ((job as any).shipments).length === 0) ? (
                              <p className="text-sm text-gray-400">{t("common.no_data")}</p>
                            ) : (
                              <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-100 text-xs">
                                  <thead>
                                    <tr>
                                      <th className="px-3 py-2 bg-gray-50 text-left font-bold text-gray-500">{language === "vi" ? "Mã đơn hàng" : "Order ID"}</th><th className="px-3 py-2 bg-gray-50 text-left font-bold text-gray-500">{t("common.hub")}</th><th className="px-3 py-2 bg-gray-50 text-left font-bold text-gray-500">{t("common.commodity")}</th><th className="px-3 py-2 bg-gray-50 text-left font-bold text-gray-500">{t("common.weight")}</th><th className="px-3 py-2 bg-gray-50 text-left font-bold text-gray-500">{t("common.deadline")}</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-gray-100">
                                    {((job as any).shipments || []).map((s: any) => (
                                      <tr key={s.shipment_id}>
                                        <td className="px-3 py-2 whitespace-nowrap font-semibold text-gray-900">ORDER-{s.shipment_id}</td>
                                        <td className="px-3 py-2 whitespace-nowrap text-gray-600">{s.hub_id}</td>
                                        <td className="px-3 py-2 whitespace-nowrap text-gray-600">{s.loai_hang}</td>
                                        <td className="px-3 py-2 whitespace-nowrap text-gray-900 font-medium">{formatWeightKg(s.weight_kg, language)}</td>
                                        <td className="px-3 py-2 whitespace-nowrap text-gray-500">{s.deadline}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Deliveries({ view }: { view: DashboardView }) {
  return (
    <div className="card-list">
      {(view.deliveries || []).map((delivery) => (
        <article className="panel compact" key={delivery.delivery_id}>
          <strong>{delivery.delivery_id}</strong>
          <span>{delivery.route_code}</span>
          <span className="status">{delivery.status}</span>
          <span>ETA {delivery.eta}</span>
        </article>
      ))}
    </div>
  );
}

function LogisticsOrders({ view, onViewChange }: Pick<Props, "view" | "onViewChange">) {
  const { language, t } = useLanguage();
  const queue = view.provider_orders;
  const [selectedVehicleByOrder, setSelectedVehicleByOrder] = useState<Record<number, string>>({});
  const [selectedOrderIds, setSelectedOrderIds] = useState<number[]>([]);
  const [dispatchVehicle, setDispatchVehicle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!queue) return <div className="empty">{t("orders.no_queue")}</div>;

  const orders = queue.orders || [];
  const acceptedOrders = orders.filter((order) => order.provider_assignment_status === "accepted");
  const selectedAccepted = acceptedOrders.filter((order) => selectedOrderIds.includes(order.order_id));
  const selectedWeight = selectedAccepted.reduce((total, order) => total + order.weight_ton * 1000, 0);
  const selectedMode = selectedAccepted[0]?.required_outbound_mode;
  const dispatchVehicles = queue.vehicles.filter(
    (vehicle) =>
      vehicle.status === "available" &&
      vehicle.mode === selectedMode &&
      vehicle.capacity_kg >= selectedWeight &&
      selectedAccepted.every((order) => order.assigned_vehicle_id === vehicle.vehicle_id),
  );

  async function reloadQueue() {
    const next = await getLogisticsOrders();
    onViewChange({ ...view, provider_orders: next });
  }

  async function acceptOrder(order: ProviderOrder) {
    const vehicleId = selectedVehicleByOrder[order.order_id] || order.transport_options[0]?.vehicle_id;
    if (!vehicleId) {
      setError(t("errors.vehicle_unavailable"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await acceptLogisticsOrder(order.order_id, vehicleId);
      await reloadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("orders.accept_failed", "Không thể nhận đơn."));
    } finally {
      setBusy(false);
    }
  }

  async function dispatchSelected() {
    if (!selectedOrderIds.length || !dispatchVehicle) return;
    setBusy(true);
    setError(null);
    try {
      await dispatchLogisticsOrders(selectedOrderIds, dispatchVehicle);
      setSelectedOrderIds([]);
      setDispatchVehicle("");
      await reloadQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("orders.dispatch_failed", "Không thể xuất bến."));
    } finally {
      setBusy(false);
    }
  }

  function toggleOrder(orderId: number) {
    setSelectedOrderIds((current) =>
      current.includes(orderId) ? current.filter((id) => id !== orderId) : [...current, orderId],
    );
  }

  return (
    <div className="panel flex flex-col gap-4">
      <div className="flex justify-between items-start border-b border-gray-100 pb-3">
        <div>
          <h2 className="text-lg font-bold">{t("orders.waiting_title", "Đơn hàng chờ nhận tại Cần Thơ")}</h2>
          <p className="text-xs text-gray-500">{t("orders.waiting_description", "Chọn xe phù hợp, nhận đơn rồi gom nhiều đơn trước khi xuất bến.")}</p>
        </div>
        <div className="text-right text-xs text-gray-500">
          <div>{formatNumber(queue.summary.open_orders, language)} {t("orders.open", "đơn đang mở")}</div>
          <strong className="text-blue-700">{formatWeightKg(queue.summary.waiting_weight_kg, language)}</strong>
        </div>
      </div>

      {error ? <div className="alert">{error}</div> : null}

      {acceptedOrders.length > 0 ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 flex flex-col gap-3">
          <div className="flex justify-between items-center gap-3">
            <div>
              <strong className="text-sm text-blue-900">{t("orders.ready_to_dispatch", "Sẵn sàng xuất bến")}</strong>
              <p className="text-xs text-blue-700 m-0">{t("orders.accepted_summary", "Đã nhận {count} đơn. Có thể gom các đơn cùng xe và cùng phương thức.", { count: acceptedOrders.length })}</p>
            </div>
            <button className="primary" disabled={busy || !selectedOrderIds.length || !dispatchVehicle} onClick={dispatchSelected}>
              {busy ? t("common.loading") : t("orders.dispatch")}
            </button>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            {acceptedOrders.map((order) => (
              <label key={order.order_id} className="text-xs flex items-center gap-1 bg-white border border-blue-100 rounded px-2 py-1">
                <input type="checkbox" checked={selectedOrderIds.includes(order.order_id)} onChange={() => toggleOrder(order.order_id)} />
                {order.id} · {fmtNumber(order.weight_ton, 1)} tấn
              </label>
            ))}
            <select
              value={dispatchVehicle}
              onChange={(event) => setDispatchVehicle(event.target.value)}
              className="text-xs border border-blue-200 rounded px-2 py-1 bg-white"
            >
              <option value="">{t("orders.select_dispatch_vehicle", "Chọn xe xuất bến")}</option>
              {dispatchVehicles.map((vehicle) => (
                <option key={vehicle.vehicle_id} value={vehicle.vehicle_id}>
                  {vehicle.vehicle_id} · {fmtNumber(vehicle.capacity_ton, 1)} tấn
                </option>
              ))}
            </select>
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {orders.length === 0 ? (
          <div className="empty lg:col-span-2">{t("orders.no_waiting", "Hiện chưa có đơn nào chờ provider nhận tại Cần Thơ.")}</div>
        ) : (
          orders.map((order) => {
            const selectedVehicle = selectedVehicleByOrder[order.order_id] || order.transport_options[0]?.vehicle_id || "";
            const accepted = order.provider_assignment_status === "accepted";
            return (
              <article key={order.order_id} className={`rounded-lg border p-4 flex flex-col gap-3 ${accepted ? "border-blue-200 bg-blue-50/40" : "border-gray-200 bg-white"}`}>
                <div className="flex justify-between items-start gap-3">
                  <div>
                    <strong className="text-blue-700">{order.id}</strong>
                    <h3 className="font-bold text-gray-900 m-0 mt-1">{order.business_name}</h3>
                    <p className="text-xs text-gray-500 m-0">{order.commodity} · {order.origin} → {order.destination}</p>
                  </div>
                  <span className="text-xs font-bold rounded-full px-2 py-1 bg-gray-100 text-gray-700">
                    {accepted ? t("orders.accepted") : t("orders.open")}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div><span className="text-gray-500 block">{t("common.weight")}</span><strong>{formatWeightKg(order.weight_ton * 1000, language)}</strong></div>
                  <div><span className="text-gray-500 block">{t("common.mode")}</span><strong>{modeLabel(order.required_outbound_mode, language)}</strong></div>
                  <div><span className="text-gray-500 block">{t("orders.selected_vehicle", "Xe đã chọn")}</span><strong>{order.assigned_vehicle_id || t("common.not_available")}</strong></div>
                </div>
                {!accepted ? (
                  <div className="flex gap-2 items-center">
                    <select
                      value={selectedVehicle}
                      onChange={(event) => setSelectedVehicleByOrder((current) => ({ ...current, [order.order_id]: event.target.value }))}
                      className="flex-1 text-xs border border-gray-200 rounded px-2 py-2 bg-white"
                    >
                      <option value="">{t("orders.select_vehicle")}</option>
                      {order.transport_options.map((vehicle) => (
                        <option key={vehicle.vehicle_id} value={vehicle.vehicle_id}>
                          {vehicle.vehicle_id} · {fmtNumber(vehicle.capacity_ton, 1)} tấn
                        </option>
                      ))}
                    </select>
                    <button className="primary" disabled={busy || !selectedVehicle} onClick={() => acceptOrder(order)}>
                      {t("orders.accept")}
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-blue-700 m-0">{t("orders.held_for_vehicle", "Đã giữ đơn cho xe {vehicle}. Chọn đơn ở trên để gom và xuất bến.", { vehicle: order.assigned_vehicle_id || "-" })}</p>
                )}
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}

function Inventory({ view }: { view: DashboardView }) {
  const kpis = view.kpis;
  const { language, t } = useLanguage();
  if (!kpis) return <div className="empty">{t("common.no_data")}</div>;
  return (
    <>
      <div className="kpi-grid">
        <div className="kpi">
          <span>{t("admin.cost_savings")}</span>
          <strong>{formatCurrency(kpis.cost_savings, language)}</strong>
        </div>
        <div className="kpi">
          <span>CO2e {language === "vi" ? "giảm so với đi thẳng" : "reduction vs direct road"}</span>
          <strong>{formatWeightKg(kpis.co2_savings_ton * 1000, language, 2)}</strong>
        </div>
        <div className="kpi">
          <span>{kpis.time_direction === "faster" ? (language === "vi" ? "Thời gian rút ngắn" : "Time saved") : (language === "vi" ? "Thời gian tăng thêm" : "Time added")}</span>
          <strong>{formatDurationHours(kpis.time_delta_hours_abs, language)}</strong>
          <small>
            {formatNumber(kpis.time_delta_pct_abs, language, 1)}% {kpis.time_direction === "faster" ? (language === "vi" ? "nhanh hơn" : "faster") : (language === "vi" ? "chậm hơn" : "slower")}
          </small>
        </div>
        <div className="kpi">
          <span>{language === "vi" ? "Đơn hàng trong phép tính" : "Orders compared"}</span>
          <strong>{formatNumber(kpis.compared_orders, language)}</strong>
        </div>
      </div>
      <p className="note">
        {language === "vi" ? "Cửa sổ báo cáo" : "Reporting window"}: {kpis.reporting_start} → {kpis.reporting_end}. {language === "vi" ? "Baseline là route A_DIRECT_ROAD; CO2e là proxy theo mode và khối lượng đơn." : "Baseline is A_DIRECT_ROAD; CO2e is a mode and order-weight proxy."}
      </p>
      {view.map_payload ? (
        <div className="panel">
          <VaicMap data={view.map_payload} />
          <p className="note">{language === "vi" ? "Các tuyến hiển thị theo hành lang địa lý đã cấu hình cho demo." : "Routes use the configured geographic corridors for the demo."}</p>
        </div>
      ) : null}
    </>
  );
}

function Weather({ view }: { view: DashboardView }) {
  const { language, t } = useLanguage();
  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>{language === "vi" ? "Hub" : "Node"}</th><th>{t("common.time")}</th><th>{language === "vi" ? "Hệ số đường bộ" : "Road factor"}</th><th>{language === "vi" ? "Hệ số đường thủy" : "Water factor"}</th><th>{language === "vi" ? "Cảnh báo" : "Alert"}</th>
          </tr>
        </thead>
        <tbody>
          {(view.weather || []).map((row) => (
            <tr key={row.node_id}>
              <td>{row.node_id}</td>
              <td>{row.ts}</td>
              <td>{row.road_factor.toFixed(3)}</td>
              <td>{row.water_factor.toFixed(3)}</td>
              <td>{row.alert_level}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Logs({ view }: { view: DashboardView }) {
  const { language, t } = useLanguage();
  const routeCounts = view.kpis?.route_counts || {};
  const max = Math.max(1, ...Object.values(routeCounts));
  return (
    <>
      <div className="panel">
        <div className="bar-chart">
          {Object.entries(routeCounts).map(([route, count]) => (
            <div className="bar-row" key={route}>
              <span>{route}</span>
              <div>
                <strong style={{ width: `${(count / max) * 100}%` }} />
              </div>
              <em>{count}</em>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <h2>{language === "vi" ? "Lỗi hệ thống" : "Errors"}</h2>
        {(view.errors || []).length <= 1 ? (
          <div className="empty">{t("admin.no_exceptions", "Không có lỗi batch đáng kể.")}</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t("common.orders")}</th><th>{language === "vi" ? "Lỗi" : "Error"}</th>
              </tr>
            </thead>
            <tbody>
              {(view.errors || []).map((error, index) => (
                <tr key={`${error.order_id}-${index}`}>
                  <td>{error.order_id}</td>
                  <td>{error.error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function LogisticsOverview({ view }: { view: DashboardView }) {
  const { language, t } = useLanguage();
  const overview = view.logistics_overview;
  const summary = overview?.summary;
  if (!overview || !summary) return <div className="text-gray-500 p-4 border border-dashed border-gray-200 rounded-lg bg-white text-center">{language === "vi" ? "Không có dữ liệu tổng quan logistics." : "No logistics overview data available."}</div>;

  const totalVehicles = overview.vehicle_points?.length || 0;
  const availableVehicles = (overview.vehicle_points || []).filter(v => v.display_status === "available").length;
  const transitVehicles = (overview.vehicle_points || []).filter(v => v.display_status === "in_delivery").length;
  const maintenanceVehicles = (overview.vehicle_points || []).filter(v => v.source_status === "maintenance").length;

  const activeJobs = overview.active_deliveries || [];

  const statusLabels: Record<string, string> = {
    waiting_for_pickup: t("jobs.waiting_for_pickup"), moving_to_can_tho: t("jobs.moving_to_can_tho"), consolidating_at_can_tho: t("jobs.consolidating_at_can_tho"), dispatching_to_hcm: t("jobs.dispatching_to_hcm"), completed: t("jobs.completed"),
  };

  const statusColors: Record<string, string> = {
    waiting_for_pickup: "bg-amber-100 text-amber-800 border-amber-200",
    moving_to_can_tho: "bg-blue-100 text-blue-800 border-blue-200",
    consolidating_at_can_tho: "bg-purple-100 text-purple-800 border-purple-200",
    dispatching_to_hcm: "bg-indigo-100 text-indigo-800 border-indigo-200",
    completed: "bg-green-100 text-green-800 border-green-200",
  };

  const consolidatingJobs = activeJobs.filter(j => j.status === "consolidating_at_can_tho");
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-10 gap-6 animate-fade-in" style={{ minHeight: "600px" }}>
      {/* Left Column: 70% Map View */}
      <div className="md:col-span-7 flex flex-col" style={{ height: "650px" }}>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm flex flex-col h-full p-4">
          <div className="flex justify-between items-center mb-3">
            <div>
              <h2 className="text-lg font-extrabold text-gray-800 m-0">{language === "vi" ? "Bản đồ giám sát hành trình" : "Shipment monitoring map"}</h2>
              <p className="text-xs text-gray-500 m-0 mt-1">{language === "vi" ? "Vị trí trực quan của phương tiện và luồng hàng." : "Live positions of vehicles and shipment flows."}</p>
            </div>
            <span className="bg-red-100 text-red-800 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider border border-red-200">LIVE TRACKING</span>
          </div>
          <div className="relative flex-1 rounded-md overflow-hidden border border-gray-200">
            <VaicMap data={overview} />
          </div>
        </div>
      </div>

      {/* Right Column: 30% Stack of UI Cards */}
      <div className="md:col-span-3 flex flex-col gap-4 overflow-y-auto pr-1" style={{ maxHeight: "650px" }}>
        
        {/* Card 1: Fleet Status Summary Card */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm flex flex-col gap-3 p-4">
          <div className="border-b border-gray-100 pb-2 flex justify-between items-center">
            <h3 className="text-sm font-extrabold text-gray-800 m-0 uppercase tracking-wider">{language === "vi" ? "Tóm tắt đội xe" : "Fleet summary"}</h3>
            <span className="text-xs text-gray-400 font-semibold">{totalVehicles} {language === "vi" ? "phương tiện" : "vehicles"}</span>
          </div>
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between p-2 rounded bg-green-50 border border-green-100">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-green-600"></span>
                <span className="text-xs text-green-800 font-semibold">{t("fleet.available")}</span>
              </div>
              <strong className="text-sm text-green-900 font-bold">{availableVehicles} {language === "vi" ? "xe" : "vehicles"}</strong>
            </div>

            <div className="flex items-center justify-between p-2 rounded bg-blue-50 border border-blue-100">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
                <span className="text-xs text-blue-800 font-semibold">{t("fleet.in_transit")}</span>
              </div>
              <strong className="text-sm text-blue-900 font-bold">{transitVehicles} {language === "vi" ? "xe" : "vehicles"}</strong>
            </div>

            <div className="flex items-center justify-between p-2 rounded bg-gray-50 border border-gray-200">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-gray-400"></span>
                <span className="text-xs text-gray-600 font-semibold">{t("fleet.maintenance")}</span>
              </div>
              <strong className="text-sm text-gray-800 font-bold">{maintenanceVehicles} {language === "vi" ? "xe" : "vehicles"}</strong>
            </div>
          </div>
        </div>

        {/* Card 2: Active Transportation Jobs Card */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm flex flex-col gap-3 p-4">
          <div className="border-b border-gray-100 pb-2">
            <h3 className="text-sm font-extrabold text-gray-800 m-0 uppercase tracking-wider">{language === "vi" ? "Chuyến xe đang vận hành" : "Active transport jobs"}</h3>
          </div>
          <div className="flex flex-col gap-2 max-h-[220px] overflow-y-auto pr-1">
            {activeJobs.length === 0 ? (
              <div className="text-xs text-gray-400 text-center py-4 border border-dashed border-gray-200 rounded">{language === "vi" ? "Không có chuyến xe nào đang hoạt động." : "No active transport jobs."}</div>
            ) : (
              activeJobs.map((job) => (
                <div key={job.delivery_id} className="p-2.5 border border-gray-100 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors flex flex-col gap-1.5 animate-slide-in">
                  <div className="flex justify-between items-center">
                    <strong className="text-xs font-bold text-blue-700">{job.delivery_id}</strong>
                    <span className="text-[10px] text-gray-500 font-semibold bg-white px-1.5 py-0.5 rounded border border-gray-200">{t("common.route")}: {routeLabel(job.route_code, language)}</span>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                      statusColors[job.status] || "bg-gray-100 text-gray-800 border-gray-200"
                    }`}>
                      {statusLabels[job.status] || job.status}
                    </span>
                    <span className="text-[10px] text-gray-600 font-bold">ETA: {job.eta}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Card 3: AI Predictive Alerts Card */}
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm flex flex-col gap-3 p-4">
          <div className="border-b border-gray-100 pb-2">
            <h3 className="text-sm font-extrabold text-gray-800 m-0 uppercase tracking-wider">{language === "vi" ? "Dự báo và cảnh báo AI" : "AI forecasts and alerts"}</h3>
          </div>
          <div className="flex flex-col gap-2">
            {consolidatingJobs.length > 0 ? (
              consolidatingJobs.map((job) => {
                const plate = job.delivery_id.replace("JOB-", "");
                return (
                  <div key={job.delivery_id} className="border-l-4 border-purple-500 bg-purple-50 p-2.5 rounded-r-lg animate-slide-in">
                    <strong className="text-[11px] text-purple-800 block font-bold">{language === "vi" ? "Tiến trình gom hàng Cần Thơ" : "Can Tho consolidation progress"}</strong>
                    <p className="text-xs text-purple-700 mt-1 mb-0 leading-relaxed">
                      {language === "vi" ? <>Xe <strong className="font-extrabold">{plate}</strong> đang gom hàng tại Cần Thơ. Dự báo đầy tải và xuất bến lúc <strong className="font-extrabold">{job.eta}</strong>. (Tin cậy 92%).</> : <>Vehicle <strong className="font-extrabold">{plate}</strong> is consolidating at Can Tho. Full-load and dispatch are forecast for <strong className="font-extrabold">{job.eta}</strong>. (92% confidence).</>}
                    </p>
                  </div>
                );
              })
            ) : (
              <div className="border-l-4 border-green-500 bg-green-50 p-2.5 rounded-r-lg">
                <strong className="text-[11px] text-green-800 block font-bold">{language === "vi" ? "Trạng thái gom hàng Cần Thơ" : "Can Tho consolidation status"}</strong>
                <p className="text-xs text-green-700 mt-1 mb-0 leading-relaxed">
                  {language === "vi" ? "Tất cả luồng hàng Cần Thơ hoạt động tối ưu. Không phát hiện sự cố tắc nghẽn hoặc quá tải." : "All Can Tho flows are operating normally. No congestion or overload detected."}
                </p>
              </div>
            )}

            <div className="border-l-4 border-blue-500 bg-blue-50 p-2.5 rounded-r-lg">
              <strong className="text-[11px] text-blue-800 block font-bold">{language === "vi" ? "Thời tiết và thủy văn" : "Weather and hydrology"}</strong>
              <p className="text-xs text-blue-700 mt-1 mb-0 leading-relaxed">
                {language === "vi" ? "Các tuyến sông Tiền và sông Hậu có mực nước bình thường. Giao thông vận tải thủy bộ an toàn." : "Water levels on the Tien and Hau rivers are normal. Road and water transport are safe."}
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

export function DashboardSection(props: Props) {
  const { language } = useLanguage();
  const { view, onViewChange } = props;
  switch (view.section) {
    case "business_shipment_form":
    case "admin_simulation":
      return <ShipmentForm view={view} onViewChange={onViewChange} />;
    case "business_recommendations":
      return view.result ? (
        <Recommendations view={view} result={view.result} />
      ) : (
        <div className="empty">{language === "vi" ? "Chưa có kết quả. Gửi biểu mẫu vận chuyển để xem 5 tuyến đề xuất." : "No result yet. Submit the shipment form to see five route options."}</div>
      );
    case "business_tracking":
      return <Tracking view={view} />;
    case "logistics_overview":
      return <LogisticsOverview view={view} />;
    case "logistics_orders":
      return <LogisticsOrders view={view} onViewChange={onViewChange} />;
    case "logistics_fleet":
      return <Fleet {...props} />;
    case "logistics_jobs":
      return <Jobs view={view} />;
    case "logistics_deliveries":
      return <Deliveries view={view} />;
    case "admin_inventory":
      return <Inventory view={view} />;
    case "admin_weather":
      return <Weather view={view} />;
    case "admin_dispatch":
      return <Jobs view={view} admin />;
    case "admin_logs":
      return <Logs view={view} />;
    default:
      return <div className="empty">{language === "vi" ? "Mục này chưa được hỗ trợ." : "This section is not supported yet."}</div>;
  }
}
