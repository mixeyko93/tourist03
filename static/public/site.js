import { publicFeatures } from "./feature-flags.js";

const features = publicFeatures();
if (features.telegram_webapp) {
  import("./telegram.js").then(({ initialiseTelegramWebApp }) => {
    initialiseTelegramWebApp(features);
  }).catch(() => {});
}
document.querySelectorAll("[data-placement-submissions]").forEach((node) => {
  node.hidden = !features.placement_submissions;
});
document.querySelectorAll("[data-placement-unavailable]").forEach((node) => {
  node.hidden = features.placement_submissions;
});
document.querySelectorAll("[data-feature-link]").forEach((node) => {
  node.hidden = !features[node.dataset.featureLink];
});
document.querySelectorAll("[data-telegram-unavailable]").forEach((node) => {
  node.hidden = features.telegram_contact;
});

const menuToggle = document.querySelector("[data-menu-toggle]");
const menu = document.querySelector("[data-menu]");
const searchInput = document.querySelector("[data-map-search]");
const searchClear = document.querySelector("[data-search-clear]");
const mapShell = document.querySelector("[data-map-shell]");
const mapCanvas = document.querySelector("#map");
const mapLoading = document.querySelector("[data-map-loading]");
const mapStatus = document.querySelector("[data-map-status]");
const mapResults = document.querySelector("[data-map-results]");
const mapFilterPanel = document.querySelector("[data-map-filters]");
const mapFilterToggle = document.querySelector("[data-map-filter-toggle]");
const mapFilterClose = document.querySelector("[data-map-filter-close]");
const mapFilterKinds = [...document.querySelectorAll("[data-filter-kind]")];
const mapFilterSubtype = document.querySelector("[data-filter-subtype]");
const mapFilterRegion = document.querySelector("[data-filter-region]");
const mapFilterDistrict = document.querySelector("[data-filter-district]");
const mapFilterCity = document.querySelector("[data-filter-city]");
const mapFilterSeasonality = document.querySelector("[data-filter-seasonality]");
const mapFilterAmenities = document.querySelector("[data-filter-amenities]");
const mapFilterAmenityOptions = document.querySelector("[data-filter-amenity-options]");
const mapFilterLegacyAmenity = document.querySelector("[data-filter-amenity]");
const mapFilterPriceMin = document.querySelector("[data-filter-price-min]");
const mapFilterPriceMax = document.querySelector("[data-filter-price-max]");
const mapFilterOpenNow = document.querySelector("[data-filter-open-now]");
const mapFilterChildren = document.querySelector("[data-filter-children]");
const mapFilterPets = document.querySelector("[data-filter-pets]");
const mapFilterParking = document.querySelector("[data-filter-parking]");
const mapFilterWifi = document.querySelector("[data-filter-wifi]");
const mapFilterReset = document.querySelector("[data-filter-reset]");
const mapCount = document.querySelector("[data-map-count]");
const mapLegend = document.querySelector("[data-map-legend]");
const mapAutocomplete = document.querySelector("[data-map-autocomplete]");
const discoveryHome = document.querySelector("[data-discovery-home]");
const discoveryPreview = document.querySelector("[data-discovery-preview]");
const belowFold = document.querySelector("#about");
const mobileHome = window.matchMedia("(max-width: 520px)");
let mapController;
let mapPromise;
let autocompleteAttached = false;
const pendingMapController = Object.freeze({ search() {}, clearSearch() {}, reset() {}, locate() {} });

function installPlacementDialog() {
  const dialog = document.querySelector("[data-placement-dialog]");
  if (!dialog) return;
  const status = dialog.querySelector("[data-placement-status]");
  let restoreFocus = null;
  const open = (trigger) => {
    restoreFocus = trigger || document.activeElement;
    setMenuState(false);
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    document.body.classList.add("placement-dialog-open");
    window.setTimeout(() => dialog.querySelector("[data-placement-close]")?.focus(), 0);
  };
  const close = () => {
    if (typeof dialog.close === "function" && dialog.open) dialog.close();
    else dialog.removeAttribute("open");
  };
  document.querySelectorAll("[data-placement-open]").forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      open(trigger);
    });
  });
  dialog.querySelector("[data-placement-close]")?.addEventListener("click", close);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) close();
  });
  dialog.addEventListener("close", () => {
    document.body.classList.remove("placement-dialog-open");
    restoreFocus?.focus?.();
  });
  dialog.addEventListener("cancel", () => {
    document.body.classList.remove("placement-dialog-open");
  });
  dialog.querySelectorAll("[data-placement-message]").forEach((link) => {
    link.addEventListener("click", () => {
      const message = link.dataset.placementMessage || "";
      if (!message || !navigator.clipboard?.writeText) return;
      void navigator.clipboard.writeText(message).then(() => {
        if (status) status.textContent = "Текст обращения скопирован — вставьте его в чат Telegram.";
      }).catch(() => {});
    });
  });
}

function loadStylesheet(href) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.append(link);
}

function loadScript(src) {
  const existing = document.querySelector(`script[src="${src}"]`);
  if (existing?.dataset.loaded === "true") return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = existing || document.createElement("script");
    script.addEventListener("load", () => { script.dataset.loaded = "true"; resolve(); }, { once: true });
    script.addEventListener("error", reject, { once: true });
    if (!existing) {
      script.src = src;
      script.defer = true;
      document.head.append(script);
    }
  });
}

function setMenuState(isOpen) {
  if (!menuToggle || !menu) return;
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  menuToggle.setAttribute("aria-label", isOpen ? "Закрыть меню" : "Открыть меню");
  menu.hidden = !isOpen;
  document.body.classList.toggle("menu-is-open", isOpen);
  if (isOpen) menu.querySelector("a")?.focus();
}

async function loadMapController() {
  if (mapController) return mapController;
  if (mobileHome.matches) return pendingMapController;
  if (mapPromise) return mapPromise;
  mapPromise = (async () => {
    loadStylesheet("/static/vendor/leaflet/leaflet.css");
    loadStylesheet("/static/vendor/leaflet-markercluster/MarkerCluster.css");
    await loadScript("/static/vendor/leaflet/leaflet.js");
    await loadScript("/static/vendor/leaflet-markercluster/leaflet.markercluster.js");
    const { initialisePublicMap } = await import("./map.js?v=2026-08-03-02");
    mapController = initialisePublicMap({
    shell: mapShell,
    canvas: mapCanvas,
    loading: mapLoading,
    status: mapStatus,
    results: mapResults,
    filterPanel: mapFilterPanel,
    filterToggle: mapFilterToggle,
    filterClose: mapFilterClose,
    filterKinds: mapFilterKinds,
    filterSubtype: mapFilterSubtype,
    filterRegion: mapFilterRegion,
    filterDistrict: mapFilterDistrict,
    filterCity: mapFilterCity,
    filterSeasonality: mapFilterSeasonality,
    filterAmenities: mapFilterAmenities,
    filterAmenityOptions: mapFilterAmenityOptions,
    filterLegacyAmenity: mapFilterLegacyAmenity,
    filterPriceMin: mapFilterPriceMin,
    filterPriceMax: mapFilterPriceMax,
    filterOpenNow: mapFilterOpenNow,
    filterChildren: mapFilterChildren,
    filterPets: mapFilterPets,
    filterParking: mapFilterParking,
    filterWifi: mapFilterWifi,
    filterReset: mapFilterReset,
    count: mapCount,
    legend: mapLegend,
    });
    return mapController;
  })().catch(() => {
    if (mapLoading) mapLoading.hidden = true;
    if (mapStatus) mapStatus.textContent = "Карта временно недоступна. Откройте отдельный режим карты.";
    return pendingMapController;
  });
  return mapPromise;
}

function ensureMap() {
  void loadMapController();
  return mapController || pendingMapController;
}

menuToggle?.addEventListener("click", () => setMenuState(menu?.hidden));
menu?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setMenuState(false)));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu && !menu.hidden) setMenuState(false);
});
installPlacementDialog();

document.querySelectorAll("[data-map-entry]").forEach((entry) => {
  entry.addEventListener("click", (event) => {
    if (mobileHome.matches) return;
    event.preventDefault();
    document.getElementById("map-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    void loadMapController();
  });
});

document.querySelector("[data-open-search]")?.addEventListener("click", () => {
  if (mobileHome.matches) {
    location.assign("/map?focus=search");
    return;
  }
  document.getElementById("map-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  void loadMapController().then(() => window.setTimeout(() => searchInput?.focus(), 250));
});

searchInput?.addEventListener("input", () => {
  searchClear.hidden = !searchInput.value;
  void loadMapController().then((controller) => controller.search(searchInput.value));
});
searchInput?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || searchInput.hasAttribute("aria-activedescendant")) return;
  event.preventDefault();
  void loadMapController().then((controller) => controller.search(searchInput.value, { immediate: true }));
  searchInput.blur();
});
searchInput?.addEventListener("focus", () => {
  void loadMapController();
  if (!features.discovery_search || autocompleteAttached || !mapAutocomplete) return;
  autocompleteAttached = true;
  loadStylesheet("/static/public/autocomplete.css?v=2026-08-03-02");
  import("./autocomplete.js?v=2026-08-03-02").then(({ attachAutocomplete }) => {
    attachAutocomplete(searchInput, mapAutocomplete, {
      onSelect(item) {
        if (["entity", "collection", "route"].includes(item.source) && item.href) {
          location.assign(item.href);
          return;
        }
        searchInput.value = item.value || item.title || "";
        void loadMapController().then((controller) => controller.search(searchInput.value));
        searchInput.blur();
      },
    });
  }).catch(() => {});
});
searchClear?.addEventListener("click", () => {
  if (!searchInput) return;
  searchInput.value = "";
  searchClear.hidden = true;
  void loadMapController().then((controller) => controller.clearSearch());
  searchInput.blur();
});
document.querySelector("[data-map-locate]")?.addEventListener("click", () => void loadMapController().then((controller) => controller.locate()));
mapFilterReset?.addEventListener("click", () => {
  if (searchInput) searchInput.value = "";
  if (searchClear) searchClear.hidden = true;
});
document.querySelector("[data-map-reset]")?.addEventListener("click", () => {
  if (searchInput) searchInput.value = "";
  if (searchClear) searchClear.hidden = true;
  void loadMapController().then((controller) => controller.reset());
});

document.querySelectorAll("[data-current-year]").forEach((node) => {
  node.textContent = String(new Date().getFullYear());
});

if (!mobileHome.matches && "IntersectionObserver" in window && mapShell) {
  const observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      void loadMapController();
      observer.disconnect();
    }
  }, { rootMargin: "0px 0px -300px" });
  observer.observe(mapShell);
} else if (!mobileHome.matches) {
  void loadMapController();
}

if (mobileHome.matches && discoveryPreview) {
  const loadPreview = () => import("./discovery-preview.js?v=2026-08-03-01")
    .then(({ initialiseDiscoveryPreview }) => initialiseDiscoveryPreview(discoveryPreview))
    .catch(() => {});
  if ("IntersectionObserver" in window) {
    const previewObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        previewObserver.disconnect();
        void loadPreview();
      }
    }, { rootMargin: "240px" });
    previewObserver.observe(discoveryPreview);
  } else {
    void loadPreview();
  }
}

if (
  discoveryHome
  && (features.editorial_collections || features.tourism_routes || features.related_entities)
) {
  discoveryHome.hidden = false;
  const loadDiscovery = () => {
    loadStylesheet("/static/public/discovery-home.css?v=2026-08-03-01");
    return import("./discovery-home.js?v=2026-07-28-01")
      .then(({ loadDiscoveryHome }) => loadDiscoveryHome(discoveryHome))
      .catch(() => { discoveryHome.hidden = true; });
  };
  if ("IntersectionObserver" in window) {
    const discoveryObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadDiscovery();
        discoveryObserver.disconnect();
      }
    }, { rootMargin: "400px" });
    discoveryObserver.observe(discoveryHome);
  } else {
    loadDiscovery();
  }
}

if (belowFold) {
  const loadBelowFold = () => loadStylesheet("/static/public/site-below-fold.css?v=2026-07-28-01");
  if ("IntersectionObserver" in window) {
    const belowFoldObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadBelowFold();
        belowFoldObserver.disconnect();
      }
    }, { rootMargin: "600px" });
    belowFoldObserver.observe(belowFold);
  } else {
    loadBelowFold();
  }
}
