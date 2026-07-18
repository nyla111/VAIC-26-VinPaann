"use client";

import { FormEvent, useState } from "react";
import { VaicMap } from "@/components/VaicMap";
import { submitShipment } from "@/lib/api";
import type { DashboardView, OptimizeResult, RouteOption, ShipmentPayload } from "@/types/dashboard";

type Props = {
  view: DashboardView;
  onViewChange: (view: DashboardView) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
};

const statuses = ["available", "en_route", "maintenance"];

function fmtNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

function ShipmentForm({ view, onViewChange }: Pick<Props, "view" | "onViewChange">) {
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
      setError(err instanceof Error ? err.message : "Không tối ưu được tuyến.");
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
            Hub xuất phát
            <select name="hub_id" defaultValue="HUB_VITHANH">
              {view.hub_options.map((hub) => (
                <option key={hub.value} value={hub.value}>
                  {hub.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Commodity ID
            <select name="commodity_id" defaultValue="COM_RICE">
              {view.commodity_options.map((commodity) => (
                <option key={commodity} value={commodity}>
                  {commodity}
                </option>
              ))}
            </select>
          </label>
          <label>
            Loại hàng
            <input name="loai_hang" placeholder="lua_gao, ca_tra, buoi..." />
          </label>
          <label>
            Khối lượng kg
            <input name="khoi_luong_kg" type="number" min="1" step="0.1" defaultValue="5000" required />
          </label>
          <label>
            Timestamp
            <input name="timestamp" defaultValue="2026-01-15T08:00:00+07:00" required />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? "Đang tối ưu..." : "Tối ưu tuyến"}
          </button>
        </form>
      </div>
      {view.result ? <Recommendations view={view} result={view.result} /> : null}
    </>
  );
}

function Recommendations({ view, result }: { view: DashboardView; result: OptimizeResult }) {
  return (
    <>
      <div className="summary-strip">
        <div>
          <span>Route AI khuyến nghị</span>
          <strong>{result.recommended_route || "Không có"}</strong>
        </div>
        <div>
          <span>Priority</span>
          <strong>{result.priority.tier}</strong>
        </div>
        <div>
          <span>Weather TS</span>
          <strong>{result.evidence.weather_ts || "-"}</strong>
        </div>
        <div>
          <span>Price TS</span>
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
  const isRecommended = route.route_code === recommendedRoute;
  const disabled = route.trang_thai !== "available";
  return (
    <article className={`route-card ${isRecommended ? "recommended" : ""} ${disabled ? "disabled" : ""}`}>
      <header>
        <strong>{route.route_code}</strong>
        {isRecommended ? <span className="badge">Khuyến nghị</span> : null}
      </header>
      <p>{route.ten}</p>
      {route.trang_thai === "available" ? (
        <>
          <div className="metric">
            <span>Chi phí</span>
            <strong>{fmtNumber(route.chi_phi_du_doan_vnd)} VND</strong>
          </div>
          <div className="metric">
            <span>Thời gian</span>
            <strong>{route.thoi_gian_du_kien_gio ?? "-"} giờ</strong>
          </div>
        </>
      ) : (
        <div className="unavailable">{reasonLabels[route.ly_do || ""] || "Tuyến chưa khả dụng."}</div>
      )}
    </article>
  );
}

function Tracking({ view }: { view: DashboardView }) {
  const rows = view.tracking || [];
  if (!rows.length) return <div className="empty">Chưa có đơn nào trong session của user này.</div>;
  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>Thời điểm</th>
            <th>Hub</th>
            <th>Khối lượng</th>
            <th>Route</th>
            <th>Khuyến nghị</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => (
            <tr key={`${item.created_at}-${item.input.hub_id}`}>
              <td>{item.created_at}</td>
              <td>{item.input.hub_id}</td>
              <td>{item.input.khoi_luong_kg}</td>
              <td>{item.recommended_route || "-"}</td>
              <td>{item.khuyen_nghi || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Fleet({ view, statusFilter, onStatusFilterChange }: Props) {
  return (
    <div className="panel">
      <form className="inline-form" onSubmit={(event) => event.preventDefault()}>
        <label>
          Trạng thái
          <select value={statusFilter} onChange={(event) => onStatusFilterChange(event.target.value)}>
            <option value="">Tất cả</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </label>
      </form>
      <table>
        <thead>
          <tr>
            <th>Vehicle</th>
            <th>Loại</th>
            <th>Sức chứa</th>
            <th>Vị trí</th>
            <th>Trạng thái</th>
          </tr>
        </thead>
        <tbody>
          {(view.fleet || []).slice(0, 120).map((vehicle) => (
            <tr key={vehicle.vehicle_id}>
              <td>{vehicle.vehicle_id}</td>
              <td>{vehicle.vehicle_type}</td>
              <td>{vehicle.capacity_ton} tấn</td>
              <td>{vehicle.current_node_id}</td>
              <td>
                <span className="status">{vehicle.status}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Jobs({ view, admin = false }: { view: DashboardView; admin?: boolean }) {
  return (
    <div className="panel">
      {!view.ai2_live ? <span className="badge warning">{admin ? "AI2 MOCK" : "DEMO DATA"}</span> : null}
      <table>
        <thead>
          <tr>
            <th>Job</th>
            <th>Hub</th>
            <th>Khối lượng tích lũy</th>
            <th>Quyết định</th>
            <th>Thời gian chạy</th>
            <th>Route</th>
          </tr>
        </thead>
        <tbody>
          {(view.jobs || []).map((job) => (
            <tr key={job.job_id}>
              <td>{job.job_id}</td>
              <td>{job.hub_id}</td>
              <td>{job.khoi_luong_tich_luy_hien_tai_kg} kg</td>
              <td>{job.quyet_dinh}</td>
              <td>{job.thoi_gian_de_xuat_chay}</td>
              <td>{job.route_code}</td>
            </tr>
          ))}
        </tbody>
      </table>
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

function LogisticsOverview({ view }: { view: DashboardView }) {
  const overview = view.logistics_overview;
  const summary = overview?.summary;
  if (!overview || !summary) return <div className="empty">Không có dữ liệu tổng quan logistics.</div>;
  return (
    <>
      <div className="kpi-grid">
        <div className="kpi">
          <span>Waiting jobs</span>
          <strong>{summary.waiting_jobs}</strong>
          <small>Awaiting provider acceptance</small>
        </div>
        <div className="kpi">
          <span>Active deliveries</span>
          <strong>{summary.active_deliveries}</strong>
          <small>{(overview.vehicle_points || []).filter((vehicle) => vehicle.display_status === "in_delivery").length} trucks in transit</small>
        </div>
        <div className="kpi">
          <span>Available vehicles</span>
          <strong className="metric-available">{summary.available_vehicles}</strong>
          <small>Ready and stationary</small>
        </div>
        <div className="kpi">
          <span>Unavailable vehicles</span>
          <strong className="metric-unavailable">{summary.unavailable_vehicles}</strong>
          <small>Reserved or in maintenance</small>
        </div>
      </div>
      <div className="panel overview-map-panel">
        <div className="panel-heading">
          <div>
            <h2>Live Operations Map</h2>
            <p>Active deliveries, waiting jobs, and current fleet availability across the network.</p>
          </div>
          {!view.ai2_live ? <span className="badge warning">SIMULATED TRACKING</span> : <span className="badge">LIVE</span>}
        </div>
        <VaicMap data={overview} />
        <p className="note">
          Vehicle positions are simulated from current fleet status and assigned routes until live GPS tracking is connected.
        </p>
      </div>
    </>
  );
}

function Inventory({ view }: { view: DashboardView }) {
  const kpis = view.kpis;
  if (!kpis) return <div className="empty">Không có dữ liệu KPI.</div>;
  return (
    <>
      <div className="kpi-grid">
        <div className="kpi">
          <span>Chi phí tiết kiệm 30 ngày</span>
          <strong>{fmtNumber(kpis.cost_savings)} VND</strong>
        </div>
        <div className="kpi">
          <span>CO2e giảm so với đi thẳng</span>
          <strong>{fmtNumber(kpis.co2_savings_ton, 2)} tấn</strong>
        </div>
        <div className="kpi">
          <span>{kpis.time_direction === "faster" ? "Thời gian rút ngắn" : "Thời gian tăng thêm"}</span>
          <strong>{fmtNumber(kpis.time_delta_hours_abs, 1)} giờ</strong>
          <small>
            {fmtNumber(kpis.time_delta_pct_abs, 1)}% {kpis.time_direction === "faster" ? "nhanh hơn" : "chậm hơn"}
          </small>
        </div>
        <div className="kpi">
          <span>Đơn hàng trong phép tính</span>
          <strong>{kpis.compared_orders}</strong>
        </div>
      </div>
      <p className="note">
        Cửa sổ báo cáo: {kpis.reporting_start} đến {kpis.reporting_end}. Baseline là route A_DIRECT_ROAD; CO2e là proxy
        theo mode từ legs.csv và khối lượng đơn.
      </p>
      {view.map_payload ? (
        <div className="panel">
          <VaicMap data={view.map_payload} />
          <p className="note">Các tuyến trên bản đồ là đường thẳng nối node để demo, không phải đường thực tế theo quốc lộ/sông.</p>
        </div>
      ) : null}
    </>
  );
}

function Weather({ view }: { view: DashboardView }) {
  return (
    <div className="panel">
      <table>
        <thead>
          <tr>
            <th>Node</th>
            <th>Timestamp</th>
            <th>Road factor</th>
            <th>Water factor</th>
            <th>Alert</th>
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
        <h2>Errors</h2>
        {(view.errors || []).length <= 1 ? (
          <div className="empty">Không có lỗi batch đáng kể.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Error</th>
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

export function DashboardSection(props: Props) {
  const { view, onViewChange } = props;
  switch (view.section) {
    case "business_shipment_form":
    case "admin_simulation":
      return <ShipmentForm view={view} onViewChange={onViewChange} />;
    case "business_recommendations":
      return view.result ? (
        <Recommendations view={view} result={view.result} />
      ) : (
        <div className="empty">Chưa có kết quả. Gửi Shipment Form để xem đủ 5 tuyến đề xuất.</div>
      );
    case "business_tracking":
      return <Tracking view={view} />;
    case "logistics_overview":
      return <LogisticsOverview view={view} />;
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
      return <div className="empty">Section chưa được hỗ trợ.</div>;
  }
}
