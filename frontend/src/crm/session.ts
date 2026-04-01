export type CrmSession = {
  id: number;
  email: string;
  name: string;
  phone: string;
  defaultRoleKey: string;
};

export type CrmLoginPayload = {
  email: string;
  password: string;
};

export type CrmCamp = {
  id: number;
  name: string;
  region: string;
  description: string;
  is_active: boolean;
};

export type CrmCalendarBooking = {
  id: number;
  label: string;
  status: "processing" | "confirmed" | "cancelled" | "completed";
  start_day: number;
  span_days: number;
  check_in: string;
  check_out: string;
  source: string;
};

export type CrmCalendarRoom = {
  id: string;
  room_id: number | null;
  camp_id: number;
  camp_name: string;
  title: string;
  category: string;
  bookings: CrmCalendarBooking[];
};

export type CrmCalendarFeed = {
  date_from: string | null;
  date_to: string | null;
  rooms: CrmCalendarRoom[];
};

export type CrmBooking = {
  id: number;
  camp_id: number | null;
  camp_name: string | null;
  room_id: number | null;
  room_name: string | null;
  check_in: string;
  check_out: string;
  guests_count: number;
  status: string;
  source: string;
  payment_status: string;
  payment_required: boolean;
  user_id: number | null;
  user_name: string | null;
  user_phone: string | null;
  user_email: string | null;
  guest_name: string | null;
  guest_phone: string | null;
  guest_email: string | null;
  comment: string | null;
};

export type CrmRoomOption = {
  id: number;
  camp_id: number | null;
  name: string | null;
  room_type: string | null;
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
  has_ac?: number | null;
  capacity: number | null;
  price: number | null;
  price_adult?: number | null;
  price_child?: number | null;
  discount_pct?: number | null;
  discount_from_nights?: number | null;
  description?: string | null;
  photo_main?: string | null;
  photos?: Array<{ url: string; cover: boolean; sort: number }>;
};

export type CrmCreateBookingPayload = {
  camp_id: number;
  room_id?: number | null;
  check_in: string;
  check_out: string;
  guests_count: number;
  status: string;
  payment_status: string;
  payment_required: boolean;
  guest_name?: string;
  guest_phone?: string;
  guest_email?: string;
  comment?: string;
};

export type CrmCampProfile = {
  camp: {
    id: number;
    name: string | null;
    lake_name?: string | null;
    address?: string | null;
    phone?: string | null;
    site_url?: string | null;
    description?: string | null;
  };
  settings: {
    time_zone?: string | null;
    check_in_time?: string | null;
    check_out_time?: string | null;
    cancellation_policy?: string | null;
    arrival_instructions?: string | null;
    payment_instructions?: string | null;
    admin_contact_phone?: string | null;
    support_whatsapp?: string | null;
    support_telegram?: string | null;
    notifications_enabled?: boolean;
  };
  photos: Array<{ id?: number; url: string; cover?: number; sort?: number }>;
};

export type CrmGuestBooking = {
  id: number;
  camp_name: string;
  room_name: string;
  check_in: string | null;
  check_out: string | null;
  guests_count: number;
  status: string;
  payment_status: string;
  source: string;
  comment: string;
};

export type CrmGuest = {
  id: string;
  name: string;
  phone: string;
  email: string;
  visits_count: number;
  total_estimate: number;
  last_visit: string | null;
  status: "Новый" | "Постоянный" | "VIP";
  bookings: CrmGuestBooking[];
};

export type CrmService = {
  id: number;
  camp_id: number;
  category_id: number | null;
  category_name: string | null;
  provider_name: string | null;
  provider_contact_phone: string | null;
  provider_contact_telegram: string | null;
  responsible_scope: string;
  responsible_admin_id: number | null;
  responsible_admin_name: string | null;
  name: string;
  description: string | null;
  status: string;
  requires_booking: boolean;
  allows_standalone: boolean;
  location_hint: string | null;
  duration_minutes: number | null;
  cover_photo_url: string | null;
  cover_video_url: string | null;
  media_json?: unknown[];
  slots_count: number;
  active_slots_count: number;
  min_price: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CrmStaffRoleMeta = {
  key: string;
  label: string;
};

export type CrmStaffPermissionMeta = {
  key: string;
  label: string;
};

export type CrmStaffMember = {
  id: number;
  email: string;
  display_name: string;
  phone: string | null;
  default_role_key: string;
  role_key: string;
  role_label: string;
  can_manage_staff: boolean;
  is_primary: boolean;
  is_active: boolean;
  notifications_enabled: boolean;
  telegram_chat_id: number | null;
  telegram_username: string | null;
  has_telegram_link: boolean;
  last_seen_at: string | null;
  delegated_until: string | null;
  permission_keys: string[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type CrmAuditEntry = {
  id: number;
  actor_type: string;
  actor_id: number | null;
  actor_display: string | null;
  camp_id: number | null;
  target_type: string;
  target_id: string | null;
  action_type: string;
  action_label: string;
  changed_field: string | null;
  old_value: unknown;
  new_value: unknown;
  comment: string | null;
  is_sensitive: boolean;
  was_auto_applied: boolean;
  metadata: unknown;
  created_at: string;
};

export type CrmCampProfileUpdatePayload = {
  name: string;
  lake_name?: string;
  address?: string;
  phone?: string;
  site_url?: string;
  description?: string;
  time_zone?: string;
  check_in_time?: string;
  check_out_time?: string;
  cancellation_policy?: string;
  arrival_instructions?: string;
  payment_instructions?: string;
  admin_contact_phone?: string;
  support_whatsapp?: string;
  support_telegram?: string;
  notifications_enabled: boolean;
};

export type CrmRoomUpsertPayload = {
  name: string;
  room_type?: string;
  floors: number;
  floor: number;
  beds_single: number;
  beds_double: number;
  bath_type?: string;
  wc_type?: string;
  bbq_type?: string;
  kitchen_type?: string;
  gazebo_type?: string;
  terrace_type?: string;
  pool_type?: string;
  balcony_type?: string;
  has_ac: boolean;
  price_adult: number;
  price_child: number;
  price: number;
  discount_pct: number;
  discount_from_nights: number;
  description?: string;
};

export type CrmServiceUpsertPayload = {
  category_name?: string;
  provider_name?: string;
  provider_contact_phone?: string;
  provider_contact_telegram?: string;
  responsible_scope: string;
  responsible_admin_id?: number | null;
  name: string;
  description?: string;
  status: string;
  requires_booking: boolean;
  allows_standalone: boolean;
  location_hint?: string;
  duration_minutes?: number | null;
  cover_photo_url?: string;
  cover_video_url?: string;
};

export type CrmStaffUpsertPayload = {
  email: string;
  display_name: string;
  phone?: string;
  password?: string;
  role_key: string;
  can_manage_staff: boolean;
  is_primary: boolean;
  is_active: boolean;
  notifications_enabled: boolean;
  permission_keys: string[];
};

type AdminSessionPayload = {
  id: number;
  email: string;
  display_name: string;
  phone?: string;
  default_role_key?: string;
};

async function parseJsonOrNull(response: Response) {
  return (await response.json().catch(() => null)) as { detail?: string } | null;
}

async function assertOk(response: Response) {
  if (response.ok) {
    return;
  }
  const payload = await parseJsonOrNull(response);
  throw new Error(payload?.detail || "Не удалось выполнить запрос");
}

function mapSession(payload: AdminSessionPayload): CrmSession {
  return {
    id: Number(payload.id),
    email: String(payload.email || ""),
    name: String(payload.display_name || ""),
    phone: String(payload.phone || ""),
    defaultRoleKey: String(payload.default_role_key || "administrator"),
  };
}

export async function fetchCrmSession(signal?: AbortSignal): Promise<CrmSession | null> {
  const response = await fetch("/api/admin/me", {
    credentials: "same-origin",
    signal,
  });
  if (response.status === 401) {
    return null;
  }
  await assertOk(response);
  const payload = (await response.json()) as AdminSessionPayload;
  return mapSession(payload);
}

export async function loginCrmSession(payload: CrmLoginPayload) {
  const response = await fetch("/api/admin/login", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  const session = await fetchCrmSession();
  if (!session) {
    throw new Error("Сессия не открылась после входа");
  }
  return session;
}

export async function logoutCrmSession() {
  const response = await fetch("/api/admin/logout", {
    method: "POST",
    credentials: "same-origin",
  });
  await assertOk(response);
}

export async function fetchCrmCamps(signal?: AbortSignal): Promise<CrmCamp[]> {
  const response = await fetch("/api/admin/my-camps", {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmCamp[];
}

export async function fetchCrmCalendarFeed(
  params: {
    campId?: number | null;
    dateFrom: string;
    dateTo: string;
  },
  signal?: AbortSignal,
): Promise<CrmCalendarFeed> {
  const query = new URLSearchParams();
  if (params.campId) {
    query.set("camp_id", String(params.campId));
  }
  query.set("date_from", params.dateFrom);
  query.set("date_to", params.dateTo);
  const response = await fetch(`/api/admin/calendar-feed?${query.toString()}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmCalendarFeed;
}

export async function fetchCrmBookings(
  params: {
    campId?: number | null;
    dateFrom?: string;
    dateTo?: string;
  },
  signal?: AbortSignal,
): Promise<CrmBooking[]> {
  const query = new URLSearchParams();
  if (params.campId) {
    query.set("camp_id", String(params.campId));
  }
  if (params.dateFrom) {
    query.set("date_from", params.dateFrom);
  }
  if (params.dateTo) {
    query.set("date_to", params.dateTo);
  }
  const response = await fetch(`/api/admin/bookings?${query.toString()}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmBooking[];
}

export async function fetchCrmGuests(
  params: {
    campId?: number | null;
  },
  signal?: AbortSignal,
): Promise<CrmGuest[]> {
  const query = new URLSearchParams();
  if (params.campId) {
    query.set("camp_id", String(params.campId));
  }
  const response = await fetch(`/api/admin/guests?${query.toString()}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmGuest[];
}

export async function fetchCrmCampRooms(campId: number, signal?: AbortSignal): Promise<CrmRoomOption[]> {
  const response = await fetch(`/api/admin/camps/${campId}/rooms`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmRoomOption[];
}

export async function fetchCrmServices(campId: number, signal?: AbortSignal): Promise<CrmService[]> {
  const response = await fetch(`/api/admin/camps/${campId}/services`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmService[];
}

export async function fetchCrmStaff(
  campId: number,
  signal?: AbortSignal,
): Promise<{ items: CrmStaffMember[]; roles: CrmStaffRoleMeta[]; permissions: CrmStaffPermissionMeta[] }> {
  const response = await fetch(`/api/admin/camps/${campId}/staff`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as { items: CrmStaffMember[]; roles: CrmStaffRoleMeta[]; permissions: CrmStaffPermissionMeta[] };
}

export async function fetchCrmAuditLog(
  campId: number,
  params: {
    search?: string;
    actorId?: number | null;
    targetType?: string;
    limit?: number;
  },
  signal?: AbortSignal,
): Promise<{ items: CrmAuditEntry[]; actors: Array<{ id: number; label: string }>; target_types: string[] }> {
  const query = new URLSearchParams();
  if (params.search) {
    query.set("search", params.search);
  }
  if (params.actorId) {
    query.set("actor_id", String(params.actorId));
  }
  if (params.targetType) {
    query.set("target_type", params.targetType);
  }
  if (params.limit) {
    query.set("limit", String(params.limit));
  }
  const response = await fetch(`/api/admin/camps/${campId}/audit-log?${query.toString()}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as { items: CrmAuditEntry[]; actors: Array<{ id: number; label: string }>; target_types: string[] };
}

export async function createCrmBooking(payload: CrmCreateBookingPayload) {
  const response = await fetch("/api/admin/bookings", {
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

export async function fetchCrmCampProfile(campId: number, signal?: AbortSignal): Promise<CrmCampProfile> {
  const response = await fetch(`/api/admin/camps/${campId}/profile`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmCampProfile;
}

export async function saveCrmCampProfile(campId: number, payload: CrmCampProfileUpdatePayload) {
  const response = await fetch(`/api/admin/camps/${campId}/profile`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; item: CrmCampProfile };
}

export async function createCrmRoom(campId: number, payload: CrmRoomUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/rooms`, {
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

export async function updateCrmRoom(campId: number, roomId: number, payload: CrmRoomUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/rooms/${roomId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function deleteCrmRoom(campId: number, roomId: number) {
  const response = await fetch(`/api/admin/camps/${campId}/rooms/${roomId}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function createCrmStaff(campId: number, payload: CrmStaffUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/staff`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; id: number; item: CrmStaffMember };
}

export async function updateCrmStaff(campId: number, staffId: number, payload: CrmStaffUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/staff/${staffId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; item: CrmStaffMember };
}

export async function issueCrmStaffTelegramLink(campId: number, staffId: number) {
  const response = await fetch(`/api/admin/camps/${campId}/staff/${staffId}/telegram-link`, {
    method: "POST",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; code: string };
}

export async function createCrmService(campId: number, payload: CrmServiceUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/services`, {
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

export async function updateCrmService(campId: number, serviceId: number, payload: CrmServiceUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/services/${serviceId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}

export async function deleteCrmService(campId: number, serviceId: number) {
  const response = await fetch(`/api/admin/camps/${campId}/services/${serviceId}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
}
