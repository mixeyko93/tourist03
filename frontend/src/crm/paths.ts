const REACT_MAP_BASE = "/react-map";

export function detectCrmBase(pathname: string) {
  if (pathname.startsWith(REACT_MAP_BASE)) return REACT_MAP_BASE;
  return "";
}

export function getCrmBase() {
  if (typeof window === "undefined") return "";
  return detectCrmBase(window.location.pathname);
}

export function crmPath(path: string, base = getCrmBase()) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (!base) return normalized;
  if (normalized === "/") return base;
  return `${base}${normalized}`;
}
