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
      quality: CardQuality;
      changes: OwnerChange[];
      activity: OwnerDashboard["activity"];
      amenity_catalog: Array<{ id: number; name: string; category: string }>;
    }>(
      `/api/owner/camps/${id}`,
    ),
  createChange: (campId: number) =>
    apiRequest<{ change: OwnerChange; created: boolean }>(`/api/owner/camps/${campId}/changes`, { method: "POST" }),
  getChange: (changeId: number) =>
    apiRequest<{ change: OwnerChange }>(`/api/owner/changes/${changeId}`),
  saveChange: (changeId: number, contentVersion: number, proposedPayload: Record<string, unknown>) =>
    apiRequest<{ change: OwnerChange }>(`/api/owner/changes/${changeId}`, {
      method: "PATCH",
      body: JSON.stringify({ content_version: contentVersion, proposed_payload: proposedPayload }),
    }),
  submitChange: (changeId: number) =>
    apiRequest<{ change: OwnerChange }>(`/api/owner/changes/${changeId}/submit`, { method: "POST" }),
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
