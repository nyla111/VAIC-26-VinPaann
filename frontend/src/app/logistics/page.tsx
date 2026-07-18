"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getDashboardView } from "@/lib/api";
import dynamic from "next/dynamic";
const VaicMap = dynamic(() => import("@/components/VaicMap").then((m) => m.VaicMap), {
  ssr: false,
});

import type { DashboardView } from "@/types/dashboard";

export default function LogisticsDashboard() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [view, setView] = useState<DashboardView | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== "logistics") {
      router.replace(`/${user.role}`);
      return;
    }

    getDashboardView("logistics_fleet", statusFilter)
      .then((nextView) => {
        setView(nextView);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Không tải được đội xe.");
      });
  }, [loading, router, statusFilter, user]);

  if (loading || !user || user.role !== "logistics") {
    return <main className="loading-screen">Đang tải...</main>;
  }

  const handleStatusFilterChange = (val: string) => {
    setStatusFilter(val);
  };

  const mapPayload = view?.map_payload || { nodes: [], fleet: [] };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">L</span>
          <div>
            <strong>VAIC Logistics</strong>
            <small>Điều phối & Vận tải</small>
          </div>
        </div>
        <nav>
          <a className="active" href="#">Đội xe & Tuyến đường</a>
          <a href="#">Dự báo nhu cầu AI</a>
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>Giám sát đội xe (Logistics)</h1>
            <p>Theo dõi vị trí tàu/xe và dự đoán khối lượng trung chuyển của mô hình AI lớp 2</p>
          </div>
          <div className="user-box">
            <span>{user.email}</span>
            <button className="secondary" type="button" onClick={() => logout().then(() => router.replace("/login"))}>
              Đăng xuất
            </button>
          </div>
        </header>

        <section className="content">
          {error && <div className="alert">{error}</div>}
          
          <div className="panel">
            <h2 style={{ marginBottom: "16px" }}>Bản đồ giám sát đội vận tải thủy bộ</h2>
            {view ? (
              <div style={{ height: "450px", position: "relative" }}>
                <VaicMap data={mapPayload} />
              </div>
            ) : (
              <div className="empty">Đang tải bản đồ...</div>
            )}
          </div>

          <div className="panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2>Trạng thái đội phương tiện</h2>
              <div>
                Bộ lọc:{" "}
                <select value={statusFilter} onChange={(e) => handleStatusFilterChange(e.target.value)}>
                  <option value="">Tất cả</option>
                  <option value="available">Available (Sẵn sàng)</option>
                  <option value="en_route">En route (Đang di chuyển)</option>
                  <option value="maintenance">Maintenance (Bảo trì)</option>
                </select>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Mã phương tiện</th>
                  <th>Loại</th>
                  <th>Tải trọng</th>
                  <th>Vị trí hiện tại</th>
                  <th>Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {(view?.fleet || []).slice(0, 10).map((vehicle: any) => (
                  <tr key={vehicle.vehicle_id}>
                    <td>{vehicle.vehicle_id}</td>
                    <td>{vehicle.vehicle_type === "truck_5t" || vehicle.vehicle_type === "truck_15t" || vehicle.vehicle_type === "reefer_8t" ? "Đường bộ (Truck)" : "Đường thủy (Barge/Boat)"}</td>
                    <td>{vehicle.capacity_ton} Tấn</td>
                    <td>{vehicle.current_node_id}</td>
                    <td>
                      <span className="status" style={{
                        background: vehicle.status === "available" ? "#dcfce7" : vehicle.status === "en_route" ? "#dbeafe" : "#fee2e2",
                        color: vehicle.status === "available" ? "#166534" : vehicle.status === "en_route" ? "#1e40af" : "#991b1b"
                      }}>
                        {vehicle.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}
