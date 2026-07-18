import { Suspense } from "react";
import { DashboardShell } from "@/components/DashboardShell";

export default function AdminPage() {
  return (
    <Suspense fallback={<main className="loading-screen">Đang tải...</main>}>
      <DashboardShell role="admin" />
    </Suspense>
  );
}
