"use client";

import Image from "next/image";
import { useLanguage } from "@/context/LanguageContext";

export function Brand({ role }: { role?: "enterprise" | "logistics" | "admin" }) {
  const { dictionary } = useLanguage();
  const subtitle = role === "enterprise"
    ? dictionary.enterprise
    : role === "logistics"
      ? dictionary.logistics
      : role === "admin"
        ? dictionary.admin
        : "AI logistics platform";

  return (
    <div className="brand">
      <Image className="brand-logo" src="/logo.png" alt="DeltaFlow AI" width={42} height={42} priority />
      <div>
        <strong>{dictionary.brand}</strong>
        <small>{subtitle}</small>
      </div>
    </div>
  );
}
