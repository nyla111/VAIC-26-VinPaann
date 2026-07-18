"use client";

import { useEffect } from "react";

export interface ToastMessage {
  id: string;
  message: string;
  type: "success" | "error" | "info";
}

interface Props {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: Props) {
  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        zIndex: 400,
        pointerEvents: "none",
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }: { toast: ToastMessage; onDismiss: (id: string) => void }) {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 3500);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const colors = {
    success: { bg: "#dcfce7", border: "#86efac", color: "#166534" },
    error: { bg: "#fee2e2", border: "#fca5a5", color: "#991b1b" },
    info: { bg: "#dbeafe", border: "#93c5fd", color: "#1e40af" },
  }[toast.type];

  return (
    <div
      style={{
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        color: colors.color,
        padding: "12px 16px",
        borderRadius: 8,
        fontWeight: 600,
        fontSize: 14,
        boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
        pointerEvents: "auto",
        minWidth: 260,
        maxWidth: 380,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        animation: "toastIn 0.2s ease",
      }}
    >
      <span>{toast.message}</span>
      <button
        onClick={() => onDismiss(toast.id)}
        style={{
          background: "transparent",
          border: "none",
          color: "inherit",
          cursor: "pointer",
          fontWeight: 700,
          padding: "0 4px",
          lineHeight: 1,
          opacity: 0.6,
        }}
      >
        ✕
      </button>
    </div>
  );
}
