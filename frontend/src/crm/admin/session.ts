export type SuperadminSessionResponse = {
  ok: boolean;
  authenticated: boolean;
};

export type SuperadminLoginPayload = {
  login: string;
  password: string;
};

export type SuperadminBaseStatus = "active" | "disabled" | "archived";

export type SuperadminLinkedAdmin = {
  id: number;
  display_name?: string | null;
  email?: string | null;
  is_active?: boolean | null;
};

export type SuperadminBaseSummary = {
  id: number;
  name?: string | null;
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

export type SuperadminCampPhoto = {
  id?: number;
  url: string;
  sort?: number | null;
  cover?: number | boolean | null;
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
};

export type SuperadminBaseEditor = {
  camp: {
    id: number;
    name?: string | null;
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
  rooms: SuperadminRoom[];
  linked_accounts: Array<{
    id: number;
    email?: string | null;
    display_name?: string | null;
    is_active?: boolean | null;
  }>;
};

export type SuperadminAccount = {
  id: number;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at?: string | null;
  camps: Array<{ camp_id: number; camp_name?: string | null }>;
};

export type SuperadminAccountPayload = {
  email: string;
  password?: string;
  display_name: string;
  is_active?: boolean;
  camp_ids: number[];
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

async function parseSessionResponse(response: Response): Promise<SuperadminSessionResponse> {
  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(typeof payload?.detail === "string" ? payload.detail : "Не удалось выполнить запрос");
  }

  return {
    ok: Boolean(payload?.ok),
    authenticated: Boolean(payload?.authenticated),
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

export async function fetchSuperadminBases(
  params: { archivedOnly?: boolean; status?: string; search?: string; signal?: AbortSignal } = {},
): Promise<SuperadminBaseSummary[]> {
  const response = await fetch(
    `/api/superadmin/camps${buildQuery({
      archived_only: params.archivedOnly ? true : undefined,
      status: params.status,
      search: params.search,
    })}`,
    {
      credentials: "same-origin",
      signal: params.signal,
    },
  );
  await assertOk(response);
  return (await response.json()) as SuperadminBaseSummary[];
}

export async function fetchSuperadminBaseEditor(campId: number, signal?: AbortSignal): Promise<SuperadminBaseEditor> {
  const response = await fetch(`/api/superadmin/camps/${campId}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as SuperadminBaseEditor;
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
  return (await response.json()) as { ok: boolean; id: number };
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
  return (await response.json()) as { ok: boolean; id: number };
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
