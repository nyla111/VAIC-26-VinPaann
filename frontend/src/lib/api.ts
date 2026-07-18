import type { DashboardView, ShipmentPayload, User } from "@/types/dashboard";

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.error || payload?.detail || `Request failed with ${response.status}`;
    throw new Error(message);
  }
  return payload as T;
}

export async function getSession(): Promise<{ authenticated: boolean; user: User | null }> {
  const response = await fetch("/api/vaic/session", { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function login(username: string, password: string): Promise<{ user: User }> {
  const response = await fetch("/api/vaic/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return parseResponse(response);
}

export async function logout(): Promise<void> {
  await fetch("/api/vaic/logout", { method: "POST", credentials: "include" });
}

export async function getDashboardView(section?: string, statusFilter?: string): Promise<DashboardView> {
  const params = new URLSearchParams();
  if (section) params.set("section", section);
  if (statusFilter) params.set("status_filter", statusFilter);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`/api/vaic/view${suffix}`, { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function submitShipment(payload: ShipmentPayload): Promise<DashboardView> {
  const response = await fetch("/api/vaic/shipment", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}
