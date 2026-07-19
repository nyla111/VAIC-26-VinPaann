"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Brand } from "@/components/Brand";
import { LanguageToggle } from "@/components/LanguageToggle";
import { routeLabel } from "@/lib/labels";

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
        <nav style={{ flex: 1 }}>
          <Link
            className={pathname === "/enterprise" ? "active" : ""}
            href="/enterprise"
          >
            <span className="nav-icon" style={{ display: "inline-flex", alignItems: "center" }}>
              <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
            </span>
            {language === "vi" ? "Tạo đơn hàng" : "Create Shipment"}
          </Link>
          <Link
            className={pathname === "/enterprise/orders" ? "active" : ""}
            href="/enterprise/orders"
          >
            <span className="nav-icon" style={{ display: "inline-flex", alignItems: "center" }}>
              <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
                <path d="M11 17a1 1 0 001.447.894l5-2.5A1 1 0 0018 14.5V8.382l-7 3.5V17zM9 17v-5.118L2 8.382v6.118a1 1 0 00.553.894l5 2.5A1 1 0 009 17zM10 2.236l-7 3.5L10 9.236l7-3.5-7-3.5z" />
              </svg>
            </span>
            {language === "vi" ? "Danh sách đơn hàng" : "Order History"}
          </Link>
        </nav>

        <div className="admin-sidebar-footer" style={{ marginTop: "auto" }}>
          <div className="user-badge" style={{ marginBottom: 12 }}>
            <div className="user-avatar">
              {user.email ? user.email.split("@")[0].slice(0, 2).toUpperCase() : "EN"}
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span className="user-email" style={{ fontSize: "13px" }}>{user.email}</span>
              <span style={{ fontSize: "11px", color: "var(--muted)" }}>{dictionary.enterprise}</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <LanguageToggle />
            <button
              className="secondary"
              style={{ flex: 1, fontSize: 12, padding: "8px 10px" }}
              onClick={() => logout().then(() => router.replace("/login"))}
            >
              {dictionary.logout}
            </button>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{t("enterprise.heading")}</h1>
            <p>{t("enterprise.subtitle")}</p>
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
                    {orders.map((order) => {
                      const orderId = order.id; // e.g. "ORD143"
                      const dbId = order.db_id; // e.g. 143
                      const routeCode = order.recommended_route; // e.g. "D_WATER_VIA_CT"
                      const origin = order.origin; // e.g. "Vị Thanh Hub"
                      const commodity = order.commodity; // e.g. "Rice"
                      const weightText = order.weight_ton ? `${order.weight_ton} ${language === "vi" ? "tấn" : "tons"}` : "-";
                      const status = order.status; // e.g. "awaiting_assignment", "in_transit", etc.
                      
                      const getStatusLabel = (statusVal: string) => {
                        const mapping: Record<string, { vi: string; en: string }> = {
                          awaiting_assignment: { vi: "Chờ phân công", en: "Awaiting assignment" },
                          in_transit: { vi: "Đang di chuyển", en: "In transit" },
                          assigned: { vi: "Đã gán xe", en: "Vehicle assigned" },
                          delivered: { vi: "Đã giao hàng", en: "Delivered" },
                        };
                        return mapping[statusVal]?.[language] || statusVal;
                      };

                      const trackingUrl = routeCode 
                        ? `/enterprise?order_id=${dbId}&route=${routeCode}&step=tracking`
                        : `/enterprise?order_id=${dbId}&step=routes`;

                      return (
                        <tr
                          key={dbId}
                          onClick={() => router.push(trackingUrl)}
                          style={{ cursor: "pointer" }}
                          className="table-row-hover"
                        >
                          <td style={{ fontWeight: "bold" }}>
                            <Link
                              href={trackingUrl}
                              style={{ color: "#1d4ed8", textDecoration: "none" }}
                              onClick={(e) => e.stopPropagation()}
                            >
                              {orderId}
                            </Link>
                          </td>
                          <td>{origin}</td>
                          <td>{commodity}</td>
                          <td>{weightText}</td>
                          <td>{routeLabel(routeCode || "N/A", language)}</td>
                          <td>
                            <span className={`status-badge ${status}`}>
                              {getStatusLabel(status)}
                            </span>
                          </td>
                          <td>
                            <Link
                              href={trackingUrl}
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
                              onClick={(e) => e.stopPropagation()}
                            >
                              {routeCode ? (language === "vi" ? "Theo dõi" : "Track") : (language === "vi" ? "Chọn tuyến" : "Select Route")}
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
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
