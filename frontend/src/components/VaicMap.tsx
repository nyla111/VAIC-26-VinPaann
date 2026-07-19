"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import type { MapPayload, RouteSegment } from "@/types/dashboard";
import { useLanguage } from "@/context/LanguageContext";
import { routeLabel } from "@/lib/labels";

// Fix default marker icon issues in Next.js
if (typeof window !== "undefined") {
  delete (L.Icon.Default.prototype as any)._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png",
    iconRetinaUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon-2x.png",
    shadowUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png",
  });
}

type Props = {
  data: MapPayload;
  selectedRoute?: string | null;
  onSelectedRouteChange?: (routeCode: string) => void;
  trackingMarker?: { lat: number; lon: number; label: string } | null;
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

export function VaicMap({ data, selectedRoute, onSelectedRouteChange, trackingMarker }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const routeLayerRef = useRef<LayerGroup | null>(null);
  const geometryCache = useRef(new Map<string, [number, number][]>());
  const [routeCode, setRouteCode] = useState(selectedRoute || data.activeRoute || null);
  const { language, t } = useLanguage();
  const mapText = language === "vi" ? {
    road: "Đường bộ", water: "Đường thủy", status: "Trạng thái", eta: "Dự kiến",
    type: "Loại", job: "Chuyến vận chuyển", waiting: "Chờ gom hàng tại Cần Thơ",
    available: "Sẵn sàng", unavailable: "Không sẵn sàng", delivery: "Đang giao hàng", unassigned: "Chưa gán",
    arrived: "Đã đến hub", waitingJobs: "Đơn chờ gom", activeRoutes: "Tuyến đang chạy",
  } : {
    road: "Road", water: "Waterway", status: "Status", eta: "ETA", type: "Type",
    job: "Transport job", waiting: "Waiting for consolidation at Can Tho", available: "Available",
    unavailable: "Unavailable", delivery: "In delivery", unassigned: "Unassigned", arrived: "Arrived at hub",
    waitingJobs: "Waiting jobs", activeRoutes: "Active routes",
  };

  useEffect(() => {
    setRouteCode(selectedRoute || data.activeRoute || null);
  }, [data.activeRoute, selectedRoute]);

  useEffect(() => {
    let mounted = true;
    if (!ref.current || mapRef.current) return;
    if (!mounted || !ref.current) return;
    const nodeCoordinates = (data.nodes || [])
      .filter((node) => Number.isFinite(node.lat) && Number.isFinite(node.lon))
      .map((node) => L.latLng(node.lat, node.lon));
    const bounds = nodeCoordinates.length ? L.latLngBounds(nodeCoordinates).pad(0.08) : null;
    const mekongBounds = L.latLngBounds([8.5, 104.0], [11.5, 107.0]);
    const map = L.map(ref.current, {
      maxBounds: mekongBounds,
      maxBoundsViscosity: 1.0,
      minZoom: 8,
      attributionControl: false,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
    }).addTo(map);
    
    if (bounds) {
      map.fitBounds(bounds, { padding: [20, 20], animate: false });
    } else {
      map.setView([10.05, 105.75], 8);
    }
    routeLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      mounted = false;
      mapRef.current?.remove();
      mapRef.current = null;
      routeLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function draw() {
      if (!mapRef.current || !routeLayerRef.current) return;
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

      async function geographicGeometry(segment: RouteSegment) {
        const key = `${segment.origin.lon},${segment.origin.lat};${segment.destination.lon},${segment.destination.lat}`;
        if (geometryCache.current.has(key)) return geometryCache.current.get(key)!;
        const points = segment.points;
        geometryCache.current.set(key, points);
        return points;
      }

      await Promise.all(
        segments.map(async (segment) => {
          const color = segment.mode === "water" ? "#0f766e" : "#64748b";
          const points = await geographicGeometry(segment);
          if (!cancelled) {
            L.polyline(points, {
              color,
              weight: 4,
              opacity: 0.78,
              dashArray: segment.mode === "water" ? "8 6" : undefined,
            })
              .addTo(routeLayer)
              .bindPopup(`${routeCode || segment.leg_id}<br>${segment.leg_id}<br>${segment.mode === "water" ? mapText.water : mapText.road}<br>${segment.distance_km} km`);
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
                let hasGeographicGeometry = false;
                points = await geographicGeometry(segment);
                hasGeographicGeometry = points.length > 2;
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
                    `${escapeHtml(delivery.route_code)} · ${escapeHtml(segment.mode === "water" ? mapText.water : mapText.road)}<br>` +
                      `${mapText.status}: ${escapeHtml(delivery.status)}<br>${mapText.eta}: ${escapeHtml(delivery.eta)}` +
                      (!hasGeographicGeometry ? `<br><em>${t("map.fallback_geometry")}</em>` : ""),
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
                `<strong>${mapText.waiting}: ${escapeHtml(job.job_id)}</strong><br>` +
                  `${mapText.type}: ${escapeHtml(job.hub_id)}<br>${t("common.weight")}: ${escapeHtml(job.khoi_luong_tich_luy_hien_tai_kg)} kg<br>` +
                  `${t("map.departure")}: ${escapeHtml(job.thoi_gian_de_xuat_chay)}<br>${t("common.route")}: ${escapeHtml(routeLabel(job.route_code, language))}`,
              );
          });

          const truckIcon = L.divIcon({
            className: "custom-truck-icon",
            html: `<div style="background-color: #ea580c; border: 2px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">🚚</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16]
          });

          const boatIcon = L.divIcon({
            className: "custom-boat-icon",
            html: `<div style="background-color: #1d4ed8; border: 2px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">🚢</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16]
          });

          const yellowTruckIcon = L.divIcon({
            className: "custom-truck-icon-waiting",
            html: `<div style="background-color: #fbbf24; border: 2px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">🚚</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16]
          });

          const yellowBoatIcon = L.divIcon({
            className: "custom-boat-icon-waiting",
            html: `<div style="background-color: #fbbf24; border: 2px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">🚢</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
            popupAnchor: [0, -16]
          });

          const statusLabels: Record<string, string> = language === "vi" ? {
            available: "Sẵn sàng",
            in_transit: "Đang giao hàng",
            en_route: "Đang giao hàng",
            maintenance: "Bảo trì"
          } : {
            available: "Available",
            in_transit: "In delivery",
            en_route: "In delivery",
            maintenance: "Maintenance"
          };

          const typeLabels: Record<string, string> = {
            road: t("fleet.vehicle_truck"),
            water: t("fleet.vehicle_vessel")
          };

          (data.vehicle_points || []).forEach((vehicle) => {
            const isRoad = vehicle.vehicle_type === "road";
            const isWaiting = vehicle.display_status === "arrived_waiting";
            const icon = isWaiting
              ? (isRoad ? yellowTruckIcon : yellowBoatIcon)
              : (isRoad ? truckIcon : boatIcon);
            
            const lat = vehicle.lat;
            const lon = vehicle.lon;
            
            if (Number.isFinite(lat) && Number.isFinite(lon)) {
              let popupContent = 
                `<div style="font-family: inherit; font-size: 13px; line-height: 1.5; padding: 4px;">` +
                  `<h3 style="margin: 0 0 6px; font-size: 14px; font-weight: bold; border-bottom: 1px solid #eee; padding-bottom: 4px; color: ${isWaiting ? '#d97706' : isRoad ? '#ea580c' : '#1d4ed8'}">` +
                    `${escapeHtml(vehicle.vehicle_id)}` +
                  `</h3>` +
                  `<div><strong>${mapText.type}:</strong> ${escapeHtml(typeLabels[vehicle.vehicle_type] || vehicle.vehicle_type)}</div>` +
                  `<div><strong>${mapText.status}:</strong> ${isWaiting ? mapText.waiting : escapeHtml(statusLabels[vehicle.source_status] || vehicle.source_status)}</div>` +
                  `<div><strong>${mapText.job}:</strong> ${vehicle.delivery_id ? escapeHtml(vehicle.delivery_id) : `<span style="color: #999;">${mapText.unassigned}</span>`}</div>`;
              
              if (isWaiting && vehicle.ai2_metrics) {
                const metrics = vehicle.ai2_metrics;
                popupContent += 
                  `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px dashed #ddd; font-size: 11px; color: #4b5563;">` +
                    `<div><strong>${t("map.layer2_decision")}:</strong> <span style="color: #b45309; font-weight: bold;">${escapeHtml(metrics.decision)}</span></div>` +
                    `<div><strong>${t("map.explanation")}:</strong> ${escapeHtml(metrics.explanation)}</div>` +
                  `</div>`;
              }
              popupContent += `</div>`;

              let tooltipContent = escapeHtml(vehicle.vehicle_id);
              if (isWaiting && vehicle.ai2_metrics) {
                tooltipContent += ` (AI2: ${escapeHtml(vehicle.ai2_metrics.decision)})`;
              }

              L.marker([lat, lon], { icon })
                .addTo(routeLayer)
                .bindPopup(popupContent)
                .bindTooltip(tooltipContent, { direction: "top", offset: [0, -16] });
            }
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

        if (trackingMarker) {
          L.marker([trackingMarker.lat, trackingMarker.lon])
            .addTo(routeLayer)
            .bindPopup(`<strong>${trackingMarker.label}</strong>`)
            .openPopup();
          if (mapRef.current) {
            mapRef.current.panTo([trackingMarker.lat, trackingMarker.lon]);
          }
        }
      }
    }
    draw();
    return () => {
      cancelled = true;
    };
  }, [data, language, mapText, routeCode, trackingMarker]);

  const routeCodes = Object.keys(data.routes || {});

  return (
    <div className="map-stack">
      {data.operational ? (
        <div className="map-legend" aria-label={language === "vi" ? "Chú giải bản đồ" : "Map legend"}>
          <span><i className="legend-dot available" />{mapText.available} ({data.summary?.available_vehicles || 0})</span>
          <span><i className="legend-dot legend-unavailable" />{mapText.unavailable} ({data.summary?.unavailable_vehicles || 0})</span>
          <span><i className="legend-dot delivery" />{mapText.delivery} ({(data.vehicle_points || []).filter((vehicle) => vehicle.display_status === "in_delivery").length})</span>
          <span className="flex items-center gap-1"><i className="legend-dot" style={{ backgroundColor: "#fbbf24", display: "inline-block", borderRadius: "50%", width: "10px", height: "10px" }} />{mapText.arrived} ({(data.vehicle_points || []).filter((vehicle) => vehicle.display_status === "arrived_waiting").length})</span>
          <span><i className="legend-dot job" />{mapText.waitingJobs} ({data.summary?.waiting_jobs || 0})</span>
          <span><i className="legend-line" />{mapText.activeRoutes} ({data.summary?.active_deliveries || 0})</span>
        </div>
      ) : null}
      {routeCodes.length ? (
        <div className="route-toolbar" aria-label={t("map.route_selector")}>
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
              {routeLabel(code, language)}
            </button>
          ))}
        </div>
      ) : null}
      <div ref={ref} className="map" />
    </div>
  );
}
