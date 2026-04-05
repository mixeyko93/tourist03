import type { CrmMediaItem } from "./mediaTools";

export type CrmSession = {
  id: number;
  login: string;
  name: string;
  phone: string;
  defaultRoleKey: string;
};

export type CrmLoginPayload = {
  login: string;
  password: string;
};

export type CrmUiOverrideResponse = {
  key: string;
  payload: Record<string, unknown>;
  updated_at?: string | null;
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
  media?: CrmMediaItem[];
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

export type CrmBookingUpdatePayload = {
  status?: string;
  payment_status?: string;
  payment_required?: boolean;
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
  media?: CrmMediaItem[];
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
  login: string;
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

export type CrmShiftSettings = {
  camp_id: number;
  time_zone: string;
  booking_hold_hours: number;
  night_release_after_shift_minutes: number;
  escalation_step_minutes: number;
  escalation_repeats_before_manager: number;
};

export type CrmShiftStaffOption = {
  id: number;
  display_name: string;
  role_key: string;
  role_label: string;
  is_active: boolean;
  notifications_enabled: boolean;
  has_telegram_link: boolean;
};

export type CrmShiftRule = {
  id: number;
  camp_id: number;
  admin_id: number;
  admin_name: string;
  admin_email: string;
  shift_date: string | null;
  weekday: number;
  starts_at: string;
  ends_at: string;
  is_night_shift: boolean;
  is_active: boolean;
  comment: string | null;
  comment_author_display: string | null;
  comment_author_login: string | null;
  created_at: string;
  updated_at: string;
};

export type CrmShiftOccurrence = {
  rule_id: number;
  admin_id: number;
  admin_name: string;
  weekday: number;
  weekday_label: string;
  starts_at: string;
  ends_at: string;
  starts_time: string;
  ends_time: string;
  is_night_shift: boolean;
  is_active: boolean;
  comment: string;
  timezone: string;
};

export type CrmShiftOverview = {
  timezone: string;
  now: string;
  active_rules: CrmShiftOccurrence[];
  next_rule: CrmShiftOccurrence | null;
  upcoming_windows: CrmShiftOccurrence[];
};

export type CrmEventCenterItem = {
  id: number;
  camp_id: number | null;
  camp_name: string | null;
  recipient_scope: string;
  recipient_admin_id: number | null;
  recipient_role_key: string | null;
  channel: string;
  event_type: string;
  title: string;
  body: string;
  action_url: string | null;
  action_payload: Record<string, unknown> | null;
  severity: "info" | "warning" | "critical" | string;
  status: "new" | "viewed" | "in_progress" | "closed" | string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  read_at: string | null;
  closed_at: string | null;
};

export type CrmEventCenterSummary = {
  total_count: number;
  new_count: number;
  viewed_count: number;
  in_progress_count: number;
  closed_count: number;
  warning_count: number;
  critical_count: number;
};

export type CrmChangeRequest = {
  id: number;
  camp_id: number;
  camp_name: string | null;
  created_by_admin_id: number;
  created_by_display: string | null;
  created_by_email: string | null;
  reviewer_admin_id: number | null;
  reviewer_display: string | null;
  reviewer_email: string | null;
  target_type: string;
  target_id: string | null;
  change_kind: string;
  status: string;
  summary: string;
  request_comment: string | null;
  reviewer_comment: string | null;
  payload: Record<string, unknown> | null;
  applied_snapshot: Record<string, unknown> | null;
  created_at: string;
  decided_at: string | null;
  updated_at: string;
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
  media?: CrmMediaItem[];
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
  media?: CrmMediaItem[];
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
  login: string;
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

export type CrmShiftSettingsUpdatePayload = {
  time_zone: string;
  booking_hold_hours: number;
  night_release_after_shift_minutes: number;
  escalation_step_minutes: number;
  escalation_repeats_before_manager: number;
};

export type CrmShiftRuleUpsertPayload = {
  admin_id: number;
  shift_date: string;
  starts_at: string;
  ends_at: string;
  is_night_shift: boolean;
  is_active: boolean;
  comment?: string;
};

export type CrmChangeRequestCreatePayload = {
  operation: string;
  payload: Record<string, unknown>;
  request_comment?: string;
  apply_mode: "pending_review" | "apply_with_responsibility";
};

export type CrmChangeRequestDecisionPayload = {
  action: "approve" | "reject" | "clarify" | "rollback";
  comment?: string;
};

export type CrmEventStatusUpdatePayload = {
  status: "new" | "viewed" | "in_progress" | "closed";
};

type AdminSessionPayload = {
  id: number;
  login: string;
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
    login: String(payload.login || ""),
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

export async function fetchPublicUiOverride(key: string, signal?: AbortSignal): Promise<CrmUiOverrideResponse> {
  const response = await fetch(`/api/public/ui-overrides/${encodeURIComponent(key)}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmUiOverrideResponse;
}

export async function saveCrmUiOverride(key: string, payload: Record<string, unknown>): Promise<CrmUiOverrideResponse> {
  const response = await fetch(`/api/admin/ui-overrides/${encodeURIComponent(key)}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ payload }),
  });
  await assertOk(response);
  return (await response.json()) as CrmUiOverrideResponse;
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

export async function fetchCrmEventCenter(
  params: {
    campId?: number | null;
    search?: string;
    status?: string;
    severity?: string;
    limit?: number;
  },
  signal?: AbortSignal,
): Promise<{ items: CrmEventCenterItem[]; summary: CrmEventCenterSummary }> {
  const query = new URLSearchParams();
  if (params.campId) {
    query.set("camp_id", String(params.campId));
  }
  if (params.search) {
    query.set("search", params.search);
  }
  if (params.status) {
    query.set("event_status", params.status);
  }
  if (params.severity) {
    query.set("severity", params.severity);
  }
  if (params.limit) {
    query.set("limit", String(params.limit));
  }
  const response = await fetch(`/api/admin/events?${query.toString()}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as { items: CrmEventCenterItem[]; summary: CrmEventCenterSummary };
}

export async function fetchCrmEventCenterSummary(
  params?: { campId?: number | null },
  signal?: AbortSignal,
): Promise<CrmEventCenterSummary> {
  const query = new URLSearchParams();
  if (params?.campId) {
    query.set("camp_id", String(params.campId));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await fetch(`/api/admin/events/summary${suffix}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmEventCenterSummary;
}

export async function updateCrmEventStatus(eventId: number, payload: CrmEventStatusUpdatePayload) {
  const response = await fetch(`/api/admin/events/${eventId}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; item: CrmEventCenterItem };
}

export async function fetchCrmChangeRequests(
  params: {
    campId?: number | null;
    search?: string;
    status?: string;
    changeKind?: string;
    limit?: number;
  },
  signal?: AbortSignal,
): Promise<{ items: CrmChangeRequest[]; status_labels: Record<string, string>; change_kind_labels: Record<string, string> }> {
  const query = new URLSearchParams();
  if (params.campId) {
    query.set("camp_id", String(params.campId));
  }
  if (params.search) {
    query.set("search", params.search);
  }
  if (params.status) {
    query.set("status", params.status);
  }
  if (params.changeKind) {
    query.set("change_kind", params.changeKind);
  }
  if (params.limit) {
    query.set("limit", String(params.limit));
  }
  const response = await fetch(`/api/admin/change-requests?${query.toString()}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as { items: CrmChangeRequest[]; status_labels: Record<string, string>; change_kind_labels: Record<string, string> };
}

export async function createCrmChangeRequest(campId: number, payload: CrmChangeRequestCreatePayload) {
  const response = await fetch(`/api/admin/camps/${campId}/change-requests`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; item: CrmChangeRequest };
}

export async function updateCrmChangeRequest(requestId: number, payload: CrmChangeRequestDecisionPayload) {
  const response = await fetch(`/api/admin/change-requests/${requestId}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; item: CrmChangeRequest };
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

export async function fetchCrmShifts(
  campId: number,
  signal?: AbortSignal,
): Promise<{ settings: CrmShiftSettings; rules: CrmShiftRule[]; overview: CrmShiftOverview; staff: CrmShiftStaffOption[] }> {
  const response = await fetch(`/api/admin/camps/${campId}/shifts`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as { settings: CrmShiftSettings; rules: CrmShiftRule[]; overview: CrmShiftOverview; staff: CrmShiftStaffOption[] };
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

export async function updateCrmBooking(bookingId: number, payload: CrmBookingUpdatePayload) {
  const response = await fetch(`/api/admin/bookings/${bookingId}`, {
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

export async function uploadCrmMedia(file: File, options: { campId?: number; roomIndex?: number } = {}) {
  const body = new FormData();
  body.set("file", file);
  if (options.campId) {
    body.set("camp_id", String(options.campId));
  }
  if (options.roomIndex !== undefined) {
    body.set("room_idx", String(options.roomIndex));
  }
  const response = await fetch("/api/admin/upload", {
    method: "POST",
    credentials: "same-origin",
    body,
  });
  await assertOk(response);
  return (await response.json()) as { url: string };
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
  return (await response.json()) as { ok: boolean; code: string; command: string; deep_link: string | null };
}

export async function saveCrmShiftSettings(campId: number, payload: CrmShiftSettingsUpdatePayload) {
  const response = await fetch(`/api/admin/camps/${campId}/shifts/settings`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; item: CrmShiftSettings };
}

export async function createCrmShiftRule(campId: number, payload: CrmShiftRuleUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/shift-rules`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; id: number; item: CrmShiftRule };
}

export async function updateCrmShiftRule(campId: number, ruleId: number, payload: CrmShiftRuleUpsertPayload) {
  const response = await fetch(`/api/admin/camps/${campId}/shift-rules/${ruleId}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean; item: CrmShiftRule };
}

export async function deleteCrmShiftRule(campId: number, ruleId: number) {
  const response = await fetch(`/api/admin/camps/${campId}/shift-rules/${ruleId}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  await assertOk(response);
  return (await response.json()) as { ok: boolean };
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
