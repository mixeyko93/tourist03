import { createElement, getJson, resultCard } from "./discovery-common.js";

function group(title, items) {
  if (!items?.length) return null;
  const section = createElement("section", "discovery-home__group");
  const heading = createElement("h3", "", title);
  const track = createElement("div", "discovery-home__track");
  items.forEach((item) => track.append(resultCard(item)));
  section.append(heading, track);
  return section;
}

export async function loadDiscoveryHome(root) {
  const groups = root.querySelector("[data-discovery-home-groups]");
  try {
    const payload = await getJson("/api/public/discovery/home");
    groups.replaceChildren();
    [
      group("Редакционные подборки", payload.collections),
      group("Готовые маршруты", payload.routes),
      group("Недавно обновили", payload.recently_updated),
    ].filter(Boolean).forEach((section) => groups.append(section));
    if (!groups.childElementCount) root.hidden = true;
  } catch {
    root.hidden = true;
  }
}
