import { ChevronDown, ChevronLeft, ChevronRight, ChevronsLeftRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { fetchCrmCalendarFeed, fetchCrmCamps, type CrmCalendarFeed, type CrmCamp } from "../session";

const statusClasses = {
  processing: "border-amber-500/30 bg-amber-500/20 text-amber-200",
  confirmed: "border-emerald-500/30 bg-emerald-500/20 text-emerald-200",
  cancelled: "border-rose-500/30 bg-rose-500/20 text-rose-200",
  completed: "border-slate-500/30 bg-slate-500/20 text-slate-200",
} as const;

const statusDotClasses = {
  processing: "bg-amber-400",
  confirmed: "bg-emerald-400",
  cancelled: "bg-rose-400",
  completed: "bg-slate-300",
} as const;

const emptyFeed: CrmCalendarFeed = {
  date_from: null,
  date_to: null,
  rooms: [],
};

const roomColumnWidth = 308;

type ViewMode = "month" | "week";

function formatDateParam(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getMonthLabel(value: Date) {
  const monthLabelRaw = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" }).format(value);
  return `${monthLabelRaw.charAt(0).toUpperCase()}${monthLabelRaw.slice(1)}`;
}

function startOfWeek(value: Date) {
  const next = new Date(value);
  const weekday = next.getDay() || 7;
  next.setHours(0, 0, 0, 0);
  next.setDate(next.getDate() - weekday + 1);
  return next;
}

function addDays(value: Date, amount: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + amount);
  return next;
}

function buildPeriodDates(start: Date, end: Date) {
  const result: Date[] = [];
  for (let cursor = new Date(start); cursor <= end; cursor = addDays(cursor, 1)) {
    result.push(new Date(cursor));
  }
  return result;
}

function getWeekLabel(start: Date, end: Date) {
  const startDay = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(start);
  const endDay = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(end);
  return `${startDay} — ${endDay}`;
}

function getDayNumberLabel(value: Date) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric" }).format(value);
}

function getWeekdayLabel(value: Date) {
  return new Intl.DateTimeFormat("ru-RU", { weekday: "short" }).format(value).replace(".", "");
}

export default function CalendarPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [focusDate, setFocusDate] = useState(() => new Date());
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [selectedRoomId, setSelectedRoomId] = useState("");
  const [feed, setFeed] = useState<CrmCalendarFeed>(emptyFeed);
  const [isMetaLoading, setIsMetaLoading] = useState(true);
  const [isFeedLoading, setIsFeedLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [hasHorizontalOverflow, setHasHorizontalOverflow] = useState(false);
  const gridScrollRef = useRef<HTMLDivElement | null>(null);
  const sliderScrollRef = useRef<HTMLDivElement | null>(null);
  const syncSourceRef = useRef<"grid" | "slider" | null>(null);

  const periodStart = useMemo(() => {
    if (viewMode === "week") {
      return startOfWeek(focusDate);
    }
    return new Date(focusDate.getFullYear(), focusDate.getMonth(), 1);
  }, [focusDate, viewMode]);

  const periodEnd = useMemo(() => {
    if (viewMode === "week") {
      return addDays(periodStart, 6);
    }
    return new Date(periodStart.getFullYear(), periodStart.getMonth() + 1, 0);
  }, [periodStart, viewMode]);

  const visibleDates = useMemo(() => buildPeriodDates(periodStart, periodEnd), [periodEnd, periodStart]);
  const dayColumnWidth = viewMode === "week" ? 88 : 56;
  const calendarContentWidth = roomColumnWidth + visibleDates.length * dayColumnWidth;
  const dateFrom = formatDateParam(periodStart);
  const dateTo = formatDateParam(periodEnd);
  const periodLabel = viewMode === "week" ? getWeekLabel(periodStart, periodEnd) : getMonthLabel(periodStart);

  useEffect(() => {
    const controller = new AbortController();
    setIsMetaLoading(true);
    setErrorMessage("");

    fetchCrmCamps(controller.signal)
      .then((items) => {
        setCamps(items);
        setSelectedCampId((current) => {
          if (!items.length) {
            return null;
          }
          if (current && items.some((item) => item.id === current)) {
            return current;
          }
          return items[0].id;
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить список баз");
        setCamps([]);
        setSelectedCampId(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsMetaLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedCampId) {
      setFeed(emptyFeed);
      return;
    }

    const controller = new AbortController();
    setIsFeedLoading(true);
    setErrorMessage("");

    fetchCrmCalendarFeed(
      {
        campId: selectedCampId,
        dateFrom,
        dateTo,
      },
      controller.signal,
    )
      .then((payload) => {
        setFeed(payload);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить календарь");
        setFeed(emptyFeed);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsFeedLoading(false);
        }
      });

    return () => controller.abort();
  }, [dateFrom, dateTo, reloadKey, selectedCampId]);

  useEffect(() => {
    if (!selectedRoomId) {
      return;
    }
    if (!feed.rooms.some((room) => room.id === selectedRoomId)) {
      setSelectedRoomId("");
    }
  }, [feed.rooms, selectedRoomId]);

  useEffect(() => {
    const updateOverflowState = () => {
      const node = gridScrollRef.current;
      if (!node) {
        setHasHorizontalOverflow(false);
        return;
      }
      setHasHorizontalOverflow(node.scrollWidth - node.clientWidth > 8);
    };

    updateOverflowState();
    if (typeof window !== "undefined") {
      window.addEventListener("resize", updateOverflowState);
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("resize", updateOverflowState);
      }
    };
  }, [calendarContentWidth, feed.rooms.length, selectedRoomId, viewMode]);

  const hasCampOptions = camps.length > 0;
  const hasRoomOptions = feed.rooms.length > 0;
  const visibleRooms = selectedRoomId ? feed.rooms.filter((room) => room.id === selectedRoomId) : feed.rooms;

  const syncScroll = (source: "grid" | "slider") => {
    const fromNode = source === "grid" ? gridScrollRef.current : sliderScrollRef.current;
    const toNode = source === "grid" ? sliderScrollRef.current : gridScrollRef.current;
    if (!fromNode || !toNode) {
      return;
    }
    if (syncSourceRef.current && syncSourceRef.current !== source) {
      return;
    }
    syncSourceRef.current = source;
    toNode.scrollLeft = fromNode.scrollLeft;
    requestAnimationFrame(() => {
      syncSourceRef.current = null;
    });
  };

  return (
    <PageMotion className="space-y-6">
      <SectionHeading title="Календарь размещения" description="Живой календарь показывает реальные бронирования по выбранной базе, чтобы быстро видеть загрузку и конфликты." />

      <section className="glass-card p-5 md:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() =>
                setFocusDate((current) =>
                  viewMode === "week" ? addDays(current, -7) : new Date(current.getFullYear(), current.getMonth() - 1, 1),
                )
              }
              className="soft-button h-11 w-11 px-0"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button type="button" onClick={() => setFocusDate(new Date())} className="soft-button">
              Сегодня
            </button>
            <button
              type="button"
              onClick={() =>
                setFocusDate((current) =>
                  viewMode === "week" ? addDays(current, 7) : new Date(current.getFullYear(), current.getMonth() + 1, 1),
                )
              }
              className="soft-button h-11 w-11 px-0"
            >
              <ChevronRight className="h-4 w-4" />
            </button>

            <div className="ml-0 rounded-2xl border border-border bg-background/70 p-1 sm:ml-2">
              <button
                type="button"
                onClick={() => setViewMode("month")}
                className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                  viewMode === "month" ? "border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Месяц
              </button>
              <button
                type="button"
                onClick={() => setViewMode("week")}
                className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                  viewMode === "week" ? "border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Неделя
              </button>
            </div>

            <h2 className="text-xl font-semibold tracking-[-0.04em] text-foreground sm:ml-2">{periodLabel}</h2>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:flex xl:flex-wrap xl:items-center">
            <div className="relative">
              <select
                className="soft-input w-full min-w-0 appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-52"
                value={selectedCampId ?? ""}
                onChange={(event) => {
                  setSelectedCampId(event.target.value ? Number(event.target.value) : null);
                  setSelectedRoomId("");
                }}
                disabled={!hasCampOptions || isMetaLoading}
              >
                {hasCampOptions ? (
                  camps.map((camp) => (
                    <option key={camp.id} value={camp.id}>
                      {camp.name}
                    </option>
                  ))
                ) : (
                  <option value="">Нет подключённых баз</option>
                )}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>

            <div className="relative">
              <select
                className="soft-input w-full min-w-0 appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-44"
                value={selectedRoomId}
                onChange={(event) => setSelectedRoomId(event.target.value)}
                disabled={!hasRoomOptions || isFeedLoading}
              >
                {hasRoomOptions ? (
                  <>
                    <option value="">Все апартаменты</option>
                    {feed.rooms.map((room) => (
                      <option key={room.id} value={room.id}>
                        {room.title}
                      </option>
                    ))}
                  </>
                ) : (
                  <option value="">Апартаменты не найдены</option>
                )}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>
        </div>

        <p className="mt-4 text-sm text-muted-foreground md:hidden">На телефоне календарь прокручивается по горизонтали. Ниже появится бегунок, если сетка шире экрана.</p>

        <div className="mt-5 flex flex-wrap items-center gap-4 text-xs font-medium text-muted-foreground">
          {[
            ["processing", "Нужно обработать"],
            ["confirmed", "Подтверждено"],
            ["cancelled", "Отменено"],
            ["completed", "Завершено"],
          ].map(([status, label]) => (
            <div key={status} className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${statusDotClasses[status as keyof typeof statusDotClasses]}`} />
              {label}
            </div>
          ))}
        </div>

        {errorMessage ? (
          <div className="mt-6 rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p>{errorMessage}</p>
              <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="soft-button shrink-0">
                Повторить
              </button>
            </div>
          </div>
        ) : null}

        {isMetaLoading || isFeedLoading ? (
          <div className="mt-6">
            <EmptyState icon={ChevronRight} title="Загружаем календарь" description="Подтягиваем базы, апартаменты и бронирования из CRM." />
          </div>
        ) : !hasCampOptions ? (
          <div className="mt-6">
            <EmptyState icon={ChevronRight} title="У вас пока нет подключённых баз" description="После выдачи доступа к базе здесь появятся её апартаменты и бронирования." />
          </div>
        ) : !feed.rooms.length ? (
          <div className="mt-6">
            <EmptyState
              icon={ChevronRight}
              title="Номерной фонд ещё не заполнен"
              description="Добавьте апартаменты в CRM или через superadmin, и календарь сразу начнёт отображать сетку размещения."
            />
          </div>
        ) : (
          <>
            <div
              ref={gridScrollRef}
              onScroll={() => syncScroll("grid")}
              className="mt-6 overflow-x-auto rounded-3xl border border-border bg-background/55"
            >
              <div style={{ minWidth: calendarContentWidth }}>
                <div className="flex border-b border-border bg-card/70">
                  <div className="sticky left-0 z-10 shrink-0 border-r border-border bg-card/90 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground" style={{ width: roomColumnWidth }}>
                    Апартамент
                  </div>
                  <div className="grid flex-1" style={{ gridTemplateColumns: `repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}>
                    {visibleDates.map((value) => (
                      <div key={formatDateParam(value)} className="border-r border-border px-2 py-3 text-center last:border-r-0">
                        <div className="text-sm font-semibold text-foreground">{getDayNumberLabel(value)}</div>
                        <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{getWeekdayLabel(value)}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  {visibleRooms.map((room) => (
                    <div key={room.id} className="flex border-b border-border last:border-b-0">
                      <div className="sticky left-0 z-10 flex shrink-0 flex-col justify-center border-r border-border bg-card/85 px-5 py-5" style={{ width: roomColumnWidth }}>
                        <span className="text-sm font-semibold text-foreground">{room.title}</span>
                        <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{room.category}</span>
                      </div>

                      <div className="relative grid flex-1" style={{ gridTemplateColumns: `repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}>
                        {visibleDates.map((value) => (
                          <div key={`${room.id}-${formatDateParam(value)}`} className="h-18 border-r border-border/80 last:border-r-0" />
                        ))}

                        <div className="pointer-events-none absolute inset-0 px-1 py-2">
                          {room.bookings.map((booking) => (
                            <div
                              key={`${room.id}-${booking.id}`}
                              className={`absolute top-2 flex h-[calc(100%-1rem)] items-center rounded-2xl border px-3 text-xs font-medium shadow-lg shadow-black/10 ${statusClasses[booking.status]}`}
                              style={{
                                left: `calc((100% / ${visibleDates.length}) * ${booking.start_day - 1} + 4px)`,
                                width: `calc((100% / ${visibleDates.length}) * ${booking.span_days} - 8px)`,
                              }}
                              title={`${booking.label}: ${booking.check_in} → ${booking.check_out}`}
                            >
                              <span className="truncate">{booking.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {hasHorizontalOverflow ? (
              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between gap-3 text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  <span className="inline-flex items-center gap-2">
                    <ChevronsLeftRight className="h-3.5 w-3.5" />
                    Горизонтальная прокрутка
                  </span>
                  <span>Потяните бегунок для обзора календаря</span>
                </div>
                <div ref={sliderScrollRef} onScroll={() => syncScroll("slider")} className="crm-calendar-scrollbar overflow-x-auto rounded-full border border-border bg-card/70 p-1">
                  <div className="h-2 rounded-full bg-gradient-to-r from-[#E5D3B3]/28 via-sky-500/15 to-[#E5D3B3]/28" style={{ width: calendarContentWidth }} />
                </div>
              </div>
            ) : null}
          </>
        )}
      </section>
    </PageMotion>
  );
}
