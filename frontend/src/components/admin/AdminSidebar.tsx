"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Brand } from "@/components/Brand";
import { LanguageToggle } from "@/components/LanguageToggle";

const SOLID_ICONS: Record<string, React.ReactNode> = {
  admin_inventory: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
    </svg>
  ),
  businesses: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2h-3a1 1 0 01-1-1v-2a1 1 0 00-1-1H9a1 1 0 00-1 1v2a1 1 0 01-1 1H4a1 1 0 110-2V4zm3 1h2v2H7V5zm2 4H7v2h2V9zm2-4h2v2h-2V5zm2 4h-2v2h2V9z" clipRule="evenodd" />
    </svg>
  ),
  admin_logistics: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M2 3a1 1 0 00-1 1v11a1.5 1.5 0 001.5 1.5H3a2 2 0 004 0h6a2 2 0 004 0h1.5a1.5 1.5 0 001.5-1.5v-5a1.5 1.5 0 00-.44-1.06l-3-3A1.5 1.5 0 0010.5 5H2zm3 13a1 1 0 110-2 1 1 0 010 2zm10 0a1 1 0 110-2 1 1 0 010 2z" />
    </svg>
  ),
  admin_orders: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M11 17a1 1 0 001.447.894l5-2.5A1 1 0 0018 14.5V8.382l-7 3.5V17zM9 17v-5.118L2 8.382v6.118a1 1 0 00.553.894l5 2.5A1 1 0 009 17zM10 2.236l-7 3.5L10 9.236l7-3.5-7-3.5z" />
    </svg>
  ),
  admin_operations: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v6.5h3.71a1 1 0 01.82 1.573l-7 10A1 1 0 018 19.5V13H4.29a1 1 0 01-.82-1.573l7-10a1 1 0 011.03-.381z" clipRule="evenodd" />
    </svg>
  ),
  admin_logs: (
    <svg style={{ width: "16px", height: "16px" }} viewBox="0 0 20 20" fill="currentColor">
      <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
    </svg>
  )
};

const NAV_ITEMS = [
  { href: "/admin", key: "admin_inventory", label: "Overview" },
  { href: "/admin/businesses", key: "businesses", label: "Businesses" },
  { href: "/admin/logistics", key: "admin_logistics", label: "Logistics Partners" },
  { href: "/admin/orders", key: "admin_orders", label: "Orders" },
  { href: "/admin/operations", key: "admin_operations", label: "Operations" },
  { href: "/admin/analytics", key: "admin_logs", label: "Analytics" },
];

export function AdminSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { dictionary, sectionLabel } = useLanguage();

  function isActive(href: string) {
    if (href === "/admin") return pathname === "/admin";
    return pathname.startsWith(href);
  }

  return (
    <aside className="admin-sidebar">
      <Brand role="admin" />

      <nav className="admin-nav">
        <p className="nav-section-label">{dictionary.language === "Language" ? "Platform Management" : "Quản trị nền tảng"}</p>
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`admin-nav-link${isActive(item.href) ? " active" : ""}`}
          >
            <span className="nav-icon" style={{ display: "inline-flex", alignItems: "center" }}>
              {SOLID_ICONS[item.key]}
            </span>
            {sectionLabel(item.key, item.label)}
          </Link>
        ))}
      </nav>

      <div className="admin-sidebar-footer">
        <div className="user-badge" style={{ marginBottom: 12 }}>
          <div className="user-avatar">
            {user?.email ? user.email.split("@")[0].slice(0, 2).toUpperCase() : "AD"}
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span className="user-email" style={{ fontSize: "13px" }}>{user?.email}</span>
            <span style={{ fontSize: "11px", color: "var(--muted)" }}>{dictionary.admin}</span>
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
  );
}
