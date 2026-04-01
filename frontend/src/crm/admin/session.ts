export type SuperadminSessionResponse = {
  ok: boolean;
  authenticated: boolean;
};

export type SuperadminLoginPayload = {
  login: string;
  password: string;
  key: string;
};

async function parseSessionResponse(response: Response): Promise<SuperadminSessionResponse> {
  const payload = (await response.json().catch(() => null)) as
    | (SuperadminSessionResponse & { detail?: string })
    | { detail?: string }
    | null;

  if (!response.ok) {
    throw new Error(payload?.detail || "Не удалось выполнить запрос");
  }

  return {
    ok: Boolean((payload as SuperadminSessionResponse | null)?.ok),
    authenticated: Boolean((payload as SuperadminSessionResponse | null)?.authenticated),
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
