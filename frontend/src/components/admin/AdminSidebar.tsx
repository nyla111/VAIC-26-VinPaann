"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Brand } from "@/components/Brand";
import { LanguageToggle } from "@/components/LanguageToggle";

const NAV_ITEMS = [
  { href: "/admin", key: "admin_inventory", label: "Overview", icon: "◉" },
  { href: "/admin/businesses", key: "businesses", label: "Businesses", icon: "🏢" },
  { href: "/admin/logistics", key: "admin_logistics", label: "Logistics Partners", icon: "🚛" },
  { href: "/admin/orders", key: "admin_orders", label: "Orders", icon: "📦" },
  { href: "/admin/operations", key: "admin_operations", label: "Operations", icon: "⚡" },
  { href: "/admin/analytics", key: "admin_logs", label: "Analytics", icon: "📊" },
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
            <span className="nav-icon">{item.icon}</span>
            {sectionLabel(item.key, item.label)}
          </Link>
        ))}
      </nav>

      <div className="admin-sidebar-footer">
        <LanguageToggle />
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 14, wordBreak: "break-all" }}>{user?.email}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{dictionary.admin}</div>
        </div>
        <button
          className="secondary"
          style={{ width: "100%", fontSize: 13 }}
          onClick={() => logout().then(() => router.replace("/login"))}
        >
          {dictionary.logout}
        </button>
      </div>
    </aside>
  );
}
