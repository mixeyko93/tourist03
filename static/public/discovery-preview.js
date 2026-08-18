const COLORS = Object.freeze({
  accommodation: "#247da8",
  activity: "#d06c32",
});

function pilotCategory(key) {
  if (key === "accommodation") return "accommodation";
  if (["activity", "event", "service", "rental"].includes(key)) return "activity";
  return "";
}

function shuffled(items) {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const target = Math.floor(Math.random() * (index + 1));
    [result[index], result[target]] = [result[target], result[index]];
  }
  return result;
}

function point(entity, index, total) {
  const lat = Number(entity.lat);
  const lng = Number(entity.lng);
  if (Number.isFinite(lat) && Number.isFinite(lng)) {
    return {
      x: Math.max(8, Math.min(94, 8 + ((lng - 20) / 160) * 86)),
      y: Math.max(13, Math.min(82, 78 - ((lat - 42) / 36) * 65)),
    };
  }
  return { x: 12 + ((index * 29) % 78), y: 22 + ((index * 17) % 53) + (total % 3) };
}

function separatedPoint(base, occupied) {
  const candidates = [{ x: base.x, y: base.y }];
  for (let ring = 1; ring <= 4; ring += 1) {
    const slots = ring * 8;
    for (let slot = 0; slot < slots; slot += 1) {
      const angle = (slot / slots) * Math.PI * 2;
      candidates.push({
        x: Math.max(7, Math.min(93, base.x + Math.cos(angle) * ring * 13)),
        y: Math.max(12, Math.min(84, base.y + Math.sin(angle) * ring * 22)),
      });
    }
  }
  return candidates.find((candidate) => occupied.every((current) => (
    Math.hypot((candidate.x - current.x) * 3.6, (candidate.y - current.y) * 2.06) >= 46
  ))) || candidates[candidates.length - 1];
}

function kindKey(entity) {
  if (typeof entity.entity_kind === "string") return entity.entity_kind;
  return entity.entity_kind?.key || entity.entity_kind?.slug || "service";
}

function kindName(entity) {
  return entity.entity_kind_name || entity.subtype_name || entity.entity_kind?.name || "Туристический объект";
}

export async function initialiseDiscoveryPreview(root) {
  const markerRoot = root.querySelector("[data-preview-markers]");
  const popover = root.querySelector("[data-preview-popover]");
  const message = root.querySelector("[data-preview-message]");
  try {
    const response = await fetch("/api/public/discovery/home", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const counts = payload.counts || {};
    const pilotCounts = {
      accommodation: Number(counts.accommodation) || 0,
      activity: ["activity", "event", "service", "rental"].reduce((total, key) => total + (Number(counts[key]) || 0), 0),
    };
    Object.entries(pilotCounts).forEach(([key, value]) => {
      const node = root.querySelector(`[data-preview-count="${key}"]`);
      if (node) node.textContent = new Intl.NumberFormat("ru-RU").format(value);
    });
    const items = shuffled(payload.preview_items || payload.recently_updated || [])
      .filter((entity) => pilotCategory(kindKey(entity)))
      .slice(0, 24);
    const occupied = [];
    items.forEach((entity, index) => {
      const marker = document.createElement("button");
      const location = entity.location || [entity.city, entity.region].filter(Boolean).join(", ") || "Россия";
      const position = separatedPoint(point(entity, index, items.length), occupied);
      occupied.push(position);
      marker.type = "button";
      marker.className = "discovery-preview__marker";
      marker.style.setProperty("--x", `${position.x}%`);
      marker.style.setProperty("--y", `${position.y}%`);
      marker.style.setProperty("--marker", COLORS[pilotCategory(kindKey(entity))] || "#087184");
      marker.setAttribute("aria-label", `Открыть подсказку: ${entity.title || entity.name || "туристический объект"}`);
      marker.addEventListener("click", () => {
        popover.querySelector("[data-preview-type]").textContent = kindName(entity);
        popover.querySelector("[data-preview-name]").textContent = entity.title || entity.name || "Туристический объект";
        popover.querySelector("[data-preview-region]").textContent = location;
        popover.querySelector("[data-preview-link]").href = entity.slug
          ? `/map?id=${encodeURIComponent(entity.slug)}`
          : "/map";
        popover.hidden = false;
      });
      markerRoot.append(marker);
      window.setTimeout(() => {
        marker.classList.add("is-visible");
        if (index % 4 === 0) marker.classList.add("is-pulsing");
      }, 140 + index * 110);
    });
    popover.querySelector("[data-preview-close]")?.addEventListener("click", () => { popover.hidden = true; });
    const total = pilotCounts.accommodation + pilotCounts.activity;
    const messages = [
      total ? `Более ${new Intl.NumberFormat("ru-RU").format(total)} интересных мест по России` : "Открывайте новые места по всей России",
      "Популярные впечатления уже на карте",
      "Постройте своё путешествие",
    ];
    let messageIndex = 0;
    message.textContent = messages[0];
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
      window.setInterval(() => {
        messageIndex = (messageIndex + 1) % messages.length;
        message.textContent = messages[messageIndex];
      }, 5200);
    }
  } catch {
    root.querySelectorAll("[data-preview-count]").forEach((node) => { node.textContent = "—"; });
    message.textContent = "Откройте карту и начните путешествие";
  }
}
