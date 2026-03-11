import type { ApiAvailableRoomsResponse, ApiRoom } from "../types/catalog";

export type BookingFilter = {
  from: string;
  to: string;
  adults: number;
  kids: number;
  allowSplitRooms: boolean;
};

export type RoomAllocation = {
  room: ApiRoom;
  adults: number;
  kids: number;
};

const BOOKING_FILTER_STORAGE_KEY = "t03_react_map_booking_filter";

export function bookingGuestsTotal(filter: BookingFilter | null): number {
  if (!filter) return 0;
  return Math.max(0, Number(filter.adults) || 0) + Math.max(0, Number(filter.kids) || 0);
}

export function bookingNightsFromFilter(filter: BookingFilter | null): number {
  if (!filter?.from || !filter?.to) return 0;
  const from = new Date(filter.from);
  const to = new Date(filter.to);
  const diff = Math.round((to.getTime() - from.getTime()) / 86400000);
  return diff > 0 ? diff : 0;
}

export function isBookingFilterReady(filter: BookingFilter | null): filter is BookingFilter {
  if (!filter) return false;
  if (!filter.from || !filter.to) return false;
  if (bookingGuestsTotal(filter) <= 0) return false;
  if ((Number(filter.kids) || 0) > 0 && (Number(filter.adults) || 0) < 1) return false;
  return bookingNightsFromFilter(filter) > 0;
}

export function roomCapacity(room: ApiRoom): number {
  const direct = Number(room.capacity);
  if (Number.isFinite(direct) && direct > 0) return direct;
  const single = Number(room.beds_single) || 0;
  const double = Number(room.beds_double) || 0;
  const guess = single + double * 2;
  return guess > 0 ? guess : 2;
}

export function roomPriceFrom(room: ApiRoom): number {
  const fixed = Number(room.price) || 0;
  const adult = Number(room.price_adult) || 0;
  if (fixed > 0) return fixed;
  if (adult > 0) return adult;
  return 0;
}

export function formatPriceRub(value?: number | null): string {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return "—";
  return `${number.toLocaleString("ru-RU")} ₽`;
}

export function calcRoomSubtotal(room: ApiRoom, adults: number, kids: number): number | null {
  const total = (Number(adults) || 0) + (Number(kids) || 0);
  if (total <= 0) return 0;
  const fixed = Number(room.price) || 0;
  if (fixed > 0) return fixed;
  const adultPrice = Number(room.price_adult) || 0;
  const childPrice = Number(room.price_child) || 0;
  if (adultPrice <= 0 && childPrice <= 0) return null;
  return (Number(adults) || 0) * adultPrice + (Number(kids) || 0) * childPrice;
}

export function findBestAllocation(rooms: ApiRoom[], totalGuests: number): ApiRoom[] | null {
  const need = Number(totalGuests) || 0;
  if (need <= 0) return [];
  const items = rooms.filter((room) => roomCapacity(room) > 0);
  if (!items.length) return null;

  const maxCap = Math.max(...items.map(roomCapacity));
  const maxSum = Math.min(need + maxCap * 2, 200);
  const dp: Array<{ cnt: number; price: number; prev: number | null; idx: number } | null> = Array(maxSum + 1).fill(null);
  dp[0] = { cnt: 0, price: 0, prev: null, idx: -1 };

  for (let index = 0; index < items.length; index += 1) {
    const cap = roomCapacity(items[index]);
    const price = roomPriceFrom(items[index]) || 0;
    for (let sum = maxSum; sum >= 0; sum -= 1) {
      const current = dp[sum];
      if (!current) continue;
      const nextSum = Math.min(maxSum, sum + cap);
      const candidate = { cnt: current.cnt + 1, price: current.price + price, prev: sum, idx: index };
      const best = dp[nextSum];
      if (
        !best ||
        candidate.cnt < best.cnt ||
        (candidate.cnt === best.cnt && candidate.price < best.price)
      ) {
        dp[nextSum] = candidate;
      }
    }
  }

  let bestSum = -1;
  let bestScore: { cnt: number; over: number; price: number } | null = null;
  for (let sum = need; sum <= maxSum; sum += 1) {
    const state = dp[sum];
    if (!state) continue;
    const score = { cnt: state.cnt, over: sum - need, price: state.price };
    if (
      !bestScore ||
      score.cnt < bestScore.cnt ||
      (score.cnt === bestScore.cnt && score.over < bestScore.over) ||
      (score.cnt === bestScore.cnt && score.over === bestScore.over && score.price < bestScore.price)
    ) {
      bestSum = sum;
      bestScore = score;
    }
  }
  if (bestSum < 0) return null;

  const chosen: ApiRoom[] = [];
  let pointer = bestSum;
  while (pointer > 0) {
    const state = dp[pointer];
    if (!state || state.idx < 0 || state.prev == null) break;
    chosen.push(items[state.idx]);
    pointer = state.prev;
  }

  return chosen.reverse();
}

export function autoDistributeGuests(selectedRooms: ApiRoom[], filter: BookingFilter): RoomAllocation[] {
  const rooms = Array.isArray(selectedRooms) ? selectedRooms : [];
  const items = rooms.map((room) => ({ room, adults: 0, kids: 0 }));
  let adultsLeft = Number(filter.adults) || 0;
  let kidsLeft = Number(filter.kids) || 0;

  for (let index = 0; index < items.length && (adultsLeft > 0 || kidsLeft > 0); index += 1) {
    const cap = roomCapacity(items[index].room);
    if (cap <= 0) continue;

    const kidsTarget = kidsLeft > 0 ? Math.min(kidsLeft, Math.floor(cap / 2)) : 0;
    let adultsHere = 0;
    let kidsHere = 0;

    if (kidsTarget > 0 && adultsLeft > 0) {
      kidsHere = kidsTarget;
      adultsHere = Math.min(adultsLeft, cap - kidsHere);
      if (adultsHere <= 0) {
        kidsHere = 0;
      }
    }

    if (adultsHere <= 0 && adultsLeft > 0) {
      adultsHere = Math.min(adultsLeft, cap);
    }

    if (adultsHere > 0 && kidsLeft > kidsHere) {
      const remainCapacity = Math.max(0, cap - (adultsHere + kidsHere));
      kidsHere += Math.min(remainCapacity, kidsLeft - kidsHere);
    }

    if (adultsHere + kidsHere > cap) {
      kidsHere = Math.max(0, kidsHere - (adultsHere + kidsHere - cap));
    }
    if (kidsHere > 0 && adultsHere <= 0) {
      kidsHere = 0;
    }

    items[index].adults = adultsHere;
    items[index].kids = kidsHere;
    adultsLeft -= adultsHere;
    kidsLeft -= kidsHere;
  }

  return items;
}

export function validateAllocation(items: RoomAllocation[], filter: BookingFilter) {
  const errors: string[] = [];
  let sumAdults = 0;
  let sumKids = 0;
  let totalPrice = 0;
  let priceUnknown = false;
  const nights = bookingNightsFromFilter(filter);

  items.forEach((item) => {
    const adults = Number(item.adults) || 0;
    const kids = Number(item.kids) || 0;
    sumAdults += adults;
    sumKids += kids;
    const cap = roomCapacity(item.room);
    if (kids > 0 && adults <= 0) {
      errors.push(`В ${item.room.name || item.room.room_type || `варианте #${item.room.id}`} дети должны быть со взрослым`);
    }
    if (adults + kids > cap) {
      errors.push(`Превышена вместимость у ${item.room.name || item.room.room_type || `варианта #${item.room.id}`}`);
    }
    const subtotal = calcRoomSubtotal(item.room, adults, kids);
    if (subtotal == null) {
      priceUnknown = true;
    } else {
      totalPrice += subtotal * nights;
    }
  });

  const needAdults = Number(filter.adults) || 0;
  const needKids = Number(filter.kids) || 0;
  if (sumAdults !== needAdults || sumKids !== needKids) {
    errors.push(`Распределите гостей: взрослые ${sumAdults}/${needAdults}, дети ${sumKids}/${needKids}`);
  }

  return {
    ok: errors.length === 0 && items.length > 0,
    errors,
    sumAdults,
    sumKids,
    totalPrice: priceUnknown ? null : totalPrice,
  };
}

export function campCanSatisfyFilter(rooms: ApiRoom[], filter: BookingFilter): boolean {
  const availableRooms = rooms.filter((room) => room.available !== false);
  if (!availableRooms.length) return false;
  const totalGuests = bookingGuestsTotal(filter);
  if (totalGuests <= 0) return false;
  if (filter.allowSplitRooms) {
    return !!findBestAllocation(availableRooms, totalGuests);
  }
  return availableRooms.some((room) => roomCapacity(room) >= totalGuests);
}

export function normalizeAvailableRooms(payload: unknown): ApiRoom[] {
  if (!payload || typeof payload !== "object") return [];
  const rows = (payload as ApiAvailableRoomsResponse).rooms;
  if (!Array.isArray(rows)) return [];
  const rooms: ApiRoom[] = [];
  for (const item of rows) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const id = Number(row.id);
    if (!Number.isFinite(id)) continue;
    const photos = Array.isArray(row.photos)
      ? row.photos
          .map((photo) => {
            if (!photo || typeof photo !== "object") return null;
            const value = photo as Record<string, unknown>;
            if (typeof value.url !== "string" || !value.url) return null;
            return {
              url: value.url,
              cover: Boolean(value.cover),
              sort: value.sort == null ? null : Number(value.sort),
            };
          })
          .filter((photo): photo is NonNullable<typeof photo> => photo !== null)
      : [];
    rooms.push({
      id,
      camp_id: row.camp_id == null ? null : Number(row.camp_id),
      name: typeof row.name === "string" ? row.name : null,
      room_type: typeof row.room_type === "string" ? row.room_type : null,
      floors: row.floors == null ? null : Number(row.floors),
      floor: row.floor == null ? null : Number(row.floor),
      beds_single: row.beds_single == null ? null : Number(row.beds_single),
      beds_double: row.beds_double == null ? null : Number(row.beds_double),
      capacity: row.capacity == null ? null : Number(row.capacity),
      price: row.price == null ? null : Number(row.price),
      price_adult: row.price_adult == null ? null : Number(row.price_adult),
      price_child: row.price_child == null ? null : Number(row.price_child),
      photo_main: typeof row.photo_main === "string" ? row.photo_main : null,
      description: typeof row.description === "string" ? row.description : null,
      available: row.available == null ? true : Boolean(row.available),
      photos,
    });
  }
  return rooms.filter((room) => room.available !== false);
}

export function loadStoredBookingFilter(): BookingFilter | null {
  try {
    const raw = window.localStorage.getItem(BOOKING_FILTER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<BookingFilter>;
    if (!parsed) return null;
    const normalized: BookingFilter = {
      from: typeof parsed.from === "string" ? parsed.from : "",
      to: typeof parsed.to === "string" ? parsed.to : "",
      adults: Math.max(1, Number(parsed.adults) || 2),
      kids: Math.max(0, Number(parsed.kids) || 0),
      allowSplitRooms: Boolean(parsed.allowSplitRooms),
    };
    return isBookingFilterReady(normalized) ? normalized : null;
  } catch {
    return null;
  }
}

export function saveStoredBookingFilter(filter: BookingFilter | null) {
  if (!filter || !isBookingFilterReady(filter)) {
    window.localStorage.removeItem(BOOKING_FILTER_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(BOOKING_FILTER_STORAGE_KEY, JSON.stringify(filter));
}
