import L from "leaflet";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { Root } from "react-dom/client";
import { createCampDivIcon, mountCampMarker } from "../lib/leafletMarkers";
import type { ApiCamp } from "../types/catalog";

export type MapCanvasHandle = {
  fitToCamps: () => void;
  locateUser: () => void;
  focusCamp: (camp: ApiCamp | null) => void;
};

type MapCanvasProps = {
  camps: ApiCamp[];
  selectedCampId: number | null;
  onSelectCamp: (campId: number) => void;
};

const DEFAULT_CENTER: [number, number] = [51.83, 107.58];
const DEFAULT_ZOOM = 9;

export const MapCanvas = forwardRef<MapCanvasHandle, MapCanvasProps>(function MapCanvas(
  { camps, selectedCampId, onSelectCamp },
  ref,
) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);
  const markerRootsRef = useRef<Root[]>([]);
  const userLayerRef = useRef<L.Layer | null>(null);
  const hasFittedRef = useRef(false);

  useEffect(() => {
    if (!rootRef.current || mapRef.current) return;

    const map = L.map(rootRef.current, {
      zoomControl: false,
      attributionControl: false,
    }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
    }).addTo(map);

    markersRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    const resizeObserver = new ResizeObserver(() => {
      map.invalidateSize(false);
    });
    resizeObserver.observe(rootRef.current);

    return () => {
      resizeObserver.disconnect();
      markerRootsRef.current.forEach((root) => root.unmount());
      markerRootsRef.current = [];
      map.remove();
      mapRef.current = null;
      markersRef.current = null;
      userLayerRef.current = null;
      hasFittedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const markersLayer = markersRef.current;
    if (!map || !markersLayer) return;

    markerRootsRef.current.forEach((root) => root.unmount());
    markerRootsRef.current = [];
    markersLayer.clearLayers();

    const bounds = L.latLngBounds([]);
    camps.forEach((camp) => {
      if (!Number.isFinite(camp.lat) || !Number.isFinite(camp.lng)) return;
      const marker = L.marker([Number(camp.lat), Number(camp.lng)], {
        icon: createCampDivIcon(camp, selectedCampId === camp.id),
        riseOnHover: true,
      });
      marker.setZIndexOffset(selectedCampId === camp.id ? 1000 : 0);
      marker.on("click", () => {
        onSelectCamp(camp.id);
      });
      marker.addTo(markersLayer);
      const root = mountCampMarker(marker, camp, selectedCampId === camp.id, () => onSelectCamp(camp.id));
      if (root) markerRootsRef.current.push(root);
      bounds.extend([Number(camp.lat), Number(camp.lng)]);
    });

    if (bounds.isValid() && !hasFittedRef.current) {
      map.fitBounds(bounds, { padding: [36, 36] });
      hasFittedRef.current = true;
    }
  }, [camps, onSelectCamp, selectedCampId]);

  useImperativeHandle(
    ref,
    () => ({
      fitToCamps() {
        const map = mapRef.current;
        if (!map || camps.length === 0) return;
        const bounds = L.latLngBounds(
          camps
            .filter((camp) => Number.isFinite(camp.lat) && Number.isFinite(camp.lng))
            .map((camp) => [Number(camp.lat), Number(camp.lng)] as [number, number]),
        );
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [36, 36] });
        }
      },
      locateUser() {
        const map = mapRef.current;
        if (!map || !navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
          ({ coords }) => {
            userLayerRef.current?.remove();
            const point = L.circleMarker([coords.latitude, coords.longitude], {
              radius: 11,
              weight: 3,
              color: "#ffffff",
              fillColor: "#2f6d59",
              fillOpacity: 0.96,
            }).addTo(map);
            userLayerRef.current = point;
            map.flyTo([coords.latitude, coords.longitude], 12, { duration: 0.5 });
          },
          () => {},
          { enableHighAccuracy: true, timeout: 8000 },
        );
      },
      focusCamp(camp) {
        const map = mapRef.current;
        if (!map || !camp || !Number.isFinite(camp.lat) || !Number.isFinite(camp.lng)) return;
        map.flyTo([Number(camp.lat), Number(camp.lng)], Math.max(map.getZoom(), 11), {
          duration: 0.45,
        });
      },
    }),
    [camps],
  );

  return <div className="map-canvas" ref={rootRef} />;
});
