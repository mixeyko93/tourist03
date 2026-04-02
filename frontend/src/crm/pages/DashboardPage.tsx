import { BarChart3, BedDouble, Building2, CalendarClock, CircleDollarSign, Sparkles, TrendingUp, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { fetchCrmBookings, fetchCrmCampRooms, fetchCrmCamps, type CrmBooking, type CrmCamp, type CrmRoomOption } from "../session";

const statusClasses = {
  confirmed: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  processing: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  completed: "border-sky-500/25 bg-sky-500/10 text-sky-300",
  cancelled: "border-rose-500/25 bg-rose-500/10 text-rose-300",
} as const;

function formatCurrency(value: number) {
  return `${new Intl.NumberFormat("ru-RU").format(value)} ₽`;
}

function formatDateLabel(value: string) {
  if (!value) return "Не указано";
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}.${month}.${year}`;
}

function bookingTone(status: string) {
  if (status === "completed") return "completed";
  if (status === "confirmed" || status === "checked_in") return "confirmed";
  if (["cancelled", "cancelled_by_user", "cancelled_by_base", "rejected", "expired_pending", "no_show"].includes(status)) return "cancelled";
  return "processing";
}

function bookingStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Новая заявка",
    awaiting_confirmation: "Ожидает подтверждения",
    awaiting_payment: "Ожидает оплаты",
    confirmed: "Подтверждена",
    checked_in: "Заселён",
    completed: "Завершена",
    cancelled: "Отменена базой",
    cancelled_by_user: "Отменена гостем",
    cancelled_by_base: "Отменена базой",
    rejected: "Отклонена",
    expired_pending: "Просрочена без ответа",
    no_show: "Не заехал",
  };
  return labels[status] || status || "Без статуса";
}

function bookingGuest(booking: CrmBooking) {
  return booking.guest_name || booking.user_name || booking.guest_phone || booking.user_phone || `Бронь #${booking.id}`;
}

function bookingSourceLabel(source: string) {
  const labels: Record<string, string> = {
    crm: "CRM",
    webapp: "Мини-приложение",
    app: "Приложение",
    site: "Сайт",
    telegram: "Телеграм",
  };
  return labels[source] || source || "Не указан";
}

function nightsBetween(checkIn: string, checkOut: string) {
  const start = new Date(checkIn);
  const end = new Date(checkOut);
  const diff = Math.round((end.getTime() - start.getTime()) / 86400000);
  return Math.max(diff, 1);
}

export default function DashboardPage() {
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [bookings, setBookings] = useState<CrmBooking[]>([]);
  const [rooms, setRooms] = useState<CrmRoomOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    fetchCrmCamps(controller.signal)
      .then((items) => {
        setCamps(items);
        setSelectedCampId((current) => {
          if (!items.length) return null;
          if (current && items.some((item) => item.id === current)) return current;
          return items[0].id;
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить базы");
        setCamps([]);
        setSelectedCampId(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedCampId) {
      setBookings([]);
      setRooms([]);
      return;
    }
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    Promise.all([
      fetchCrmBookings({ campId: selectedCampId }, controller.signal),
      fetchCrmCampRooms(selectedCampId, controller.signal),
    ])
      .then(([bookingItems, roomItems]) => {
        setBookings(bookingItems);
        setRooms(roomItems);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить сводку");
        setBookings([]);
        setRooms([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [selectedCampId, reloadKey]);

  const metrics = useMemo(() => {
    const today = new Date();
    const todayIso = today.toISOString().slice(0, 10);
    const roomsById = new Map(rooms.map((room) => [room.id, room]));
    const todayCheckIns = bookings.filter((booking) => booking.check_in === todayIso).length;
    const inProcessing = bookings.filter((booking) => ["pending", "awaiting_confirmation", "awaiting_payment"].includes(booking.status)).length;
    const occupiedToday = new Set(
      bookings
        .filter((booking) => booking.room_id && booking.check_in <= todayIso && booking.check_out > todayIso && !["cancelled", "cancelled_by_user", "cancelled_by_base", "rejected", "expired_pending", "no_show"].includes(booking.status))
        .map((booking) => booking.room_id as number),
    );
    const freeRooms = Math.max(rooms.length - occupiedToday.size, 0);

    const months = Array.from({ length: 6 }, (_, index) => {
      const date = new Date(today.getFullYear(), today.getMonth() - 5 + index, 1);
      const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      const label = new Intl.DateTimeFormat("ru-RU", { month: "short" }).format(date).replace(".", "");
      const monthBookings = bookings.filter((booking) => booking.check_in.startsWith(key));
      const revenue = monthBookings.reduce((sum, booking) => {
        if (!booking.room_id) return sum;
        const room = roomsById.get(booking.room_id);
        if (!room) return sum;
        return sum + Number(room.price || 0) * nightsBetween(booking.check_in, booking.check_out);
      }, 0);
      const occupancyBase = rooms.length ? Math.min(Math.round((monthBookings.length / rooms.length) * 100), 100) : 0;
      return {
        key,
        label: label.charAt(0).toUpperCase() + label.slice(1),
        bookingsCount: monthBookings.length,
        revenue,
        occupancy: occupancyBase,
      };
    });

    return {
      todayCheckIns,
      inProcessing,
      freeRooms,
      series: months,
    };
  }, [bookings, rooms]);

  const maxRevenue = Math.max(1, ...metrics.series.map((item) => item.revenue));
  const totalRevenue = metrics.series.reduce((sum, item) => sum + item.revenue, 0);
  const averageOccupancy = metrics.series.length
    ? Math.round(metrics.series.reduce((sum, item) => sum + item.occupancy, 0) / metrics.series.length)
    : 0;
  const peakMonth = metrics.series.reduce<(typeof metrics.series)[number] | null>(
    (best, item) => (best === null || item.occupancy > best.occupancy ? item : best),
    null,
  );
  const recentBookings = bookings.slice(0, 5);
  const hasCampOptions = camps.length > 0;
  const hasRooms = rooms.length > 0;
  const hasRevenue = metrics.series.some((item) => item.revenue > 0 || item.bookingsCount > 0);

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Сводка"
        title="Сводка по базе"
        description="Живой обзор загрузки, ближайших заездов, выручки по базовым тарифам и потока реальных заявок."
        actions={
          <>
            <div className="relative w-full min-w-0 sm:min-w-52">
              <select
                className="soft-input w-full min-w-0 pr-10 disabled:cursor-not-allowed disabled:opacity-60"
                value={selectedCampId ?? ""}
                onChange={(event) => setSelectedCampId(event.target.value ? Number(event.target.value) : null)}
                disabled={!hasCampOptions || isLoading}
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
            </div>
            <button type="button" className="brand-outline w-full sm:w-auto" onClick={() => setReloadKey((value) => value + 1)}>
              Обновить сводку
            </button>
          </>
        }
      />

      {errorMessage ? (
        <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
          {errorMessage}
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        {[
          {
            label: "Заявок в работе",
            value: String(metrics.inProcessing),
            note: "Требуют реакции менеджера или управляющего",
            delta: hasCampOptions ? "Живые данные" : "Нет базы",
            icon: CalendarClock,
          },
          {
            label: "Заездов сегодня",
            value: String(metrics.todayCheckIns),
            note: "Запланированные заселения на текущую дату",
            delta: hasCampOptions ? "По CRM" : "Нет базы",
            icon: Users,
          },
          {
            label: "Свободных апартаментов",
            value: String(metrics.freeRooms),
            note: hasRooms ? `Всего в фонде: ${rooms.length}` : "Номерной фонд ещё не заполнен",
            delta: hasCampOptions ? "На сегодня" : "Нет базы",
            icon: BedDouble,
          },
        ].map((stat) => {
          const Icon = stat.icon;
          return (
            <article key={stat.label} className="glass-card p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{stat.label}</p>
                  <p className="text-4xl font-semibold tracking-[-0.06em] text-foreground">{stat.value}</p>
                </div>
                <span className="rounded-2xl border border-[#E5D3B3]/30 bg-[#E5D3B3]/10 p-3 text-[#E5D3B3]">
                  <Icon className="h-5 w-5" />
                </span>
              </div>
              <div className="mt-6 flex items-center justify-between gap-3 text-sm">
                <span className="text-muted-foreground">{stat.note}</span>
                <span className="shrink-0 font-semibold text-[#E5D3B3]">{stat.delta}</span>
              </div>
            </article>
          );
        })}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <article className="glass-card p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Доход и загрузка</p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-0.04em] text-foreground">Динамика по базовым тарифам</h2>
            </div>
            <div className="rounded-2xl border border-border bg-background/70 px-4 py-2 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{formatCurrency(totalRevenue)}</span> за 6 месяцев
            </div>
          </div>

          {hasRevenue ? (
            <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_220px]">
              <div className="-mx-1 overflow-x-auto pb-2">
                <div className="flex min-w-[560px] items-end gap-3 px-1">
                  {metrics.series.map((item) => (
                    <div key={item.key} className="flex flex-1 flex-col items-center gap-3">
                      <div className="flex h-64 w-full items-end rounded-[1.6rem] border border-border bg-background/55 p-2">
                        <div
                          className="w-full rounded-[1.1rem] bg-gradient-to-t from-[#E5D3B3] via-[#E5D3B3]/70 to-white/30 shadow-lg shadow-[#E5D3B3]/10"
                          style={{ height: `${(item.revenue / maxRevenue) * 100}%` }}
                        />
                      </div>
                      <div className="space-y-1 text-center">
                        <p className="text-sm font-medium text-foreground">{item.label}</p>
                        <p className="text-xs text-muted-foreground">{item.bookingsCount} броней</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-3 rounded-[1.8rem] border border-border bg-background/65 p-4">
                <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 p-4">
                  <CircleDollarSign className="h-5 w-5 text-[#E5D3B3]" />
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Оценка выручки</p>
                    <p className="text-lg font-semibold text-foreground">{formatCurrency(totalRevenue)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 p-4">
                  <TrendingUp className="h-5 w-5 text-[#E5D3B3]" />
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Средняя загрузка</p>
                    <p className="text-lg font-semibold text-foreground">{averageOccupancy}%</p>
                  </div>
                </div>
                <div className="rounded-2xl border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[#E5D3B3]">Пик периода</p>
                  <p className="mt-2 text-sm leading-6 text-foreground">
                    {peakMonth ? `Максимальная расчётная загрузка ${peakMonth.occupancy}% пришлась на ${peakMonth.label}.` : "Первые реальные брони покажут динамику автоматически."}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState
                icon={BarChart3}
                title="Пока нет данных для аналитики"
                description="Как только по базе появятся реальные брони, здесь автоматически отобразятся расчётная загрузка и выручка по базовым тарифам."
              />
            </div>
          )}
        </article>

        <article className="glass-card p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Последние брони</p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-0.04em] text-foreground">Живая лента заявок</h2>
            </div>
            <span className="rounded-full border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#E5D3B3]">
              {recentBookings.length ? `${recentBookings.length} записей` : "Нет данных"}
            </span>
          </div>

          <div className="mt-6">
            {recentBookings.length ? (
              <div className="space-y-3">
                {recentBookings.map((booking) => (
                  <article key={booking.id} className="rounded-[1.4rem] border border-border bg-background/65 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold text-foreground">{bookingGuest(booking)}</p>
                          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${statusClasses[bookingTone(booking.status)]}`}>
                            {bookingStatusLabel(booking.status)}
                          </span>
                        </div>
                        <p className="mt-1 truncate text-sm text-muted-foreground">{booking.room_name || "Без апартамента"}</p>
                        <p className="mt-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                          {formatDateLabel(booking.check_in)} → {formatDateLabel(booking.check_out)}
                        </p>
                      </div>
                      <p className="text-sm font-semibold text-foreground sm:text-right">{bookingSourceLabel(booking.source)}</p>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={CalendarClock}
                compact
                title="Брони ещё не поступали"
                description="Когда гости начнут оформлять реальные заказы, новые заявки появятся в этой ленте без ручного обновления."
              />
            )}
          </div>
        </article>
      </section>

      {!hasCampOptions ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={Building2}
            compact
            title="CRM ожидает подключение базы"
            description="Сейчас в системе нет подключённых объектов. Как только superadmin или управляющий подключат базу, сводка заработает автоматически."
          />
        </section>
      ) : null}

      {hasCampOptions && !hasRooms ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={Sparkles}
            compact
            title="Добавьте апартаменты для полной аналитики"
            description="Сводка уже читает реальные брони, но для точной загрузки и выручки по базовым тарифам нужно заполнить номерной фонд."
          />
        </section>
      ) : null}
    </PageMotion>
  );
}
