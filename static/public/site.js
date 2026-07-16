import { publicFeatures } from "./feature-flags.js";
import { initialisePublicMap } from "./map.js";
import { initialiseTelegramWebApp } from "./telegram.js";

const features = publicFeatures();
initialiseTelegramWebApp(features);

const menuToggle = document.querySelector("[data-menu-toggle]");
const menu = document.querySelector("[data-menu]");
const searchInput = document.querySelector("[data-map-search]");
const searchClear = document.querySelector("[data-search-clear]");
const mapShell = document.querySelector("[data-map-shell]");
const mapCanvas = document.querySelector("#map");
const mapLoading = document.querySelector("[data-map-loading]");
const mapStatus = document.querySelector("[data-map-status]");
const mapResults = document.querySelector("[data-map-results]");
let mapController;
let mapInitialisationScheduled = false;
const pendingMapController = Object.freeze({ search() {}, reset() {}, locate() {} });

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
searchInput?.addEventListener("focus", ensureMap);
searchClear?.addEventListener("click", () => {
  if (!searchInput) return;
  searchInput.value = "";
  searchClear.hidden = true;
  ensureMap().reset();
  searchInput.focus();
});
document.querySelector("[data-map-locate]")?.addEventListener("click", () => ensureMap().locate());
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
