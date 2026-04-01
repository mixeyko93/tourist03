import { CalendarRange, ChevronDown, Filter, Plus, Search } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { ModalShell } from "../components/ModalShell";
import {
  createCrmBooking,
  fetchCrmBookings,
  fetchCrmCampRooms,
  fetchCrmCamps,
  type CrmBooking,
  type CrmCamp,
  type CrmRoomOption,
} from "../session";

const statusClasses = {
  confirmed: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  processing: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  completed: "border-sky-500/25 bg-sky-500/10 text-sky-300",
  cancelled: "border-rose-500/25 bg-rose-500/10 text-rose-300",
} as const;

const paymentLabels: Record<string, string> = {
  unpaid: "Не оплачено",
  paid: "Оплачено",
  cash: "Оплата на месте",
};

const bookingLabels: Record<string, string> = {
  pending: "Новая заявка",
  awaiting_confirmation: "Ожидает подтверждения",
  awaiting_payment: "Ожидает оплаты",
  confirmed: "Подтверждена",
  checked_in: "Заселён",
  completed: "Завершена",
  no_show: "Не заехал",
  cancelled_by_user: "Отменена гостем",
  cancelled: "Отменена базой",
  cancelled_by_base: "Отменена базой",
  rejected: "Отклонена",
  expired_pending: "Просрочена без ответа",
};

const sourceLabels: Record<string, string> = {
  crm: "CRM",
  webapp: "Приложение",
  app: "Приложение",
  site: "Сайт",
  telegram: "Telegram",
};

type CreateBookingForm = {
  guestName: string;
  guestPhone: string;
  guestEmail: string;
  checkIn: string;
  checkOut: string;
  roomId: string;
  guestsCount: string;
  paymentStatus: string;
  paymentRequired: boolean;
  comment: string;
};

const emptyCreateForm: CreateBookingForm = {
  guestName: "",
  guestPhone: "",
  guestEmail: "",
  checkIn: "",
  checkOut: "",
  roomId: "",
  guestsCount: "1",
  paymentStatus: "unpaid",
  paymentRequired: false,
  comment: "",
};

function formatDateLabel(value: string) {
  if (!value) {
    return "Не указано";
  }
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) {
    return value;
  }
  return `${day}.${month}.${year}`;
}

function bookingStatusTone(status: string) {
  if (status === "confirmed" || status === "checked_in") {
    return "confirmed";
  }
  if (status === "completed") {
    return "completed";
  }
  if (["cancelled", "cancelled_by_user", "cancelled_by_base", "rejected", "expired_pending", "no_show"].includes(status)) {
    return "cancelled";
  }
  return "processing";
}

function getBookingGuest(booking: CrmBooking) {
  return booking.guest_name || booking.user_name || booking.guest_phone || booking.user_phone || `Бронь #${booking.id}`;
}

function getBookingStatusLabel(status: string) {
  return bookingLabels[status] || status || "Без статуса";
}

function getPaymentLabel(paymentStatus: string, paymentRequired: boolean) {
  if (paymentRequired && paymentStatus === "unpaid") {
    return "Нужна предоплата";
  }
  return paymentLabels[paymentStatus] || paymentStatus || "Не указано";
}

function getSourceLabel(source: string) {
  return sourceLabels[source] || source || "Не указан";
}

export default function BookingsPage() {
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [bookings, setBookings] = useState<CrmBooking[]>([]);
  const [roomOptions, setRoomOptions] = useState<CrmRoomOption[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateBookingForm>(emptyCreateForm);
  const [createError, setCreateError] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
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
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить базы");
        setCamps([]);
        setSelectedCampId(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedCampId) {
      setBookings([]);
      setRoomOptions([]);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");

    Promise.all([
      fetchCrmBookings(
        {
          campId: selectedCampId,
          dateFrom: dateFrom || undefined,
          dateTo: dateTo || undefined,
        },
        controller.signal,
      ),
      fetchCrmCampRooms(selectedCampId, controller.signal),
    ])
      .then(([bookingItems, rooms]) => {
        setBookings(bookingItems);
        setRoomOptions(rooms);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить список броней");
        setBookings([]);
        setRoomOptions([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedCampId, dateFrom, dateTo, reloadKey]);

  useEffect(() => {
    if (!roomOptions.some((room) => String(room.id) === createForm.roomId)) {
      setCreateForm((current) => ({
        ...current,
        roomId: "",
      }));
    }
  }, [roomOptions, createForm.roomId]);

  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredBookings = bookings.filter((booking) => {
    if (!normalizedQuery) {
      return true;
    }
    const haystack = [
      booking.id,
      booking.room_name,
      booking.guest_name,
      booking.user_name,
      booking.guest_phone,
      booking.user_phone,
      booking.source,
      booking.comment,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(normalizedQuery);
  });

  const hasBookings = filteredBookings.length > 0;
  const hasCampOptions = camps.length > 0;
  const hasRoomOptions = roomOptions.length > 0;
  const selectedCamp = camps.find((camp) => camp.id === selectedCampId) || null;

  async function handleCreateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId) {
      setCreateError("Сначала выберите базу, для которой создаётся бронь.");
      return;
    }
    if (!createForm.roomId) {
      setCreateError("Выберите апартамент для ручной брони.");
      return;
    }

    try {
      setIsCreating(true);
      setCreateError("");
      await createCrmBooking({
        camp_id: selectedCampId,
        room_id: Number(createForm.roomId),
        check_in: createForm.checkIn,
        check_out: createForm.checkOut,
        guests_count: Number(createForm.guestsCount || 1),
        status: "confirmed",
        payment_status: createForm.paymentStatus,
        payment_required: createForm.paymentStatus === "unpaid" ? createForm.paymentRequired : false,
        guest_name: createForm.guestName,
        guest_phone: createForm.guestPhone,
        guest_email: createForm.guestEmail || undefined,
        comment: createForm.comment || undefined,
      });
      setCreateForm(emptyCreateForm);
      setIsCreateOpen(false);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Не удалось сохранить бронь");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Брони"
        title="Управление бронями"
        description="Живой список заявок и ручных броней по выбранной базе с быстрым поиском, фильтрами и созданием внутри CRM."
        actions={
          <button
            type="button"
            className="brand-button w-full gap-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
            onClick={() => {
              setCreateError("");
              setIsCreateOpen(true);
            }}
            disabled={!selectedCampId || !hasRoomOptions}
          >
            <Plus className="h-4 w-4" />
            Создать бронь
          </button>
        }
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_220px_180px_180px_auto] xl:items-center">
          <div className="relative min-w-0">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              className="soft-input pl-11"
              placeholder="Поиск по гостю, телефону, номеру или комментарию"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <div className="relative min-w-0">
            <select
              className="soft-input appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60"
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
            <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>

          <label className="relative min-w-0">
            <CalendarRange className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input type="date" className="soft-input pl-11" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
          </label>

          <label className="relative min-w-0">
            <CalendarRange className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input type="date" className="soft-input pl-11" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
          </label>

          <button type="button" className="soft-button w-full gap-2 md:col-span-2 xl:w-auto" onClick={() => setReloadKey((value) => value + 1)}>
            <Filter className="h-4 w-4 text-[#E5D3B3]" />
            Обновить
          </button>
        </div>
      </section>

      {errorMessage ? (
        <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p>{errorMessage}</p>
            <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="soft-button shrink-0">
              Повторить
            </button>
          </div>
        </section>
      ) : null}

      <section className="glass-card overflow-hidden md:hidden">
        {isLoading ? (
          <div className="p-4">
            <EmptyState
              icon={CalendarRange}
              compact
              title="Загружаем брони"
              description="Подтягиваем реальные заявки и ручные брони по выбранной базе."
            />
          </div>
        ) : hasBookings ? (
          <div className="space-y-3 p-4">
            {filteredBookings.map((booking) => (
              <article key={booking.id} className="rounded-[1.4rem] border border-border bg-background/65 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">{getBookingGuest(booking)}</p>
                    <p className="mt-1 truncate text-xs uppercase tracking-[0.18em] text-muted-foreground">
                      {booking.room_name || "Без апартамента"} • #{booking.id}
                    </p>
                  </div>
                  <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-medium ${statusClasses[bookingStatusTone(booking.status)]}`}>
                    {getBookingStatusLabel(booking.status)}
                  </span>
                </div>

                <div className="mt-4 grid gap-3 text-sm">
                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Даты</p>
                    <p className="mt-1 text-foreground">
                      {formatDateLabel(booking.check_in)}
                      {" → "}
                      {formatDateLabel(booking.check_out)}
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Гости</p>
                      <p className="mt-1 font-medium text-foreground">{booking.guests_count}</p>
                    </div>
                    <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Источник</p>
                      <p className="mt-1 font-medium text-foreground">{getSourceLabel(booking.source)}</p>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Оплата</p>
                    <p className="mt-1 text-foreground">{getPaymentLabel(booking.payment_status, booking.payment_required)}</p>
                  </div>

                  {booking.comment ? (
                    <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Комментарий</p>
                      <p className="mt-1 text-foreground">{booking.comment}</p>
                    </div>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="p-4">
            <EmptyState
              icon={CalendarRange}
              compact
              title="Список броней пуст"
              description="После появления заявок из приложения, сайта или CRM здесь отобразятся только реальные брони."
            />
          </div>
        )}
      </section>

      <section className="glass-card hidden overflow-hidden md:block">
        {isLoading ? (
          <div className="p-6">
            <EmptyState
              icon={CalendarRange}
              title="Загружаем список броней"
              description="Подтягиваем реальные заезды, статусы и оплаты по выбранной базе."
            />
          </div>
        ) : hasBookings ? (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead className="bg-background/70">
                <tr className="border-b border-border">
                  {["Гость", "Заезд", "Выезд", "Гости", "Апартамент", "Статус", "Оплата", "Источник"].map((cell) => (
                    <th key={cell} className="px-6 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredBookings.map((booking) => (
                  <tr key={booking.id} className="border-b border-border/80 last:border-b-0 hover:bg-accent/40">
                    <td className="px-6 py-4 text-sm font-medium text-foreground">{getBookingGuest(booking)}</td>
                    <td className="px-6 py-4 text-sm text-foreground">{formatDateLabel(booking.check_in)}</td>
                    <td className="px-6 py-4 text-sm text-foreground">{formatDateLabel(booking.check_out)}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{booking.guests_count}</td>
                    <td className="px-6 py-4 text-sm text-foreground">{booking.room_name || "Без апартамента"}</td>
                    <td className="px-6 py-4">
                      <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusClasses[bookingStatusTone(booking.status)]}`}>
                        {getBookingStatusLabel(booking.status)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{getPaymentLabel(booking.payment_status, booking.payment_required)}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{getSourceLabel(booking.source)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6">
            <EmptyState
              icon={CalendarRange}
              title="Пока нет ни одной брони"
              description="Здесь будут только реальные заказы из CRM, сайта, Telegram Mini App и других подключённых каналов."
            />
          </div>
        )}
      </section>

      <ModalShell
        open={isCreateOpen}
        onClose={() => {
          if (!isCreating) {
            setIsCreateOpen(false);
          }
        }}
        title="Новая бронь"
        description={selectedCamp ? `Ручное создание подтверждённой брони для базы «${selectedCamp.name}».` : "Ручное создание подтверждённой брони."}
      >
        <form onSubmit={handleCreateSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            {createError ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200 md:col-span-2">
                {createError}
              </div>
            ) : null}

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Гость</span>
              <input
                className="soft-input"
                placeholder="Имя гостя"
                value={createForm.guestName}
                onChange={(event) => setCreateForm((current) => ({ ...current, guestName: event.target.value }))}
                required
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Телефон</span>
              <input
                className="soft-input"
                placeholder="+7 (999) 000-00-00"
                value={createForm.guestPhone}
                onChange={(event) => setCreateForm((current) => ({ ...current, guestPhone: event.target.value }))}
                required
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Email</span>
              <input
                type="email"
                className="soft-input"
                placeholder="guest@example.ru"
                value={createForm.guestEmail}
                onChange={(event) => setCreateForm((current) => ({ ...current, guestEmail: event.target.value }))}
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Гостей</span>
              <input
                type="number"
                min="1"
                className="soft-input"
                value={createForm.guestsCount}
                onChange={(event) => setCreateForm((current) => ({ ...current, guestsCount: event.target.value }))}
                required
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Заезд</span>
              <input
                type="date"
                className="soft-input"
                value={createForm.checkIn}
                onChange={(event) => setCreateForm((current) => ({ ...current, checkIn: event.target.value }))}
                required
              />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Выезд</span>
              <input
                type="date"
                className="soft-input"
                value={createForm.checkOut}
                onChange={(event) => setCreateForm((current) => ({ ...current, checkOut: event.target.value }))}
                required
              />
            </label>

            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Апартамент</span>
              <select
                className="soft-input appearance-none disabled:cursor-not-allowed disabled:opacity-60"
                value={createForm.roomId}
                onChange={(event) => setCreateForm((current) => ({ ...current, roomId: event.target.value }))}
                disabled={!hasRoomOptions}
                required
              >
                <option value="">Выберите апартамент</option>
                {roomOptions.map((room) => (
                  <option key={room.id} value={room.id}>
                    {room.name || "Без названия"}{room.room_type ? ` • ${room.room_type}` : ""}
                  </option>
                ))}
              </select>
              {!hasRoomOptions ? (
                <p className="text-sm text-muted-foreground">Сначала добавьте апартаменты, чтобы можно было оформить ручную бронь.</p>
              ) : null}
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Статус оплаты</span>
              <select
                className="soft-input appearance-none"
                value={createForm.paymentStatus}
                onChange={(event) => setCreateForm((current) => ({ ...current, paymentStatus: event.target.value }))}
              >
                <option value="unpaid">Не оплачено</option>
                <option value="paid">Оплачено</option>
                <option value="cash">Оплата на месте</option>
              </select>
            </label>

            <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/60 px-4 py-3 md:self-end">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border bg-background"
                checked={createForm.paymentRequired}
                onChange={(event) => setCreateForm((current) => ({ ...current, paymentRequired: event.target.checked }))}
                disabled={createForm.paymentStatus !== "unpaid"}
              />
              <span className="text-sm text-foreground">Нужна предоплата</span>
            </label>

            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
              <textarea
                className="soft-input min-h-32 resize-none"
                placeholder="Особые пожелания гостя, условия заселения, заметки по оплате"
                value={createForm.comment}
                onChange={(event) => setCreateForm((current) => ({ ...current, comment: event.target.value }))}
              />
            </label>
          </div>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
            <button type="button" className="soft-button" onClick={() => setIsCreateOpen(false)} disabled={isCreating}>
              Отмена
            </button>
            <button type="submit" className="brand-button disabled:cursor-not-allowed disabled:opacity-60" disabled={isCreating || !hasRoomOptions}>
              {isCreating ? "Сохраняем бронь..." : "Сохранить бронь"}
            </button>
          </div>
        </form>
      </ModalShell>
    </PageMotion>
  );
}
