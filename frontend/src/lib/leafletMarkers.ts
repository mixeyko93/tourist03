import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import L from "leaflet";
import { MapMarker } from "../app/components/MapMarker";
import type { ApiCamp } from "../types/catalog";
import { formatCampPrice, isCampDisabled, isCampVip, resolveCampKind, resolveCampSize } from "./camps";

function markerSizePx(size: string, selected: boolean): [number, number] {
  if (selected) return [184, 112];
  if (size === "large") return [176, 104];
  if (size === "compact") return [150, 96];
  return [164, 100];
}

function markerPriceLabel(camp: ApiCamp): string {
  if (!camp.min_price || camp.min_price <= 0) return "по запросу";
  return `от ${formatCampPrice(camp.min_price)}`;
}

export function createCampDivIcon(camp: ApiCamp, selected: boolean): L.DivIcon {
  const size = selected ? "large" : resolveCampSize(camp);
  const [iconWidth, iconHeight] = markerSizePx(size, selected);

  return L.divIcon({
    html: '<div class="react-map-marker-root"></div>',
    className: `react-map-marker-icon${selected ? " is-selected" : ""}${isCampDisabled(camp) ? " is-disabled" : ""}`,
    iconSize: [iconWidth, iconHeight],
    iconAnchor: [iconWidth / 2, iconHeight - 14],
    popupAnchor: [0, -(iconHeight - 30)],
  });
}

export function mountCampMarker(
  marker: L.Marker,
  camp: ApiCamp,
  selected: boolean,
  onClick: () => void,
): Root | null {
  const markerElement = marker.getElement();
  if (!markerElement) return null;
  const host = markerElement.querySelector(".react-map-marker-root");
  if (!(host instanceof HTMLDivElement)) return null;

  const root = createRoot(host);
  root.render(
    createElement(
      "div",
      {
        className: `react-map-marker-shell${selected ? " is-selected" : ""}${isCampDisabled(camp) ? " is-disabled" : ""}`,
      },
      createElement(MapMarker, {
        type: resolveCampKind(camp),
        price: markerPriceLabel(camp),
        isVIP: isCampVip(camp),
        onClick,
      }),
    ),
  );
  return root;
}
