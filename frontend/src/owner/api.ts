export type OwnerProfile = {
  id: number;
  email: string;
  display_name: string;
  company?: string | null;
  phone?: string | null;
  telegram?: string | null;
  whatsapp?: string | null;
  max?: string | null;
  preferred_contact_type?: string | null;
  account_status: string;
  last_login?: string | null;
  created_at?: string | null;
};

export type EntityKindKey =
  | "accommodation"
  | "service"
  | "activity"
  | "food"
  | "transport"
  | "rental"
  | "guide"
  | "event"
  | "sight"
  | "excursion";

export type EntityKind = {
  id: number;
  key: EntityKindKey;
  slug: EntityKindKey;
  name: string;
  plural_name: string;
  marker_key: string;
  icon_key: string;
  sort_order: number;
};

export type EntityType = {
  id: number;
  slug: string;
  name: string;
  plural_name: string;
  marker_key: string;
  icon_key: string;
  sort_order: number;
  entity_kind: EntityKindKey;
  schema_key: string;
  schema_version: number;
  is_active?: boolean;
};

export type EntitySchemaField = {
  key: string;
  label: string;
  type: "string" | "integer" | "number" | "boolean" | "enum" | "string_list";
  section: string;
  public: boolean;
  required: boolean;
  min?: number;
  max?: number;
  max_length?: number;
  max_items?: number;
  options?: Array<string | number | boolean>;
  unit?: string | null;
};

export type EntitySchema = {
  key: string;
  version: number;
  name: string;
  entity_kind: EntityKindKey;
  fields: EntitySchemaField[];
  sections: Array<{
    key: string;
    title: string;
    component: string;
    fields: string[];
  }>;
  validation: Record<string, unknown>;
  display: Record<string, unknown>;
  schema_org_type: string;
};

export type EntityCatalog = {
  entityKinds: EntityKind[];
  entityTypes: EntityType[];
  entitySchemas: EntitySchema[];
};

export type OwnerEntityCreatePayload = {
  entity_kind: EntityKindKey;
  subtype: string;
  name: string;
  short_description?: string | null;
  region?: string | null;
  district?: string | null;
  city?: string | null;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  attributes: Record<string, unknown>;
  min_price?: number | null;
  price_mode: "from" | "fixed" | "request" | "free" | "none";
  currency: string;
};

const ENTITY_KIND_KEYS = new Set<EntityKindKey>([
  "accommodation",
  "service",
  "activity",
  "food",
  "transport",
  "rental",
  "guide",
  "event",
  "sight",
  "excursion",
]);
const ENTITY_FIELD_TYPES = new Set<EntitySchemaField["type"]>([
  "string",
  "integer",
  "number",
  "boolean",
  "enum",
  "string_list",
]);
const SAFE_KEY = /^[a-z][a-z0-9_-]{0,63}$/;

function asObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function asEntityKindKey(value: unknown): EntityKindKey | null {
  const key = String(value || "").trim().toLowerCase() as EntityKindKey;
  return ENTITY_KIND_KEYS.has(key) ? key : null;
}

/**
 * Treat the server registry as untrusted configuration. Only the declarative
 * field vocabulary understood by the client reaches the schema-driven form.
 */
export function adaptEntityCatalog(
  rawKinds: unknown,
  rawTypes: unknown,
  rawSchemas: unknown,
): EntityCatalog {
  const entityKinds = (Array.isArray(rawKinds) ? rawKinds : []).flatMap((raw) => {
    const item = asObject(raw);
    const key = asEntityKindKey(item?.key ?? item?.slug);
    if (!item || !key || !Number.isInteger(Number(item.id))) return [];
    return [{
      id: Number(item.id),
      key,
      slug: key,
      name: String(item.name || key),
      plural_name: String(item.plural_name || item.name || key),
      marker_key: String(item.marker_key || "default"),
      icon_key: String(item.icon_key || "default"),
      sort_order: Number(item.sort_order || 0),
    }];
  });
  const entityTypes = (Array.isArray(rawTypes) ? rawTypes : []).flatMap((raw) => {
    const item = asObject(raw);
    const kind = asEntityKindKey(item?.entity_kind);
    const slug = String(item?.slug || "").trim().toLowerCase();
    const schemaKey = String(item?.schema_key || "").trim().toLowerCase();
    if (!item || !kind || !SAFE_KEY.test(slug) || !SAFE_KEY.test(schemaKey)) return [];
    return [{
      id: Number(item.id),
      slug,
      name: String(item.name || slug),
      plural_name: String(item.plural_name || item.name || slug),
      marker_key: String(item.marker_key || "default"),
      icon_key: String(item.icon_key || "default"),
      sort_order: Number(item.sort_order || 0),
      entity_kind: kind,
      schema_key: schemaKey,
      schema_version: Math.max(1, Number(item.schema_version || 1)),
      is_active: item.is_active !== false,
    }];
  }).filter((item) => Number.isInteger(item.id) && item.id > 0);
  const entitySchemas = (Array.isArray(rawSchemas) ? rawSchemas : []).flatMap((raw) => {
    const item = asObject(raw);
    const key = String(item?.key || "").trim().toLowerCase();
    const kind = asEntityKindKey(item?.entity_kind);
    if (!item || !kind || !SAFE_KEY.test(key)) return [];
    const fields = (Array.isArray(item.fields) ? item.fields : []).flatMap((rawField) => {
      const field = asObject(rawField);
      const fieldKey = String(field?.key || "").trim().toLowerCase();
      const fieldType = String(field?.type || "").trim().toLowerCase() as EntitySchemaField["type"];
      if (!field || !SAFE_KEY.test(fieldKey) || !ENTITY_FIELD_TYPES.has(fieldType)) return [];
      const options = Array.isArray(field.options)
        ? field.options.filter((option): option is string | number | boolean =>
          ["string", "number", "boolean"].includes(typeof option))
        : undefined;
      return [{
        key: fieldKey,
        label: String(field.label || fieldKey),
        type: fieldType,
        section: String(field.section || "details"),
        public: field.public !== false,
        required: field.required === true,
        min: typeof field.min === "number" ? field.min : undefined,
        max: typeof field.max === "number" ? field.max : undefined,
        max_length: typeof field.max_length === "number" ? field.max_length : undefined,
        max_items: typeof field.max_items === "number" ? field.max_items : undefined,
        options,
        unit: typeof field.unit === "string" ? field.unit : null,
      }];
    });
    const allowedFields = new Set(fields.map((field) => field.key));
    const sections = (Array.isArray(item.sections) ? item.sections : []).flatMap((rawSection) => {
      const section = asObject(rawSection);
      const sectionKey = String(section?.key || "").trim().toLowerCase();
      if (!section || !SAFE_KEY.test(sectionKey)) return [];
      return [{
        key: sectionKey,
        title: String(section.title || "Характеристики"),
        component: String(section.component || "facts"),
        fields: (Array.isArray(section.fields) ? section.fields : [])
          .map(String)
          .filter((field) => allowedFields.has(field)),
      }];
    });
    return [{
      key,
      version: Math.max(1, Number(item.version || 1)),
      name: String(item.name || key),
      entity_kind: kind,
      fields,
      sections,
      validation: asObject(item.validation) || {},
      display: asObject(item.display) || {},
      schema_org_type: String(item.schema_org_type || "LocalBusiness"),
    }];
  });
  return { entityKinds, entityTypes, entitySchemas };
}

export type QualityCheck = {
  key: string;
  complete: boolean;
  label: string;
  weight: number;
};

export type CardQuality = {
  score: number;
  checklist: QualityCheck[];
  recommendations: string[];
  health: Array<{ key: string; level: "good" | "warning" | "danger"; label: string }>;
};

export type OwnerCamp = {
  id: number;
  name: string;
  slug?: string | null;
  place_type_name?: string | null;
  subtype?: string | null;
  entity_kind?: EntityKindKey | null;
  entity_kind_name?: string | null;
  schema_key?: string | null;
  schema_version?: number | null;
  publication_status: string;
  role_key: string;
  is_primary: boolean;
  pending_changes: number;
  quality: CardQuality;
  statistics: Record<string, number | string | null>;
};

export type ChangeDiff = {
  field: string;
  label: string;
  before: unknown;
  after: unknown;
};

export type OwnerChange = {
  id: number;
  public_number: string;
  camp_id: number;
  camp_name: string;
  status: string;
  status_label: string;
  content_version: number;
  schema_key?: string | null;
  schema_version?: number | null;
  proposed_payload?: Record<string, unknown>;
  published_snapshot?: Record<string, unknown>;
  diff_payload?: ChangeDiff[];
  diff_count?: number;
  moderator_comment?: string | null;
  moderator_name?: string | null;
  submitted_at?: string | null;
  decided_at?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
  history?: Array<{
    id: number;
    summary: string;
    comment?: string | null;
    new_status: string;
    created_at: string;
  }>;
  staged_media?: Array<{
    id: number;
    public_preview_url?: string | null;
    is_cover: boolean;
    scope: string;
    action?: "add" | "remove";
    target_media_id?: number | null;
  }>;
};

export type OwnerDashboard = {
  features: {
    change_requests: boolean;
    entity_creation?: boolean;
    universal_catalog?: boolean;
  };
  owner: OwnerProfile;
  profile_statistics: {
    objects_count: number;
    approved_changes: number;
    pending_changes: number;
    rejected_changes: number;
  };
  camps: OwnerCamp[];
  attention: Array<{ camp_id: number; camp_name: string; message: string }>;
  pending_changes: OwnerChange[];
  object_pagination: {
    limit: number;
    offset: number;
    total: number;
    has_more: boolean;
  };
  activity: Array<{
    id: number;
    created_at: string;
    type: string;
    description: string;
    camp_id?: number | null;
    action_url?: string | null;
  }>;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  const payload = (await response.json().catch(() => ({}))) as T & { detail?: string };
  if (!response.ok) {
    throw new ApiError(payload.detail || `Ошибка запроса (${response.status})`, response.status);
  }
  return payload;
}

export const ownerApi = {
  session: () => apiRequest<{ authenticated: true; owner: OwnerProfile }>("/api/owner/auth/session"),
  login: (email: string, password: string) =>
    apiRequest<{ owner: OwnerProfile }>("/api/owner/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => apiRequest("/api/owner/auth/logout", { method: "POST" }),
  forgot: (email: string) =>
    apiRequest<{ message: string }>("/api/owner/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  reset: (token: string, password: string) =>
    apiRequest<{ message: string }>("/api/owner/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),
  dashboard: () => apiRequest<OwnerDashboard & { ok: true }>("/api/owner/dashboard"),
  camps: (limit = 20, offset = 0) =>
    apiRequest<{
      camps: OwnerCamp[];
      pagination: OwnerDashboard["object_pagination"];
    }>(`/api/owner/camps?limit=${limit}&offset=${offset}`),
  changes: (limit = 30, offset = 0) =>
    apiRequest<{
      changes: OwnerChange[];
      pagination: { limit: number; offset: number; total: number; has_more: boolean };
    }>(`/api/owner/changes?limit=${limit}&offset=${offset}`),
  camp: (id: number) =>
    apiRequest<{
      camp: Record<string, unknown>;
      entity?: Record<string, unknown>;
      entity_schema?: EntitySchema | null;
      quality: CardQuality;
      changes: OwnerChange[];
      activity: OwnerDashboard["activity"];
      amenity_catalog: Array<{ id: number; name: string; category: string }>;
    }>(
      `/api/owner/camps/${id}`,
    ),
  entityCatalog: async () => {
    const [kinds, types, schemas] = await Promise.all([
      apiRequest<unknown>("/api/public/entity-kinds"),
      apiRequest<unknown>("/api/public/entity-types"),
      apiRequest<unknown>("/api/public/entity-schemas"),
    ]);
    return adaptEntityCatalog(kinds, types, schemas);
  },
  entities: (limit = 20, offset = 0) =>
    apiRequest<{
      entities: OwnerCamp[];
      pagination: OwnerDashboard["object_pagination"];
    }>(`/api/owner/entities?limit=${limit}&offset=${offset}`),
  createEntity: (payload: OwnerEntityCreatePayload) =>
    apiRequest<{
      entity: {
        id: number;
        entity_id?: number;
        name: string;
        entity_kind: EntityKindKey;
        subtype: string;
      };
      change: OwnerChange;
    }>("/api/owner/entities", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createChange: (campId: number) =>
    apiRequest<{ change: OwnerChange; created: boolean }>(`/api/owner/camps/${campId}/changes`, { method: "POST" }),
  getChange: (changeId: number) =>
    apiRequest<{ change: OwnerChange }>(`/api/owner/changes/${changeId}`),
  saveChange: (changeId: number, contentVersion: number, proposedPayload: Record<string, unknown>) =>
    apiRequest<{ change: OwnerChange }>(`/api/owner/changes/${changeId}`, {
      method: "PATCH",
      body: JSON.stringify({ content_version: contentVersion, proposed_payload: proposedPayload }),
    }),
  submitChange: (
    changeId: number,
    contentVersion: number,
    proposedPayload: Record<string, unknown>,
  ) =>
    apiRequest<{ change: OwnerChange }>(`/api/owner/changes/${changeId}/submit`, {
      method: "POST",
      body: JSON.stringify({
        content_version: contentVersion,
        proposed_payload: proposedPayload,
      }),
    }),
  withdrawChange: (changeId: number) =>
    apiRequest<{ change: OwnerChange }>(`/api/owner/changes/${changeId}/withdraw`, { method: "POST" }),
  uploadMedia: (changeId: number, body: FormData) =>
    apiRequest<{ media: { id: number; url: string; thumbnail_url: string } }>(
      `/api/owner/changes/${changeId}/media`,
      { method: "POST", body },
    ),
  deleteStagedMedia: (changeId: number, mediaId: number) =>
    apiRequest(`/api/owner/changes/${changeId}/media/${mediaId}`, { method: "DELETE" }),
  removePublishedMedia: (changeId: number, mediaId: number) =>
    apiRequest(`/api/owner/changes/${changeId}/published-media/${mediaId}`, { method: "DELETE" }),
  unpublish: (campId: number) =>
    apiRequest(`/api/owner/camps/${campId}/unpublish`, { method: "POST" }),
  updateProfile: (payload: Partial<OwnerProfile>) =>
    apiRequest<{ owner: OwnerProfile }>("/api/owner/profile", {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  changePassword: (currentPassword: string, newPassword: string) =>
    apiRequest<{ message: string }>("/api/owner/profile/password", {
      method: "PATCH",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    }),
};
