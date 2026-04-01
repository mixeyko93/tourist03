const CRM_SESSION_KEY = "tourist03.crm.session";

export type CrmSession = {
  email: string;
  name: string;
};

export function getCrmSession(): CrmSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CRM_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CrmSession>;
    if (!parsed.email || !parsed.name) return null;
    return {
      email: String(parsed.email),
      name: String(parsed.name),
    };
  } catch {
    return null;
  }
}

export function saveCrmSession(session: CrmSession) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CRM_SESSION_KEY, JSON.stringify(session));
}

export function clearCrmSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(CRM_SESSION_KEY);
}
