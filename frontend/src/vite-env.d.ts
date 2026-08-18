/// <reference types="vite/client" />

type TouristicaMapTilesController = {
  getLayer: () => import("leaflet").TileLayer;
  getProvider: () => "yandex" | "osm";
  isFallback: () => boolean;
};

interface Window {
  __TOURISTIKA_MAPS__?: { yandexTilesApiKey?: string };
  TouristikaMapTiles?: {
    addBaseLayer: (
      map: import("leaflet").Map,
      options?: { maxZoom?: number; leaflet?: typeof import("leaflet") },
    ) => TouristicaMapTilesController;
  };
}
