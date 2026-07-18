"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

const NAV_ITEMS = [
  { href: "/admin", label: "Overview", icon: "◉" },
  { href: "/admin/businesses", label: "Businesses", icon: "🏢" },
  { href: "/admin/logistics", label: "Logistics Partners", icon: "🚛" },
  { href: "/admin/orders", label: "Orders", icon: "📦" },
  { href: "/admin/operations", label: "Operations", icon: "⚡" },
  { href: "/admin/analytics", label: "Analytics", icon: "📊" },
];

export function AdminSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  function isActive(href: string) {
    if (href === "/admin") return pathname === "/admin";
    return pathname.startsWith(href);
  }

  return (
    <aside className="admin-sidebar">
      <div className="brand">
        <span className="brand-mark">V</span>
        <div>
          <strong>VAIC</strong>
          <small>Admin Portal</small>
        </div>
      </div>

      <nav className="admin-nav">
        <p className="nav-section-label">Platform Management</p>
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`admin-nav-link${isActive(item.href) ? " active" : ""}`}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="admin-sidebar-footer">
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{user?.name}</div>
          <div style={{ fontSize: 12, color: "#94a3b8" }}>{user?.username} · Admin</div>
        </div>
        <button
          className="secondary"
          style={{ width: "100%", fontSize: 13 }}
          onClick={() => logout().then(() => router.replace("/login"))}
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
