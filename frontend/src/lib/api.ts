import type { DashboardView, FleetDemandForecast, LogisticsOrderQueue, ShipmentPayload, User } from "@/types/dashboard";

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.error || payload?.detail || `Request failed with ${response.status}`;
    throw new Error(message);
  }
  return payload as T;
}

export async function getSession(): Promise<{ authenticated: boolean; user: User | null }> {
  const response = await fetch("/api/v1/auth/session", { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function login(email: string, password: string): Promise<{ user: User }> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return parseResponse(response);
}

export async function logout(): Promise<void> {
  await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
}


export async function getDashboardView(section?: string, statusFilter?: string): Promise<DashboardView> {
  const params = new URLSearchParams();
  if (section) params.set("section", section);
  if (statusFilter) params.set("status_filter", statusFilter);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`/api/vaic/view${suffix}`, { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function getScopedMapData(): Promise<DashboardView["map_payload"]> {
  const response = await fetch("/api/vaic/map-data", { credentials: "include", cache: "no-store" });
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

export async function getLogisticsOverview(): Promise<any> {
  const response = await fetch("/api/v1/logistics/overview", { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function getLogisticsFleet(statusFilter?: string): Promise<any[]> {
  const suffix = statusFilter ? `?status_filter=${statusFilter}` : "";
  const response = await fetch(`/api/v1/logistics/fleet${suffix}`, { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function getLogisticsFleetForecast(forecastDate?: string): Promise<FleetDemandForecast> {
  const suffix = forecastDate ? `?forecast_date=${encodeURIComponent(forecastDate)}` : "";
  const response = await fetch(`/api/v1/logistics/fleet/forecast${suffix}`, {
    credentials: "include",
    cache: "no-store",
  });
  return parseResponse(response);
}

export async function getLogisticsJobs(): Promise<any[]> {
  const response = await fetch("/api/v1/logistics/jobs", { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function getLogisticsOrders(): Promise<LogisticsOrderQueue> {
  const response = await fetch("/api/v1/logistics/orders", { credentials: "include", cache: "no-store" });
  return parseResponse(response);
}

export async function acceptLogisticsOrder(orderId: number, vehicleId: string): Promise<any> {
  const response = await fetch(`/api/v1/logistics/orders/${orderId}/accept`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vehicle_id: vehicleId }),
  });
  return parseResponse(response);
}

export async function dispatchLogisticsOrders(orderIds: number[], vehicleId: string): Promise<any> {
  const response = await fetch("/api/v1/logistics/orders/dispatch", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order_ids: orderIds, vehicle_id: vehicleId }),
  });
  return parseResponse(response);
}
