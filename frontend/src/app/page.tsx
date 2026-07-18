"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function HomePage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? `/${user.role}` : "/login");
  }, [loading, router, user]);

  return <main className="loading-screen">Đang tải...</main>;
}
