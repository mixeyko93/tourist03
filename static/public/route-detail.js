import { installShareButtons, rememberCurrentPage } from "./discovery-common.js";

function initialize() {
  const root = document.querySelector("[data-route-map]");
  if (!root) return;
  if (!window.L) {
    window.setTimeout(initialize, 40);
    return;
  }
  let points = [];
  let geojson = null;
  try { points = JSON.parse(root.dataset.points || "[]"); } catch {}
  try { geojson = JSON.parse(root.dataset.geojson || "null"); } catch {}
  const map = window.L.map(root, { scrollWheelZoom: false });
  window.TouristikaMapTiles.addBaseLayer(map, { maxZoom: 18 });
  const bounds = [];
  points.forEach((point, index) => {
    if (!Number.isFinite(Number(point.lat)) || !Number.isFinite(Number(point.lng))) return;
    const latlng = [Number(point.lat), Number(point.lng)];
    bounds.push(latlng);
    window.L.marker(latlng).addTo(map).bindTooltip(`${index + 1}. ${point.title || "Точка маршрута"}`);
  });
  if (geojson) {
    try {
      const layer = window.L.geoJSON(geojson, { style: { color: "#167245", weight: 5, opacity: .85 } }).addTo(map);
      layer.getBounds().eachLayer?.(() => {});
    } catch {}
  } else if (bounds.length > 1) {
    window.L.polyline(bounds, { color: "#167245", weight: 5, opacity: .85 }).addTo(map);
  }
  if (bounds.length) map.fitBounds(bounds, { padding: [28, 28], maxZoom: 13 });
  else map.setView([61.5, 96.5], 3);
  document.querySelector("[data-scroll-route-map]")?.addEventListener("click", () => {
    root.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    window.setTimeout(() => map.invalidateSize(), 300);
  });
}

installShareButtons();
rememberCurrentPage();
initialize();
