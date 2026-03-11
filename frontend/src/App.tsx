import { AnimatePresence, motion } from "framer-motion";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { AuthSheet } from "./components/AuthSheet";
import { BookingFilterSheet } from "./components/BookingFilterSheet";
import { CampMarker } from "./components/CampMarker";
import { MapCanvas, type MapCanvasHandle } from "./components/MapCanvas";
import { authFetchJson, clearStoredAuth, getStoredAuth, setStoredAuth, type StoredAuth } from "./lib/auth";
import {
  autoDistributeGuests,
  bookingGuestsTotal,
  bookingNightsFromFilter,
  campCanSatisfyFilter,
  calcRoomSubtotal,
  findBestAllocation,
  formatPriceRub,
  isBookingFilterReady,
  loadStoredBookingFilter,
  normalizeAvailableRooms,
  roomCapacity,
  roomPriceFrom,
  saveStoredBookingFilter,
  validateAllocation,
  type BookingFilter,
} from "./lib/booking";
import { formatCampPrice, isCampDisabled, normalizeCampList, resolveCampKind, resolveCampSize } from "./lib/camps";
import type { AuthMeResponse } from "./types/auth";
import type { ApiCamp, ApiRoom } from "./types/catalog";

type OrderCreateResponse = {
  ok: boolean;
  order_id: string;
  booking_ids: number[];
};

function App() {
  const [camps, setCamps] = useState<ApiCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<BookingFilter | null>(() => loadStoredBookingFilter());
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [availabilityByCamp, setAvailabilityByCamp] = useState<Record<number, ApiRoom[]>>({});
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [availabilityError, setAvailabilityError] = useState<string | null>(null);
  const [selectedRoomIds, setSelectedRoomIds] = useState<number[]>([]);
  const [bookingComment, setBookingComment] = useState("");
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingSuccess, setBookingSuccess] = useState<{ orderId: string; bookingIds: number[] } | null>(null);
  const [isSubmittingBooking, setIsSubmittingBooking] = useState(false);
  const [auth, setAuth] = useState<StoredAuth | null>(() => getStoredAuth());
  const [isAuthLoading, setIsAuthLoading] = useState(Boolean(getStoredAuth()?.token));
  const [isAuthSheetOpen, setIsAuthSheetOpen] = useState(false);
  const mapRef = useRef<MapCanvasHandle | null>(null);
  const drawerRef = useRef<HTMLElement | null>(null);
  const shouldRevealDrawerRef = useRef(false);

  const activeCamps = useMemo(() => camps.filter((camp) => !isCampDisabled(camp)), [camps]);
  const filterReady = isBookingFilterReady(filter);
  const totalGuests = bookingGuestsTotal(filter);
  const nights = bookingNightsFromFilter(filter);

  async function loadCamps(cache: RequestCache = "default") {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await fetch("/api/camps", { credentials: "same-origin", cache });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      const nextCamps = normalizeCampList(payload);
      setCamps(nextCamps);
      setSelectedCampId((current) => {
        if (current && nextCamps.some((camp) => camp.id === current && !isCampDisabled(camp))) return current;
        return nextCamps.find((camp) => !isCampDisabled(camp))?.id ?? null;
      });
    } catch {
      setErrorMessage("Не удалось загрузить базы. Проверьте API и повторите.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadCamps();
  }, []);

  useEffect(() => {
    saveStoredBookingFilter(filter);
  }, [filter]);

  useEffect(() => {
    let cancelled = false;
    const stored = getStoredAuth();
    if (!stored?.token) {
      setAuth(null);
      setIsAuthLoading(false);
      return;
    }

    setIsAuthLoading(true);
    void authFetchJson<AuthMeResponse>("/api/auth/me")
      .then((payload) => {
        if (cancelled) return;
        const nextAuth = { token: stored.token, user: payload.user };
        setStoredAuth(nextAuth);
        setAuth(nextAuth);
      })
      .catch(() => {
        clearStoredAuth();
        if (!cancelled) {
          setAuth(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsAuthLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!filterReady || !filter) {
      setAvailabilityByCamp({});
      setAvailabilityLoading(false);
      setAvailabilityError(null);
      return;
    }
    const appliedFilter = filter;

    async function loadAvailability() {
      setAvailabilityLoading(true);
      setAvailabilityError(null);
      try {
        const entries = await Promise.all(
          activeCamps.map(async (camp) => {
            const query = new URLSearchParams({ from: appliedFilter.from, to: appliedFilter.to });
            const response = await fetch(`/api/camps/${camp.id}/available-rooms?${query.toString()}`, {
              credentials: "same-origin",
            });
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`);
            }
            return [camp.id, normalizeAvailableRooms(await response.json())] as const;
          }),
        );
        if (cancelled) return;
        setAvailabilityByCamp(Object.fromEntries(entries));
      } catch {
        if (cancelled) return;
        setAvailabilityByCamp({});
        setAvailabilityError("Не удалось проверить доступность на выбранные даты.");
      } finally {
        if (!cancelled) {
          setAvailabilityLoading(false);
        }
      }
    }

    void loadAvailability();
    return () => {
      cancelled = true;
    };
  }, [activeCamps, filterReady, filter?.from, filter?.to]);

  const visibleCamps = useMemo(() => {
    if (!filterReady || !filter) return activeCamps;
    return activeCamps.filter((camp) => campCanSatisfyFilter(availabilityByCamp[camp.id] || [], filter));
  }, [activeCamps, availabilityByCamp, filter, filterReady]);

  useEffect(() => {
    setSelectedCampId((current) => {
      if (current && visibleCamps.some((camp) => camp.id === current)) return current;
      return visibleCamps[0]?.id ?? null;
    });
  }, [visibleCamps]);

  const selectedCamp = useMemo(
    () => visibleCamps.find((camp) => camp.id === selectedCampId) ?? visibleCamps[0] ?? null,
    [selectedCampId, visibleCamps],
  );

  useEffect(() => {
    if (!selectedCamp) return;
    mapRef.current?.focusCamp(selectedCamp);
    const shouldRevealDrawer = shouldRevealDrawerRef.current;
    shouldRevealDrawerRef.current = false;
    if (!shouldRevealDrawer) return;
    if (typeof window === "undefined") return;
    if (!window.matchMedia("(max-width: 760px)").matches) return;
    window.requestAnimationFrame(() => {
      drawerRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    });
  }, [selectedCamp]);

  const selectedCampRooms = useMemo(
    () => (selectedCamp ? availabilityByCamp[selectedCamp.id] || [] : []),
    [availabilityByCamp, selectedCamp],
  );

  const recommendedRoomIds = useMemo(() => {
    if (!selectedCamp || !filterReady || !filter) return [];
    if (!selectedCampRooms.length) return [];
    if (filter.allowSplitRooms) {
      return (findBestAllocation(selectedCampRooms, totalGuests) ?? []).map((room) => room.id);
    }
    const bestRoom = [...selectedCampRooms]
      .filter((room) => roomCapacity(room) >= totalGuests)
      .sort((left, right) => (roomPriceFrom(left) || Number.MAX_SAFE_INTEGER) - (roomPriceFrom(right) || Number.MAX_SAFE_INTEGER))[0];
    return bestRoom ? [bestRoom.id] : [];
  }, [filter, filterReady, selectedCamp, selectedCampRooms, totalGuests]);

  useEffect(() => {
    if (!selectedCamp || !filterReady || !filter) {
      if (selectedRoomIds.length) setSelectedRoomIds([]);
      return;
    }

    const roomsById = new Map(selectedCampRooms.map((room) => [room.id, room]));
    const currentRooms = selectedRoomIds
      .map((roomId) => roomsById.get(roomId))
      .filter((room): room is ApiRoom => Boolean(room));

    let currentValid = false;
    if (filter.allowSplitRooms) {
      currentValid = validateAllocation(autoDistributeGuests(currentRooms, filter), filter).ok;
    } else {
      currentValid = currentRooms.length === 1 && roomCapacity(currentRooms[0]) >= totalGuests;
    }

    const nextIds = currentValid ? selectedRoomIds : recommendedRoomIds;
    if (selectedRoomIds.join(",") !== nextIds.join(",")) {
      setSelectedRoomIds(nextIds);
    }
  }, [filter, filterReady, recommendedRoomIds, selectedCamp, selectedCampRooms, selectedRoomIds, totalGuests]);

  const selectedRooms = useMemo(
    () => selectedCampRooms.filter((room) => selectedRoomIds.includes(room.id)),
    [selectedCampRooms, selectedRoomIds],
  );
  const allocations = useMemo(
    () => (filterReady && filter ? autoDistributeGuests(selectedRooms, filter) : []),
    [filter, filterReady, selectedRooms],
  );
  const allocationCheck = useMemo(
    () =>
      filterReady && filter
        ? validateAllocation(allocations.filter((item) => item.adults + item.kids > 0), filter)
        : { ok: false, errors: [], sumAdults: 0, sumKids: 0, totalPrice: null as number | null },
    [allocations, filter, filterReady],
  );

  const filterSummary = useMemo(() => {
    if (!filterReady || !filter) return "Фильтр ещё не выбран";
    const fromText = new Date(filter.from).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
    const toText = new Date(filter.to).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
    return `${fromText} → ${toText} • ${filter.adults} взрослых${filter.kids ? `, ${filter.kids} детей` : ""}`;
  }, [filter, filterReady]);

  async function handleRefresh() {
    await loadCamps("no-store");
  }

  function handleSelectCamp(campId: number) {
    shouldRevealDrawerRef.current = true;
    startTransition(() => {
      setSelectedCampId(campId);
    });
  }

  function handleApplyFilter(nextFilter: BookingFilter | null) {
    setFilter(nextFilter);
    setIsFilterOpen(false);
    setSelectedRoomIds([]);
    setBookingComment("");
    setBookingError(null);
    setBookingSuccess(null);
  }

  function handleToggleRoom(room: ApiRoom) {
    if (!filterReady || !filter) return;
    const selectable = filter.allowSplitRooms || roomCapacity(room) >= totalGuests;
    if (!selectable) return;

    setBookingError(null);
    setBookingSuccess(null);
    setSelectedRoomIds((current) => {
      const exists = current.includes(room.id);
      if (!filter.allowSplitRooms) {
        return exists ? [] : [room.id];
      }
      if (exists) {
        return current.filter((roomId) => roomId !== room.id);
      }
      return [...current, room.id];
    });
  }

  async function handleSubmitBooking() {
    if (!selectedCamp || !filterReady || !filter) {
      setBookingError("Сначала выберите даты и гостей.");
      return;
    }
    if (!auth?.token) {
      setIsAuthSheetOpen(true);
      return;
    }

    const items = allocations.filter((item) => item.adults + item.kids > 0);
    const validation = validateAllocation(items, filter);
    if (!validation.ok) {
      setBookingError(validation.errors[0] || "Проверьте распределение гостей.");
      return;
    }

    setIsSubmittingBooking(true);
    setBookingError(null);
    setBookingSuccess(null);
    try {
      const payload = await authFetchJson<OrderCreateResponse>("/api/auth/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camp_id: selectedCamp.id,
          check_in: filter.from,
          check_out: filter.to,
          items: items.map((item) => ({
            room_id: item.room.id,
            adults: item.adults,
            kids: item.kids,
          })),
          comment: bookingComment.trim() || undefined,
        }),
      });
      setBookingSuccess({ orderId: payload.order_id, bookingIds: payload.booking_ids || [] });
    } catch (error) {
      setBookingError(error instanceof Error ? error.message : "Не удалось создать заявку.");
    } finally {
      setIsSubmittingBooking(false);
    }
  }

  async function handleLogout() {
    try {
      await authFetchJson("/api/auth/logout", { method: "POST" });
    } catch {
      // ignore logout transport errors
    }
    clearStoredAuth();
    setAuth(null);
  }

  return (
    <main className="shell shell--app">
      <section className="hero panel">
        <div className="hero__copy">
          <span className="eyebrow">React Booking Screen</span>
          <h1>Новая карта уже умеет не только показывать базы, но и вести к бронированию.</h1>
          <p>
            В этот экран уже перенесены фильтр дат, подбор доступных баз по вашему API,
            выбор вариантов размещения и отправка заявки на бронь для авторизованного пользователя.
          </p>

          <div className="hero__chips">
            <span>Leaflet карта</span>
            <span>новые marker icons</span>
            <span>реальный availability check</span>
            <span>order create через `/api/auth/orders`</span>
          </div>
        </div>

        <aside className="inspector panel panel--soft">
          <div className="inspector__label">Статус экрана</div>
          <div className="inspector__name">
            {isLoading ? "Загрузка карты" : filterReady ? `${visibleCamps.length} баз подходят под фильтр` : `${activeCamps.length} активных баз на карте`}
          </div>
          <div className="inspector__meta">Старый экран ещё жив как fallback, но booking-flow уже начал переезжать сюда.</div>
          <div className="status-stack">
            <div className="status-card">
              <strong>Фильтр</strong>
              <span>{filterSummary}</span>
            </div>
            <div className="status-card">
              <strong>Авторизация</strong>
              <span>
                {isAuthLoading
                  ? "Проверяем сессию..."
                  : auth?.user
                    ? `${auth.user.name || "Пользователь"} • ${auth.user.phone || "без телефона"}`
                    : "Пока не вошли"}
              </span>
            </div>
          </div>
          <div className="hero__chips">
            <span onClick={() => setIsFilterOpen(true)} role="button" tabIndex={0}>даты и гости</span>
            <span onClick={() => mapRef.current?.locateUser()} role="button" tabIndex={0}>моё местоположение</span>
            <span onClick={() => void handleRefresh()} role="button" tabIndex={0}>обновить данные</span>
            {auth?.user ? (
              <span onClick={() => void handleLogout()} role="button" tabIndex={0}>выйти</span>
            ) : (
              <span onClick={() => setIsAuthSheetOpen(true)} role="button" tabIndex={0}>войти</span>
            )}
          </div>
        </aside>
      </section>

      <section className="map-layout">
        <section className="map-screen panel">
          <div className="map-screen__toolbar">
            <button type="button" className="map-action" onClick={() => setIsFilterOpen(true)}>
              Даты и гости
            </button>
            <button type="button" className="map-action" onClick={() => mapRef.current?.locateUser()}>
              Геопозиция
            </button>
            <button type="button" className="map-action map-action--ghost" onClick={() => mapRef.current?.fitToCamps()}>
              Все базы
            </button>
          </div>

          {filterReady ? <div className="map-screen__filter-chip">{filterSummary}</div> : null}

          <MapCanvas
            ref={mapRef}
            camps={visibleCamps}
            selectedCampId={selectedCampId}
            onSelectCamp={handleSelectCamp}
          />

          <AnimatePresence>
            {selectedCamp ? (
              <motion.aside
                key={selectedCamp.id}
                className="map-drawer"
                ref={drawerRef}
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 18 }}
                transition={{ duration: 0.22 }}
              >
                {selectedCamp.photo_main ? (
                  <div
                    className="map-drawer__media"
                    style={{
                      backgroundImage: `linear-gradient(180deg, rgba(17,22,18,0.08), rgba(17,22,18,0.42)), url(${selectedCamp.photo_main})`,
                    }}
                  />
                ) : null}

                <div className="map-drawer__body">
                  <div className="map-drawer__kicker">Сейчас выбрано</div>
                  <h2>{selectedCamp.name || `База #${selectedCamp.id}`}</h2>
                  <div className="map-drawer__meta">
                    {selectedCamp.lake_name ? <span>озеро {selectedCamp.lake_name}</span> : null}
                    {selectedCamp.rooms_count ? <span>{selectedCamp.rooms_count} размещений</span> : null}
                    {selectedCamp.address ? <span>{selectedCamp.address}</span> : null}
                  </div>
                  <p>{selectedCamp.description || "Описание пока не заполнено."}</p>

                  <div className="map-drawer__price">
                    <span>от</span> {formatCampPrice(selectedCamp.min_price)}
                  </div>

                  <div className="map-drawer__badges">
                    <span>{resolveCampKind(selectedCamp)}</span>
                    <span>{resolveCampSize(selectedCamp)}</span>
                    <span>{filterReady ? `${nights} ночи` : "без фильтра дат"}</span>
                  </div>

                  <section className="booking-block">
                    <div className="booking-block__head">
                      <div>
                        <div className="map-drawer__subkicker">Бронирование</div>
                        <strong>{filterReady ? filterSummary : "Сначала укажите даты и гостей"}</strong>
                      </div>
                      <button type="button" className="mini-button" onClick={() => setIsFilterOpen(true)}>
                        Изменить
                      </button>
                    </div>

                    {!filterReady ? (
                      <div className="empty-state">
                        Новый экран уже умеет фильтровать базу по доступности. Сначала задайте даты и состав гостей.
                      </div>
                    ) : availabilityLoading ? (
                      <div className="empty-state">Проверяем доступность на выбранные даты...</div>
                    ) : availabilityError ? (
                      <div className="empty-state empty-state--error">{availabilityError}</div>
                    ) : !selectedCampRooms.length ? (
                      <div className="empty-state">
                        Для этой базы нет свободных вариантов на выбранные даты и состав гостей.
                      </div>
                    ) : (
                      <>
                        <div className="room-grid">
                          {selectedCampRooms.map((room) => {
                            const selected = selectedRoomIds.includes(room.id);
                            const selectable = filter.allowSplitRooms || roomCapacity(room) >= totalGuests;
                            const photo = room.photo_main || room.photos?.[0]?.url || "";
                            const priceHint =
                              Number(room.price) > 0
                                ? `${formatPriceRub(room.price)}/сутки`
                                : Number(room.price_adult) > 0
                                  ? `${formatPriceRub(room.price_adult)}/взр.`
                                  : "цена уточняется";

                            return (
                              <button
                                key={room.id}
                                type="button"
                                className={`room-card ${selected ? "room-card--selected" : ""} ${!selectable ? "room-card--disabled" : ""}`}
                                onClick={() => handleToggleRoom(room)}
                                disabled={!selectable}
                              >
                                <div
                                  className="room-card__media"
                                  style={
                                    photo
                                      ? { backgroundImage: `linear-gradient(180deg, rgba(16,22,18,0.06), rgba(16,22,18,0.38)), url(${photo})` }
                                      : undefined
                                  }
                                />
                                <div className="room-card__body">
                                  <div className="room-card__title-row">
                                    <strong>{room.name || room.room_type || `Вариант #${room.id}`}</strong>
                                    <span>{priceHint}</span>
                                  </div>
                                  <div className="room-card__meta">
                                    <span>вместимость {roomCapacity(room)}</span>
                                    {room.room_type ? <span>{room.room_type}</span> : null}
                                    {selected ? <span>выбран</span> : null}
                                  </div>
                                  {!selectable ? (
                                    <div className="room-card__note">
                                      Не подходит для {totalGuests} гостей без split-режима.
                                    </div>
                                  ) : room.description ? (
                                    <div className="room-card__note">{room.description}</div>
                                  ) : null}
                                </div>
                              </button>
                            );
                          })}
                        </div>

                        <div className="allocation-panel">
                          <div className="map-drawer__subkicker">Итоговое размещение</div>
                          {!allocations.filter((item) => item.adults + item.kids > 0).length ? (
                            <div className="empty-state">
                              Выберите вариант размещения. Если нужен split-формат, включите его в фильтре.
                            </div>
                          ) : (
                            <>
                              <div className="alloc-list">
                                {allocations
                                  .filter((item) => item.adults + item.kids > 0)
                                  .map((item) => {
                                    const subtotal = calcRoomSubtotal(item.room, item.adults, item.kids);
                                    return (
                                      <div key={item.room.id} className="alloc-card">
                                        <div>
                                          <strong>{item.room.name || item.room.room_type || `Вариант #${item.room.id}`}</strong>
                                          <span>
                                            {item.adults} взрослых{item.kids ? `, ${item.kids} детей` : ""}
                                          </span>
                                        </div>
                                        <b>{subtotal == null ? "цена уточняется" : formatPriceRub(subtotal * nights)}</b>
                                      </div>
                                    );
                                  })}
                              </div>

                              <label className="comment-field">
                                <span>Комментарий к заявке</span>
                                <textarea
                                  rows={3}
                                  placeholder="Например: нужен ранний заезд или размещение ближе к воде"
                                  value={bookingComment}
                                  onChange={(event) => setBookingComment(event.target.value)}
                                />
                              </label>

                              <div className="booking-summary-card">
                                <div>
                                  <strong>
                                    {allocationCheck.totalPrice == null
                                      ? "Цена зависит от подтверждения"
                                      : `Итого ${formatPriceRub(allocationCheck.totalPrice)}`}
                                  </strong>
                                  <span>
                                    {nights} ночи • {allocationCheck.sumAdults} взрослых
                                    {allocationCheck.sumKids ? ` • ${allocationCheck.sumKids} детей` : ""}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  className="sheet-button"
                                  onClick={() => void handleSubmitBooking()}
                                  disabled={isSubmittingBooking || !allocationCheck.ok}
                                >
                                  {!auth?.token
                                    ? "Войти и продолжить"
                                    : isSubmittingBooking
                                      ? "Отправка..."
                                      : "Отправить заявку"}
                                </button>
                              </div>

                              {bookingError ? <div className="sheet-error">{bookingError}</div> : null}
                              {allocationCheck.errors.length && !bookingError ? (
                                <div className="sheet-error">{allocationCheck.errors[0]}</div>
                              ) : null}
                              {bookingSuccess ? (
                                <div className="success-card">
                                  <strong>Заявка создана</strong>
                                  <span>
                                    Заказ #{bookingSuccess.orderId}
                                    {bookingSuccess.bookingIds.length
                                      ? ` • броней: ${bookingSuccess.bookingIds.join(", ")}`
                                      : ""}
                                  </span>
                                </div>
                              ) : null}
                            </>
                          )}
                        </div>
                      </>
                    )}
                  </section>
                </div>
              </motion.aside>
            ) : null}
          </AnimatePresence>
        </section>

        <section className="system-column">
          <div className="panel panel--soft">
            <div className="section-head">
              <div>
                <div className="section-head__eyebrow">Marker System</div>
                <h2>Состояния новых маркеров</h2>
              </div>
              <p>Тот же визуальный язык, который уже работает на реальной карте и больше не живёт отдельно от продукта.</p>
            </div>

            <div className="state-grid">
              <div className="state-card">
                <div className="state-card__title">Обычная база</div>
                <CampMarker kind="house" price={3500} name="Обычная база" />
              </div>
              <div className="state-card">
                <div className="state-card__title">Selected</div>
                <CampMarker kind="glamping" price={7800} name="Selected" selected />
              </div>
              <div className="state-card">
                <div className="state-card__title">VIP</div>
                <CampMarker kind="family" price={9500} name="VIP" vip />
              </div>
              <div className="state-card">
                <div className="state-card__title">Disabled</div>
                <CampMarker kind="hotel" price={5100} name="Disabled" disabled />
              </div>
            </div>
          </div>

          <div className="panel panel--soft">
            <div className="section-head">
              <div>
                <div className="section-head__eyebrow">Booking Flow</div>
                <h2>Что уже переехало</h2>
              </div>
              <p>Это уже не просто витрина карты. Новый экран начал забирать реальный пользовательский сценарий целиком.</p>
            </div>

            <div className="migration-list">
              <div className="migration-item">
                <strong>Уже есть</strong>
                <span>Фильтр дат и гостей, проверка доступности по всем активным базам, выбор вариантов и отправка `order`.</span>
              </div>
              <div className="migration-item">
                <strong>Auth reuse</strong>
                <span>Если пользователь уже входил в старом экране, новый маршрут использует тот же token из `auth_profile`.</span>
              </div>
              <div className="migration-item">
                <strong>Следующий слой</strong>
                <span>Глубокая карточка базы, rooms details, регистрация нового пользователя и личный кабинет уже в React.</span>
              </div>
              {errorMessage ? (
                <div className="migration-item migration-item--error">
                  <strong>Ошибка</strong>
                  <span>{errorMessage}</span>
                </div>
              ) : null}
            </div>
          </div>
        </section>
      </section>

      <BookingFilterSheet
        open={isFilterOpen}
        value={filter}
        onClose={() => setIsFilterOpen(false)}
        onApply={handleApplyFilter}
      />

      <AuthSheet
        open={isAuthSheetOpen}
        onClose={() => setIsAuthSheetOpen(false)}
        onSuccess={(nextAuth) => {
          setStoredAuth(nextAuth);
          setAuth(nextAuth);
          setBookingError(null);
        }}
      />
    </main>
  );
}

export default App;
