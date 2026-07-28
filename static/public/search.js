import { attachAutocomplete } from "./autocomplete.js";
import { createElement, getJson, rememberSearch, renderCards, renderHistory, shareUrl, trackEvent } from "./discovery-common.js";

const form = document.querySelector("[data-search-form]");
const input = document.querySelector("[data-search-input]");
const suggestions = document.querySelector("[data-search-suggestions]");
const results = document.querySelector("[data-search-results]");
const heading = document.querySelector("[data-search-heading]");
const status = document.querySelector("[data-search-status]");
const pagination = document.querySelector("[data-pagination]");
const controls = {
  source: document.querySelector("[data-filter-source]"),
  kind: document.querySelector("[data-filter-kind]"),
  subtype: document.querySelector("[data-filter-subtype]"),
  region: document.querySelector("[data-filter-region]"),
  district: document.querySelector("[data-filter-district]"),
  city: document.querySelector("[data-filter-city]"),
  tag: document.querySelector("[data-filter-tag]"),
  amenity: document.querySelector("[data-filter-amenity]"),
  season: document.querySelector("[data-filter-season]"),
  difficulty: document.querySelector("[data-filter-difficulty]"),
  duration_max: document.querySelector("[data-filter-duration]"),
  audience: document.querySelector("[data-filter-audience]"),
  sort: document.querySelector("[data-filter-sort]"),
};
let requestController = null;

function stateFromUrl() {
  const params = new URLSearchParams(location.search);
  return {
    q: (params.get("q") || "").slice(0, 120),
    source: params.get("source") || "",
    entity_kind: params.get("entity_kind") || "",
    subtype: params.get("subtype") || "",
    region: params.get("region") || "",
    district: params.get("district") || "",
    city: params.get("city") || "",
    tag: params.get("tag") || "",
    amenity: params.get("amenity") || "",
    season: params.get("season") || "",
    difficulty: params.get("difficulty") || "",
    duration_max: params.get("duration_max") || "",
    audience: params.get("audience") || "",
    sort: params.get("sort") || "relevance",
    page: Math.max(1, Number(params.get("page") || 1)),
  };
}

function applyState(state) {
  input.value = state.q;
  controls.source.value = state.source;
  controls.kind.value = state.entity_kind;
  controls.subtype.value = state.subtype;
  controls.region.value = state.region;
  controls.district.value = state.district;
  controls.city.value = state.city;
  controls.tag.value = state.tag;
  controls.amenity.value = state.amenity;
  controls.season.value = state.season;
  controls.difficulty.value = state.difficulty;
  controls.duration_max.value = state.duration_max;
  controls.audience.value = state.audience;
  controls.sort.value = state.sort;
}

function urlFor(state) {
  const params = new URLSearchParams();
  Object.entries(state).forEach(([key, value]) => {
    if (value && !(key === "page" && value === 1) && !(key === "sort" && value === "relevance")) params.set(key, String(value));
  });
  return `/search${params.size ? `?${params}` : ""}`;
}

function currentState(page = 1) {
  const previous = stateFromUrl();
  return {
    q: input.value.trim(),
    source: controls.source.value,
    entity_kind: controls.kind.value,
    subtype: controls.subtype.value.trim(),
    region: controls.region.value.trim(),
    district: controls.district.value.trim(),
    city: controls.city.value.trim(),
    tag: controls.tag.value.trim(),
    amenity: controls.amenity.value.trim(),
    season: controls.season.value,
    difficulty: controls.difficulty.value,
    duration_max: controls.duration_max.value,
    audience: controls.audience.value.trim(),
    sort: controls.sort.value,
    page,
  };
}

function searchApiUrl(state) {
  const params = new URLSearchParams({ q: state.q, page: String(state.page), limit: "18", sort: state.sort });
  ["source", "entity_kind", "subtype", "region", "district", "city", "tag", "amenity", "season", "difficulty", "duration_max", "audience"].forEach((key) => {
    if (state[key]) params.set(key, state[key]);
  });
  return `/api/public/search?${params}`;
}

function renderPagination(state, pages) {
  pagination.replaceChildren();
  if (pages <= 1) return;
  for (let page = 1; page <= pages; page += 1) {
    if (pages > 9 && page > 2 && page < pages - 1 && Math.abs(page - state.page) > 1) continue;
    const button = createElement("button", "", page);
    button.type = "button";
    if (page === state.page) button.setAttribute("aria-current", "page");
    button.addEventListener("click", () => navigate({ ...state, page }));
    pagination.append(button);
  }
}

async function load(state, { updateUrl = true } = {}) {
  requestController?.abort();
  requestController = new AbortController();
  if (updateUrl) history.pushState(state, "", urlFor(state));
  status.textContent = "Ищем…";
  results.setAttribute("aria-busy", "true");
  try {
    const payload = await getJson(searchApiUrl(state), { signal: requestController.signal });
    heading.textContent = state.q
      ? `По запросу «${state.q}»`
      : state.source === "collection"
        ? "Редакционные подборки"
        : state.source === "route"
          ? "Готовые маршруты"
          : "Идеи для поездки";
    status.textContent = `Найдено: ${payload.total}`;
    renderCards(results, payload.items, { emptyText: "Попробуйте убрать часть фильтров или изменить формулировку." });
    renderPagination(state, payload.pages);
  } catch (error) {
    if (error?.name === "AbortError") return;
    status.textContent = "Ошибка загрузки";
    renderCards(results, [], { emptyTitle: "Поиск временно недоступен", emptyText: "Обновите страницу или попробуйте немного позже." });
  } finally {
    results.removeAttribute("aria-busy");
  }
}

function navigate(state) {
  applyState(state);
  load(state);
  document.querySelector("#search-results")?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
}

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  const state = currentState();
  rememberSearch(state.q, urlFor(state));
  trackEvent("search_submitted", { contentType: "search" });
  navigate(state);
});
document.querySelector("[data-filter-apply]")?.addEventListener("click", () => { trackEvent("filter_changed", { contentType: "search" }); navigate(currentState()); });
document.querySelector("[data-filter-reset]")?.addEventListener("click", () => {
  Object.values(controls).forEach((control) => { control.value = control === controls.sort ? "relevance" : ""; });
  navigate({
    q: input.value.trim(), source: "", entity_kind: "", subtype: "", region: "", district: "",
    city: "", tag: "", amenity: "", season: "", difficulty: "", duration_max: "", audience: "",
    sort: "relevance", page: 1,
  });
});
attachAutocomplete(input, suggestions, {
  onSelect: (item) => {
    trackEvent("suggestion_selected", {
      contentType: ["entity", "collection", "route"].includes(item.source) ? item.source : "search",
      contentSlug: item.slug || undefined,
    });
    if (item.source === "entity" || item.source === "collection" || item.source === "route") location.assign(item.href);
    else navigate({ ...currentState(), q: item.value || item.title });
  },
});
results?.addEventListener("click", (event) => {
  const link = event.target.closest?.("a");
  const card = link?.closest?.("[data-source]");
  if (link && card) trackEvent("search_result_opened", {
    contentType: card.dataset.source || "entity",
    contentSlug: new URL(link.href).pathname.split("/").filter(Boolean).pop(),
  });
});
window.addEventListener("popstate", () => { const state = stateFromUrl(); applyState(state); load(state, { updateUrl: false }); });
document.querySelector("[data-share-search]")?.addEventListener("click", () => {
  shareUrl(new URL(urlFor(currentState(stateFromUrl().page)), location.origin).href, "Поиск — Туристика", document.querySelector("[data-share-feedback]"));
});

async function loadPopular() {
  const root = document.querySelector("[data-search-popular]");
  if (!root) return;
  try {
    const payload = await getJson("/api/public/search/popular?limit=8");
    payload.items.forEach((item) => {
      const button = createElement("button", "", item.title);
      button.type = "button";
      button.addEventListener("click", () => navigate({ ...currentState(), q: item.query, page: 1 }));
      root.append(button);
    });
  } catch {}
}

const initial = stateFromUrl();
applyState(initial);
load(initial, { updateUrl: false });
loadPopular();
renderHistory();
