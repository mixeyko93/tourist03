import { catalogIconSvg } from "./catalog-icons.js?v=2026-07-27-03";

const RUSSIA_VIEW = [61, 99];
const RUSSIA_ZOOM = 3;
const OBJECT_ZOOM = 11;
const SEARCH_MAX_ZOOM = 9;
const SEARCH_DEBOUNCE_MS = 400;
const MAP_PAGE_SIZE = 200;
const MAP_MAX_RESULTS = 10000;
const MAP_REQUEST_CONCURRENCY = 4;
const HEX_COLOR = /^#[0-9a-f]{6}$/i;
const KIND_COLORS = Object.freeze({
  accommodation: "#247da8",
  service: "#7b5aa6",
  rental: "#7b5aa6",
  activity: "#d06c32",
  event: "#d06c32",
  food: "#a34f4f",
  transport: "#376c5a",
  excursion: "#81691c",
  guide: "#81691c",
  sight: "#81691c",
});

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

function asItems(payload) {
  if (Array.isArray(payload)) return payload;
  return Array.isArray(payload?.items) ? payload.items : [];
}

function entityKind(entity) {
  const candidate = entity?.entity_kind || entity?.place_type?.entity_kind || "accommodation";
  if (typeof candidate === "string") {
    return {
      key: candidate,
      slug: candidate,
      name: candidate === "accommodation" ? "Проживание" : "Туристический объект",
      icon_key: candidate,
      config: {},
    };
  }
  return candidate || {};
}

function kindKey(value) {
  if (typeof value === "string") return value;
  return String(value?.key || value?.slug || value?.entity_kind || "");
}

function subtype(entity) {
  if (entity?.subtype && typeof entity.subtype === "object") return entity.subtype;
  if (entity?.place_type && typeof entity.place_type === "object") return entity.place_type;
  if (entity?.entity_type && typeof entity.entity_type === "object") return entity.entity_type;
  return { slug: String(entity?.subtype || entity?.type || "") };
}

function entityKey(entity) {
  return entity?.entity_id ?? entity?.id;
}

function formatPrice(value) {
  const price = Number(value);
  if (!Number.isFinite(price) || price <= 0) return "";
  return `от ${new Intl.NumberFormat("ru-RU").format(price)} ₽`;
}

function priceLabel(entity) {
  const explicit = String(entity?.price_display || entity?.price_label || "").trim();
  if (explicit) return explicit;
  const mode = String(entity?.price_mode || "").trim().toLowerCase();
  if (mode && !["from", "fixed"].includes(mode)) return "";
  return formatPrice(entity?.min_price);
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

function accentColor(entityOrType) {
  const type = entityOrType?.place_type || entityOrType?.subtype ? subtype(entityOrType) : entityOrType;
  const kind = entityOrType?.entity_kind ? entityKind(entityOrType) : {};
  const candidate = String(type?.config?.accent || kind?.config?.accent || "");
  if (HEX_COLOR.test(candidate)) return candidate;
  return KIND_COLORS[kindKey(kind) || kindKey(type?.entity_kind)] || "#247da8";
}

function markerIcon(entity) {
  const type = subtype(entity);
  const kind = entityKind(entity);
  const iconKey = type.icon_key || kind.icon_key || kindKey(kind) || entity.schema_key;
  return window.L.divIcon({
    className: "public-map-marker-wrap",
    html: `<span class="public-map-marker" style="--marker-accent:${accentColor(entity)}" aria-hidden="true">${catalogIconSvg(iconKey)}</span>`,
    iconSize: [44, 44],
    iconAnchor: [22, 44],
    popupAnchor: [0, -40],
  });
}

function contactLinks(entity) {
  return (entity.primary_contacts || []).slice(0, 2).map((contact) => {
    const url = safeContactUrl(contact.url);
    if (!url) return "";
    const label = escapeHtml(contact.label || (contact.contact_type === "phone" ? "Позвонить" : "Связаться"));
    const external = /^https?:/i.test(url) ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<a class="public-map-popup__contact" href="${escapeHtml(url)}"${external}>${label}</a>`;
  }).filter(Boolean).join("");
}

function popupContent(entity) {
  const name = escapeHtml(entity.name || "Туристический объект");
  const type = escapeHtml(subtype(entity).name || entityKind(entity).name || "Туристический объект");
  const location = escapeHtml([entity.region, entity.city, entity.locality].filter(Boolean).join(", ") || "Россия");
  const description = escapeHtml(entity.short_description || "Информация появится в каталоге.");
  const price = escapeHtml(priceLabel(entity));
  const cover = safeImageUrl(entity.cover);
  const slug = encodeURIComponent(String(entity.slug || ""));
  return `
    <article class="public-map-popup" data-entity-kind="${escapeHtml(kindKey(entityKind(entity)))}">
      ${cover ? `<img src="${escapeHtml(cover)}" alt="" loading="lazy" width="310" height="110" decoding="async">` : '<div class="public-map-popup__placeholder" aria-hidden="true">Т</div>'}
      <p>${type}</p>
      <h3>${name}</h3>
      <span>${location}</span>
      <small>${description}</small>
      ${price ? `<strong>${price}</strong>` : ""}
      <div class="public-map-popup__actions">
        <a class="public-map-popup__detail" href="/places/${slug}">Подробнее</a>
        ${contactLinks(entity)}
      </div>
    </article>`;
}

function locationLabel(entity) {
  return [entity.city, entity.locality, entity.region].filter(Boolean).join(", ") || "Россия";
}

function distanceKm(from, entity) {
  if (!from || !isCoordinate(entity.lat) || !isCoordinate(entity.lng)) return null;
  const radians = (value) => value * Math.PI / 180;
  const latDelta = radians(entity.lat - from.lat);
  const lngDelta = radians(entity.lng - from.lng);
  const a = Math.sin(latDelta / 2) ** 2
    + Math.cos(radians(from.lat)) * Math.cos(radians(entity.lat)) * Math.sin(lngDelta / 2) ** 2;
  return Math.round(6371.0088 * 2 * Math.asin(Math.sqrt(a)) * 10) / 10;
}

function createClusterLayer() {
  if (typeof window.L.markerClusterGroup !== "function") return window.L.featureGroup();
  return window.L.markerClusterGroup({
    maxClusterRadius: 56,
    showCoverageOnHover: false,
    spiderfyOnMaxZoom: true,
    // Keep the first mobile frame responsive when the catalog returns a large
    // mixed set. MarkerCluster yields between chunks instead of recalculating
    // clusters for every marker in one blocking task.
    chunkedLoading: true,
    chunkInterval: 16,
    chunkDelay: 0,
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

function replaceOptions(select, items, placeholder, getValue = (item) => item.value, getLabel = (item) => item.label) {
  if (!select) return;
  const selected = select.value;
  select.replaceChildren();
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = placeholder;
  select.append(empty);
  items.forEach((item) => {
    const value = String(getValue(item) || "");
    if (!value) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = String(getLabel(item) || value);
    select.append(option);
  });
  if ([...select.options].some((option) => option.value === selected)) select.value = selected;
}

function uniqueTextValues(items, key) {
  return [...new Set(items.map((item) => String(item[key] || "").trim()).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "ru"))
    .map((value) => ({ value, label: value }));
}

function normaliseFacetOptions(values) {
  return (Array.isArray(values) ? values : []).map((item) => {
    if (typeof item === "string") return { value: item, label: item, count: 0 };
    const value = item?.value ?? item?.slug ?? item?.key ?? "";
    return {
      value: String(value),
      label: String(item?.label ?? item?.name ?? value),
      count: Number(item?.count || 0),
    };
  }).filter((item) => item.value);
}

function resultCountLabel(total) {
  const absolute = Math.abs(total) % 100;
  const remainder = absolute % 10;
  const noun = absolute > 10 && absolute < 20 ? "результатов" : remainder === 1 ? "результат" : remainder >= 2 && remainder <= 4 ? "результата" : "результатов";
  return `${total} ${noun}`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function optionalJson(url) {
  try {
    return await fetchJson(url);
  } catch {
    return null;
  }
}

export function initialisePublicMap({
  shell,
  canvas,
  loading,
  status,
  results,
  filterPanel,
  filterToggle,
  filterClose,
  filterKinds = [],
  filterSubtype,
  filterRegion,
  filterDistrict,
  filterCity,
  filterSeasonality,
  filterAmenities,
  filterAmenityOptions,
  filterLegacyAmenity,
  filterPriceMin,
  filterPriceMax,
  filterOpenNow,
  filterChildren,
  filterPets,
  filterParking,
  filterWifi,
  filterReset,
  count,
  legend,
  onMapReady,
  list,
  listItems,
  listCount,
  sheet,
  sheetContent,
  sheetToggle,
  searchArea,
  appMode = false,
  onShowList,
}) {
  if (!window.L || !canvas) {
    if (status) status.textContent = "Карта временно недоступна. Попробуйте обновить страницу.";
    if (loading) loading.hidden = true;
    return {
      search() {}, clearSearch() {}, reset() {}, locate() {}, refreshList() {}, invalidate() {}, selectById() {},
    };
  }

  const map = window.L.map(canvas, {
    zoomControl: false,
    attributionControl: false,
    scrollWheelZoom: false,
  }).setView(RUSSIA_VIEW, RUSSIA_ZOOM);
  if (window.__TOURISTIKA_TEST_HOOKS__) window.__TOURISTIKA_TEST_MAP__ = map;
  const tiles = window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap",
  }).addTo(map);
  const markerLayer = createClusterLayer().addTo(map);
  const markers = new Map();
  let entities = [];
  let entityTypes = [];
  let searchQuery = "";
  let tilesFailed = false;
  let requestController;
  let searchTimer;
  let inputTimer;
  let areaPromptTimer;
  let programmaticMoveTimer;
  const pageParams = new URLSearchParams(window.location.search);
  const requestedEntitySlug = pageParams.get("id") || pageParams.get("entity");
  let requestedEntityPending = Boolean(requestedEntitySlug);
  searchQuery = pageParams.get("search") || pageParams.get("q") || "";
  let contextSlugs = null;
  let selectedEntity = null;
  let userLocation = null;
  let boundsQuery = null;
  let areaPromptReady = false;
  let programmaticMove = false;
  let userMovedMap = false;
  let previousArea = null;
  let currentArea = { center: [...RUSSIA_VIEW], zoom: RUSSIA_ZOOM };
  let lastLoadedSearch = null;
  const deepLinkSelectValues = [
    [filterSubtype, pageParams.get("subtype")],
    [filterRegion, pageParams.get("region")],
    [filterDistrict, pageParams.get("district")],
    [filterCity, pageParams.get("city")],
    [filterSeasonality, pageParams.get("seasonality")],
  ];

  window.L.control.zoom({ position: "bottomright" }).addTo(map);
  tiles.on("tileerror", () => {
    if (!tilesFailed && status) status.textContent = "Часть карты не загрузилась. Проверьте подключение к интернету.";
    tilesFailed = true;
  });
  tiles.on("tileload", () => {
    if (tilesFailed && status) status.textContent = "";
    tilesFailed = false;
  });

  function snapshotArea() {
    const center = map.getCenter();
    return { center: [center.lat, center.lng], zoom: map.getZoom() };
  }

  function moveProgrammatically(callback) {
    programmaticMove = true;
    window.clearTimeout(programmaticMoveTimer);
    callback();
    programmaticMoveTimer = window.setTimeout(() => {
      programmaticMove = false;
      currentArea = snapshotArea();
    }, 900);
  }

  function closeSelectedEntity() {
    selectedEntity = null;
    map.closePopup();
    if (sheet) sheet.hidden = true;
    renderList();
    if (status) status.textContent = "Карточка закрыта. Карта останется в выбранной области.";
  }

  function selectedKindValues() {
    return [...new Set(filterKinds.filter((input) => input.checked).flatMap((input) => (
      String(input.dataset.kindValues || input.value || "").split(",").map((value) => value.trim()).filter(Boolean)
    )))];
  }

  function selectedAmenities() {
    const selected = [...(filterAmenityOptions?.querySelectorAll("[data-filter-amenity]:checked") || [])]
      .map((input) => input.value).filter(Boolean);
    if (filterLegacyAmenity?.value) selected.push(filterLegacyAmenity.value);
    return [...new Set(selected)];
  }

  function updateSubtypeOptions() {
    const selectedKinds = new Set(selectedKindValues());
    const available = entityTypes.filter((type) => {
      const typeKind = kindKey(type.entity_kind);
      return !selectedKinds.size || !typeKind || selectedKinds.has(typeKind);
    });
    replaceOptions(
      filterSubtype,
      available,
      "Все подтипы",
      (type) => type.slug || type.key,
      (type) => type.name,
    );
  }

  function populateAmenities(options) {
    const values = normaliseFacetOptions(options);
    replaceOptions(filterLegacyAmenity, values, "Все удобства");
    if (!filterAmenityOptions || !filterAmenities) return;
    const quick = new Set(["wifi", "parking", "children", "pets"]);
    const previous = new Set(selectedAmenities());
    filterAmenityOptions.replaceChildren();
    values.filter((item) => !quick.has(item.value)).forEach((item) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      const text = document.createElement("span");
      input.type = "checkbox";
      input.value = item.value;
      input.dataset.filterAmenity = "";
      input.checked = previous.has(item.value);
      text.textContent = item.count ? `${item.label} · ${item.count}` : item.label;
      label.append(input, text);
      filterAmenityOptions.append(label);
      input.addEventListener("change", () => void loadEntities());
    });
    filterAmenities.hidden = filterAmenityOptions.childElementCount === 0;
  }

  function populateFacets(facets, fallbackEntities = []) {
    const regionOptions = normaliseFacetOptions(facets?.regions);
    const districtOptions = normaliseFacetOptions(facets?.districts);
    const cityOptions = normaliseFacetOptions(facets?.cities);
    const seasonalityOptions = normaliseFacetOptions(facets?.seasonality || facets?.seasonalities);
    replaceOptions(filterRegion, regionOptions.length ? regionOptions : uniqueTextValues(fallbackEntities, "region"), "Все регионы");
    replaceOptions(filterDistrict, districtOptions.length ? districtOptions : uniqueTextValues(fallbackEntities, "district"), "Все районы");
    replaceOptions(filterCity, cityOptions.length ? cityOptions : uniqueTextValues(fallbackEntities, "city"), "Все города");
    replaceOptions(filterSeasonality, seasonalityOptions, "Любой сезон");
    populateAmenities(facets?.amenities || []);
  }

  function setSheetState(state) {
    if (!sheet) return;
    sheet.dataset.sheetState = state;
    if (sheetToggle) {
      sheetToggle.setAttribute("aria-label", state === "expanded" ? "Свернуть карточку" : "Развернуть карточку");
    }
  }

  async function shareEntity(entity) {
    const url = new URL(`/places/${encodeURIComponent(String(entity.slug || ""))}`, window.location.origin).href;
    try {
      if (navigator.share) await navigator.share({ title: entity.name || "Туристика", url });
      else await navigator.clipboard.writeText(url);
      if (status) status.textContent = navigator.share ? "Ссылка отправлена." : "Ссылка скопирована.";
    } catch (error) {
      if (error?.name !== "AbortError" && status) status.textContent = "Не удалось поделиться ссылкой.";
    }
  }

  function renderSheet(entity) {
    if (!sheet || !sheetContent) return;
    const cover = safeImageUrl(entity.cover);
    const slug = encodeURIComponent(String(entity.slug || ""));
    const type = subtype(entity).name || entityKind(entity).name || "Туристический объект";
    const distance = distanceKm(userLocation, entity);
    const telegram = (entity.primary_contacts || []).find((contact) => contact.contact_type === "telegram");
    const telegramUrl = telegram ? safeContactUrl(telegram.url) : null;
    const routeUrl = isCoordinate(entity.lat) && isCoordinate(entity.lng)
      ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${entity.lat},${entity.lng}`)}`
      : null;
    sheetContent.innerHTML = `
      <article class="map-sheet-card">
        <button class="map-sheet-card__close" type="button" data-sheet-close aria-label="Закрыть карточку объекта">×</button>
        ${cover ? `<img class="map-sheet-card__cover" src="${escapeHtml(cover)}" alt="" width="224" height="236" loading="lazy" decoding="async">` : '<div class="map-sheet-card__placeholder" aria-hidden="true">Т</div>'}
        <div class="map-sheet-card__body">
          <small>${escapeHtml(type)}${distance !== null ? ` · ${distance} км` : ""}</small>
          <h2 id="map-sheet-title">${escapeHtml(entity.name || "Туристический объект")}</h2>
          <p>${escapeHtml(locationLabel(entity))}</p>
          <p>${escapeHtml(entity.short_description || "Откройте карточку, чтобы узнать подробности.")}</p>
        </div>
        <div class="map-sheet-card__actions">
          <a href="/places/${slug}">Подробнее</a>
          ${routeUrl ? `<a href="${routeUrl}" target="_blank" rel="noopener noreferrer">Маршрут</a>` : ""}
          ${telegramUrl ? `<a href="${escapeHtml(telegramUrl)}" target="_blank" rel="noopener noreferrer">Telegram</a>` : ""}
          <button type="button" data-sheet-share>Поделиться</button>
          <button type="button" data-sheet-list>Показать в списке</button>
        </div>
      </article>`;
    sheetContent.querySelector("[data-sheet-share]")?.addEventListener("click", () => void shareEntity(entity));
    sheetContent.querySelector("[data-sheet-list]")?.addEventListener("click", () => onShowList?.(entity));
    sheetContent.querySelector("[data-sheet-close]")?.addEventListener("click", closeSelectedEntity);
    sheet.hidden = false;
    setSheetState("medium");
  }

  function selectEntity(entity, { move = true } = {}) {
    selectedEntity = entity;
    userMovedMap = false;
    const tip = document.querySelector("[data-map-tip]");
    if (tip) tip.hidden = true;
    if (move) moveProgrammatically(() => map.flyTo([entity.lat, entity.lng], OBJECT_ZOOM, { duration: 0.65 }));
    if (appMode) renderSheet(entity);
    else window.setTimeout(() => markers.get(entityKey(entity))?.openPopup(), move ? 450 : 0);
    renderList();
    if (status) status.textContent = entity.name ? `Выбрано: ${entity.name}` : "Выбран объект";
  }

  function focusEntity(entity) {
    const marker = markers.get(entityKey(entity));
    if (!marker) return;
    selectEntity(entity);
  }

  function entitiesInView() {
    const bounds = map.getBounds();
    return entities.filter((entity) => (
      isCoordinate(entity.lat) && isCoordinate(entity.lng) && bounds.contains([entity.lat, entity.lng])
    ));
  }

  function renderList() {
    if (!listItems) return;
    const visible = entitiesInView();
    listItems.replaceChildren();
    if (listCount) listCount.textContent = resultCountLabel(visible.length);
    if (!visible.length) {
      const empty = document.createElement("p");
      empty.className = "map-list-empty";
      empty.textContent = "В этой области пока ничего нет. Переместите карту или измените фильтры.";
      listItems.append(empty);
      return;
    }
    visible.forEach((entity) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "map-list-card";
      button.dataset.entityId = String(entityKey(entity));
      button.setAttribute("aria-current", String(entityKey(selectedEntity) === entityKey(entity)));
      const cover = safeImageUrl(entity.cover);
      if (cover) {
        const image = document.createElement("img");
        image.src = cover;
        image.alt = "";
        image.width = 184;
        image.height = 176;
        image.loading = "lazy";
        image.decoding = "async";
        button.append(image);
      } else {
        const placeholder = document.createElement("span");
        placeholder.className = "map-list-card__placeholder";
        placeholder.setAttribute("aria-hidden", "true");
        placeholder.textContent = "Т";
        button.append(placeholder);
      }
      const copy = document.createElement("span");
      const type = document.createElement("small");
      type.textContent = subtype(entity).name || entityKind(entity).name || "Туристический объект";
      const name = document.createElement("strong");
      name.textContent = entity.name || "Туристический объект";
      const place = document.createElement("em");
      place.textContent = locationLabel(entity);
      copy.append(type, name, place);
      button.append(copy);
      button.addEventListener("click", () => selectEntity(entity));
      listItems.append(button);
    });
  }

  function renderResults() {
    if (!results) return;
    results.replaceChildren();
    if (!searchQuery.trim()) return;
    const summary = document.createElement("p");
    summary.className = "public-map__result-summary";
    summary.textContent = entities.length ? `Найдено: ${entities.length}` : "Ничего не нашли. Попробуйте другой запрос.";
    results.append(summary);
    entities.slice(0, 4).forEach((entity) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "public-map__result";
      const strong = document.createElement("strong");
      strong.textContent = entity.name || "Туристический объект";
      const description = document.createElement("span");
      description.textContent = [
        subtype(entity).name || entityKind(entity).name,
        entity.city || entity.locality || entity.region,
      ].filter(Boolean).join(" · ") || "Россия";
      button.append(strong, description);
      button.addEventListener("click", () => focusEntity(entity));
      results.append(button);
    });
  }

  function renderLegend() {
    if (!legend) return;
    legend.replaceChildren();
    const visibleTypes = new Map();
    entities.forEach((entity) => {
      const type = subtype(entity);
      const kind = entityKind(entity);
      const key = String(type.slug || type.key || kindKey(kind) || "");
      if (!key || visibleTypes.has(key)) return;
      visibleTypes.set(key, {
        ...type,
        name: type.name || kind.name || "Туристический объект",
        icon_key: type.icon_key || kind.icon_key || kindKey(kind),
        entity_kind: kind,
      });
    });
    [...visibleTypes.values()].sort((left, right) => (
      Number(left.sort_order || 0) - Number(right.sort_order || 0)
      || String(left.name).localeCompare(String(right.name), "ru")
    )).forEach((type) => {
      const item = document.createElement("span");
      item.style.setProperty("--legend-accent", accentColor(type));
      const icon = document.createElement("i");
      icon.setAttribute("aria-hidden", "true");
      icon.innerHTML = catalogIconSvg(type.icon_key);
      const label = document.createElement("b");
      label.textContent = type.name;
      item.append(icon, label);
      legend.append(item);
    });
    legend.hidden = visibleTypes.size === 0;
  }

function decorateMarker(marker, entity, onActivate) {
    const element = marker.getElement?.();
    if (!element || element.dataset.catalogKeyboardReady) return;
    element.dataset.catalogKeyboardReady = "true";
    element.setAttribute("role", "button");
    element.setAttribute("aria-label", `Открыть карточку «${entity.name || "Туристический объект"}» на карте`);
    element.addEventListener("keydown", (event) => {
      if (event.key !== " " && event.key !== "Enter") return;
      event.preventDefault();
      if (onActivate) onActivate();
      else marker.openPopup();
    });
  }

  function renderMarkers(total) {
    markerLayer.clearLayers();
    markers.clear();
    const layers = [];
    entities.filter((entity) => isCoordinate(entity.lat) && isCoordinate(entity.lng)).forEach((entity) => {
      const marker = window.L.marker([entity.lat, entity.lng], {
        icon: markerIcon(entity),
        title: entity.name || "Туристический объект",
        alt: entity.name || "Туристический объект",
        keyboard: true,
      });
      const compactPopup = window.matchMedia("(max-width: 360px)").matches;
      if (!appMode) {
        marker.bindPopup(popupContent(entity), {
          closeButton: true,
          maxWidth: compactPopup ? 252 : 310,
          minWidth: compactPopup ? 210 : 240,
          offset: [0, -2],
          autoPanPaddingTopLeft: [12, 82],
          autoPanPaddingBottomRight: [12, 12],
        });
      }
      marker.on("add", () => decorateMarker(marker, entity, appMode ? () => selectEntity(entity, { move: false }) : null));
      marker.on("click", () => {
        selectEntity(entity, { move: false });
      });
      markers.set(entityKey(entity), marker);
      layers.push(marker);
    });
    if (layers.length) markerLayer.addLayers(layers);
    renderResults();
    renderLegend();
    renderList();
    const mappedCount = markers.size;
    if (count) count.textContent = resultCountLabel(total);
    if (status) status.textContent = mappedCount
      ? `На карте показано: ${mappedCount} из ${total}`
      : "По выбранным фильтрам объектов на карте нет.";
  }

  function queryParameters() {
    const query = new URLSearchParams({ map_only: "true" });
    if (searchQuery.trim()) query.set("q", searchQuery.trim());
    const kinds = selectedKindValues();
    if (kinds.length) query.set("entity_kind", kinds.join(","));
    if (filterSubtype?.value) query.set("subtype", filterSubtype.value);
    if (filterRegion?.value) query.set("region", filterRegion.value);
    if (filterDistrict?.value) query.set("district", filterDistrict.value);
    if (filterCity?.value) query.set("city", filterCity.value);
    if (filterSeasonality?.value) query.set("seasonality", filterSeasonality.value);
    const amenities = selectedAmenities();
    if (amenities.length) query.set("amenity", amenities.join(","));
    if (filterOpenNow?.checked) query.set("open_now", "true");
    if (filterChildren?.checked) query.set("children", "true");
    if (filterPets?.checked) query.set("pets", "true");
    if (filterParking?.checked) query.set("parking", "true");
    if (filterWifi?.checked) query.set("wifi", "true");
    if (filterPriceMin?.value) query.set("price_min", filterPriceMin.value);
    if (filterPriceMax?.value) query.set("price_max", filterPriceMax.value);
    if (boundsQuery) query.set("bbox", boundsQuery);
    return query;
  }

  async function fetchEntities(query, signal) {
    try {
      return await fetchJson(`/api/public/entities?${query}`, { signal });
    } catch (error) {
      if (error?.name === "AbortError") throw error;
      if (![404, 405].includes(error?.status)) throw error;
      const legacy = new URLSearchParams();
      ["limit", "offset", "q", "region", "city", "amenity"].forEach((name) => {
        if (query.has(name)) legacy.set(name, query.get(name));
      });
      if (query.has("subtype")) legacy.set("place_type", query.get("subtype"));
      return fetchJson(`/api/public/places?${legacy}`, { signal });
    }
  }

  async function fetchAllEntities(query, signal) {
    const firstQuery = new URLSearchParams(query);
    firstQuery.set("limit", String(MAP_PAGE_SIZE));
    firstQuery.set("offset", "0");
    const firstPayload = await fetchEntities(firstQuery, signal);
    const firstItems = asItems(firstPayload);
    const total = Math.max(0, Number(firstPayload?.total ?? firstItems.length));
    const target = Math.min(total, MAP_MAX_RESULTS);
    const offsets = [];
    for (let offset = MAP_PAGE_SIZE; offset < target; offset += MAP_PAGE_SIZE) {
      offsets.push(offset);
    }
    const pages = [firstItems];
    for (let index = 0; index < offsets.length; index += MAP_REQUEST_CONCURRENCY) {
      const batch = offsets.slice(index, index + MAP_REQUEST_CONCURRENCY);
      const payloads = await Promise.all(batch.map((offset) => {
        const pageQuery = new URLSearchParams(query);
        pageQuery.set("limit", String(MAP_PAGE_SIZE));
        pageQuery.set("offset", String(offset));
        return fetchEntities(pageQuery, signal);
      }));
      payloads.forEach((payload) => pages.push(asItems(payload)));
    }
    return {
      items: pages.flat().slice(0, target),
      total,
      truncated: total > target,
    };
  }

  function fitSearchResults() {
    const points = entities
      .filter((entity) => markers.has(entityKey(entity)))
      .map((entity) => [entity.lat, entity.lng]);
    if (!points.length) return;
    const compact = window.matchMedia("(max-width: 720px)").matches;
    if (points.length === 1) {
      moveProgrammatically(() => map.flyTo(points[0], SEARCH_MAX_ZOOM, { duration: 0.55 }));
      return;
    }
    const bounds = window.L.latLngBounds(points);
    if (!bounds.isValid()) return;
    moveProgrammatically(() => map.fitBounds(bounds.pad(0.18), {
      maxZoom: SEARCH_MAX_ZOOM,
      animate: true,
      paddingTopLeft: compact ? [24, 88] : [54, 74],
      paddingBottomRight: compact ? [24, 190] : [54, 74],
    }));
  }

  async function loadEntities({ initialiseFilters = false, facets = null, fitResults = false } = {}) {
    const minimumPrice = Number(filterPriceMin?.value);
    const maximumPrice = Number(filterPriceMax?.value);
    if (
      filterPriceMin?.value
      && filterPriceMax?.value
      && Number.isFinite(minimumPrice)
      && Number.isFinite(maximumPrice)
      && minimumPrice > maximumPrice
    ) {
      if (loading) loading.hidden = true;
      if (status) status.textContent = "Минимальная цена не может быть больше максимальной.";
      return;
    }
    requestController?.abort();
    const controller = new AbortController();
    requestController = controller;
    if (loading) loading.hidden = false;
    try {
      const payload = await fetchAllEntities(queryParameters(), controller.signal);
      entities = asItems(payload);
      if (contextSlugs?.size) entities = entities.filter((entity) => contextSlugs.has(String(entity.slug || "")));
      const total = contextSlugs?.size ? entities.length : Number(payload?.total ?? entities.length);
      if (initialiseFilters) {
        populateFacets(facets, entities);
        deepLinkSelectValues.forEach(([select, value]) => {
          if (select && value && [...select.options].some((option) => option.value === value)) select.value = value;
        });
      }
      renderMarkers(total);
      lastLoadedSearch = searchQuery.trim();
      if (payload.truncated && status) {
        status.textContent = `Показаны первые ${entities.length} из ${total}. Уточните фильтры, чтобы увидеть остальные.`;
      }
      if (fitResults && markers.size && !userMovedMap) fitSearchResults();
      if (requestedEntityPending && requestedEntitySlug) {
        const requested = entities.find((entity) => (
          String(entity.slug || "") === requestedEntitySlug
          || String(entityKey(entity)) === requestedEntitySlug
        ));
        requestedEntityPending = false;
        if (requested) focusEntity(requested);
      }
    } catch (error) {
      if (error?.name !== "AbortError") {
        entities = [];
        renderMarkers(0);
        if (status) status.textContent = "Не удалось загрузить каталог. Попробуйте обновить страницу.";
      }
    } finally {
      if (!controller.signal.aborted && requestController === controller && loading) loading.hidden = true;
    }
  }

  async function bootstrap() {
    const collectionSlug = pageParams.get("collection");
    const routeSlug = pageParams.get("route");
    const contextPromise = collectionSlug
      ? optionalJson(`/api/public/collections/${encodeURIComponent(collectionSlug)}`)
      : routeSlug
        ? optionalJson(`/api/public/routes/${encodeURIComponent(routeSlug)}`)
        : Promise.resolve(null);
    const [kindsPayload, typesPayload, facetsPayload, amenitiesPayload, contextPayload] = await Promise.all([
      optionalJson("/api/public/entity-kinds"),
      optionalJson("/api/public/entity-types"),
      optionalJson("/api/public/catalog-facets"),
      optionalJson("/api/public/amenities"),
      contextPromise,
    ]);
    if (contextPayload) {
      const slugs = collectionSlug
        ? (contextPayload.items || []).filter((item) => item.source === "entity").map((item) => item.slug)
        : (contextPayload.points || []).map((point) => point.entity_slug);
      contextSlugs = new Set(slugs.filter(Boolean).map(String));
    }
    const kinds = asItems(kindsPayload);
    entityTypes = asItems(typesPayload);
    if (!entityTypes.length) entityTypes = asItems(await optionalJson("/api/public/place-types"));
    const facetAmenities = Array.isArray(facetsPayload?.amenities) ? facetsPayload.amenities : [];
    const facets = {
      ...(facetsPayload || {}),
      amenities: facetAmenities.length ? facetAmenities : asItems(amenitiesPayload),
    };
    if (kinds.length) {
      const availableKinds = new Set(kinds.map((kind) => kindKey(kind)));
      filterKinds.forEach((input) => {
        const aliases = String(input.dataset.kindValues || input.value || "").split(",");
        const unavailable = !aliases.some((alias) => availableKinds.has(alias));
        input.disabled = unavailable;
        if (unavailable) input.checked = false;
        input.closest("label")?.classList.toggle("is-unavailable", unavailable);
      });
    }
    const deepKinds = new Set((pageParams.get("entity_kind") || pageParams.get("type") || "").split(",").filter(Boolean));
    filterKinds.forEach((input) => {
      const aliases = String(input.dataset.kindValues || input.value || "").split(",");
      if (aliases.some((alias) => deepKinds.has(alias))) input.checked = true;
    });
    updateSubtypeOptions();
    await loadEntities({
      initialiseFilters: true,
      facets,
      fitResults: Boolean(searchQuery.trim()) && !requestedEntitySlug,
    });
    if (deepLinkSelectValues.some(([, value]) => value)) await loadEntities({ fitResults: true });
    areaPromptReady = true;
  }

  function setFiltersOpen(open, { restoreFocus = true } = {}) {
    if (!filterPanel || !filterToggle) return;
    filterPanel.hidden = !open;
    filterToggle.setAttribute("aria-expanded", String(open));
    filterToggle.setAttribute("aria-label", open ? "Закрыть фильтры каталога" : "Открыть фильтры каталога");
    if (open) {
      window.setTimeout(() => filterPanel.querySelector("input:not([tabindex='-1']), select, button")?.focus(), 0);
    } else if (restoreFocus) {
      filterToggle.focus();
    }
  }

  function clearSearch({ resetFilters = false, restoreDefault = false } = {}) {
    window.clearTimeout(searchTimer);
    searchTimer = 0;
    searchQuery = "";
    lastLoadedSearch = null;
    boundsQuery = null;
    if (searchArea) searchArea.hidden = true;
    selectedEntity = null;
    map.closePopup();
    if (sheet) sheet.hidden = true;
    results?.replaceChildren();
    if (resetFilters) {
      [filterSubtype, filterRegion, filterDistrict, filterCity, filterSeasonality, filterLegacyAmenity].forEach((select) => {
        if (select) select.value = "";
      });
      [filterPriceMin, filterPriceMax].forEach((input) => {
        if (input) input.value = "";
      });
      [
        ...filterKinds,
        filterOpenNow,
        filterChildren,
        filterPets,
        filterParking,
        filterWifi,
        ...(filterAmenityOptions?.querySelectorAll("input[type='checkbox']") || []),
      ].filter(Boolean).forEach((input) => { input.checked = false; });
      updateSubtypeOptions();
    }
    const target = restoreDefault ? { center: RUSSIA_VIEW, zoom: RUSSIA_ZOOM } : (previousArea || { center: RUSSIA_VIEW, zoom: RUSSIA_ZOOM });
    previousArea = null;
    userMovedMap = false;
    moveProgrammatically(() => map.flyTo(target.center, target.zoom, { duration: 0.55 }));
    void loadEntities();
  }

  function reset() {
    clearSearch({ resetFilters: true, restoreDefault: true });
  }

  function locate() {
    if (!navigator.geolocation) {
      if (status) status.textContent = "Геолокация не поддерживается этим браузером.";
      return;
    }
    if (status) status.textContent = "Определяем ваше местоположение…";
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const point = [coords.latitude, coords.longitude];
        userLocation = { lat: coords.latitude, lng: coords.longitude };
        window.L.circleMarker(point, {
          radius: 7,
          color: "#ffffff",
          weight: 3,
          fillColor: "#23b7c7",
          fillOpacity: 1,
        }).addTo(map);
        moveProgrammatically(() => map.flyTo(point, 10, { duration: 0.75 }));
        if (status) status.textContent = "Показали ваше местоположение. Нажмите «Искать рядом».";
        if (searchArea) {
          searchArea.textContent = "Искать рядом";
          searchArea.hidden = false;
        }
      },
      () => {
        if (status) status.textContent = "Не удалось определить местоположение. Разрешите доступ в настройках браузера.";
      },
      { enableHighAccuracy: false, timeout: 7000, maximumAge: 300000 },
    );
  }

  filterKinds.forEach((input) => input.addEventListener("change", () => {
    updateSubtypeOptions();
    void loadEntities();
  }));
  [filterSubtype, filterRegion, filterDistrict, filterCity, filterSeasonality, filterLegacyAmenity].forEach((select) => {
    select?.addEventListener("change", () => void loadEntities());
  });
  [filterOpenNow, filterChildren, filterPets, filterParking, filterWifi].forEach((input) => {
    input?.addEventListener("change", () => void loadEntities());
  });
  [filterPriceMin, filterPriceMax].forEach((input) => {
    input?.addEventListener("input", () => {
      window.clearTimeout(inputTimer);
      inputTimer = window.setTimeout(() => void loadEntities(), 300);
    });
  });
  filterReset?.addEventListener("click", reset);
  filterToggle?.addEventListener("click", () => setFiltersOpen(Boolean(filterPanel?.hidden)));
  filterClose?.addEventListener("click", () => setFiltersOpen(false));
  searchArea?.addEventListener("click", () => {
    const bounds = map.getBounds();
    boundsQuery = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()]
      .map((value) => Number(value.toFixed(5))).join(",");
    searchArea.hidden = true;
    searchArea.textContent = "Искать в этой области";
    void loadEntities();
  });
  sheetToggle?.addEventListener("click", () => {
    const current = sheet?.dataset.sheetState || "collapsed";
    setSheetState(current === "collapsed" ? "medium" : current === "medium" ? "expanded" : "collapsed");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && filterPanel && !filterPanel.hidden) setFiltersOpen(false);
  });
  if (window.matchMedia("(max-width: 520px)").matches && filterPanel) {
    setFiltersOpen(false, { restoreFocus: false });
  } else if (filterPanel && filterToggle) {
    filterToggle.setAttribute("aria-expanded", String(!filterPanel.hidden));
  }

  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    resizeObserver.observe(shell);
  } else {
    window.addEventListener("resize", () => map.invalidateSize({ animate: false }), { passive: true });
  }
  map.on("moveend", () => {
    currentArea = snapshotArea();
    renderList();
    if (programmaticMove) window.requestAnimationFrame(() => { programmaticMove = false; });
  });
  map.on("dragend zoomend", () => {
    if (programmaticMove || !areaPromptReady || !searchArea) return;
    userMovedMap = true;
    currentArea = snapshotArea();
    window.clearTimeout(areaPromptTimer);
    areaPromptTimer = window.setTimeout(() => {
      searchArea.textContent = "Искать в этой области";
      searchArea.hidden = false;
    }, 350);
  });
  map.once("load", () => onMapReady?.());
  window.requestAnimationFrame(() => map.invalidateSize({ animate: false }));
  void bootstrap();

  return {
    search(value, { immediate = false } = {}) {
      const next = String(value || "").trim();
      const previous = searchQuery.trim();
      window.clearTimeout(searchTimer);
      searchTimer = 0;
      searchQuery = value || "";
      if (!next) {
        clearSearch();
        return;
      }
      if (next.length < 2) {
        requestController?.abort();
        results?.replaceChildren();
        if (status) status.textContent = "Введите минимум два символа.";
        return;
      }
      if (!previous || previous.length < 2) previousArea = currentArea;
      boundsQuery = null;
      userMovedMap = false;
      if (next === lastLoadedSearch) return;
      searchTimer = window.setTimeout(() => {
        searchTimer = 0;
        void loadEntities({ fitResults: true });
      }, immediate ? 0 : SEARCH_DEBOUNCE_MS);
    },
    clearSearch,
    reset,
    locate,
    refreshList: renderList,
    invalidate() {
      map.invalidateSize({ animate: false });
    },
    selectById(value) {
      const entity = entities.find((item) => String(entityKey(item)) === String(value) || String(item.slug || "") === String(value));
      if (entity) selectEntity(entity);
    },
  };
}
