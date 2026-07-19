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

  // REST loads the view; WebSocket is the production push channel. Any
  // committed backend state change causes a cheap authoritative re-read so
  // role-specific projections never become a second source of truth.
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

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand role={role} />
        <nav>
          {(view?.menu || []).map((item, index) => (
            <div key={item.id} className="nav-item-wrap">
              {role === "admin" && index === 5 ? <div className="nav-divider">{t("common.view_by_role", "Xem theo góc nhìn")}</div> : null}
              <Link className={activeSection === item.id ? "active" : ""} href={sectionHref(item.id)}>
                {sectionLabel(item.id, item.label)}
              </Link>
            </div>
          ))}
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div className="user-box">
            <LanguageToggle />
            <span>
              {user.email}
            </span>
            <button
              className="secondary"
              type="button"
              onClick={() => logout().then(() => router.replace("/login"))}
            >
              {dictionary.logout}
            </button>
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
