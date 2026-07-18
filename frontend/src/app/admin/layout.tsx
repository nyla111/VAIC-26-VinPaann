"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { AdminSidebar } from "@/components/admin/AdminSidebar";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) { router.replace("/login"); return; }
    if (user.role !== "admin") { router.replace(`/${user.role}`); }
  }, [loading, user, router]);

  if (loading || !user || user.role !== "admin") {
    return <main className="loading-screen">Loading…</main>;
  }

  return (
    <div className="admin-shell">
      <AdminSidebar />
      <div className="admin-main">
        {children}
      </div>
    </div>
  );
}
