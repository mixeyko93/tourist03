const RUSSIA_VIEW = [61, 99];
const RUSSIA_ZOOM = 3;
const HEX_COLOR = /^#[0-9a-f]{6}$/i;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[character]);
}

function isCoordinate(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function formatPrice(value) {
  const price = Number(value);
  if (!Number.isFinite(price) || price <= 0) return "";
  return `от ${new Intl.NumberFormat("ru-RU").format(price)} ₽`;
}

function safeContactUrl(value) {
  try {
    const url = new URL(String(value));
    if (!["http:", "https:", "tel:", "mailto:"].includes(url.protocol)) return null;
    if (["http:", "https:"].includes(url.protocol) && (url.username || url.password)) return null;
    return url.href;
  } catch {
    return null;
  }
}

function safeImageUrl(value) {
  const raw = String(value || "").trim();
  if (raw.startsWith("/") && !raw.startsWith("//") && !raw.includes("\\")) return raw;
  try {
    const url = new URL(raw);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

function accentColor(placeType) {
  const candidate = String(placeType?.config?.accent || "");
  return HEX_COLOR.test(candidate) ? candidate : "#247da8";
}

function markerGlyph(iconKey) {
  const paths = {
    home: '<path d="M4 11.5 12 5l8 6.5V20h-5v-5H9v5H4Z"/>',
    house: '<path d="M3.5 12 12 4.5l8.5 7.5M6 10.5V20h12v-9.5M10 20v-5h4v5"/>',
    hotel: '<path d="M5 20V5h10v15M15 10h4v10M8 8h2m2 0h1M8 12h2m2 0h1M3 20h18"/>',
    tent: '<path d="m4 20 8-16 8 16M8.5 20 12 13l3.5 7M4 20h16"/>',
    camp: '<path d="M12 3v18M5 19 12 5l7 14M7.5 14h9"/>',
    building: '<path d="M5 20V6l7-3 7 3v14M9 8h2m2 0h2M9 12h2m2 0h2M10 20v-4h4v4"/>',
    cottage: '<path d="m3 11 9-7 9 7M5 10v10h14V10M9 20v-6h6v6"/>',
    health: '<path d="M12 21s-8-4.8-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6.2-8 11-8 11Z"/>',
    trees: '<path d="m7 3-4 8h3l-4 7h10l-4-7h3L7 3Zm10 2-3 6h2l-3 6h8l-3-6h2l-3-6ZM7 18v3m10-4v4"/>',
    bed: '<path d="M4 18V7m0 7h16v4M7 14v-4h5a3 3 0 0 1 3 3v1M4 18v2m16-2v2"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5 5-2Z"/>',
    pin: '<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[iconKey] || paths.pin}</svg>`;
}

function markerIcon(place) {
  const label = escapeHtml((place.name || "Место отдыха").slice(0, 48));
  const type = place.place_type || {};
  const accent = accentColor(type);
  return window.L.divIcon({
    className: "public-map-marker-wrap",
    html: `<span class="public-map-marker" style="--marker-accent:${accent}" aria-hidden="true">${markerGlyph(type.icon_key)}<b>${label}</b></span>`,
    iconSize: [44, 44],
    iconAnchor: [22, 44],
    popupAnchor: [0, -40],
  });
}

function contactLinks(place) {
  return (place.primary_contacts || []).slice(0, 2).map((contact) => {
    const url = safeContactUrl(contact.url);
    if (!url) return "";
    const label = escapeHtml(contact.label || (contact.contact_type === "phone" ? "Позвонить" : "Связаться"));
    const external = /^https?:/i.test(url) ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<a class="public-map-popup__contact" href="${escapeHtml(url)}"${external}>${label}</a>`;
  }).filter(Boolean).join("");
}

function popupContent(place) {
  const name = escapeHtml(place.name || "Место отдыха");
  const type = escapeHtml(place.place_type?.name || "Туристический объект");
  const location = escapeHtml([place.region, place.city, place.locality].filter(Boolean).join(", ") || "Россия");
  const description = escapeHtml(place.short_description || "Информация об объекте появится в каталоге.");
  const price = formatPrice(place.min_price);
  const cover = safeImageUrl(place.cover);
  const slug = encodeURIComponent(String(place.slug || ""));
  return `
    <article class="public-map-popup">
      ${cover ? `<img src="${escapeHtml(cover)}" alt="" loading="lazy">` : '<div class="public-map-popup__placeholder" aria-hidden="true">Т</div>'}
      <p>${type}</p>
      <h3>${name}</h3>
      <span>${location}</span>
      <small>${description}</small>
      ${price ? `<strong>${price}</strong>` : ""}
      <div class="public-map-popup__actions">
        <a class="public-map-popup__detail" href="/places/${slug}">Подробнее</a>
        ${contactLinks(place)}
      </div>
    </article>`;
}

function createClusterLayer() {
  if (typeof window.L.markerClusterGroup !== "function") return window.L.featureGroup();
  return window.L.markerClusterGroup({
    maxClusterRadius: 56,
    showCoverageOnHover: false,
    spiderfyOnMaxZoom: true,
    iconCreateFunction(cluster) {
      const count = cluster.getChildCount();
      return window.L.divIcon({
        className: "public-map-cluster-wrap",
        html: `<span class="public-map-cluster">${count}</span>`,
        iconSize: [46, 46],
        iconAnchor: [23, 23],
      });
    },
  });
}

function replaceOptions(select, items, placeholder, getValue, getLabel) {
  if (!select) return;
  select.replaceChildren();
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = placeholder;
  select.append(empty);
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = getValue(item);
    option.textContent = getLabel(item);
    select.append(option);
  });
}

function uniqueTextValues(items, key) {
  return [...new Set(items.map((item) => String(item[key] || "").trim()).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "ru"));
}

export function initialisePublicMap({
  shell,
  canvas,
  loading,
  status,
  results,
  filterPanel,
  filterToggle,
  filterType,
  filterRegion,
  filterCity,
  filterAmenity,
  filterReset,
  count,
  legend,
  onMapReady,
}) {
  if (!window.L || !canvas) {
    status.textContent = "Карта временно недоступна. Попробуйте обновить страницу.";
    loading.hidden = true;
    return { search() {}, reset() {}, locate() {} };
  }

  const map = window.L.map(canvas, { zoomControl: false, attributionControl: false, scrollWheelZoom: false }).setView(RUSSIA_VIEW, RUSSIA_ZOOM);
  const tiles = window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);
  const markerLayer = createClusterLayer().addTo(map);
  const markers = new Map();
  let places = [];
  let searchQuery = "";
  let tilesFailed = false;
  let requestController;
  let searchTimer;

  window.L.control.zoom({ position: "bottomright" }).addTo(map);
  tiles.on("tileerror", () => {
    if (!tilesFailed) status.textContent = "Часть карты не загрузилась. Проверьте подключение к интернету.";
    tilesFailed = true;
  });
  tiles.on("tileload", () => {
    if (tilesFailed) status.textContent = "";
    tilesFailed = false;
  });

  function focusPlace(place) {
    const marker = markers.get(place.id);
    if (!marker) return;
    map.flyTo([place.lat, place.lng], Math.max(map.getZoom(), 10), { duration: 0.65 });
    window.setTimeout(() => marker.openPopup(), 450);
  }

  function renderResults() {
    results.replaceChildren();
    if (!searchQuery.trim()) return;
    const summary = document.createElement("p");
    summary.className = "public-map__result-summary";
    summary.textContent = places.length ? `Нашли объектов: ${places.length}` : "Ничего не нашли. Попробуйте другой запрос.";
    results.append(summary);
    places.slice(0, 4).forEach((place) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "public-map__result";
      const strong = document.createElement("strong");
      strong.textContent = place.name || "Место отдыха";
      const span = document.createElement("span");
      span.textContent = [place.place_type?.name, place.city || place.locality || place.region].filter(Boolean).join(" · ") || "Россия";
      button.append(strong, span);
      button.addEventListener("click", () => focusPlace(place));
      results.append(button);
    });
  }

  function renderMarkers(total) {
    markerLayer.clearLayers();
    markers.clear();
    places.filter((place) => isCoordinate(place.lat) && isCoordinate(place.lng)).forEach((place) => {
      const marker = window.L.marker([place.lat, place.lng], { icon: markerIcon(place), title: place.name || "Место отдыха" });
      marker.bindPopup(popupContent(place), { closeButton: true, maxWidth: 310, minWidth: 240, offset: [0, -2] });
      marker.on("click", () => { status.textContent = place.name ? `Выбрано: ${place.name}` : "Выбран объект"; });
      markers.set(place.id, marker);
      markerLayer.addLayer(marker);
    });
    renderResults();
    const mappedCount = markers.size;
    if (count) count.textContent = `${total} ${total === 1 ? "объект" : "объектов"}`;
    status.textContent = mappedCount ? `На карте показано: ${mappedCount} из ${total}` : "По выбранным фильтрам объектов на карте нет.";
  }

  function renderLegend(types, initialPlaces) {
    if (!legend) return;
    legend.replaceChildren();
    const used = new Set(initialPlaces.map((place) => place.place_type?.slug).filter(Boolean));
    types.filter((type) => used.has(type.slug)).forEach((type) => {
      const item = document.createElement("span");
      item.style.setProperty("--legend-accent", accentColor(type));
      const dot = document.createElement("i");
      const label = document.createElement("b");
      label.textContent = type.name;
      item.append(dot, label);
      legend.append(item);
    });
  }

  function filtersActive() {
    return Boolean(searchQuery.trim() || filterType?.value || filterRegion?.value || filterCity?.value || filterAmenity?.value);
  }

  async function loadPlaces({ initialiseFilters = false } = {}) {
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    loading.hidden = false;
    const query = new URLSearchParams({ limit: "100", offset: "0" });
    if (searchQuery.trim()) query.set("q", searchQuery.trim());
    if (filterType?.value) query.set("place_type", filterType.value);
    if (filterRegion?.value) query.set("region", filterRegion.value);
    if (filterCity?.value) query.set("city", filterCity.value);
    if (filterAmenity?.value) query.set("amenity", filterAmenity.value);
    try {
      const response = await fetch(`/api/public/places?${query}`, { credentials: "same-origin", signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      places = Array.isArray(payload.items) ? payload.items : [];
      const total = Number(payload.total || 0);
      if (initialiseFilters) {
        replaceOptions(filterRegion, uniqueTextValues(places, "region"), "Все регионы", (value) => value, (value) => value);
        replaceOptions(filterCity, uniqueTextValues(places, "city"), "Все города", (value) => value, (value) => value);
      }
      renderMarkers(total);
      if (filtersActive() && markers.size) {
        const bounds = window.L.latLngBounds(places.filter((place) => markers.has(place.id)).map((place) => [place.lat, place.lng]));
        if (bounds.isValid()) map.fitBounds(bounds.pad(0.25), { maxZoom: 10, animate: true });
      }
    } catch (error) {
      if (error?.name !== "AbortError") {
        places = [];
        renderMarkers(0);
        status.textContent = "Не удалось загрузить каталог. Попробуйте обновить страницу.";
      }
    } finally {
      if (!controller.signal.aborted && requestController === controller) loading.hidden = true;
    }
  }

  async function bootstrap() {
    try {
      const [typesResponse, amenitiesResponse] = await Promise.all([
        fetch("/api/public/place-types", { credentials: "same-origin" }),
        fetch("/api/public/amenities", { credentials: "same-origin" }),
      ]);
      if (!typesResponse.ok || !amenitiesResponse.ok) throw new Error("dictionary request failed");
      const [types, amenities] = await Promise.all([typesResponse.json(), amenitiesResponse.json()]);
      replaceOptions(filterType, types, "Все типы", (item) => item.slug, (item) => item.name);
      replaceOptions(filterAmenity, amenities, "Все удобства", (item) => item.slug, (item) => item.name);
      await loadPlaces({ initialiseFilters: true });
      renderLegend(types, places);
    } catch {
      status.textContent = "Не удалось загрузить справочники каталога. Попробуйте обновить страницу.";
      loading.hidden = true;
    }
  }

  function reset() {
    searchQuery = "";
    [filterType, filterRegion, filterCity, filterAmenity].forEach((select) => { if (select) select.value = ""; });
    results.replaceChildren();
    map.flyTo(RUSSIA_VIEW, RUSSIA_ZOOM, { duration: 0.65 });
    void loadPlaces();
  }

  function locate() {
    if (!navigator.geolocation) {
      status.textContent = "Геолокация не поддерживается этим браузером.";
      return;
    }
    status.textContent = "Определяем ваше местоположение…";
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const point = [coords.latitude, coords.longitude];
        window.L.circleMarker(point, { radius: 7, color: "#ffffff", weight: 3, fillColor: "#23b7c7", fillOpacity: 1 }).addTo(map);
        map.flyTo(point, 10, { duration: 0.75 });
        status.textContent = "Показали ваше местоположение.";
      },
      () => { status.textContent = "Не удалось определить местоположение. Разрешите доступ в настройках браузера."; },
      { enableHighAccuracy: false, timeout: 7000, maximumAge: 300000 },
    );
  }

  [filterType, filterRegion, filterCity, filterAmenity].forEach((select) => select?.addEventListener("change", () => void loadPlaces()));
  filterReset?.addEventListener("click", reset);
  filterToggle?.addEventListener("click", () => {
    const isOpen = !filterPanel?.hidden;
    if (filterPanel) filterPanel.hidden = isOpen;
    filterToggle.setAttribute("aria-expanded", String(!isOpen));
    filterToggle.setAttribute("aria-label", isOpen ? "Открыть фильтры каталога" : "Закрыть фильтры каталога");
  });
  if (window.matchMedia("(max-width: 520px)").matches && filterPanel) {
    filterPanel.hidden = true;
    filterToggle?.setAttribute("aria-expanded", "false");
  }

  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    resizeObserver.observe(shell);
  } else {
    window.addEventListener("resize", () => map.invalidateSize({ animate: false }), { passive: true });
  }
  map.once("load", () => onMapReady?.());
  window.requestAnimationFrame(() => map.invalidateSize({ animate: false }));
  void bootstrap();

  return {
    search(value) {
      searchQuery = value || "";
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => void loadPlaces(), 220);
    },
    reset,
    locate,
  };
}
