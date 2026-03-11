import type { MarkerType } from "../app/components/MapMarker";
import type { ApiCamp } from "../types/catalog";

export type CampMarkerSize = "compact" | "default" | "large";

export function formatCampPrice(price?: number | null): string {
  if (!price || price <= 0) return "по запросу";
  return `${new Intl.NumberFormat("ru-RU").format(price)}₽`;
}

const TYPE_ALIASES: Record<string, MarkerType> = {
  hotel: "hotel",
  motel: "hotel",
  room: "hotel",
  rooms: "hotel",
  cottage: "cottage",
  house: "cottage",
  houses: "cottage",
  apartment: "apartment",
  apartments: "apartment",
  flat: "apartment",
  glamping: "glamping",
  camping: "camping",
  camp: "camping",
  villa: "villa",
  hostel: "hostel",
  resort: "resort",
  guesthouse: "guesthouse",
  bungalow: "bungalow",
};

const TYPE_HINTS: Array<{ type: MarkerType; patterns: RegExp[] }> = [
  { type: "guesthouse", patterns: [/гостев/i, /гостиный/i, /guest\s*house/i] },
  { type: "hotel", patterns: [/отел/i, /гостиниц/i, /мотел/i, /hotel/i] },
  { type: "hostel", patterns: [/хостел/i, /hostel/i] },
  { type: "resort", patterns: [/курорт/i, /санатор/i, /resort/i, /спа/i, /\bspa\b/i] },
  { type: "glamping", patterns: [/глэмп/i, /glamp/i, /шатер/i, /шатёр/i] },
  { type: "camping", patterns: [/кемп/i, /camping/i, /палат/i] },
  { type: "villa", patterns: [/вилл/i, /villa/i] },
  { type: "bungalow", patterns: [/бунгал/i, /bungalow/i] },
  { type: "cottage", patterns: [/коттедж/i, /домик/i, /cottage/i] },
  { type: "apartment", patterns: [/апарт/i, /квартир/i, /apartment/i] },
];

export function resolveCampKind(camp: ApiCamp): MarkerType {
  const directCandidates = [camp.marker_type, camp.camp_type, camp.type];
  for (const candidate of directCandidates) {
    const key = String(candidate || "").trim().toLowerCase();
    if (key && TYPE_ALIASES[key]) return TYPE_ALIASES[key];
  }

  const housingType = String(camp.housing_type || "").trim().toLowerCase();
  const haystack = `${camp.name || ""} ${camp.description || ""} ${camp.housing_type || ""}`.toLowerCase();

  for (const hint of TYPE_HINTS) {
    if (hint.patterns.some((pattern) => pattern.test(haystack))) return hint.type;
  }

  if (housingType === "houses") {
    return "cottage";
  }
  if (housingType === "rooms") {
    return "hotel";
  }
  return "apartment";
}

export function resolveCampSize(camp: ApiCamp): CampMarkerSize {
  const raw = String(camp.emoji_size || "").trim().toLowerCase();
  if (raw === "vip") return "large";
  if ((camp.min_price || 0) >= 8000) return "large";
  if ((camp.min_price || 0) > 0 && (camp.min_price || 0) <= 3500) return "compact";
  return "default";
}

export function isCampDisabled(camp: ApiCamp): boolean {
  return String(camp.status || "active").trim().toLowerCase() !== "active";
}

export function isCampVip(camp: ApiCamp): boolean {
  return Boolean(camp.is_vip) || String(camp.emoji_size || "").trim().toLowerCase() === "vip";
}

export function normalizeCampList(payload: unknown): ApiCamp[] {
  if (!Array.isArray(payload)) return [];
  const camps: ApiCamp[] = [];
  for (const item of payload) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const id = Number(row.id);
    const lat = row.lat == null ? null : Number(row.lat);
    const lng = row.lng == null ? null : Number(row.lng);
    if (!Number.isFinite(id) || !Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    camps.push({
      id,
      name: typeof row.name === "string" ? row.name : null,
      lat,
      lng,
      min_price: row.min_price == null ? null : Number(row.min_price),
      lake_name: typeof row.lake_name === "string" ? row.lake_name : null,
      photo_main: typeof row.photo_main === "string" ? row.photo_main : null,
      status: typeof row.status === "string" ? row.status : null,
      address: typeof row.address === "string" ? row.address : null,
      phone: typeof row.phone === "string" ? row.phone : null,
      rooms_count: row.rooms_count == null ? null : Number(row.rooms_count),
      description: typeof row.description === "string" ? row.description : null,
      housing_type: typeof row.housing_type === "string" ? row.housing_type : null,
      emoji_size: typeof row.emoji_size === "string" ? row.emoji_size : null,
      marker_type: typeof row.marker_type === "string" ? row.marker_type : null,
      camp_type: typeof row.camp_type === "string" ? row.camp_type : null,
      type: typeof row.type === "string" ? row.type : null,
      is_vip: typeof row.is_vip === "boolean" ? row.is_vip : null,
    });
  }
  return camps.sort((left, right) => {
    const leftDisabled = isCampDisabled(left) ? 1 : 0;
    const rightDisabled = isCampDisabled(right) ? 1 : 0;
    if (leftDisabled !== rightDisabled) return leftDisabled - rightDisabled;
    return (left.min_price || Number.MAX_SAFE_INTEGER) - (right.min_price || Number.MAX_SAFE_INTEGER);
  });
}
