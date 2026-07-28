import { createElement, getJson } from "./discovery-common.js";

export function attachAutocomplete(input, list, { onSelect, minLength = 2 } = {}) {
  if (!input || !list) return () => {};
  let active = -1;
  let items = [];
  let timer = 0;
  let controller = null;

  const close = () => {
    active = -1;
    items = [];
    list.hidden = true;
    list.replaceChildren();
    input.removeAttribute("aria-activedescendant");
  };
  const setActive = (index) => {
    const options = [...list.querySelectorAll("[role=option]")];
    if (!options.length) return;
    active = (index + options.length) % options.length;
    options.forEach((option, position) => option.setAttribute("aria-selected", String(position === active)));
    input.setAttribute("aria-activedescendant", options[active].id);
    options[active].scrollIntoView({ block: "nearest" });
  };
  const choose = (item) => {
    input.value = item.value || item.title;
    close();
    if (onSelect) onSelect(item);
    else if (item.href) location.assign(item.href);
  };
  const render = () => {
    list.replaceChildren();
    items.forEach((item, index) => {
      const option = createElement("button");
      option.type = "button";
      option.id = `${list.id || "suggestion"}-${index}`;
      option.setAttribute("role", "option");
      option.setAttribute("aria-selected", "false");
      option.append(createElement("strong", "", item.title));
      if (item.subtitle) option.append(createElement("small", "", item.subtitle));
      option.addEventListener("pointerdown", (event) => event.preventDefault());
      option.addEventListener("click", () => choose(item));
      list.append(option);
    });
    list.hidden = !items.length;
  };
  const load = () => {
    window.clearTimeout(timer);
    controller?.abort();
    const query = input.value.trim();
    if (query.length < minLength) {
      close();
      return;
    }
    timer = window.setTimeout(async () => {
      controller = new AbortController();
      try {
        const payload = await getJson(`/api/public/search/suggestions?q=${encodeURIComponent(query)}&limit=8`, { signal: controller.signal });
        items = payload.items || [];
        active = -1;
        render();
      } catch (error) {
        if (error?.name !== "AbortError") close();
      }
    }, 180);
  };
  input.addEventListener("input", load);
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive(active + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive(active - 1);
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      choose(items[active]);
    } else if (event.key === "Escape") {
      close();
    }
  });
  input.addEventListener("blur", () => window.setTimeout(close, 100));
  return close;
}
