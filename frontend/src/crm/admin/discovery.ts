export type EditorialStatus = "draft" | "in_review" | "published" | "disabled" | "archived";

export type CollectionItem = {
  entity_id: number;
  position: number;
  editorial_note?: string | null;
  custom_title?: string | null;
  custom_description?: string | null;
  name?: string | null;
};

export type CollectionRule = {
  conditions: Record<string, unknown>;
  sort: "editorial" | "newest" | "name";
  limit: number;
  position: number;
};

export type EditorialCollection = {
  id: number;
  slug: string;
  title: string;
  short_description: string;
  description?: string | null;
  cover_url?: string | null;
  collection_type: "manual" | "rule_based" | "mixed";
  status: EditorialStatus;
  region?: string | null;
  city?: string | null;
  season?: string | null;
  audience?: string | null;
  editorial_weight: number;
  editorial_exception: boolean;
  seo_title?: string | null;
  seo_description?: string | null;
  published_at?: string | null;
  updated_at?: string | null;
  content_version: number;
  items: CollectionItem[];
  rules: CollectionRule[];
};

export type RoutePoint = {
  entity_id?: number | null;
  position: number;
  custom_title?: string | null;
  title?: string | null;
  description?: string | null;
  lat?: number | null;
  lng?: number | null;
  stay_minutes?: number | null;
  overnight: boolean;
  transport_note?: string | null;
};

export type TourismRoute = {
  id: number;
  slug: string;
  title: string;
  short_description: string;
  description?: string | null;
  cover_url?: string | null;
  route_type: string;
  transport_mode: string;
  duration_minutes?: number | null;
  duration_text?: string | null;
  distance_km?: number | null;
  difficulty?: string | null;
  season?: string | null;
  region?: string | null;
  city?: string | null;
  start_lat?: number | null;
  start_lng?: number | null;
  end_lat?: number | null;
  end_lng?: number | null;
  geojson?: Record<string, unknown> | null;
  status: EditorialStatus;
  editorial_weight: number;
  editorial_exception: boolean;
  seo_title?: string | null;
  seo_description?: string | null;
  published_at?: string | null;
  updated_at?: string | null;
  content_version: number;
  points: RoutePoint[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.detail || payload?.error?.message;
    throw new Error(typeof message === "string" ? message : "Не удалось выполнить запрос");
  }
  return payload as T;
}

function query(params: Record<string, string>) {
  const value = new URLSearchParams(Object.entries(params).filter(([, item]) => item));
  return value.size ? `?${value}` : "";
}

export const discoveryAdminApi = {
  collections: {
    list: (params: { search: string; status: string }, signal?: AbortSignal) =>
      request<EditorialCollection[]>(`/api/superadmin/collections${query(params)}`, { signal }),
    detail: (id: number, signal?: AbortSignal) => request<EditorialCollection>(`/api/superadmin/collections/${id}`, { signal }),
    save: (id: number | null, payload: Omit<EditorialCollection, "id" | "published_at" | "updated_at">) =>
      request<EditorialCollection>(id ? `/api/superadmin/collections/${id}` : "/api/superadmin/collections", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(payload),
      }),
    preview: (id: number) => request<Record<string, unknown>>(`/api/superadmin/collections/${id}/preview`),
  },
  routes: {
    list: (params: { search: string; status: string }, signal?: AbortSignal) =>
      request<TourismRoute[]>(`/api/superadmin/routes${query(params)}`, { signal }),
    detail: (id: number, signal?: AbortSignal) => request<TourismRoute>(`/api/superadmin/routes/${id}`, { signal }),
    save: (id: number | null, payload: Omit<TourismRoute, "id" | "published_at" | "updated_at">) =>
      request<TourismRoute>(id ? `/api/superadmin/routes/${id}` : "/api/superadmin/routes", {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(payload),
      }),
    preview: (id: number) => request<Record<string, unknown>>(`/api/superadmin/routes/${id}/preview`),
  },
};
