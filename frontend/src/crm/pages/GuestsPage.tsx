import { Filter, Mail, Phone, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageLoadingState } from "../components/PageLoadingState";
import { PageMotion } from "../components/PageMotion";
import { usePageLoadState } from "../components/usePageLoadState";
import { SectionHeading } from "../components/SectionHeading";
import { fetchCrmCamps, fetchCrmGuests, type CrmCamp, type CrmGuest } from "../session";

const guestStatusClasses = {
  Новый: "border-slate-500/20 bg-slate-500/10 text-slate-300",
  Постоянный: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  VIP: "border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-[#E5D3B3]",
} as const;

const bookingStatusLabels: Record<string, string> = {
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

function formatCurrency(value: number) {
  return `${new Intl.NumberFormat("ru-RU").format(value)} ₽`;
}

function formatDateLabel(value: string | null) {
  if (!value) {
    return "Не указано";
  }
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) {
    return value;
  }
  return `${day}.${month}.${year}`;
}

export default function GuestsPage() {
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [guests, setGuests] = useState<CrmGuest[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "Новый" | "Постоянный" | "VIP">("");
  const [selectedGuest, setSelectedGuest] = useState<CrmGuest | null>(null);
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
      setGuests([]);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");

    fetchCrmGuests({ campId: selectedCampId }, controller.signal)
      .then((items) => {
        setGuests(items);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить гостевую базу");
        setGuests([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [selectedCampId, reloadKey]);

  const filteredGuests = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return guests.filter((guest) => {
      if (statusFilter && guest.status !== statusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [guest.name, guest.phone, guest.email].filter(Boolean).join(" ").toLowerCase().includes(query);
    });
  }, [guests, searchQuery, statusFilter]);

  const hasGuests = filteredGuests.length > 0;
  const { showInitialSkeleton } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={!showInitialSkeleton}>
      <SectionHeading
        title="База гостей"
        description="Живой список гостей по реальным бронированиям с контактами, историей визитов и оценкой клиентской ценности."
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px_200px_auto] lg:items-center">
          <div className="relative w-full">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              className="soft-input pl-11"
              placeholder="Поиск по имени, телефону или эл. почте"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <select
            className="soft-input disabled:cursor-not-allowed disabled:opacity-60"
            value={selectedCampId ?? ""}
            onChange={(event) => setSelectedCampId(event.target.value ? Number(event.target.value) : null)}
            disabled={!camps.length || isLoading}
          >
            {camps.length ? (
              camps.map((camp) => (
                <option key={camp.id} value={camp.id}>
                  {camp.name}
                </option>
              ))
            ) : (
              <option value="">Нет доступных баз</option>
            )}
          </select>

          <select className="soft-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "" | "Новый" | "Постоянный" | "VIP")}>
            <option value="">Все сегменты</option>
            <option value="Новый">Новый</option>
            <option value="Постоянный">Постоянный</option>
            <option value="VIP">VIP</option>
          </select>

          <button type="button" className="soft-button w-full gap-2 self-start sm:w-auto" onClick={() => setReloadKey((value) => value + 1)}>
            <Filter className="h-4 w-4 text-[#E5D3B3]" />
            Обновить
          </button>
        </div>
      </section>

      {errorMessage ? (
        <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
          {errorMessage}
        </section>
      ) : null}

      <section className="glass-card overflow-hidden md:hidden">
        {isLoading ? (
          <div className="p-4">
            <PageLoadingState blocks={2} columnsClassName="grid-cols-1" blockHeightClassName="h-44" />
          </div>
        ) : hasGuests ? (
          <div className="space-y-3 p-4">
            {filteredGuests.map((guest) => (
              <article key={guest.id} className="rounded-[1.4rem] border border-border bg-background/65 p-4" onClick={() => setSelectedGuest(guest)}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">{guest.name}</p>
                    <div className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1.5">
                        <Phone className="h-3.5 w-3.5 text-[#E5D3B3]" />
                        {guest.phone || "Телефон не указан"}
                      </span>
                      <span className="inline-flex items-center gap-1.5 break-all">
                        <Mail className="h-3.5 w-3.5 shrink-0 text-[#E5D3B3]" />
                        {guest.email || "Эл. почта не указана"}
                      </span>
                    </div>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${guestStatusClasses[guest.status]}`}>
                    {guest.status}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Визиты</p>
                    <p className="mt-1 font-medium text-foreground">{guest.visits_count}</p>
                  </div>
                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Последний визит</p>
                    <p className="mt-1 font-medium text-foreground">{formatDateLabel(guest.last_visit)}</p>
                  </div>
                </div>
                <div className="mt-3 rounded-2xl border border-border bg-card/55 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Оценочный оборот</p>
                  <p className="mt-1 font-semibold text-foreground">{formatCurrency(guest.total_estimate)}</p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="p-4">
            <EmptyState
              icon={Search}
              compact
              title="Гостевая база пока пуста"
              description="После первых реальных броней здесь появятся контакты гостей, история визитов и накопленный оборот."
            />
          </div>
        )}
      </section>

      <section className="glass-card hidden overflow-hidden md:block">
        {isLoading ? (
          <div className="p-6">
            <PageLoadingState blocks={1} columnsClassName="grid-cols-1" blockHeightClassName="h-[22rem]" />
          </div>
        ) : hasGuests ? (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead className="bg-background/70">
                <tr className="border-b border-border">
                  {["Имя и контакты", "Визиты", "Оборот", "Последний визит", "Сегмент"].map((cell) => (
                    <th key={cell} className="px-6 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredGuests.map((guest) => (
                  <tr key={guest.id} className="cursor-pointer border-b border-border/80 last:border-b-0 hover:bg-accent/40" onClick={() => setSelectedGuest(guest)}>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-foreground">{guest.name}</div>
                        <div className="flex flex-col gap-1 text-xs text-muted-foreground md:flex-row md:gap-4">
                          <span className="inline-flex items-center gap-1.5">
                            <Phone className="h-3.5 w-3.5 text-[#E5D3B3]" />
                            {guest.phone || "Телефон не указан"}
                          </span>
                          <span className="inline-flex items-center gap-1.5">
                            <Mail className="h-3.5 w-3.5 text-[#E5D3B3]" />
                            {guest.email || "Эл. почта не указана"}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-foreground">{guest.visits_count}</td>
                    <td className="px-6 py-4 text-sm font-semibold text-foreground">{formatCurrency(guest.total_estimate)}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{formatDateLabel(guest.last_visit)}</td>
                    <td className="px-6 py-4">
                      <span className={`rounded-full border px-3 py-1 text-xs font-medium ${guestStatusClasses[guest.status]}`}>
                        {guest.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6">
            <EmptyState
              icon={Search}
              title="Карточки гостей ещё не накоплены"
              description="CRM начнёт собирать клиентскую базу автоматически после появления первых подтверждённых броней."
            />
          </div>
        )}
      </section>

      <ModalShell
        open={Boolean(selectedGuest)}
        onClose={() => setSelectedGuest(null)}
        title={selectedGuest?.name || "Карточка гостя"}
        description="История визитов и бронирований по реальным данным CRM."
      >
        {selectedGuest ? (
          <div className="space-y-6">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Телефон</p>
                <p className="mt-2 text-sm font-medium text-foreground">{selectedGuest.phone || "Не указан"}</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Эл. почта</p>
                <p className="mt-2 text-sm font-medium text-foreground">{selectedGuest.email || "Не указан"}</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Сегмент</p>
                <p className="mt-2 text-sm font-medium text-foreground">{selectedGuest.status}</p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Визитов</p>
                <p className="mt-2 text-lg font-semibold text-foreground">{selectedGuest.visits_count}</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Оборот</p>
                <p className="mt-2 text-lg font-semibold text-foreground">{formatCurrency(selectedGuest.total_estimate)}</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Последний визит</p>
                <p className="mt-2 text-lg font-semibold text-foreground">{formatDateLabel(selectedGuest.last_visit)}</p>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="text-lg font-semibold text-foreground">История бронирований</h3>
              {selectedGuest.bookings.length ? (
                selectedGuest.bookings.map((booking) => (
                  <article key={booking.id} className="rounded-3xl border border-border bg-background/65 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-foreground">{booking.room_name}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{booking.camp_name}</p>
                        <p className="mt-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                          {formatDateLabel(booking.check_in)} → {formatDateLabel(booking.check_out)}
                        </p>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-xs font-medium ${guestStatusClasses[selectedGuest.status]}`}>
                        {bookingStatusLabels[booking.status] || booking.status || "Без статуса"}
                      </span>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Гостей</p>
                        <p className="mt-1 font-medium text-foreground">{booking.guests_count}</p>
                      </div>
                      <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Оплата</p>
                        <p className="mt-1 font-medium text-foreground">{booking.payment_status || "Не указана"}</p>
                      </div>
                      <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Источник</p>
                        <p className="mt-1 font-medium text-foreground">{booking.source || "Не указан"}</p>
                      </div>
                    </div>
                    {booking.comment ? (
                      <div className="mt-3 rounded-2xl border border-border bg-card/55 px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Комментарий</p>
                        <p className="mt-1 text-sm text-foreground">{booking.comment}</p>
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <EmptyState
                  icon={Search}
                  compact
                  title="История ещё не сформирована"
                  description="По этому гостю пока нет зафиксированных бронирований."
                />
              )}
            </div>
          </div>
        ) : null}
      </ModalShell>
    </PageMotion>
  );
}
