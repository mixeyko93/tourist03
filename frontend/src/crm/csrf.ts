const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const LOGIN_EXEMPTIONS = new Set(["POST /api/admin/login", "POST /api/superadmin/session"]);

let csrfToken: string | null = null;
let csrfRequest: Promise<string> | null = null;

function requestUrl(input: RequestInfo | URL): URL {
  if (typeof input === "string") {
    return new URL(input, window.location.origin);
  }
  if (input instanceof URL) {
    return input;
  }
  return new URL(input.url, window.location.origin);
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) {
    return init.method.toUpperCase();
  }
  return input instanceof Request ? input.method.toUpperCase() : "GET";
}

function needsCsrf(path: string, method: string): boolean {
  if (!UNSAFE_METHODS.has(method) || LOGIN_EXEMPTIONS.has(`${method} ${path}`)) {
    return false;
  }
  return (
    path.startsWith("/api/admin/") ||
    path.startsWith("/api/superadmin/") ||
    path.startsWith("/api/admincamps/") ||
    path === "/api/camps" ||
    path.startsWith("/api/camps/") ||
    path === "/api/upload" ||
    path === "/api/admin/upload"
  );
}

async function loadCsrfToken(nativeFetch: typeof window.fetch): Promise<string> {
  if (csrfToken) {
    return csrfToken;
  }
  if (!csrfRequest) {
    csrfRequest = nativeFetch("/api/security/csrf", { credentials: "same-origin" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Не удалось получить CSRF-токен");
        }
        const payload = (await response.json()) as { token?: string };
        if (!payload.token) {
          throw new Error("Сервер не вернул CSRF-токен");
        }
        csrfToken = payload.token;
        return csrfToken;
      })
      .finally(() => {
        csrfRequest = null;
      });
  }
  return csrfRequest;
}

/** Install once before React mounts, so existing fetch calls gain CSRF safely. */
export function installCsrfFetch() {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    if (url.origin !== window.location.origin) {
      return nativeFetch(input, init);
    }
    const path = url.pathname;
    const method = requestMethod(input, init);
    if (!needsCsrf(path, method)) {
      return nativeFetch(input, init);
    }
    const token = await loadCsrfToken(nativeFetch);
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    headers.set("X-CSRF-Token", token);
    return nativeFetch(input, { ...init, headers });
  }) as typeof window.fetch;
}
