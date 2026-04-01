const ADMIN_BASE = "/admincamps";
const REACT_MAP_BASE = "/react-map";

export function detectCrmBase(pathname: string) {
  if (pathname.startsWith(REACT_MAP_BASE)) return REACT_MAP_BASE;
  if (pathname.startsWith(ADMIN_BASE)) return ADMIN_BASE;
  return ADMIN_BASE;
}

export function getCrmBase() {
  if (typeof window === "undefined") return ADMIN_BASE;
  return detectCrmBase(window.location.pathname);
}

export function crmPath(path: string, base = getCrmBase()) {
  const normalized = path === "/" ? "" : path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalized}`;
}
