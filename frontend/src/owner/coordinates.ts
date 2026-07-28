export type OwnerCoordinates = {
  lat: number | null;
  lng: number | null;
  error: string | null;
};

function isBlank(value: unknown) {
  return value === null || value === undefined || String(value).trim() === "";
}

export function parseOwnerCoordinates(latValue: unknown, lngValue: unknown): OwnerCoordinates {
  const latBlank = isBlank(latValue);
  const lngBlank = isBlank(lngValue);
  if (latBlank && lngBlank) return { lat: null, lng: null, error: null };
  if (latBlank || lngBlank) {
    return {
      lat: null,
      lng: null,
      error: "Укажите обе координаты: широту и долготу.",
    };
  }
  const lat = Number(String(latValue).trim().replace(",", "."));
  const lng = Number(String(lngValue).trim().replace(",", "."));
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return {
      lat: null,
      lng: null,
      error: "Координаты должны быть числами.",
    };
  }
  if (lat < -90 || lat > 90) {
    return {
      lat: null,
      lng: null,
      error: "Широта должна быть от −90 до 90.",
    };
  }
  if (lng < -180 || lng > 180) {
    return {
      lat: null,
      lng: null,
      error: "Долгота должна быть от −180 до 180.",
    };
  }
  return { lat, lng, error: null };
}
