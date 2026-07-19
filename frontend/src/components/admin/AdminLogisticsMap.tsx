"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";
import type { MapPayload } from "@/types/dashboard";
import {
  ADMIN_MAP_VIEW,
  LOGISTICS_MAP_POINTS,
  ROAD_SEGMENTS,
  WATERWAY_SEGMENTS,
} from "@/data/adminMapData";

type ModeFilter = "both" | "road" | "waterway";

interface Props {
  backendMapPayload?: MapPayload | null;
}

const ROAD_COLOR = "#1d4ed8";
const WATER_COLOR = "#0f766e";
const POINT_COLOR: Record<string, string> = {
  origin: "#1d4ed8",
  hub: "#d97706",
  destination: "#dc2626",
  transfer: "#64748b",
};

export function AdminLogisticsMap({ backendMapPayload }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const roadLayerRef = useRef<LayerGroup | null>(null);
  const waterLayerRef = useRef<LayerGroup | null>(null);
  const backendLayerRef = useRef<LayerGroup | null>(null);
  const [mode, setMode] = useState<ModeFilter>("both");

  // One-time initialization — builds demo logistics network on the map.
  useEffect(() => {
    let mounted = true;
    async function init() {
      if (!containerRef.current || mapRef.current) return;
      const L = await import("leaflet");
      if (!mounted || !containerRef.current) return;

      const map = L.map(containerRef.current, {
        minZoom: ADMIN_MAP_VIEW.minZoom,
        maxZoom: ADMIN_MAP_VIEW.maxZoom,
        maxBounds: ADMIN_MAP_VIEW.maxBounds,
        attributionControl: false,
        // viscosity 1.0 → map snaps back immediately; user cannot drag outside bounds
        maxBoundsViscosity: 1.0,
      });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: ADMIN_MAP_VIEW.maxZoom,
      }).addTo(map);

      // Road segment layer
      const roadLayer = L.layerGroup().addTo(map);
      for (const seg of ROAD_SEGMENTS) {
        L.polyline(seg.points, {
          color: ROAD_COLOR,
          weight: 3,
          opacity: 0.85,
        })
          .bindPopup(
            `<strong>${seg.label}</strong><br>Road &nbsp;·&nbsp; ${seg.distance_km} km`
          )
          .addTo(roadLayer);
      }

      // Waterway segment layer
      const waterLayer = L.layerGroup().addTo(map);
      for (const seg of WATERWAY_SEGMENTS) {
        L.polyline(seg.points, {
          color: WATER_COLOR,
          weight: 3,
          opacity: 0.85,
          dashArray: "9 5",
        })
          .bindPopup(
            `<strong>${seg.label}</strong><br>Waterway &nbsp;·&nbsp; ${seg.distance_km} km`
          )
          .addTo(waterLayer);
      }

      // Point markers (always visible — not toggled by mode filter)
      const markersLayer = L.layerGroup().addTo(map);
      for (const pt of LOGISTICS_MAP_POINTS) {
        const color = POINT_COLOR[pt.type] ?? "#64748b";
        const radius = pt.type === "hub" ? 11 : pt.type === "destination" ? 9 : 8;
        L.circleMarker([pt.latitude, pt.longitude], {
          radius,
          color: "white",
          fillColor: color,
          fillOpacity: 0.92,
          weight: 2,
        })
          .bindPopup(
            `<strong>${pt.name}</strong><br>${pt.type}${pt.province ? `<br>${pt.province}` : ""}`
          )
          .addTo(markersLayer);
      }

      // Empty layer for live backend nodes (populated by second effect)
      const backendLayer = L.layerGroup().addTo(map);

      // Set initial view to the configured operating area
      map.setView(ADMIN_MAP_VIEW.center, ADMIN_MAP_VIEW.zoom);

      roadLayerRef.current = roadLayer;
      waterLayerRef.current = waterLayer;
      backendLayerRef.current = backendLayer;
      mapRef.current = map;
    }

    init();
    return () => {
      mounted = false;
      mapRef.current?.remove();
      mapRef.current = null;
      roadLayerRef.current = null;
      waterLayerRef.current = null;
      backendLayerRef.current = null;
    };
  }, []);

  // Toggle road / waterway layers when the mode filter changes.
  useEffect(() => {
    const map = mapRef.current;
    const road = roadLayerRef.current;
    const water = waterLayerRef.current;
    if (!map || !road || !water) return;

    if (mode === "road") {
      if (!map.hasLayer(road)) map.addLayer(road);
      if (map.hasLayer(water)) map.removeLayer(water);
    } else if (mode === "waterway") {
      if (map.hasLayer(road)) map.removeLayer(road);
      if (!map.hasLayer(water)) map.addLayer(water);
    } else {
      if (!map.hasLayer(road)) map.addLayer(road);
      if (!map.hasLayer(water)) map.addLayer(water);
    }
  }, [mode]);

  // Overlay live backend nodes when the backend payload becomes available.
  useEffect(() => {
    const layer = backendLayerRef.current;
    if (!layer || !backendMapPayload) return;

    let cancelled = false;
    async function drawBackendNodes() {
      const L = await import("leaflet");
      if (cancelled) return;
      layer!.clearLayers();
      for (const node of backendMapPayload!.nodes ?? []) {
        L.circleMarker([node.lat, node.lon], {
          radius: 5,
          color: "#94a3b8",
          fillColor: "#cbd5e1",
          fillOpacity: 0.7,
          weight: 1,
        })
          .bindPopup(`<strong>${node.name}</strong><br>${node.node_id}`)
          .addTo(layer!);
      }
    }
    drawBackendNodes();
    return () => { cancelled = true; };
  }, [backendMapPayload]);

  const modeOptions: { value: ModeFilter; label: string }[] = [
    { value: "both", label: "All Routes" },
    { value: "road", label: "Road Only" },
    { value: "waterway", label: "Waterway Only" },
  ];

  return (
    <div>
      {/* Filter toolbar + legend */}
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <div className="route-toolbar" style={{ margin: 0 }}>
          {modeOptions.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className={mode === value ? "selected" : "secondary"}
              onClick={() => setMode(value)}
            >
              {label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", gap: 14, fontSize: 12, color: "#64748b", flexWrap: "wrap" }}>
          <span style={{ display: "flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 22, height: 3, background: ROAD_COLOR, display: "inline-block", borderRadius: 2 }} />
            Road
          </span>
          <span style={{ display: "flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 22, height: 3, background: WATER_COLOR, display: "inline-block", borderRadius: 2, borderTop: `2px dashed ${WATER_COLOR}` }} />
            Waterway
          </span>
          <span style={{ display: "flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 10, height: 10, background: POINT_COLOR.origin, borderRadius: "50%", display: "inline-block", border: "1.5px solid white", outline: "1px solid #1d4ed8" }} />
            Origin hub
          </span>
          <span style={{ display: "flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 12, height: 12, background: POINT_COLOR.hub, borderRadius: "50%", display: "inline-block", border: "1.5px solid white", outline: "1px solid #d97706" }} />
            Cần Thơ hub
          </span>
          <span style={{ display: "flex", gap: 5, alignItems: "center" }}>
            <span style={{ width: 10, height: 10, background: POINT_COLOR.destination, borderRadius: "50%", display: "inline-block", border: "1.5px solid white", outline: "1px solid #dc2626" }} />
            Destination
          </span>
        </div>
      </div>

      {/* Leaflet map container */}
      <div
        ref={containerRef}
        style={{
          height: 420,
          borderRadius: 6,
          border: "1px solid #dbe2ea",
          overflow: "hidden",
        }}
      />

      {/* Backend connectivity note */}
      <p style={{ margin: "6px 0 0", fontSize: 12, color: backendMapPayload ? "#047857" : "#94a3b8" }}>
        {backendMapPayload
          ? "✓ Live backend nodes overlaid. Route lines show the demo logistics network."
          : "Route lines show demo logistics network. Connect backend for live node positions."}
      </p>
    </div>
  );
}
