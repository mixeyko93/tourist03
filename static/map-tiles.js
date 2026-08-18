(function initialiseTouristikaMapTiles(global) {
  "use strict";

  const YANDEX_TILE_URL = "https://tiles.api-maps.yandex.ru/v1/tiles/?apikey={apikey}&lang=ru_RU&x={x}&y={y}&z={z}&l=map&scale=1&projection=web_mercator&maptype=map";
  const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  function runtimeApiKey() {
    const config = global.__TOURISTIKA_MAPS__;
    return typeof config?.yandexTilesApiKey === "string" ? config.yandexTilesApiKey.trim() : "";
  }

  function ensureAttributionControl(map, L, position) {
    if (map.attributionControl) return map.attributionControl;
    const control = L.control.attribution({ position: position || "bottomright", prefix: false });
    control.addTo(map);
    return control;
  }

  function createYandexLogoControl(map, L, position) {
    const control = L.control({ position: position || "bottomleft" });
    control.onAdd = function onAdd() {
      const link = L.DomUtil.create("a", "touristika-yandex-logo");
      link.href = "https://yandex.ru/maps/";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.title = "Открыть Яндекс Карты";
      link.setAttribute("aria-label", "Яндекс Карты");
      link.style.display = "block";
      link.style.margin = "0";
      link.innerHTML = '<img src="/static/brand/yandex-maps-logo-ru.svg" width="88" height="48" alt="Яндекс Карты">';
      link.firstElementChild.style.display = "block";
      L.DomEvent.disableClickPropagation(link);
      L.DomEvent.disableScrollPropagation(link);
      return link;
    };
    control.addTo(map);
    return control;
  }

  function addBaseLayer(map, options) {
    const config = options || {};
    const L = config.leaflet || global.L;
    if (!L || !map) throw new Error("Leaflet map is required");
    const apiKey = runtimeApiKey();
    const maxZoom = Math.min(Number(config.maxZoom) || 19, 20);
    let provider = apiKey ? "yandex" : "osm";
    let activeLayer = null;
    let logoControl = null;
    let switchedToFallback = false;
    let yandexTileLoaded = false;
    let initialFailureTimer = null;
    let initialTileErrors = 0;

    function notifyLoad(event) {
      if (typeof config.onLoad === "function") config.onLoad({ provider, event });
    }

    function notifyError(event) {
      if (typeof config.onError === "function") config.onError({ provider, event });
    }

    function addOsmLayer(reason) {
      if (initialFailureTimer) {
        global.clearTimeout(initialFailureTimer);
        initialFailureTimer = null;
      }
      provider = "osm";
      ensureAttributionControl(map, L, config.attributionPosition);
      activeLayer = L.tileLayer(OSM_TILE_URL, {
        maxZoom,
        attribution: OSM_ATTRIBUTION,
      });
      activeLayer.on("tileload", notifyLoad);
      activeLayer.on("tileerror", notifyError);
      activeLayer.addTo(map);
      if (reason && typeof config.onFallback === "function") config.onFallback({ reason, provider });
    }

    function switchToFallback() {
      if (switchedToFallback || yandexTileLoaded) return;
      switchedToFallback = true;
      if (map.hasLayer(activeLayer)) map.removeLayer(activeLayer);
      if (logoControl) {
        map.removeControl(logoControl);
        logoControl = null;
      }
      addOsmLayer("yandex-initial-load-failed");
    }

    if (!apiKey) {
      addOsmLayer("missing-api-key");
    } else {
      const tileUrl = YANDEX_TILE_URL.replace("{apikey}", encodeURIComponent(apiKey));
      activeLayer = L.tileLayer(tileUrl, { maxZoom });
      logoControl = createYandexLogoControl(map, L, config.logoPosition);
      activeLayer.on("tileload", (event) => {
        yandexTileLoaded = true;
        if (initialFailureTimer) {
          global.clearTimeout(initialFailureTimer);
          initialFailureTimer = null;
        }
        notifyLoad(event);
      });
      activeLayer.on("tileerror", (event) => {
        notifyError(event);
        if (switchedToFallback || yandexTileLoaded) return;
        initialTileErrors += 1;
        if (initialTileErrors < 3 || initialFailureTimer) return;
        initialFailureTimer = global.setTimeout(switchToFallback, 1200);
      });
      activeLayer.addTo(map);
    }

    return {
      getLayer: () => activeLayer,
      getProvider: () => provider,
      isFallback: () => provider === "osm",
    };
  }

  global.TouristikaMapTiles = Object.freeze({ addBaseLayer });
})(window);
