import type { AuthUserDTO } from "../types/auth";

export type StoredAuth = {
  token: string;
  user: AuthUserDTO;
};

export const AUTH_STORAGE_KEY = "auth_profile";
const AUTH_TOKEN_CLOUD_KEY = "t03_auth_token";

function getCloudStorage() {
  try {
    const tg = (window as Window & { Telegram?: { WebApp?: { CloudStorage?: { setItem: (key: string, value: string, cb: () => void) => void } } } }).Telegram?.WebApp;
    return tg?.CloudStorage ?? null;
  } catch {
    return null;
  }
}

function syncCloudToken(token: string) {
  const cloud = getCloudStorage();
  if (!cloud) return;
  try {
    cloud.setItem(AUTH_TOKEN_CLOUD_KEY, token, () => {});
  } catch {
    // ignore cloud storage errors for local/dev usage
  }
}

export function getStoredAuth(): StoredAuth | null {
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<StoredAuth>;
    if (!parsed || typeof parsed.token !== "string" || !parsed.token || !parsed.user) {
      return null;
    }
    return { token: parsed.token, user: parsed.user as AuthUserDTO };
  } catch {
    return null;
  }
}

export function setStoredAuth(auth: StoredAuth) {
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
  syncCloudToken(auth.token);
}

export function clearStoredAuth() {
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  syncCloudToken("");
}

export async function authFetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredAuth()?.token ?? "";
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "same-origin",
  });

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (response.status === 401) {
    clearStoredAuth();
  }
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail?: unknown }).detail || `Ошибка (${response.status})`)
        : `Ошибка (${response.status})`;
    throw new Error(message);
  }

  return payload as T;
}
