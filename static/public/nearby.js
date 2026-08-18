import { getJson, renderCards, trackEvent } from "./discovery-common.js";

const mapRoot = document.querySelector("[data-nearby-map]");
const latInput = document.querySelector("[data-nearby-lat]");
const lngInput = document.querySelector("[data-nearby-lng]");
const radius = document.querySelector("[data-nearby-radius]");
const kind = document.querySelector("[data-nearby-kind]");
const results = document.querySelector("[data-nearby-results]");
const status = document.querySelector("[data-nearby-status]");
const heading = document.querySelector("[data-nearby-heading]");
let marker = null;
let map = null;

function setPoint(lat, lng, { pan = true } = {}) {
  const safeLat = Math.max(-90, Math.min(90, Number(lat)));
  const safeLng = Math.max(-180, Math.min(180, Number(lng)));
  latInput.value = safeLat.toFixed(6);
  lngInput.value = safeLng.toFixed(6);
  if (!map || !window.L) return;
  if (!marker) marker = window.L.marker([safeLat, safeLng]).addTo(map);
  else marker.setLatLng([safeLat, safeLng]);
  if (pan) map.flyTo([safeLat, safeLng], Math.max(8, map.getZoom()), { duration: .45 });
}

function initializeMap() {
  if (!window.L || !mapRoot) {
    window.setTimeout(initializeMap, 40);
    return;
  }
  map = window.L.map(mapRoot, { zoomControl: true }).setView([61.5, 96.5], 3);
  window.TouristikaMapTiles.addBaseLayer(map, { maxZoom: 18 });
  map.on("click", ({ latlng }) => setPoint(latlng.lat, latlng.lng, { pan: false }));
}

async function search() {
  const lat = Number(latInput.value);
  const lng = Number(lngInput.value);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lng) || lng < -180 || lng > 180) {
    status.textContent = "Введите корректные координаты: широта от −90 до 90, долгота от −180 до 180.";
    return;
  }
  setPoint(lat, lng);
  trackEvent("nearby_requested", { contentType: "nearby" });
  status.textContent = "Ищем рядом…";
  try {
    const params = new URLSearchParams({ lat: String(lat), lng: String(lng), radius: radius.value, limit: "24" });
    if (kind.value) params.set("entity_kind", kind.value);
    const payload = await getJson(`/api/public/nearby?${params}`);
    heading.textContent = `В радиусе ${radius.value} км`;
    status.textContent = `Найдено: ${payload.total}`;
    renderCards(results, payload.items, { distance: true, emptyText: "В выбранном радиусе пока нет опубликованных объектов." });
  } catch (error) {
    status.textContent = error.message;
    renderCards(results, [], { emptyTitle: "Не удалось выполнить поиск", emptyText: "Попробуйте ещё раз." });
  }
}

document.querySelector("[data-nearby-search]")?.addEventListener("click", search);
document.querySelector("[data-request-location]")?.addEventListener("click", () => {
  if (!navigator.geolocation) {
    status.textContent = "Геолокация недоступна. Выберите точку на карте или введите координаты.";
    return;
  }
  status.textContent = "Запрашиваем местоположение…";
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => { trackEvent("nearby_permission_granted", { contentType: "nearby" }); setPoint(coords.latitude, coords.longitude); search(); },
    () => { trackEvent("nearby_permission_denied", { contentType: "nearby" }); status.textContent = "Не удалось определить местоположение. Выберите точку на карте."; },
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
  );
});
[latInput, lngInput].forEach((input) => input?.addEventListener("change", () => {
  if (latInput.checkValidity() && lngInput.checkValidity() && latInput.value && lngInput.value) setPoint(latInput.value, lngInput.value);
}));
initializeMap();
