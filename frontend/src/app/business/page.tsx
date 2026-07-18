import { Suspense } from "react";
import { DashboardShell } from "@/components/DashboardShell";

export default function BusinessPage() {
  return (
    <Suspense fallback={<main className="loading-screen">Đang tải...</main>}>
      <DashboardShell role="business" />
    </Suspense>
  );
}
