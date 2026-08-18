import { publicFeatures } from "./feature-flags.js";
import { initialisePublicMap } from "./map.js?v=2026-08-18-05";

const ONBOARDING_KEY = "touristika:map-onboarding:v1";
const features = publicFeatures();
const query = new URLSearchParams(location.search);
const searchInput = document.querySelector("[data-map-search]");
const searchClear = document.querySelector("[data-search-clear]");
const autocomplete = document.querySelector("[data-map-autocomplete]");
const list = document.querySelector("[data-map-list]");
const canvas = document.querySelector("[data-map-shell] .public-map__canvas");
const viewButtons = [...document.querySelectorAll("[data-map-view]")];
let controller;
let autocompleteAttached = false;

if (features.telegram_webapp) {
  import("./telegram.js").then(({ initialiseTelegramWebApp }) => initialiseTelegramWebApp(features)).catch(() => {});
}

function waitForLeaflet() {
  if (window.L) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const started = performance.now();
    const timer = window.setInterval(() => {
      if (window.L) {
        window.clearInterval(timer);
        resolve();
      } else if (performance.now() - started > 8000) {
        window.clearInterval(timer);
        reject(new Error("Leaflet unavailable"));
      }
    }, 30);
  });
}

function setView(value) {
  const showList = value === "list";
  list.hidden = !showList;
  canvas.hidden = showList;
  viewButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.mapView === value)));
  if (!showList) window.requestAnimationFrame(() => {
    controller?.invalidate();
    controller?.refreshList();
  });
}

function nodes() {
  return {
    shell: document.querySelector("[data-map-shell]"),
    canvas,
    loading: document.querySelector("[data-map-loading]"),
    status: document.querySelector("[data-map-status]"),
    results: document.querySelector("[data-map-results]"),
    filterPanel: document.querySelector("[data-map-filters]"),
    filterToggle: document.querySelector("[data-map-filter-toggle]"),
    filterClose: document.querySelector("[data-map-filter-close]"),
    filterKinds: [...document.querySelectorAll("[data-filter-kind]")],
    filterSubtype: document.querySelector("[data-filter-subtype]"),
    filterRegion: document.querySelector("[data-filter-region]"),
    filterDistrict: document.querySelector("[data-filter-district]"),
    filterCity: document.querySelector("[data-filter-city]"),
    filterSeasonality: document.querySelector("[data-filter-seasonality]"),
    filterAmenities: document.querySelector("[data-filter-amenities]"),
    filterAmenityOptions: document.querySelector("[data-filter-amenity-options]"),
    filterLegacyAmenity: document.querySelector("[data-filter-amenity]"),
    filterPriceMin: document.querySelector("[data-filter-price-min]"),
    filterPriceMax: document.querySelector("[data-filter-price-max]"),
    filterOpenNow: document.querySelector("[data-filter-open-now]"),
    filterChildren: document.querySelector("[data-filter-children]"),
    filterPets: document.querySelector("[data-filter-pets]"),
    filterParking: document.querySelector("[data-filter-parking]"),
    filterWifi: document.querySelector("[data-filter-wifi]"),
    filterReset: document.querySelector("[data-filter-reset]"),
    filterApply: document.querySelector("[data-filter-apply]"),
    count: document.querySelector("[data-map-count]"),
    legend: document.querySelector("[data-map-legend]"),
    list,
    listItems: document.querySelector("[data-map-list-items]"),
    listCount: document.querySelector("[data-map-list-count]"),
    sheet: document.querySelector("[data-map-sheet]"),
    sheetContent: document.querySelector("[data-map-sheet-content]"),
    sheetToggle: document.querySelector("[data-map-sheet-toggle]"),
    searchArea: document.querySelector("[data-map-search-area]"),
    appMode: true,
    onShowList(entity) {
      setView("list");
      window.requestAnimationFrame(() => document.querySelector(`[data-entity-id="${CSS.escape(String(entity.id || entity.entity_id))}"]`)?.focus());
    },
  };
}

function loadStylesheet(href) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.append(link);
}

function attachSearch() {
  searchInput.value = query.get("search") || query.get("q") || "";
  searchClear.hidden = !searchInput.value;
  searchInput.addEventListener("input", () => {
    searchClear.hidden = !searchInput.value;
    if (!searchInput.value) controller?.clearSearch();
  });
  searchInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || searchInput.hasAttribute("aria-activedescendant")) return;
    event.preventDefault();
    controller?.search(searchInput.value, { immediate: true });
    searchInput.blur();
  });
  searchInput.addEventListener("focus", () => {
    controller?.setKeyboardOpen(true);
    if (!features.discovery_search || autocompleteAttached || !autocomplete) return;
    autocompleteAttached = true;
    loadStylesheet("/static/public/autocomplete.css?v=2026-08-03-02");
    import("./autocomplete.js?v=2026-08-03-02").then(({ attachAutocomplete }) => {
      attachAutocomplete(searchInput, autocomplete, {
        onSelect(item) {
          if (item.source === "entity" && item.slug) {
            location.assign(`/map?id=${encodeURIComponent(item.slug)}`);
            return;
          }
          if (["collection", "route"].includes(item.source) && item.href) {
            location.assign(item.href);
            return;
          }
          searchInput.value = item.value || item.title || "";
          controller?.search(searchInput.value, { immediate: true });
          searchInput.blur();
        },
      });
    }).catch(() => {});
  });
  searchInput.addEventListener("blur", () => {
    window.setTimeout(() => {
      controller?.setKeyboardOpen(false);
      controller?.invalidate();
    }, 220);
  });
  searchClear.addEventListener("click", () => {
    searchInput.value = "";
    searchClear.hidden = true;
    controller?.clearSearch();
    searchInput.blur();
    window.setTimeout(() => controller?.invalidate(), 160);
  });
  if (query.get("focus") === "search") window.setTimeout(() => searchInput.focus(), 250);
}

function installOnboarding() {
  const onboarding = document.querySelector("[data-map-onboarding]");
  const card = onboarding?.querySelector(".map-onboarding__card");
  const help = document.querySelector("[data-map-help]");
  const tip = document.querySelector("[data-map-tip]");
  let restoreFocus = null;

  const focusable = () => [...onboarding.querySelectorAll("button:not([disabled]), a[href]")];
  const open = () => {
    restoreFocus = document.activeElement;
    onboarding.hidden = false;
    document.querySelector("[data-map-shell]").inert = true;
    document.body.classList.add("map-onboarding-open");
    window.setTimeout(() => card.focus(), 0);
  };
  const close = () => {
    onboarding.hidden = true;
    document.querySelector("[data-map-shell]").inert = false;
    document.body.classList.remove("map-onboarding-open");
    try { localStorage.setItem(ONBOARDING_KEY, "seen"); } catch {}
    restoreFocus?.focus?.();
  };
  onboarding.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const items = focusable();
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (document.activeElement === card) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
    else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  onboarding.querySelectorAll("[data-map-onboarding-close], [data-map-onboarding-start]").forEach((button) => button.addEventListener("click", close));
  help.addEventListener("click", open);

  const directEntry = query.has("id") || query.has("entity") || query.has("search") || query.has("q");
  if (directEntry) {
    tip.hidden = false;
    tip.querySelector("[data-map-tip-close]")?.addEventListener("click", () => { tip.hidden = true; });
  } else {
    let seen = false;
    try { seen = localStorage.getItem(ONBOARDING_KEY) === "seen"; } catch {}
    if (!seen) open();
  }
}

viewButtons.forEach((button) => button.addEventListener("click", () => setView(button.dataset.mapView)));
document.querySelector("[data-map-locate]")?.addEventListener("click", () => controller?.locate());
document.querySelector("[data-map-reset]")?.addEventListener("click", () => {
  searchInput.value = "";
  searchClear.hidden = true;
  controller?.reset();
});
document.querySelector("[data-filter-reset]")?.addEventListener("click", () => {
  searchInput.value = "";
  searchClear.hidden = true;
});

attachSearch();
installOnboarding();
waitForLeaflet().then(() => {
  controller = initialisePublicMap(nodes());
  if (window.__TOURISTIKA_TEST_HOOKS__) window.__TOURISTIKA_TEST_MAP_CONTROLLER__ = controller;
}).catch((error) => {
  console.error("Failed to initialise the public map", error);
  document.querySelector("[data-map-loading]").hidden = true;
  document.querySelector("[data-map-status]").textContent = "Карта временно недоступна. Попробуйте обновить страницу.";
});

window.visualViewport?.addEventListener("resize", () => {
  if (document.activeElement === searchInput) return;
  window.setTimeout(() => controller?.invalidate(), 180);
}, { passive: true });
