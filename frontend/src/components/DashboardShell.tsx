"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { getDashboardView } from "@/lib/api";
import type { DashboardView, Role } from "@/types/dashboard";
import { DashboardSection } from "@/features/dashboard/DashboardSection";

const defaultSection: Record<Role, string> = {
  business: "business_shipment_form",
  logistics: "logistics_fleet",
  admin: "admin_inventory",
};

export function DashboardShell({ role }: { role: Role }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, loading, logout } = useAuth();
  const [view, setView] = useState<DashboardView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");

  const requestedSection = searchParams.get("section") || defaultSection[role];

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
    getDashboardView(requestedSection, statusFilter)
      .then((nextView) => {
        setView(nextView);
        setError(null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Không tải được dashboard.");
        if (err instanceof Error && err.message === "unauthenticated") router.replace("/login");
      });
  }, [loading, requestedSection, role, router, statusFilter, user]);

  const activeSection = view?.section || requestedSection;
  const title = view?.section_label || "VAIC Dashboard";
  const subtitle = "AI-powered multimodal logistics for smarter routing, consolidation, and infrastructure utilization";

  const sectionHref = useMemo(() => (section: string) => `${pathname}?section=${section}`, [pathname]);

  if (loading || !user || user.role !== role) return <main className="loading-screen">Đang tải...</main>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">V</span>
          <div>
            <strong>VAIC</strong>
            <small>{role}</small>
          </div>
        </div>
        <nav>
          {(view?.menu || []).map((item, index) => (
            <div key={item.id} className="nav-item-wrap">
              {role === "admin" && index === 5 ? <div className="nav-divider">Xem theo góc nhìn</div> : null}
              <Link className={activeSection === item.id ? "active" : ""} href={sectionHref(item.id)}>
                {item.label}
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
            <span>
              {user.name} · {user.username}
            </span>
            <button
              className="secondary"
              type="button"
              onClick={() => logout().then(() => router.replace("/login"))}
            >
              Đăng xuất
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
            />
          ) : (
            <div className="empty">Đang tải dữ liệu...</div>
          )}
        </section>
      </main>
    </div>
  );
}
