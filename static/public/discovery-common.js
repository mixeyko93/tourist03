const HISTORY_KEY = "touristika:recent:v1";
const HISTORY_LIMIT = 20;
const SEARCH_HISTORY_KEY = "touristika:searches:v1";
const SEARCH_HISTORY_LIMIT = 10;

export function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}

export function resultCard(item, { distance = false } = {}) {
  const article = createElement("article", "discovery-card");
  article.dataset.source = item.source || "entity";
  const cover = createElement("a", "discovery-card__cover");
  cover.href = item.href || "#";
  cover.setAttribute("aria-label", `Открыть «${item.title || "туристический объект"}»`);
  if (item.cover) {
    const image = createElement("img");
    image.src = item.cover;
    image.alt = "";
    image.width = 520;
    image.height = 340;
    image.loading = "lazy";
    image.decoding = "async";
    cover.append(image);
  } else {
    const placeholder = createElement("span");
    const image = createElement("img");
    image.src = "/static/brand/turistika-mark.svg";
    image.alt = "";
    image.width = 92;
    image.height = 92;
    placeholder.append(image);
    cover.append(placeholder);
  }
  const body = createElement("div", "discovery-card__body");
  const sourceLabels = { collection: "Подборка", route: "Маршрут" };
  const type = item.entity_kind_name || item.subtype_name || sourceLabels[item.source] || "Туристический объект";
  body.append(createElement("p", "", type));
  const heading = createElement("h3");
  const link = createElement("a", "", item.title || "Без названия");
  link.href = item.href || "#";
  heading.append(link);
  body.append(heading);
  if (item.short_description) body.append(createElement("p", "", item.short_description));
  const footer = createElement("footer");
  const place = item.location || [item.city, item.region].filter(Boolean).join(" · ") || "Россия";
  footer.append(createElement("span", "", distance && item.distance_km !== undefined ? `${item.distance_km} км · ${place}` : place));
  if (item.source === "entity" && item.slug) {
    const mapLink = createElement("a", "", "На карте");
    mapLink.href = `/?entity=${encodeURIComponent(item.slug)}#map-section`;
    footer.append(mapLink);
  }
  body.append(footer);
  article.append(cover, body);
  return article;
}

export function renderCards(container, items, options = {}) {
  container.replaceChildren();
  if (!items?.length) {
    const empty = createElement("div", "discovery-empty");
    empty.append(
      createElement("h2", "", options.emptyTitle || "Ничего не нашли"),
      createElement("p", "", options.emptyText || "Измените запрос или параметры поиска."),
    );
    container.append(empty);
    return;
  }
  const fragment = document.createDocumentFragment();
  items.forEach((item) => fragment.append(resultCard(item, options)));
  container.append(fragment);
}

export async function getJson(url, { signal } = {}) {
  const response = await fetch(url, { headers: { Accept: "application/json" }, signal });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || "Не удалось загрузить данные.";
    throw new Error(typeof message === "string" ? message : "Не удалось загрузить данные.");
  }
  return payload;
}

export function trackEvent(eventType, details = {}) {
  const payload = {
    event_type: eventType,
    ...(details.contentType ? { content_type: details.contentType } : {}),
    ...(details.contentSlug ? { content_slug: details.contentSlug } : {}),
    ...(details.topicKey ? { topic_key: details.topicKey } : {}),
  };
  fetch("/api/public/discovery/events", {
    method: "POST",
    credentials: "same-origin",
    keepalive: true,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => {});
}

export async function shareUrl(url, title, feedback) {
  try {
    if (navigator.share) {
      await navigator.share({ title, url });
      if (feedback) feedback.textContent = "Ссылка отправлена";
    } else {
      await navigator.clipboard.writeText(url);
      if (feedback) feedback.textContent = "Ссылка скопирована";
    }
  } catch (error) {
    if (error?.name !== "AbortError" && feedback) feedback.textContent = "Не удалось поделиться ссылкой";
  }
  trackEvent("share_clicked", {
    contentType: document.body.dataset.historyKind || undefined,
    contentSlug: document.body.dataset.historySlug || undefined,
  });
  if (feedback?.textContent) window.setTimeout(() => { feedback.textContent = ""; }, 2600);
}

export function installShareButtons(root = document) {
  const feedback = root.querySelector("[data-share-feedback]") || document.querySelector("[data-share-feedback]");
  root.querySelectorAll("[data-share-url]").forEach((button) => {
    button.addEventListener("click", () => shareUrl(button.dataset.shareUrl, button.dataset.shareTitle || document.title, feedback));
  });
}

function readHistory() {
  try {
    const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(value) ? value.filter((item) => item && item.href && item.title).slice(0, HISTORY_LIMIT) : [];
  } catch {
    return [];
  }
}

function readSearchHistory() {
  try {
    const value = JSON.parse(localStorage.getItem(SEARCH_HISTORY_KEY) || "[]");
    return Array.isArray(value)
      ? value.filter((item) => item && item.href && item.title && item.kind === "search").slice(0, SEARCH_HISTORY_LIMIT)
      : [];
  } catch {
    return [];
  }
}

function historyApiUrl(item) {
  const slug = encodeURIComponent(item.slug || "");
  if (!slug) return "";
  if (item.kind === "entity") return `/api/public/entities/${slug}`;
  if (item.kind === "collection") return `/api/public/collections/${slug}`;
  if (item.kind === "route") return `/api/public/routes/${slug}`;
  return "";
}

async function pruneUnavailableHistory(items) {
  const checks = await Promise.all(items.slice(0, 8).map(async (item) => {
    const url = historyApiUrl(item);
    if (!url) return { item, unavailable: false };
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      return { item, unavailable: response.status === 404 };
    } catch {
      return { item, unavailable: false };
    }
  }));
  const unavailable = new Set(checks.filter((check) => check.unavailable).map((check) => check.item.href));
  if (!unavailable.size) return;
  try {
    localStorage.setItem(
      HISTORY_KEY,
      JSON.stringify(readHistory().filter((item) => !unavailable.has(item.href))),
    );
  } catch {}
}

export function rememberSearch(query, href) {
  const title = String(query || "").trim().slice(0, 120);
  if (!title || !String(href || "").startsWith("/search")) return;
  const items = readSearchHistory().filter((item) => item.title.toLocaleLowerCase("ru") !== title.toLocaleLowerCase("ru"));
  items.unshift({ kind: "search", title, href, visitedAt: new Date().toISOString() });
  try { localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(items.slice(0, SEARCH_HISTORY_LIMIT))); } catch {}
}

export function rememberCurrentPage() {
  const { historyKind: kind, historySlug: slug, historyTitle: title } = document.body.dataset;
  if (!kind || !slug || !title) return;
  const href = location.pathname;
  const items = readHistory().filter((item) => item.href !== href);
  items.unshift({ kind, slug, title, href, visitedAt: new Date().toISOString() });
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, HISTORY_LIMIT))); } catch {}
  if (kind === "collection") trackEvent("collection_opened", { contentType: kind, contentSlug: slug });
  if (kind === "route") trackEvent("route_opened", { contentType: kind, contentSlug: slug });
}

export function installDiscoveryLinkTracking(root = document) {
  root.querySelectorAll("[data-related-entity]").forEach((link) => {
    link.addEventListener("click", () => trackEvent("related_entity_opened", {
      contentType: "entity",
      contentSlug: link.dataset.relatedEntity,
    }));
  });
}

export function renderHistory(root = document) {
  const container = root.querySelector("[data-history-items]");
  if (!container) return;
  const render = () => {
    container.replaceChildren();
    const items = [...readSearchHistory(), ...readHistory()]
      .sort((left, right) => String(right.visitedAt || "").localeCompare(String(left.visitedAt || "")))
      .slice(0, HISTORY_LIMIT);
    if (!items.length) {
      container.append(createElement("p", "", "История пока пуста."));
      return;
    }
    items.slice(0, 8).forEach((item) => {
      const link = createElement("a", "", item.title);
      link.href = item.href;
      container.append(link);
    });
    pruneUnavailableHistory(items).catch(() => {});
  };
  root.querySelector("[data-history-clear]")?.addEventListener("click", () => {
    try { localStorage.removeItem(HISTORY_KEY); } catch {}
    try { localStorage.removeItem(SEARCH_HISTORY_KEY); } catch {}
    render();
  });
  render();
}
