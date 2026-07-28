const ICON_PATHS = Object.freeze({
  home: '<path d="M4 11.5 12 5l8 6.5V20h-5v-5H9v5H4Z"/>',
  house: '<path d="M3.5 12 12 4.5l8.5 7.5M6 10.5V20h12v-9.5M10 20v-5h4v5"/>',
  hotel: '<path d="M5 20V5h10v15M15 10h4v10M8 8h2m2 0h1M8 12h2m2 0h1M3 20h18"/>',
  tent: '<path d="m4 20 8-16 8 16M8.5 20 12 13l3.5 7M4 20h16"/>',
  camp: '<path d="M12 3v18M5 19 12 5l7 14M7.5 14h9"/>',
  building: '<path d="M5 20V6l7-3 7 3v14M9 8h2m2 0h2M9 12h2m2 0h2M10 20v-4h4v4"/>',
  cottage: '<path d="m3 11 9-7 9 7M5 10v10h14V10M9 20v-6h6v6"/>',
  health: '<path d="M12 21s-8-4.8-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6.2-8 11-8 11Z"/>',
  trees: '<path d="m7 3-4 8h3l-4 7h10l-4-7h3L7 3Zm10 2-3 6h2l-3 6h8l-3-6h2l-3-6ZM7 18v3m10-4v4"/>',
  bed: '<path d="M4 18V7m0 7h16v4M7 14v-4h5a3 3 0 0 1 3 3v1M4 18v2m16-2v2"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5 5-2Z"/>',
  pin: '<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  boat: '<path d="M4 13h16l-2.5 6h-11L4 13Zm4-1V7h7l3 5M3 21c1.3 0 1.7-1 3-1s1.7 1 3 1 1.7-1 3-1 1.7 1 3 1 1.7-1 3-1 1.7 1 3 1"/>',
  kayak: '<path d="M3 14c3-4 15-4 18 0-3 4-15 4-18 0Zm9-5v10M7 5l10 18M5 4l4 2-3 3m13 10-4 3"/>',
  sup: '<path d="M4 18c4 2 12 2 16 0M6 16c2-2 10-2 12 0M12 4v11m0-7 4-2m-4 5-3 3M8 4h8"/>',
  car: '<path d="m5 10 2-4h10l2 4m-15 0h16v7H4v-7Zm3 7v2m10-2v2M7 13h.01M17 13h.01"/>',
  atv: '<circle cx="6" cy="17" r="3"/><circle cx="18" cy="17" r="3"/><path d="M8 17h7l-2-6H9l-2 3m6-3 3-3m-9 1h4"/>',
  snowmobile: '<path d="M4 17h11a4 4 0 0 0 4-4h-5l-3-5H7m-3 12h12M5 13h5"/>',
  fishing: '<path d="M6 4h8a5 5 0 0 1 5 5v5m0 0a2 2 0 1 1-2 2M6 4v16M3 7h6"/>',
  restaurant: '<path d="M5 3v8m3-8v8M3 7h7m-3 4v10m11-18v18m0-18c-3 2-3 7 0 9"/>',
  food: '<path d="M4 12h16M6 12a6 6 0 0 1 12 0M12 6V4M4 16h16M7 20h10"/>',
  sauna: '<path d="M5 20V9h14v11M8 9V5h8v4M9 13h6m-7 4h8M4 20h16M7 4c0-1 1-1 1-2m4 2c0-1 1-1 1-2m3 2c0-1 1-1 1-2"/>',
  bath: '<path d="M4 12h16v3a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-3Zm2 7v2m12-2v2M4 8V6a3 3 0 0 1 6 0v1"/>',
  guide: '<circle cx="12" cy="8" r="3"/><path d="M6 21v-3a6 6 0 0 1 12 0v3M18 5l3-2m-3 4h3"/>',
  transfer: '<path d="M3 16V8h18v8M6 8l2-4h8l2 4M6 16v3m12-3v3M7 12h.01M17 12h.01M3 16h18"/>',
  event: '<path d="M6 3v4m12-4v4M4 9h16M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Zm4 8h2m3 0h2m-7 4h2"/>',
  sight: '<path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z"/><circle cx="12" cy="12" r="3"/>',
  horse: '<path d="M7 20v-5l-2-4 3-6 5 2 4-2 2 4-3 4v7m-7-5h7M9 7 6 3m8 4 2-4"/>',
  equipment: '<path d="M4 7h16v12H4V7Zm4 0V4h8v3M4 12h16M9 12v2h6v-2"/>',
});

const ICON_ALIASES = Object.freeze({
  accommodation: "home",
  apartments: "building",
  camping: "camp",
  city: "hotel",
  country: "trees",
  excursion: "compass",
  rental: "equipment",
  service: "compass",
  activity: "sight",
  transport: "transfer",
  guide: "guide",
  event: "event",
  restaurant: "restaurant",
  cafe: "restaurant",
  dining: "restaurant",
  watercraft: "boat",
  paddle: "kayak",
  route: "compass",
  fish: "fishing",
  quad: "atv",
  "quad-bike": "atv",
  "horse-riding": "horse",
  "equipment-rental": "equipment",
});

export function catalogIconKey(value) {
  const requested = String(value || "").trim().toLowerCase();
  const normalized = ICON_ALIASES[requested] || requested;
  return Object.hasOwn(ICON_PATHS, normalized) ? normalized : "pin";
}

export function catalogIconSvg(value) {
  const key = catalogIconKey(value);
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${ICON_PATHS[key]}</svg>`;
}
