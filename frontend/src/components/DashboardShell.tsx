"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Brand } from "@/components/Brand";
import { LanguageToggle } from "@/components/LanguageToggle";
import { getDashboardView, getLogisticsOverview, getLogisticsFleet, getLogisticsFleetForecast, getLogisticsJobs, getLogisticsOrders } from "@/lib/api";
import type { DashboardView, Role } from "@/types/dashboard";
import { DashboardSection } from "@/features/dashboard/DashboardSection";

const defaultSection: Record<Role, string> = {
  enterprise: "business_shipment_form",
  logistics: "logistics_overview",
  admin: "admin_inventory",
};

const SOLID_ICONS: Record<string, React.ReactNode> = {
  logistics_overview: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
    </svg>
  ),
  logistics_orders: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M11 17a1 1 0 001.447.894l5-2.5A1 1 0 0018 14.5V8.382l-7 3.5V17zM9 17v-5.118L2 8.382v6.118a1 1 0 00.553.894l5 2.5A1 1 0 009 17zM10 2.236l-7 3.5L10 9.236l7-3.5-7-3.5z" />
    </svg>
  ),
  logistics_fleet: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M2 3a1 1 0 00-1 1v11a1.5 1.5 0 001.5 1.5H3a2 2 0 004 0h6a2 2 0 004 0h1.5a1.5 1.5 0 001.5-1.5v-5a1.5 1.5 0 00-.44-1.06l-3-3A1.5 1.5 0 0010.5 5H2zm3 13a1 1 0 110-2 1 1 0 010 2zm10 0a1 1 0 110-2 1 1 0 010 2z" />
    </svg>
  ),
  logistics_jobs: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v6.5h3.71a1 1 0 01.82 1.573l-7 10A1 1 0 018 19.5V13H4.29a1 1 0 01-.82-1.573l7-10a1 1 0 011.03-.381z" clipRule="evenodd" />
    </svg>
  ),
  business_shipment_form: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
    </svg>
  ),
  business_orders: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M11 17a1 1 0 001.447.894l5-2.5A1 1 0 0018 14.5V8.382l-7 3.5V17zM9 17v-5.118L2 8.382v6.118a1 1 0 00.553.894l5 2.5A1 1 0 009 17zM10 2.236l-7 3.5L10 9.236l7-3.5-7-3.5z" />
    </svg>
  )
};

export function DashboardShell({ role }: { role: Role }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, loading, logout } = useAuth();
  const { dictionary, sectionLabel, sectionDescription, t } = useLanguage();
  const [view, setView] = useState<DashboardView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [forecastDate, setForecastDate] = useState(() => {
    const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
    return tomorrow.toISOString().slice(0, 10);
  });

  const requestedSection = searchParams.get("section") || defaultSection[role];

  const refreshView = useCallback(() => {
    if (loading || !user || user.role !== role) return;
    if (role === "logistics") {
      const fetchLogistics = async () => {
        try {
          let extra: Partial<DashboardView> = {};
          if (requestedSection === "logistics_overview") {
            const overview = await getLogisticsOverview();
            extra = { logistics_overview: overview, ai2_live: true };
          } else if (requestedSection === "logistics_fleet") {
            const [fleet, fleetForecast] = await Promise.all([
              getLogisticsFleet(statusFilter || undefined),
              getLogisticsFleetForecast(forecastDate),
            ]);
            extra = { fleet, fleet_forecast: fleetForecast, forecast_date: forecastDate, status_filter: statusFilter };
          } else if (requestedSection === "logistics_jobs") {
            const jobs = await getLogisticsJobs();
            extra = { jobs, ai2_live: true };
          } else if (requestedSection === "logistics_orders") {
            const providerOrders = await getLogisticsOrders();
            extra = { provider_orders: providerOrders, ai2_live: true };
          }
          const mockView: DashboardView = {
            user: { id: user.id, email: user.email, role: "logistics" },
            role: "logistics",
            section: requestedSection,
            section_label:
              requestedSection === "logistics_overview"
                ? "Tổng quan"
                : requestedSection === "logistics_fleet"
                ? "Đội xe"
                : requestedSection === "logistics_jobs"
                ? "Chuyến xe"
                : "Đơn chờ nhận",
            menu: [
              { id: "logistics_overview", label: "Tổng quan" },
              { id: "logistics_orders", label: "Đơn chờ nhận" },
              { id: "logistics_fleet", label: "Đội xe" },
              { id: "logistics_jobs", label: "Chuyến xe" },
            ],
            reason_labels: {},
            hub_options: [],
            commodity_options: [],
            ...extra,
          };
          setView(mockView);
          setError(null);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Không tải được logistics dashboard.");
        }
      };
      fetchLogistics();
    } else {
      getDashboardView(requestedSection, statusFilter)
        .then((nextView) => {
          setView(nextView);
          setError(null);
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "Không tải được dashboard.");
          if (err instanceof Error && err.message === "unauthenticated") router.replace("/login");
        });
    }
  }, [forecastDate, loading, requestedSection, role, router, statusFilter, user]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== role) {
      router.replace(`/${user.role}`);
      return;
    }
    refreshView();
  }, [loading, requestedSection, role, router, statusFilter, user, refreshView]);

  useEffect(() => {
    if (loading || !user || user.role !== role) return;
    const apiBase = process.env.NEXT_PUBLIC_VAIC_API_BASE_URL || "http://127.0.0.1:8000";
    const socket = new WebSocket(apiBase.replace(/^http/, "ws") + "/ws/status");
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.event === "STATE_UPDATE" || message.inventory) {
          refreshView();
        }
      } catch {
        // Ignore malformed keep-alive frames; the next REST refresh remains authoritative.
      }
    };
    return () => socket.close();
  }, [forecastDate, loading, requestedSection, role, statusFilter, user, refreshView]);

  const activeSection = view?.section || requestedSection;
  const title = sectionLabel(activeSection, view?.section_label || dictionary.brand);
  const subtitle = sectionDescription(activeSection, role === "enterprise"
    ? dictionary.enterpriseSubtitle
    : role === "logistics"
      ? dictionary.logisticsSubtitle
      : dictionary.adminSubtitle);

  const sectionHref = useMemo(() => (section: string) => `${pathname}?section=${section}`, [pathname]);

  if (loading || !user || user.role !== role) return <main className="loading-screen">{dictionary.loading}</main>;

  const userInitials = user.email ? user.email.split("@")[0].slice(0, 2).toUpperCase() : "US";
  const roleLabelText = role === "enterprise"
    ? dictionary.enterprise
    : role === "logistics"
      ? dictionary.logistics
      : dictionary.admin;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand role={role} />
        <nav style={{ flex: 1 }}>
          {(view?.menu || []).map((item, index) => {
            const isActive = activeSection === item.id;
            return (
              <div key={item.id} className="nav-item-wrap">
                {role === "admin" && index === 5 ? <div className="nav-divider">{t("common.view_by_role", "Xem theo góc nhìn")}</div> : null}
                <Link className={isActive ? "active" : ""} href={sectionHref(item.id)}>
                  <span className="nav-icon" style={{ display: "inline-flex", alignItems: "center" }}>
                    {SOLID_ICONS[item.id]}
                  </span>
                  {sectionLabel(item.id, item.label)}
                </Link>
              </div>
            );
          })}
        </nav>

        <div className="admin-sidebar-footer" style={{ marginTop: "auto" }}>
          <div className="user-badge" style={{ marginBottom: 12 }}>
            <div className="user-avatar">
              {userInitials}
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span className="user-email" style={{ fontSize: "13px" }}>{user.email}</span>
              <span style={{ fontSize: "11px", color: "var(--muted)" }}>{roleLabelText}</span>
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
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
        </header>
        <section className="content">
          {error ? <div className="alert">{error}</div> : null}
          {view ? (
            <DashboardSection
              view={view}
              onViewChange={setView}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              forecastDate={forecastDate}
              onForecastDateChange={setForecastDate}
            />
          ) : (
            <div className="empty">{t("common.loading")}</div>
          )}
        </section>
      </main>
    </div>
  );
}
