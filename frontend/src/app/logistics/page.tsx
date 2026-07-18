import { Suspense } from "react";
import { DashboardShell } from "@/components/DashboardShell";

export default function LogisticsPage() {
  return (
    <Suspense fallback={<main className="loading-screen">Đang tải...</main>}>
      <DashboardShell role="logistics" />
    </Suspense>
  );
}
