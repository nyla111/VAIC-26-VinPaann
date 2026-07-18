"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import type { MapPayload, RouteSegment } from "@/types/dashboard";

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


export function VaicMap({ data, selectedRoute, onSelectedRouteChange, trackingMarker }: Props) {

  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const routeLayerRef = useRef<LayerGroup | null>(null);
  const geometryCache = useRef(new Map<string, [number, number][]>());
  const [routeCode, setRouteCode] = useState(selectedRoute || data.activeRoute || null);

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
          L.circleMarker([node.lat, node.lon], { radius: 7, color: "#1d4ed8", fillOpacity: 0.9 })
            .addTo(routeLayer)
            .bindPopup(`<strong>${node.name}</strong><br>${node.node_id}`);
        });
        (data.fleet || []).forEach((group) => {
          L.marker([group.lat, group.lon])
            .addTo(routeLayer)
            .bindPopup(`<strong>${group.node_id}</strong><br>${group.count} phương tiện<br>${JSON.stringify(group.statuses)}`);
        });
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
  }, [data, routeCode, trackingMarker]);


  const routeCodes = Object.keys(data.routes || {});

  return (
    <div className="map-stack">
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
