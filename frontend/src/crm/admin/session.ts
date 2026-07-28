import type { EntityKind, EntityKindKey, EntitySchema } from "../../owner/api";

export type SuperadminSessionResponse = {
  ok: boolean;
  authenticated: boolean;
  account?: SuperadminPrincipal | null;
};

export type SuperadminLoginPayload = {
  login: string;
  password: string;
};

export type SuperadminPrincipal = {
  id?: number | null;
  login?: string | null;
  display_name?: string | null;
  is_root?: boolean;
  is_active?: boolean;
  telegram_chat_id?: number | null;
  telegram_username?: string | null;
  has_telegram_link?: boolean;
};

export type SuperadminBaseStatus = "active" | "disabled" | "archived";

export type SuperadminLinkedAdmin = {
  id: number;
  display_name?: string | null;
  login?: string | null;
  is_active?: boolean | null;
};

export type SuperadminBaseSummary = {
  id: number;
  name?: string | null;
  slug?: string | null;
  publication_status?: string | null;
  short_description?: string | null;
  place_type_id?: number | null;
  place_type_slug?: string | null;
  place_type_name?: string | null;
  entity_kind?: EntityKindKey | null;
  entity_kind_name?: string | null;
  schema_key?: string | null;
  schema_version?: number | null;
  visibility?: string | null;
  price_mode?: string | null;
  address?: string | null;
  lake_name?: string | null;
  status?: string | null;
  owner?: string | null;
  manager?: string | null;
  min_price?: number | null;
  rooms_count?: number | null;
  beds_count?: number | null;
  lat?: number | null;
  lng?: number | null;
  archived_at?: string | null;
  linked_admins?: SuperadminLinkedAdmin[];
};

export type SuperadminPlaceType = {
  id: number;
  slug: string;
  name: string;
  plural_name: string;
  marker_key: string;
  icon_key: string;
  sort_order: number;
  is_active?: boolean;
  config?: Record<string, unknown>;
  entity_kind?: EntityKindKey | null;
  schema_key?: string | null;
  schema_version?: number | null;
};

export type SuperadminEntityKind = EntityKind;
export type SuperadminEntitySchema = EntitySchema;

export type SuperadminAmenity = {
  id: number;
  slug: string;
  name: string;
  category: string;
  icon_key: string;
  sort_order: number;
  is_active?: boolean;
  value?: unknown;
};

export type SuperadminPlaceContact = {
  id?: number;
  contact_type: "phone" | "email" | "website" | "telegram" | "whatsapp" | "max" | "vk" | "route" | "other";
  label?: string | null;
  value: string;
  public_url?: string | null;
  is_public?: boolean;
  sort_order?: number;
};

export type SuperadminCampPhoto = {
  id?: number;
  url: string;
  sort?: number | null;
  cover?: number | boolean | null;
};

export type SuperadminMediaItem = {
  id?: number;
  media_type: "image" | "video";
  url: string;
  poster_url?: string | null;
  source_kind?: "upload" | "external" | null;
  moderation_status?: string | null;
  moderation_comment?: string | null;
  cover?: boolean | number | null;
  sort?: number | null;
};

export type SuperadminRoom = {
  id?: number;
  camp_id?: number | null;
  name?: string | null;
  room_type?: string | null;
  floors?: number | null;
  floor?: number | null;
  beds_single?: number | null;
  beds_double?: number | null;
  bath_type?: string | null;
  wc_type?: string | null;
  bbq_type?: string | null;
  kitchen_type?: string | null;
  gazebo_type?: string | null;
  terrace_type?: string | null;
  pool_type?: string | null;
  balcony_type?: string | null;
  has_ac?: number | boolean | null;
  capacity?: number | null;
  price?: number | null;
  price_adult?: number | null;
  price_child?: number | null;
  discount_pct?: number | null;
  discount_from_nights?: number | null;
  description?: string | null;
  photo_main?: string | null;
  photos?: Array<{ url: string; cover: boolean | number; sort: number }>;
  media?: SuperadminMediaItem[];
};

export type SuperadminBaseEditor = {
  camp: {
    id: number;
    name?: string | null;
    slug?: string | null;
    place_type_id?: number | null;
    entity_kind?: EntityKindKey | null;
    subtype?: string | null;
    schema_key?: string | null;
    schema_version?: number | null;
    attributes?: Record<string, unknown> | null;
    visibility?: string | null;
    price_mode?: string | null;
    currency?: string | null;
    seasonality_key?: string | null;
    working_hours_mode?: string | null;
    short_description?: string | null;
    region?: string | null;
    district?: string | null;
    city?: string | null;
    locality?: string | null;
    seasonality?: string | null;
    working_hours?: Record<string, unknown> | null;
    publication_status?: string | null;
    confirmed_at?: string | null;
    video_urls?: string[] | null;
    metadata?: Record<string, unknown> | null;
    lake_name?: string | null;
    address?: string | null;
    lat?: number | null;
    lng?: number | null;
    status?: string | null;
    emoji?: string | null;
    emoji_size?: string | null;
    description?: string | null;
    housing_type?: string | null;
    owner?: string | null;
    manager?: string | null;
    admin_phones?: string | null;
    site_url?: string | null;
    min_price?: number | null;
    bbq_count?: number | null;
    bbq_shared_count?: number | null;
    bath_count?: number | null;
    sauna_count?: number | null;
    pools_private_count?: number | null;
    pools_shared_count?: number | null;
    beds_count?: number | null;
  };
  photos: SuperadminCampPhoto[];
  media?: SuperadminMediaItem[];
  rooms: SuperadminRoom[];
  linked_accounts: Array<{
    id: number;
    login?: string | null;
    display_name?: string | null;
    is_active?: boolean | null;
  }>;
  place_types: SuperadminPlaceType[];
  entity_types?: SuperadminPlaceType[];
  entity_kinds?: SuperadminEntityKind[];
  entity_schemas?: SuperadminEntitySchema[];
  amenities: SuperadminAmenity[];
  selected_amenities: SuperadminAmenity[];
  contacts: SuperadminPlaceContact[];
};

export type SuperadminAccount = {
  id: number;
  login: string;
  display_name: string;
  phone?: string | null;
  is_active: boolean;
  default_role_key?: string | null;
  created_at?: string | null;
  archived_at?: string | null;
  camps: Array<{ camp_id: number; camp_name?: string | null }>;
};

export type SuperadminAccountPayload = {
  login: string;
  password?: string;
  display_name: string;
  phone?: string;
  is_active?: boolean;
  camp_ids: number[];
  default_role_key?: string;
};

export type SuperadminUserSummary = {
  id: number;
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  phone_verified?: boolean;
  email_verified?: boolean;
  created_at?: string | null;
  bookings_count?: number;
  last_booking_at?: string | null;
};

export type SuperadminUserHistoryResponse = {
  user: {
    id: number;
    name?: string | null;
    phone?: string | null;
    email?: string | null;
    role?: string | null;
    phone_verified?: boolean;
    email_verified?: boolean;
    created_at?: string | null;
  };
  bookings: Array<{
    id: number;
    camp_id?: number | null;
    camp_name?: string | null;
    room_id?: number | null;
    room_name?: string | null;
    check_in?: string | null;
    check_out?: string | null;
    guests_count?: number | null;
    status?: string | null;
    source?: string | null;
    comment?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
  }>;
  events: Array<{
    id: number;
    event_type: string;
    payload?: unknown;
    created_at?: string | null;
  }>;
  payments: unknown[];
};

export type SuperadminSystemEvent = {
  id: number;
  camp_id?: number | null;
  camp_name?: string | null;
  recipient_scope?: string | null;
  event_type?: string | null;
  title?: string | null;
  body?: string | null;
  action_url?: string | null;
  action_payload?: unknown;
  severity?: string | null;
  status?: string | null;
  metadata?: unknown;
  created_at?: string | null;
  read_at?: string | null;
  closed_at?: string | null;
};

export type SuperadminMediaQueueItem = {
  entity_type: "camp" | "room";
  media_id: number;
  camp_id?: number | null;
  camp_name?: string | null;
  room_id?: number | null;
  room_name?: string | null;
  media_type: "image" | "video";
  url: string;
  poster_url?: string | null;
  source_kind?: "upload" | "external" | null;
  moderation_status?: string | null;
  moderation_comment?: string | null;
  cover?: boolean;
  sort?: number | null;
  approved_at?: string | null;
  created_at?: string | null;
};

export type SuperadminRootAccount = {
  id: number;
  login: string;
  display_name: string;
  phone?: string | null;
  is_active: boolean;
  is_root: boolean;
  telegram_chat_id?: number | null;
  telegram_username?: string | null;
  created_by_id?: number | null;
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SuperadminRootAccountPayload = {
  login: string;
  password?: string;
  display_name: string;
  phone?: string;
  is_active?: boolean;
  is_root?: boolean;
};

export type SuperadminAuditRecord = {
  id: number;
  actor_type: string;
  actor_id?: number | null;
  actor_display?: string | null;
  camp_id?: number | null;
  camp_name?: string | null;
  target_type: string;
  target_id?: string | null;
  action_type: string;
  action_label: string;
  changed_field?: string | null;
  old_value?: unknown;
  new_value?: unknown;
  comment?: string | null;
  is_sensitive?: boolean;
  was_auto_applied?: boolean;
  metadata?: unknown;
  created_at?: string | null;
};

export type PlacementSubmissionSummary = {
  id: number;
  public_number: string;
  status: string;
  place_name?: string | null;
  place_type_id?: number | null;
  place_type_name?: string | null;
  region?: string | null;
  applicant_role?: string | null;
  applicant_name?: string | null;
  assigned_admin_id?: number | null;
  assigned_admin_name?: string | null;
  spam_score: number;
  media_count: number;
  created_at: string;
  submitted_at?: string | null;
  updated_at: string;
  content_version: number;
  published_camp_id?: number | null;
};

export type PlacementSubmissionDetail = PlacementSubmissionSummary & {
  [key: string]: unknown;
  applicant_phone?: string | null;
  applicant_email?: string | null;
  applicant_telegram?: string | null;
  applicant_whatsapp?: string | null;
  applicant_max?: string | null;
  preferred_contact_type?: string | null;
  address?: string | null;
  city?: string | null;
  locality?: string | null;
  lat?: number | null;
  lng?: number | null;
  short_description?: string | null;
  description?: string | null;
  public_contacts?: Array<Record<string, unknown>>;
  amenities?: Array<Record<string, unknown>>;
  rooms_payload?: Array<Record<string, unknown>>;
  video_urls?: string[];
  consents?: Record<string, boolean>;
  media?: Array<Record<string, unknown>>;
  history?: Array<Record<string, unknown>>;
  notes?: Array<Record<string, unknown>>;
  audit?: Array<Record<string, unknown>>;
};

function buildQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    query.set(key, String(value));
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : "";
}

async function parseJson(response: Response) {
  return (await response.json().catch(() => null)) as Record<string, unknown> | null;
}

async function assertOk(response: Response) {
  if (response.ok) {
    return;
  }
  const payload = await parseJson(response);
  throw new Error(typeof payload?.detail === "string" ? payload.detail : "Не удалось выполнить запрос");
}

async function submissionRequest(path: string, init?: RequestInit) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  await assertOk(response);
  return (await response.json()) as Record<string, unknown>;
}

export async function fetchPlacementSubmissions(
  params: {
    status?: string;
    search?: string;
    spamRisk?: string;
    placeTypeId?: string;
    region?: string;
    applicantRole?: string;
    assignedAdminId?: string;
    hasPhotos?: string;
    dateFrom?: string;
    dateTo?: string;
    limit?: number;
    offset?: number;
    signal?: AbortSignal;
  } = {},
) {
  const response = await fetch(
    `/api/superadmin/submissions${buildQuery({
      status: params.status,
      q: params.search,
      spam_risk: params.spamRisk,
      place_type_id: params.placeTypeId,
      region: params.region,
      applicant_role: params.applicantRole,
      assigned_admin_id: params.assignedAdminId,
      has_photos: params.hasPhotos,
      date_from: params.dateFrom,
      date_to: params.dateTo,
      limit: params.limit ?? 25,
      offset: params.offset ?? 0,
    })}`,
    { credentials: "same-origin", signal: params.signal },
  );
  await assertOk(response);
  return (await response.json()) as {
    ok: boolean;
    items: PlacementSubmissionSummary[];
    total: number;
    limit: number;
    offset: number;
  };
}

export async function fetchPlacementSubmission(submissionId: number, signal?: AbortSignal) {
  const payload = await submissionRequest(`/api/superadmin/submissions/${submissionId}`, { signal });
  return payload.submission as PlacementSubmissionDetail;
}

export async function updatePlacementSubmission(
  submissionId: number,
  payload: Record<string, unknown>,
) {
  return submissionRequest(`/api/superadmin/submissions/${submissionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function changePlacementSubmissionStatus(
  submissionId: number,
  status: string,
  payload: { contentVersion: number; publicComment?: string; internalComment?: string },
) {
  return submissionRequest(`/api/superadmin/submissions/${submissionId}/status`, {
    method: "POST",
    body: JSON.stringify({
      status,
      content_version: payload.contentVersion,
      public_comment: payload.publicComment,
      internal_comment: payload.internalComment,
    }),
  });
}

export async function runPlacementSubmissionAction(
  submissionId: number,
  action: "request-clarification" | "approve" | "reject" | "archive",
  status: string,
  payload: { contentVersion: number; publicComment?: string; internalComment?: string },
) {
  return submissionRequest(`/api/superadmin/submissions/${submissionId}/${action}`, {
    method: "POST",
    body: JSON.stringify({
      status,
      content_version: payload.contentVersion,
      public_comment: payload.publicComment,
      internal_comment: payload.internalComment,
    }),
  });
}

export async function addPlacementSubmissionNote(
  submissionId: number,
  text: string,
  isVisibleToApplicant = false,
) {
  return submissionRequest(`/api/superadmin/submissions/${submissionId}/notes`, {
    method: "POST",
    body: JSON.stringify({ text, is_visible_to_applicant: isVisibleToApplicant }),
  });
}

export async function createPlacementObjectDraft(submissionId: number, idempotencyKey: string) {
  return submissionRequest(`/api/superadmin/submissions/${submissionId}/create-object-draft`, {
    method: "POST",
    body: JSON.stringify({ idempotency_key: idempotencyKey }),
  });
}

async function parseSessionResponse(response: Response): Promise<SuperadminSessionResponse> {
  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(typeof payload?.detail === "string" ? payload.detail : "Не удалось выполнить запрос");
  }

  return {
    ok: Boolean(payload?.ok),
    authenticated: Boolean(payload?.authenticated),
    account: (payload?.account as SuperadminPrincipal | null | undefined) ?? null,
  };
}

export async function fetchSuperadminSession(signal?: AbortSignal) {
  const response = await fetch("/api/superadmin/session", {
    credentials: "same-origin",
    signal,
  });
  return parseSessionResponse(response);
}

export async function loginSuperadminSession(payload: SuperadminLoginPayload) {
  const response = await fetch("/api/superadmin/session", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseSessionResponse(response);
}

export async function logoutSuperadminSession() {
  const response = await fetch("/api/superadmin/session", {
    method: "DELETE",
    credentials: "same-origin",
  });
  return parseSessionResponse(response);
}

export async function issueSuperadminTelegramLink() {
  const response = await fetch("/api/superadmin/telegram-link", {
    method: "POST",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; code: string; command: string; deep_link: string | null };
}

export async function fetchSuperadminBases(
  params: { archivedOnly?: boolean; status?: string; search?: string; placeType?: string; entityKind?: string; publicationStatus?: string; signal?: AbortSignal } = {},
): Promise<SuperadminBaseSummary[]> {
  const response = await fetch(
    `/api/superadmin/camps${buildQuery({
      archived_only: params.archivedOnly ? true : undefined,
      status: params.status,
      search: params.search,
      place_type: params.placeType,
      entity_kind: params.entityKind,
      publication_status: params.publicationStatus,
    })}`,
    {
      credentials: "same-origin",
      signal: params.signal,
    },
  );
  await assertOk(response);
  return (await response.json()) as SuperadminBaseSummary[];
}

export async function fetchSuperadminEntities(
  params: {
    archivedOnly?: boolean;
    status?: string;
    search?: string;
    entityKind?: string;
    subtype?: string;
    publicationStatus?: string;
    signal?: AbortSignal;
  } = {},
): Promise<SuperadminBaseSummary[]> {
  const response = await fetch(
    `/api/superadmin/entities${buildQuery({
      archived_only: params.archivedOnly ? true : undefined,
      status: params.status,
      search: params.search,
      entity_kind: params.entityKind,
      subtype: params.subtype,
      publication_status: params.publicationStatus,
    })}`,
    { credentials: "same-origin", signal: params.signal },
  );
  await assertOk(response);
  return (await response.json()) as SuperadminBaseSummary[];
}

export async function fetchCatalogDictionaries(signal?: AbortSignal) {
  const [typesResponse, kindsResponse, schemasResponse, amenitiesResponse] = await Promise.all([
    fetch("/api/public/entity-types", { credentials: "same-origin", signal }),
    fetch("/api/public/entity-kinds", { credentials: "same-origin", signal }),
    fetch("/api/public/entity-schemas", { credentials: "same-origin", signal }),
    fetch("/api/public/amenities", { credentials: "same-origin", signal }),
  ]);
  await Promise.all([
    assertOk(typesResponse),
    assertOk(kindsResponse),
    assertOk(schemasResponse),
    assertOk(amenitiesResponse),
  ]);
  const placeTypes = (await typesResponse.json()) as SuperadminPlaceType[];
  return {
    placeTypes,
    entityTypes: placeTypes,
    entityKinds: (await kindsResponse.json()) as SuperadminEntityKind[],
    entitySchemas: (await schemasResponse.json()) as SuperadminEntitySchema[],
    amenities: (await amenitiesResponse.json()) as SuperadminAmenity[],
  };
}

export async function fetchSuperadminBaseEditor(campId: number, signal?: AbortSignal): Promise<SuperadminBaseEditor> {
  const response = await fetch(`/api/superadmin/camps/${campId}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as SuperadminBaseEditor;
}

export async function fetchSuperadminEntityEditor(entityId: number, signal?: AbortSignal): Promise<SuperadminBaseEditor> {
  const response = await fetch(`/api/superadmin/entities/${entityId}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as SuperadminBaseEditor;
}

export async function bulkUpdateSuperadminEntities(
  entityIds: number[],
  publicationStatus: "draft" | "disabled" | "published" | "archived",
) {
  const response = await fetch("/api/superadmin/entities/bulk", {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      entity_ids: [...new Set(entityIds)].filter((id) => Number.isInteger(id) && id > 0),
      publication_status: publicationStatus,
    }),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; items: SuperadminBaseSummary[] };
}

export async function createSuperadminCamp(payload: Record<string, unknown>) {
  const response = await fetch("/api/camps", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; id: number; publication_warnings?: string[] };
}

export async function updateSuperadminCamp(campId: number, payload: Record<string, unknown>) {
  const response = await fetch(`/api/camps/${campId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; id: number; publication_warnings?: string[] };
}

export async function createSuperadminEntity(payload: Record<string, unknown>) {
  const response = await fetch("/api/superadmin/entities", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; id: number; publication_warnings?: string[] };
}

export async function updateSuperadminEntity(entityId: number, payload: Record<string, unknown>) {
  const response = await fetch(`/api/superadmin/entities/${entityId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; id: number; publication_warnings?: string[] };
}

export async function updateSuperadminCampStatus(campId: number, status: SuperadminBaseStatus) {
  const response = await fetch(`/api/camps/${campId}/status`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ status }),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function deleteSuperadminCamp(campId: number) {
  const response = await fetch(`/api/camps/${campId}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function uploadSuperadminMedia(file: File, options: { campId?: number; roomIndex?: number } = {}) {
  const body = new FormData();
  body.set("file", file);
  if (options.campId) {
    body.set("camp_id", String(options.campId));
  }
  if (options.roomIndex !== undefined) {
    body.set("room_idx", String(options.roomIndex));
  }
  const response = await fetch("/api/upload", {
    method: "POST",
    credentials: "same-origin",
    body,
  });
  await assertOk(response);
  return (await response.json()) as { url: string };
}

export async function fetchSuperadminAccounts(signal?: AbortSignal): Promise<SuperadminAccount[]> {
  const response = await fetch("/api/superadmin/accounts", {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as SuperadminAccount[];
}

export async function createSuperadminAccount(payload: SuperadminAccountPayload) {
  const response = await fetch("/api/superadmin/accounts", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { status: string; admin_id: number };
}

export async function updateSuperadminAccount(accountId: number, payload: SuperadminAccountPayload) {
  const response = await fetch(`/api/superadmin/accounts/${accountId}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function deleteSuperadminAccount(accountId: number) {
  const response = await fetch(`/api/superadmin/accounts/${accountId}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function fetchSuperadminUsers(params: { search?: string; signal?: AbortSignal } = {}): Promise<SuperadminUserSummary[]> {
  const response = await fetch(`/api/superadmin/users${buildQuery({ search: params.search })}`, {
    credentials: "same-origin",
    signal: params.signal,
  });
  await assertOk(response);
  return (await response.json()) as SuperadminUserSummary[];
}

export async function fetchSuperadminUserHistory(userId: number, signal?: AbortSignal): Promise<SuperadminUserHistoryResponse> {
  const response = await fetch(`/api/superadmin/users/${userId}/history`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as SuperadminUserHistoryResponse;
}

export async function fetchSuperadminEvents(
  params: { search?: string; campId?: number | null; limit?: number; signal?: AbortSignal } = {},
): Promise<SuperadminSystemEvent[]> {
  const response = await fetch(
    `/api/superadmin/events${buildQuery({
      search: params.search,
      camp_id: params.campId ?? undefined,
      limit: params.limit,
    })}`,
    {
      credentials: "same-origin",
      signal: params.signal,
    },
  );
  await assertOk(response);
  return (await response.json()) as SuperadminSystemEvent[];
}

export async function fetchSuperadminMediaQueue(
  params: { search?: string; status?: string; limit?: number; signal?: AbortSignal } = {},
): Promise<SuperadminMediaQueueItem[]> {
  const response = await fetch(
    `/api/superadmin/media${buildQuery({
      search: params.search,
      status: params.status,
      limit: params.limit,
    })}`,
    {
      credentials: "same-origin",
      signal: params.signal,
    },
  );
  await assertOk(response);
  return (await response.json()) as SuperadminMediaQueueItem[];
}

export async function updateSuperadminMediaModeration(
  entityType: "camp" | "room",
  mediaId: number,
  payload: { status: "pending" | "approved" | "rejected"; comment?: string },
) {
  const response = await fetch(`/api/superadmin/media/${entityType}/${mediaId}/moderation`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function fetchRootSuperadminAccounts(
  params: { includeArchived?: boolean; signal?: AbortSignal } = {},
): Promise<SuperadminRootAccount[]> {
  const response = await fetch(
    `/api/superadmin/superadmins${buildQuery({ include_archived: params.includeArchived ? true : undefined })}`,
    {
      credentials: "same-origin",
      signal: params.signal,
    },
  );
  await assertOk(response);
  return (await response.json()) as SuperadminRootAccount[];
}

export async function createRootSuperadminAccount(payload: SuperadminRootAccountPayload) {
  const response = await fetch("/api/superadmin/superadmins", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { status: string; superadmin_id: number };
}

export async function updateRootSuperadminAccount(accountId: number, payload: SuperadminRootAccountPayload) {
  const response = await fetch(`/api/superadmin/superadmins/${accountId}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function archiveRootSuperadminAccount(accountId: number) {
  const response = await fetch(`/api/superadmin/superadmins/${accountId}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function restoreRootSuperadminAccount(accountId: number) {
  const response = await fetch(`/api/superadmin/superadmins/${accountId}/restore`, {
    method: "POST",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function fetchSuperadminAuditLog(
  params: {
    search?: string;
    actorType?: string;
    targetType?: string;
    campId?: number | null;
    limit?: number;
    signal?: AbortSignal;
  } = {},
): Promise<SuperadminAuditRecord[]> {
  const response = await fetch(
    `/api/superadmin/audit-log${buildQuery({
      search: params.search,
      actor_type: params.actorType,
      target_type: params.targetType,
      camp_id: params.campId ?? undefined,
      limit: params.limit,
    })}`,
    {
      credentials: "same-origin",
      signal: params.signal,
    },
  );
  await assertOk(response);
  return (await response.json()) as SuperadminAuditRecord[];
}
