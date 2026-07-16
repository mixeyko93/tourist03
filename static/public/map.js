const RUSSIA_VIEW = [61, 99];
const RUSSIA_ZOOM = 3;

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

function safeUrl(value) {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function markerIcon(camp) {
  const label = escapeHtml((camp.name || "Место отдыха").slice(0, 32));
  return window.L.divIcon({
    className: "public-map-marker-wrap",
    html: `<span class="public-map-marker" aria-hidden="true"><i></i><b>${label}</b></span>`,
    iconSize: [42, 42],
    iconAnchor: [21, 42],
    popupAnchor: [0, -38],
  });
}

function popupContent(camp) {
  const name = escapeHtml(camp.name || "Место отдыха");
  const location = escapeHtml(camp.address || camp.lake_name || "Россия");
  const type = escapeHtml(camp.housing_type || "Место отдыха");
  const price = formatPrice(camp.min_price);
  const site = safeUrl(camp.site_url);
  const phone = String(camp.phone || "").trim();
  const contact = site
    ? `<a href="${escapeHtml(site)}" target="_blank" rel="noopener noreferrer">Перейти на сайт <span aria-hidden="true">↗</span></a>`
    : phone
      ? `<a href="tel:${escapeHtml(phone.replace(/[^+\d]/g, ""))}">Позвонить</a>`
      : "";

  return `
    <article class="public-map-popup">
      <p>${type}</p>
      <h3>${name}</h3>
      <span>${location}</span>
      ${price ? `<strong>${price}</strong>` : ""}
      ${contact}
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

export function initialisePublicMap({ shell, canvas, loading, status, results, onMapReady }) {
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
  let camps = [];
  let searchQuery = "";
  let tilesFailed = false;

  window.L.control.zoom({ position: "bottomright" }).addTo(map);
  tiles.on("tileerror", () => {
    if (!tilesFailed) status.textContent = "Часть карты не загрузилась. Проверьте подключение к интернету.";
    tilesFailed = true;
  });
  tiles.on("tileload", () => {
    if (tilesFailed) status.textContent = "";
    tilesFailed = false;
  });

  function eligibleCamp(camp) {
    if (!isCoordinate(camp.lat) || !isCoordinate(camp.lng)) return false;
    const term = searchQuery.trim().toLocaleLowerCase("ru");
    if (!term) return true;
    return [camp.name, camp.address, camp.lake_name, camp.housing_type]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase("ru")
      .includes(term);
  }

  function focusCamp(camp) {
    const marker = markers.get(camp.id);
    if (!marker) return;
    map.flyTo([camp.lat, camp.lng], Math.max(map.getZoom(), 10), { duration: 0.65 });
    window.setTimeout(() => marker.openPopup(), 450);
  }

  function renderResults(visibleCamps) {
    results.replaceChildren();
    if (!searchQuery.trim()) return;
    const resultSummary = document.createElement("p");
    resultSummary.className = "public-map__result-summary";
    resultSummary.textContent = visibleCamps.length ? `Нашли мест: ${visibleCamps.length}` : "Ничего не нашли. Попробуйте другой запрос.";
    results.append(resultSummary);

    visibleCamps.slice(0, 4).forEach((camp) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "public-map__result";
      button.innerHTML = `<strong>${escapeHtml(camp.name || "Место отдыха")}</strong><span>${escapeHtml(camp.address || camp.lake_name || "Россия")}</span>`;
      button.addEventListener("click", () => focusCamp(camp));
      results.append(button);
    });
  }

  function renderMarkers() {
    markerLayer.clearLayers();
    markers.clear();
    const visibleCamps = camps.filter(eligibleCamp);
    visibleCamps.forEach((camp) => {
      const marker = window.L.marker([camp.lat, camp.lng], { icon: markerIcon(camp), title: camp.name || "Место отдыха" });
      marker.bindPopup(popupContent(camp), { closeButton: true, maxWidth: 280, minWidth: 210, offset: [0, -2] });
      marker.on("click", () => {
        status.textContent = camp.name ? `Выбрано: ${camp.name}` : "Выбрано место отдыха";
      });
      markers.set(camp.id, marker);
      markerLayer.addLayer(marker);
    });
    renderResults(visibleCamps);
    if (searchQuery.trim()) status.textContent = visibleCamps.length ? `На карте найдено мест: ${visibleCamps.length}` : "По вашему запросу мест не найдено.";
  }

  async function loadCamps() {
    try {
      const response = await fetch("/api/camps", { credentials: "same-origin" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      camps = Array.isArray(payload) ? payload : [];
      renderMarkers();
      const mappedCount = camps.filter((camp) => isCoordinate(camp.lat) && isCoordinate(camp.lng)).length;
      status.textContent = mappedCount ? `На карте доступно мест: ${mappedCount}` : "Каталог пока наполняется — скоро здесь появятся новые места.";
    } catch {
      status.textContent = "Не удалось загрузить каталог. Попробуйте обновить страницу.";
    } finally {
      loading.hidden = true;
    }
  }

  function reset() {
    searchQuery = "";
    renderMarkers();
    map.flyTo(RUSSIA_VIEW, RUSSIA_ZOOM, { duration: 0.65 });
    status.textContent = camps.length ? `На карте доступно мест: ${camps.filter((camp) => isCoordinate(camp.lat) && isCoordinate(camp.lng)).length}` : "";
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
      () => {
        status.textContent = "Не удалось определить местоположение. Разрешите доступ в настройках браузера.";
      },
      { enableHighAccuracy: false, timeout: 7000, maximumAge: 300000 },
    );
  }

  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    resizeObserver.observe(shell);
  } else {
    window.addEventListener("resize", () => map.invalidateSize({ animate: false }), { passive: true });
  }
  map.once("load", () => onMapReady?.());
  window.requestAnimationFrame(() => map.invalidateSize({ animate: false }));
  void loadCamps();

  return {
    search(value) {
      searchQuery = value || "";
      renderMarkers();
    },
    reset,
    locate,
  };
}
