function initVaicMap() {
  const el = document.getElementById("map");
  if (!el || !window.L) return;
  const data = JSON.parse(el.dataset.map || "{}");
  const routeLayer = L.layerGroup();
  const geometryCache = new Map();
  const nodeCoordinates = (data.nodes || [])
    .filter((node) => Number.isFinite(node.lat) && Number.isFinite(node.lon))
    .map((node) => [node.lat, node.lon]);
  const operationalBounds = nodeCoordinates.length ? L.latLngBounds(nodeCoordinates) : null;
  const paddedBounds = operationalBounds ? operationalBounds.pad(0.08) : null;
  const map = L.map(el, {
    maxBounds: paddedBounds || undefined,
    maxBoundsViscosity: 1.0,
  });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);
  routeLayer.addTo(map);
  if (paddedBounds) {
    map.fitBounds(paddedBounds, {
      padding: [20, 20],
      animate: false,
    });
    const overviewZoom = map.getZoom();
    map.setMinZoom(overviewZoom);
    map.setMaxBounds(paddedBounds);
  } else {
    map.setView([10.05, 105.75], 8);
  }

  function nodeRouteSegmentFromLeg(leg) {
    return {
      leg_id: leg.leg_id,
      mode: leg.mode,
      distance_km: leg.distance_km,
      origin: { lat: leg.points[0][0], lon: leg.points[0][1] },
      destination: { lat: leg.points[1][0], lon: leg.points[1][1] },
      points: leg.points,
    };
  }

  async function roadGeometry(segment) {
    const key = `${segment.origin.lon},${segment.origin.lat};${segment.destination.lon},${segment.destination.lat}`;
    if (geometryCache.has(key)) return geometryCache.get(key);
    const url = `https://router.project-osrm.org/route/v1/driving/${key}?overview=full&geometries=geojson&steps=false`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`OSRM ${response.status}`);
    const payload = await response.json();
    const coordinates = payload.routes?.[0]?.geometry?.coordinates;
    if (!coordinates || !coordinates.length) throw new Error("Missing OSRM geometry");
    const points = coordinates.map(([lon, lat]) => [lat, lon]);
    geometryCache.set(key, points);
    return points;
  }

  async function drawSegment(segment, routeCode) {
    const color = segment.mode === "water" ? "#0f766e" : "#64748b";
    if (segment.mode === "road") {
      try {
        const points = await roadGeometry(segment);
        L.polyline(points, { color, weight: 4, opacity: 0.78 })
          .addTo(routeLayer)
          .bindPopup(`${routeCode || segment.leg_id}<br>${segment.leg_id}<br>road<br>${segment.distance_km} km`);
      } catch (error) {
        console.warn(`Could not load road geometry for ${segment.leg_id}`, error);
      }
      return;
    }
    L.polyline(segment.points, { color, weight: 4, opacity: 0.72 })
      .addTo(routeLayer)
      .bindPopup(`${routeCode || segment.leg_id}<br>${segment.leg_id}<br>${segment.mode}<br>${segment.distance_km} km`);
  }

  async function drawRoute(routeCode) {
    routeLayer.clearLayers();
    const routes = data.routes || {};
    const segments = routeCode ? routes[routeCode] || [] : (data.legs || []).map(nodeRouteSegmentFromLeg);
    document.querySelectorAll("[data-route-card]").forEach((card) => {
      card.classList.toggle("recommended", card.dataset.routeCard === routeCode);
    });
    await Promise.all(segments.map((segment) => drawSegment(segment, routeCode)));
  }

  drawRoute(data.activeRoute || null);
  document.querySelectorAll(".route-select[data-route-code]").forEach((button) => {
    button.addEventListener("click", () => drawRoute(button.dataset.routeCode));
  });

  (data.nodes || []).forEach((node) => {
    L.circleMarker([node.lat, node.lon], { radius: 7, color: "#1d4ed8", fillOpacity: 0.9 })
      .addTo(map)
      .bindPopup(`<strong>${node.name}</strong><br>${node.node_id}`);
  });
  (data.fleet || []).forEach((group) => {
    L.marker([group.lat, group.lon])
      .addTo(map)
      .bindPopup(`<strong>${group.node_id}</strong><br>${group.count} phương tiện<br>${JSON.stringify(group.statuses)}`);
  });
}
document.addEventListener("DOMContentLoaded", initVaicMap);
