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
  capacity: number | null;
  price: number | null;
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

export async function fetchCrmCampRooms(campId: number, signal?: AbortSignal): Promise<CrmRoomOption[]> {
  const response = await fetch(`/api/rooms?camp_id=${campId}`, {
    credentials: "same-origin",
    signal,
  });
  await assertOk(response);
  return (await response.json()) as CrmRoomOption[];
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
