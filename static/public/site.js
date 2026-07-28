import { publicFeatures } from "./feature-flags.js";
import { initialisePublicMap } from "./map.js?v=2026-07-27-04";

const features = publicFeatures();
if (features.telegram_webapp) {
  import("./telegram.js").then(({ initialiseTelegramWebApp }) => {
    initialiseTelegramWebApp(features);
  }).catch(() => {});
}
document.querySelectorAll("[data-placement-submissions]").forEach((node) => {
  node.hidden = !features.placement_submissions;
});
document.querySelectorAll("[data-feature-link]").forEach((node) => {
  node.hidden = !features[node.dataset.featureLink];
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
const belowFold = document.querySelector("#about");
let mapController;
let mapInitialisationScheduled = false;
let autocompleteAttached = false;
const pendingMapController = Object.freeze({ search() {}, reset() {}, locate() {} });

function loadStylesheet(href) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.append(link);
}

function setMenuState(isOpen) {
  if (!menuToggle || !menu) return;
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  menuToggle.setAttribute("aria-label", isOpen ? "Закрыть меню" : "Открыть меню");
  menu.hidden = !isOpen;
  document.body.classList.toggle("menu-is-open", isOpen);
  if (isOpen) menu.querySelector("a")?.focus();
}

function ensureMap() {
  if (mapController) return mapController;
  if (!window.L) {
    if (!mapInitialisationScheduled) {
      mapInitialisationScheduled = true;
      window.setTimeout(() => {
        mapInitialisationScheduled = false;
        ensureMap();
      }, 40);
    }
    return pendingMapController;
  }
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
}

menuToggle?.addEventListener("click", () => setMenuState(menu?.hidden));
menu?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setMenuState(false)));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu && !menu.hidden) setMenuState(false);
});

document.querySelectorAll("[data-scroll-to]").forEach((button) => {
  button.addEventListener("click", () => {
    document.getElementById(button.dataset.scrollTo)?.scrollIntoView({ behavior: "smooth", block: "start" });
    ensureMap();
  });
});

document.querySelector("[data-open-search]")?.addEventListener("click", () => {
  document.getElementById("map-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  ensureMap();
  window.setTimeout(() => searchInput?.focus(), 500);
});

searchInput?.addEventListener("input", () => {
  searchClear.hidden = !searchInput.value;
  ensureMap().search(searchInput.value);
});
searchInput?.addEventListener("focus", () => {
  ensureMap();
  if (!features.discovery_search || autocompleteAttached || !mapAutocomplete) return;
  autocompleteAttached = true;
  loadStylesheet("/static/public/autocomplete.css?v=2026-07-28-01");
  import("./autocomplete.js?v=2026-07-28-01").then(({ attachAutocomplete }) => {
    attachAutocomplete(searchInput, mapAutocomplete, {
      onSelect(item) {
        if (["entity", "collection", "route"].includes(item.source) && item.href) {
          location.assign(item.href);
          return;
        }
        searchInput.value = item.value || item.title || "";
        ensureMap().search(searchInput.value);
      },
    });
  }).catch(() => {});
});
searchClear?.addEventListener("click", () => {
  if (!searchInput) return;
  searchInput.value = "";
  searchClear.hidden = true;
  ensureMap().search("");
  searchInput.focus();
});
document.querySelector("[data-map-locate]")?.addEventListener("click", () => ensureMap().locate());
mapFilterReset?.addEventListener("click", () => {
  if (searchInput) searchInput.value = "";
  if (searchClear) searchClear.hidden = true;
});
document.querySelector("[data-map-reset]")?.addEventListener("click", () => {
  if (searchInput) searchInput.value = "";
  if (searchClear) searchClear.hidden = true;
  ensureMap().reset();
});

document.querySelectorAll("[data-current-year]").forEach((node) => {
  node.textContent = String(new Date().getFullYear());
});

if ("IntersectionObserver" in window && mapShell) {
  const observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) {
      ensureMap();
      observer.disconnect();
    }
  }, { rootMargin: "0px 0px -300px" });
  observer.observe(mapShell);
} else {
  ensureMap();
}

if (
  discoveryHome
  && (features.editorial_collections || features.tourism_routes || features.related_entities)
) {
  discoveryHome.hidden = false;
  const loadDiscovery = () => {
    loadStylesheet("/static/public/discovery-home.css?v=2026-07-28-01");
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
