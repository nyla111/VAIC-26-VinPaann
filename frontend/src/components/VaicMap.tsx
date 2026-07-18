"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import type { MapPayload, RouteSegment } from "@/types/dashboard";

type Props = {
  data: MapPayload;
  selectedRoute?: string | null;
  onSelectedRouteChange?: (routeCode: string) => void;
};

function escapeHtml(value: unknown) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function pointAlongPolyline(points: [number, number][], progress: number): [number, number] | null {
  if (!points.length) return null;
  if (points.length === 1) return points[0];
  const lengths = points.slice(1).map((point, index) => {
    const previous = points[index];
    return Math.hypot(point[0] - previous[0], point[1] - previous[1]);
  });
  const total = lengths.reduce((sum, length) => sum + length, 0);
  let target = Math.min(Math.max(progress, 0), 1) * total;
  for (let index = 0; index < lengths.length; index += 1) {
    if (target <= lengths[index]) {
      const ratio = lengths[index] ? target / lengths[index] : 0;
      return [
        points[index][0] + (points[index + 1][0] - points[index][0]) * ratio,
        points[index][1] + (points[index + 1][1] - points[index][1]) * ratio,
      ];
    }
    target -= lengths[index];
  }
  return points[points.length - 1];
}

export function VaicMap({ data, selectedRoute, onSelectedRouteChange }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const routeLayerRef = useRef<LayerGroup | null>(null);
  const geometryCache = useRef(new Map<string, [number, number][]>());
  const [routeCode, setRouteCode] = useState(selectedRoute || data.activeRoute || null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    setRouteCode(selectedRoute || data.activeRoute || null);
  }, [data.activeRoute, selectedRoute]);

  useEffect(() => {
    let mounted = true;
    async function init() {
      if (!ref.current || mapRef.current) return;
      const L = await import("leaflet");
      if (!mounted || !ref.current) return;
      const nodeCoordinates = (data.nodes || [])
        .filter((node) => Number.isFinite(node.lat) && Number.isFinite(node.lon))
        .map((node) => L.latLng(node.lat, node.lon));
      const bounds = nodeCoordinates.length ? L.latLngBounds(nodeCoordinates).pad(0.08) : null;
      const map = L.map(ref.current, {
        maxBounds: bounds || undefined,
        maxBoundsViscosity: 1.0,
      });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "&copy; OpenStreetMap",
      }).addTo(map);
      if (bounds) {
        map.fitBounds(bounds, { padding: [20, 20], animate: false });
        map.setMinZoom(map.getZoom());
        map.setMaxBounds(bounds);
      } else {
        map.setView([10.05, 105.75], 8);
      }
      routeLayerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setMapReady(true);
    }
    init();
    return () => {
      mounted = false;
      mapRef.current?.remove();
      mapRef.current = null;
      routeLayerRef.current = null;
      setMapReady(false);
    };
  }, [data.nodes]);

  useEffect(() => {
    let cancelled = false;
    async function draw() {
      if (!mapRef.current || !routeLayerRef.current) return;
      const L = await import("leaflet");
      const routeLayer = routeLayerRef.current;
      routeLayer.clearLayers();
      const segments = routeCode
        ? data.routes?.[routeCode] || []
        : (data.legs || []).map((leg) => ({
            leg_id: leg.leg_id,
            mode: leg.mode,
            distance_km: leg.distance_km,
            origin: { lat: leg.points[0][0], lon: leg.points[0][1] },
            destination: { lat: leg.points[1][0], lon: leg.points[1][1] },
            points: leg.points,
          }));

      async function roadGeometry(segment: RouteSegment) {
        const key = `${segment.origin.lon},${segment.origin.lat};${segment.destination.lon},${segment.destination.lat}`;
        if (geometryCache.current.has(key)) return geometryCache.current.get(key)!;
        const url = `https://router.project-osrm.org/route/v1/driving/${key}?overview=full&geometries=geojson&steps=false`;
        const response = await fetch(url);
        if (!response.ok) throw new Error(`OSRM ${response.status}`);
        const payload = await response.json();
        const coordinates = payload.routes?.[0]?.geometry?.coordinates;
        if (!coordinates?.length) throw new Error("Missing OSRM geometry");
        const points = coordinates.map(([lon, lat]: [number, number]) => [lat, lon] as [number, number]);
        geometryCache.current.set(key, points);
        return points;
      }

      await Promise.all(
        segments.map(async (segment) => {
          const color = segment.mode === "water" ? "#0f766e" : "#64748b";
          if (segment.mode === "road") {
            try {
              const points = await roadGeometry(segment);
              if (!cancelled) {
                L.polyline(points, { color, weight: 4, opacity: 0.78 })
                  .addTo(routeLayer)
                  .bindPopup(`${routeCode || segment.leg_id}<br>${segment.leg_id}<br>road<br>${segment.distance_km} km`);
              }
            } catch {
              if (!cancelled) {
                L.polyline(segment.points, { color, weight: 4, opacity: 0.5, dashArray: "6 6" }).addTo(routeLayer);
              }
            }
            return;
          }
          if (!cancelled) {
            L.polyline(segment.points, { color, weight: 4, opacity: 0.72 })
              .addTo(routeLayer)
              .bindPopup(`${routeCode || segment.leg_id}<br>${segment.leg_id}<br>${segment.mode}<br>${segment.distance_km} km`);
          }
        }),
      );

      if (!cancelled) {
        (data.nodes || []).forEach((node) => {
          L.circleMarker([node.lat, node.lon], {
            radius: data.operational ? 3 : 7,
            color: data.operational ? "#475569" : "#1d4ed8",
            fillColor: "#ffffff",
            fillOpacity: data.operational ? 0.8 : 0.9,
            weight: 2,
          })
            .addTo(routeLayer)
            .bindPopup(`<strong>${escapeHtml(node.name)}</strong><br>${escapeHtml(node.node_id)}`);
        });
        if (data.operational) {
          const deliveryColors = ["#7c3aed", "#0891b2", "#ea580c", "#4f46e5"];
          const deliveryGeometry = new Map<string, [number, number][]>();
          await Promise.all(
            (data.active_deliveries || []).map(async (delivery, deliveryIndex) => {
              const color = deliveryColors[deliveryIndex % deliveryColors.length];
              const resolvedSegments = await Promise.all(delivery.segments.map(async (segment) => {
                let points = segment.points;
                let geographicGeometry = false;
                if (segment.mode === "road") {
                  try {
                    points = await roadGeometry(segment);
                    geographicGeometry = true;
                  } catch {
                    geographicGeometry = false;
                  }
                }
                if (cancelled) return points;
                L.polyline(points, {
                  color,
                  weight: 4,
                  opacity: 0.78,
                  dashArray:
                    delivery.status !== "dang_chay" ? "7 7" : segment.mode === "water" ? "3 6" : undefined,
                })
                  .addTo(routeLayer)
                  .bindPopup(
                    `<strong>${escapeHtml(delivery.delivery_id)}</strong><br>` +
                      `${escapeHtml(delivery.route_code)} · ${escapeHtml(segment.mode)}<br>` +
                      `Status: ${escapeHtml(delivery.status)}<br>ETA: ${escapeHtml(delivery.eta)}` +
                      (!geographicGeometry ? "<br><em>Fallback geometry</em>" : ""),
                  );
                return points;
              }));
              deliveryGeometry.set(delivery.delivery_id, resolvedSegments.flat());
            }),
          );
          (data.waiting_jobs || []).forEach((job) => {
            L.circleMarker([job.lat, job.lon], {
              radius: 8,
              color: "#92400e",
              fillColor: "#fbbf24",
              fillOpacity: 0.95,
              weight: 2,
            })
              .addTo(routeLayer)
              .bindPopup(
                `<strong>Waiting job: ${escapeHtml(job.job_id)}</strong><br>` +
                  `Hub: ${escapeHtml(job.hub_id)}<br>Weight: ${escapeHtml(job.khoi_luong_tich_luy_hien_tai_kg)} kg<br>` +
                  `Departure: ${escapeHtml(job.thoi_gian_de_xuat_chay)}<br>Route: ${escapeHtml(job.route_code)}`,
              );
          });
          const vehicleColors = { available: "#16a34a", unavailable: "#dc2626", in_delivery: "#2563eb" };
          const stationaryGroups = new Map<string, typeof data.vehicle_points>();
          (data.vehicle_points || []).filter((vehicle) => vehicle.display_status !== "in_delivery").forEach((vehicle) => {
            const key = `${vehicle.current_node_id}:${vehicle.display_status}`;
            stationaryGroups.set(key, [...(stationaryGroups.get(key) || []), vehicle]);
          });
          stationaryGroups.forEach((vehicles) => {
            if (!vehicles?.length) return;
            const first = vehicles[0];
            const color = vehicleColors[first.display_status];
            const icon = L.divIcon({
              className: "vehicle-cluster-shell",
              html: `<span class="vehicle-cluster-marker" style="--cluster-color:${color}">${vehicles.length}</span>`,
              iconSize: [24, 24],
              iconAnchor: [12, 12],
            });
            L.marker([first.lat, first.lon], { icon })
              .addTo(routeLayer)
              .bindPopup(
                `<strong>${escapeHtml(first.current_node_id)}</strong><br>` +
                  `${vehicles.length} ${escapeHtml(first.display_status)} trucks<br>` +
                  vehicles.slice(0, 8).map((vehicle) => escapeHtml(vehicle.vehicle_id)).join("<br>") +
                  (vehicles.length > 8 ? `<br>+${vehicles.length - 8} more` : ""),
              );
          });
          (data.vehicle_points || []).filter((vehicle) => vehicle.display_status === "in_delivery").forEach((vehicle) => {
            const color = vehicleColors[vehicle.display_status];
            const routedPosition = vehicle.delivery_id && vehicle.route_progress != null
              ? pointAlongPolyline(deliveryGeometry.get(vehicle.delivery_id) || [], vehicle.route_progress)
              : null;
            const position: [number, number] = routedPosition || [vehicle.lat, vehicle.lon];
            L.circleMarker(position, {
              radius: 4,
              color: "#ffffff",
              fillColor: color,
              fillOpacity: 0.96,
              weight: 1,
            })
              .addTo(routeLayer)
              .bindPopup(
                `<strong>${escapeHtml(vehicle.vehicle_id)}</strong><br>` +
                  `${escapeHtml(vehicle.vehicle_type)} · ${escapeHtml(vehicle.capacity_ton)} t<br>` +
                  `Status: ${escapeHtml(vehicle.source_status)}` +
                  (vehicle.delivery_id ? `<br>Delivery: ${escapeHtml(vehicle.delivery_id)}` : ""),
              )
              .bindTooltip(escapeHtml(vehicle.vehicle_id), { direction: "top", offset: [0, -7] });
          });
        } else {
          (data.fleet || []).forEach((group) => {
            L.marker([group.lat, group.lon])
              .addTo(routeLayer)
              .bindPopup(
                `<strong>${escapeHtml(group.node_id)}</strong><br>${group.count} phương tiện<br>${escapeHtml(JSON.stringify(group.statuses))}`,
              );
          });
        }
      }
    }
    draw();
    return () => {
      cancelled = true;
    };
  }, [data, mapReady, routeCode]);

  const routeCodes = Object.keys(data.routes || {});

  return (
    <div className="map-stack">
      {data.operational ? (
        <div className="map-legend" aria-label="Map legend">
          <span><i className="legend-dot available" />Available ({data.summary?.available_vehicles || 0})</span>
          <span><i className="legend-dot legend-unavailable" />Unavailable ({data.summary?.unavailable_vehicles || 0})</span>
          <span><i className="legend-dot delivery" />During delivery ({(data.vehicle_points || []).filter((vehicle) => vehicle.display_status === "in_delivery").length})</span>
          <span><i className="legend-dot job" />Waiting jobs ({data.summary?.waiting_jobs || 0})</span>
          <span><i className="legend-line" />Active routes ({data.summary?.active_deliveries || 0})</span>
        </div>
      ) : null}
      {routeCodes.length ? (
        <div className="route-toolbar" aria-label="Route selector">
          {routeCodes.map((code) => (
            <button
              key={code}
              className={routeCode === code ? "selected" : "secondary"}
              type="button"
              onClick={() => {
                setRouteCode(code);
                onSelectedRouteChange?.(code);
              }}
            >
              {code}
            </button>
          ))}
        </div>
      ) : null}
      <div ref={ref} className="map" />
    </div>
  );
}
