"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Brand } from "@/components/Brand";
import { LanguageToggle } from "@/components/LanguageToggle";
import { orderStateLabel, routeLabel } from "@/lib/labels";

export default function EnterpriseOrdersPage() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();
  const { dictionary, language, t } = useLanguage();
  const [orders, setOrders] = useState<any[]>([]);
  const [loadingOrders, setLoadingOrders] = useState(false);

  const fetchOrders = async () => {
    setLoadingOrders(true);
    try {
      const res = await fetch("/api/v1/orders", { credentials: "include", cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setOrders(data.orders || []);
      }
    } catch (err) {
      console.error("Error fetching orders:", err);
    } finally {
      setLoadingOrders(false);
    }
  };

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
    fetchOrders();
  }, [loading, user, router]);

  if (loading || !user) {
    return <main className="loading-screen">Đang tải...</main>;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand role="enterprise" />
        <nav>
          <Link
            className={pathname === "/enterprise" ? "active" : ""}
            href="/enterprise"
          >
            {language === "vi" ? "Tạo đơn hàng" : "Create Shipment"}
          </Link>
          <Link
            className={pathname === "/enterprise/orders" ? "active" : ""}
            href="/enterprise/orders"
          >
            {language === "vi" ? "Danh sách đơn hàng" : "Order History"}
          </Link>
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
          <div className="panel">
            <h2 style={{ marginBottom: "16px" }}>{language === "vi" ? "Danh sách đơn hàng đã tạo" : "Created Shipment Orders"}</h2>
            {loadingOrders ? (
              <div style={{ textAlign: "center", padding: "40px", color: "#64748b" }}>{dictionary.loading}</div>
            ) : orders.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px", color: "#64748b" }}>
                {language === "vi" ? "Chưa có đơn hàng nào." : "No orders found."}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table style={{ width: "100%" }}>
                  <thead>
                    <tr>
                      <th>{language === "vi" ? "Mã đơn hàng" : "Order ID"}</th>
                      <th>{t("common.hub", "Hub xuất phát")}</th>
                      <th>{t("common.commodity", "Commodity")}</th>
                      <th>{t("common.weight", "Khối lượng")}</th>
                      <th>{t("common.route", "Tuyến đường")}</th>
                      <th>{t("common.status", "Trạng thái")}</th>
                      <th>{language === "vi" ? "Hành động" : "Action"}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr key={order.order_id}>
                        <td style={{ fontWeight: "bold", color: "#1d4ed8" }}>ORDER-{order.order_id}</td>
                        <td>{order.hub_id}</td>
                        <td>{order.loai_hang || order.commodity}</td>
                        <td>{order.khoi_luong_kg ? `${order.khoi_luong_kg.toLocaleString()} kg` : `${(order.weight_ton * 1000).toLocaleString()} kg`}</td>
                        <td>{routeLabel(order.selected_route_id || "N/A", language)}</td>
                        <td>
                          <span className={`status-badge ${order.state_code || order.state}`}>
                            {orderStateLabel(order.state_code || order.state, language)}
                          </span>
                        </td>
                        <td>
                          {order.selected_route_id && (
                            <Link
                              href={`/enterprise?order_id=${order.order_id}&route=${order.selected_route_id}&step=tracking`}
                              className="button secondary"
                              style={{
                                display: "inline-block",
                                padding: "4px 8px",
                                fontSize: "12px",
                                fontWeight: "bold",
                                textDecoration: "none",
                                textAlign: "center",
                                borderRadius: "4px",
                                border: "1px solid #cbd5e1"
                              }}
                            >
                              {language === "vi" ? "Theo dõi" : "Track"}
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
