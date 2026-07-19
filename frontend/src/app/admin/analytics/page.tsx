"use client";

import { useMemo, useState } from "react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  ORDERS_OVER_TIME, VOLUME_BY_MODE, COST_OVER_TIME,
  ROUTE_MIX, SAVINGS_BY_ROUTE, DISPATCH_MIX, FORECAST_VS_ACTUAL,
  STATUS_DISTRIBUTION, BUSINESSES, PROVIDERS, ORDERS,
} from "@/data/adminMockData";
import { useLanguage } from "@/context/LanguageContext";
import { formatDate } from "@/lib/labels";

type Tab = "overview" | "orders" | "businesses" | "logistics" | "ai";

const COLORS = {
  blue: "#1d4ed8",
  green: "#047857",
  red: "#dc2626",
  purple: "#6366f1",
  amber: "#d97706",
  teal: "#0369a1",
  gray: "#64748b",
};

const ANALYTICS_TEXT: Record<string, { vi: string; en: string }> = {
  "Orders Over Time": { vi: "Đơn hàng theo thời gian", en: "Orders over time" },
  "Total vs Delivered": { vi: "Tổng số và đã giao", en: "Total vs delivered" },
  "Orders by Status": { vi: "Đơn hàng theo trạng thái", en: "Orders by status" },
  "Current distribution": { vi: "Phân bổ hiện tại", en: "Current distribution" },
  "Transport Volume by Mode": { vi: "Sản lượng theo phương thức", en: "Transport volume by mode" },
  "Monthly tonnage (tons)": { vi: "Sản lượng theo tháng (tấn)", en: "Monthly tonnage (tons)" },
  "Stacked by road, waterway, and multimodal": { vi: "Phân theo đường bộ, đường thủy và đa phương thức", en: "Stacked by road, waterway, and multimodal" },
  "Total Transport Cost Over Time": { vi: "Tổng chi phí vận chuyển theo thời gian", en: "Total transport cost over time" },
  "Millions VND": { vi: "Triệu VND", en: "Millions VND" },
  "Orders by Commodity": { vi: "Đơn hàng theo nông sản", en: "Orders by commodity" },
  "Order Volume by Origin Province": { vi: "Sản lượng theo tỉnh xuất phát", en: "Order volume by origin province" },
  "Total tonnage": { vi: "Tổng sản lượng", en: "Total tonnage" },
  "Average Delivery Time by Route (hours)": { vi: "Thời gian giao hàng trung bình theo tuyến (giờ)", en: "Average delivery time by route (hours)" },
  "Cancellation Rate": { vi: "Tỷ lệ hủy", en: "Cancellation rate" },
  "Delay Rate": { vi: "Tỷ lệ trễ", en: "Delay rate" },
  "Avg Weight per Order": { vi: "Khối lượng trung bình mỗi đơn", en: "Average weight per order" },
  "Top Businesses by Order Volume": { vi: "Doanh nghiệp có nhiều đơn nhất", en: "Top businesses by order volume" },
  "Top Businesses by Transport Spend": { vi: "Doanh nghiệp có chi phí vận chuyển cao nhất", en: "Top businesses by transport spend" },
  "On-time Delivery Rate by Provider": { vi: "Tỷ lệ giao đúng hạn theo provider", en: "On-time delivery rate by provider" },
  "Fleet Utilization by Provider": { vi: "Mức sử dụng đội xe theo provider", en: "Fleet utilization by provider" },
  "Active Orders vs Available Vehicles by Provider": { vi: "Đơn đang chạy và xe sẵn sàng theo provider", en: "Active orders vs available vehicles by provider" },
  "Recommended Route Adoption": { vi: "Tỷ lệ chọn tuyến được khuyến nghị", en: "Recommended route adoption" },
  "Total Cost Savings vs Direct": { vi: "Tổng tiền tiết kiệm so với đường thẳng", en: "Total cost savings vs direct" },
  "Most Used Route": { vi: "Tuyến được dùng nhiều nhất", en: "Most used route" },
  "AI2 Dispatch Accuracy": { vi: "Độ chính xác dispatch AI2", en: "AI2 dispatch accuracy" },
  "Route Selection Mix": { vi: "Cơ cấu lựa chọn tuyến", en: "Route selection mix" },
  "Estimated Savings by Route vs A_DIRECT_ROAD": { vi: "Tiền tiết kiệm theo tuyến so với A_DIRECT_ROAD", en: "Estimated savings by route vs A_DIRECT_ROAD" },
  "Forecast Demand vs Actual Orders": { vi: "Nhu cầu forecast và đơn thực tế", en: "Forecast demand vs actual orders" },
  "Dispatch Decision Mix": { vi: "Cơ cấu quyết định dispatch", en: "Dispatch decision mix" },
  "Platform performance, route optimization, and AI metrics": { vi: "Hiệu suất nền tảng, tối ưu tuyến và chỉ số AI", en: "Platform performance, route optimization, and AI metrics" },
  "Overview": { vi: "Tổng quan", en: "Overview" }, "Orders": { vi: "Đơn hàng", en: "Orders" },
  "Businesses": { vi: "Doanh nghiệp", en: "Businesses" }, "Logistics": { vi: "Logistics", en: "Logistics" },
  "AI Performance": { vi: "Hiệu suất AI", en: "AI performance" }, "Export CSV": { vi: "Xuất CSV", en: "Export CSV" },
};

function analyticsText(value: string, language: "vi" | "en") {
  return ANALYTICS_TEXT[value]?.[language] || value;
}

function ChartCard({ title, subtitle, children, note }: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  note?: string;
}) {
  const { language } = useLanguage();
  return (
    <div className="panel" style={{ display: "grid", gap: 12 }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 15 }}>{analyticsText(title, language)}</div>
        {subtitle && <div style={{ fontSize: 13, color: "#64748b", marginTop: 2 }}>{analyticsText(subtitle, language)}</div>}
      </div>
      {children}
      {note && <p style={{ margin: 0, fontSize: 12, color: "#94a3b8" }}>{analyticsText(note, language)}</p>}
    </div>
  );
}

function KpiMini({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  const { language } = useLanguage();
  return (
    <div style={{ background: "#f8fafc", borderRadius: 8, padding: "12px 16px" }}>
      <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>{analyticsText(label, language)}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>{analyticsText(sub, language)}</div>}
    </div>
  );
}

function OverviewTab() {
  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 }}>
        <ChartCard title="Orders Over Time" subtitle="Total vs Delivered">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={ORDERS_OVER_TIME}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="total" stroke={COLORS.blue} strokeWidth={2} name="Total Orders" dot={{ r: 3 }} />
              <Line type="monotone" dataKey="delivered" stroke={COLORS.green} strokeWidth={2} name="Delivered" dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Orders by Status" subtitle="Current distribution">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={STATUS_DISTRIBUTION} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} innerRadius={50} paddingAngle={2}>
                {STATUS_DISTRIBUTION.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend iconType="circle" iconSize={10} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 }}>
        <ChartCard title="Transport Volume by Mode" subtitle="Monthly tonnage (tons)" note="Stacked by road, waterway, and multimodal">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={VOLUME_BY_MODE}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="road" stackId="a" fill={COLORS.blue} name="Road" />
              <Bar dataKey="waterway" stackId="a" fill={COLORS.teal} name="Waterway" />
              <Bar dataKey="multimodal" stackId="a" fill={COLORS.purple} name="Multimodal" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Total Transport Cost Over Time" subtitle="Millions VND">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={COST_OVER_TIME}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="M" />
              <Tooltip formatter={(v) => `${v}M VND`} />
              <Line type="monotone" dataKey="cost" stroke={COLORS.amber} strokeWidth={2} name="Cost (M VND)" dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

const commodityOrders = Object.entries(
  ORDERS.reduce<Record<string, number>>((acc, o) => {
    acc[o.commodity] = (acc[o.commodity] ?? 0) + 1;
    return acc;
  }, {})
).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count);

const originOrders = Object.entries(
  ORDERS.reduce<Record<string, number>>((acc, o) => {
    acc[o.origin] = (acc[o.origin] ?? 0) + o.weight_ton;
    return acc;
  }, {})
).map(([province, volume]) => ({ province, volume })).sort((a, b) => b.volume - a.volume);

function OrdersTab() {
  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 }}>
        <ChartCard title="Orders by Commodity">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={commodityOrders} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={90} />
              <Tooltip />
              <Bar dataKey="count" fill={COLORS.blue} name="Orders" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Order Volume by Origin Province" subtitle="Total tonnage">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={originOrders}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="province" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} unit="t" />
              <Tooltip formatter={(v) => `${v}t`} />
              <Bar dataKey="volume" fill={COLORS.teal} name="Volume (t)" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard title="Average Delivery Time by Route (hours)">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={[
            { route: "A Direct Road", hours: 8 },
            { route: "B Road via CT", hours: 10 },
            { route: "C Water+Road CT", hours: 14 },
            { route: "D Full Water CT", hours: 20 },
            { route: "E Road+Water CT", hours: 18 },
          ]}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="route" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} unit="h" />
            <Tooltip formatter={(v) => `${v}h`} />
            <Bar dataKey="hours" fill={COLORS.purple} name="Avg Hours" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        <KpiMini label="Cancellation Rate" value="2.5%" sub="0.5 orders / month" />
        <KpiMini label="Delay Rate" value="10%" sub="2 of 20 orders delayed" />
        <KpiMini label="Avg Weight per Order" value="16t" sub="Across all commodities" />
      </div>
    </div>
  );
}

const bizVolume = BUSINESSES.map((b) => ({ name: b.name.split(" ").slice(0, 2).join(" "), orders: b.total_orders, spend: Math.round(b.total_spend_vnd / 1_000_000) })).filter((b) => b.orders > 0).sort((a, b) => b.orders - a.orders);

function BusinessesTab() {
  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 }}>
        <ChartCard title="Top Businesses by Order Volume">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={bizVolume} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={110} />
              <Tooltip />
              <Bar dataKey="orders" fill={COLORS.blue} name="Orders" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top Businesses by Transport Spend" subtitle="Millions VND">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={bizVolume.sort((a, b) => b.spend - a.spend)} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 10 }} width={110} />
              <Tooltip formatter={(v) => `${v}M VND`} />
              <Bar dataKey="spend" fill={COLORS.amber} name="Spend (M VND)" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        {BUSINESSES.filter((b) => b.total_orders > 0).slice(0, 4).map((b) => (
          <KpiMini key={b.id} label={b.name.split(" ").slice(0, 2).join(" ")} value={`${Math.round(b.avg_cost_vnd / 1_000_000)}M`} sub={`Avg cost · ${b.ontime_rate}% on-time`} />
        ))}
      </div>
    </div>
  );
}

function LogisticsTab() {
  const data = PROVIDERS.map((p) => ({
    name: p.name.split(" ")[0],
    ontime: p.ontime_rate,
    utilization: p.utilization,
    orders: p.active_orders,
    avail: p.available_vehicles,
  }));

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 }}>
        <ChartCard title="On-time Delivery Rate by Provider" subtitle="%">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="ontime" fill={COLORS.green} name="On-time %" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Fleet Utilization by Provider" subtitle="%">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="utilization" fill={COLORS.purple} name="Utilization %" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard title="Active Orders vs Available Vehicles by Provider">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="orders" fill={COLORS.blue} name="Active Orders" />
            <Bar dataKey="avail" fill={COLORS.teal} name="Available Vehicles" />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

function AiTab() {
  const totalRoutes = ROUTE_MIX.reduce((s, r) => s + r.count, 0);
  const baselineCost = ORDERS.reduce((s, o) => {
    const baseline = o.route_options.find((r) => r.code === "A_DIRECT_ROAD");
    return s + (baseline?.cost_vnd ?? 0);
  }, 0);
  const selectedCost = ORDERS.reduce((s, o) => s + o.estimated_cost_vnd, 0);
  const totalSavings = baselineCost - selectedCost;
  const savingsPct = baselineCost > 0 ? Math.round((totalSavings / baselineCost) * 100) : 0;
  const recommended = ORDERS.filter((o) => {
    const rec = o.route_options.find((r) => r.recommended);
    return rec && o.recommended_route === rec.code;
  }).length;
  const adoptionRate = Math.round((recommended / ORDERS.length) * 100);

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <KpiMini label="Recommended Route Adoption" value={`${adoptionRate}%`} sub={`${recommended} of ${ORDERS.length} orders`} />
        <KpiMini label="Total Cost Savings vs Direct" value={`${Math.round(totalSavings / 1_000_000)}M VND`} sub={`${savingsPct}% below baseline`} />
        <KpiMini label="Most Used Route" value="C_WATER_ROAD" sub="29% of all orders" />
        <KpiMini label="AI2 Dispatch Accuracy" value="62%" sub="dispatch_now decisions (demo data)" />
      </div>

      <div style={{ background: "#fef3c7", border: "1px solid #fcd34d", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#92400e" }}>
        ℹ️ AI2 forecast and dispatch data shown below is from the <strong>demo/mock module</strong> (AI2_AVAILABLE=false). Connect a live AI2 service to see real dispatch decisions.
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 }}>
        <ChartCard title="Route Selection Mix" subtitle="% of all orders per route">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={ROUTE_MIX} dataKey="count" nameKey="route" cx="50%" cy="50%" outerRadius={80} innerRadius={45} paddingAngle={2}>
                {ROUTE_MIX.map((_, i) => (
                  <Cell key={i} fill={[COLORS.blue, COLORS.teal, COLORS.green, COLORS.purple, COLORS.amber][i]} />
                ))}
              </Pie>
              <Tooltip formatter={(v, n) => [`${v} orders`, n]} />
              <Legend iconType="circle" iconSize={10} />
            </PieChart>
          </ResponsiveContainer>
          <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>Total: {totalRoutes} orders</p>
        </ChartCard>

        <ChartCard title="Estimated Savings by Route vs A_DIRECT_ROAD" subtitle="Millions VND saved vs direct road baseline">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={SAVINGS_BY_ROUTE}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="route" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} unit="M" />
              <Tooltip formatter={(v) => `${v}M VND`} />
              <Bar dataKey="savings" fill={COLORS.green} name="Savings (M VND)" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20 }}>
        <ChartCard title="Forecast Demand vs Actual Orders" subtitle="Demo module — rolling mean baseline" note="⚠️ Demo data — AI2 not connected">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={FORECAST_VS_ACTUAL}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="forecast" stroke={COLORS.amber} strokeWidth={2} strokeDasharray="5 5" name="Forecast (demo)" dot={{ r: 3 }} />
              <Line type="monotone" dataKey="actual" stroke={COLORS.blue} strokeWidth={2} name="Actual Orders" dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Dispatch Decision Mix" subtitle="AI2 decisions — demo data" note="⚠️ Demo data — AI2 not connected">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={DISPATCH_MIX} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} innerRadius={50} paddingAngle={2}>
                {DISPATCH_MIX.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `${v}%`} />
              <Legend iconType="circle" iconSize={10} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "orders", label: "Orders" },
  { key: "businesses", label: "Businesses" },
  { key: "logistics", label: "Logistics" },
  { key: "ai", label: "AI Performance" },
];

export default function AnalyticsPage() {
  const { language } = useLanguage();
  const [tab, setTab] = useState<Tab>("overview");
  const [dateRange, setDateRange] = useState("2026-07");

  const today = formatDate(new Date(), language);

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1>{analyticsText("Analytics", language)}</h1>
          <p className="page-subtitle">{analyticsText("Platform performance, route optimization, and AI metrics", language)}</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="month"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            style={{ padding: "8px 12px", border: "1px solid #dbe2ea", borderRadius: 6, fontSize: 13 }}
          />
          <button className="secondary" onClick={() => alert("CSV export — demo only")}>
            {analyticsText("Export CSV", language)}
          </button>
        </div>
      </div>

      <p style={{ color: "#64748b", fontSize: 13, margin: "0 0 4px" }}>
        {language === "vi" ? "Dữ liệu tính đến" : "Data as of"} {today}. {language === "vi" ? "Dữ liệu mock phục vụ demo hackathon." : "Mock data for hackathon demo purposes."}
      </p>

      {/* Tabs */}
      <div className="ops-tabs">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`ops-tab${tab === key ? " active" : ""}`}
          >
            {analyticsText(label, language)}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "orders" && <OrdersTab />}
      {tab === "businesses" && <BusinessesTab />}
      {tab === "logistics" && <LogisticsTab />}
      {tab === "ai" && <AiTab />}
    </div>
  );
}
