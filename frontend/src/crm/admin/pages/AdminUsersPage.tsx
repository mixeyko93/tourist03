import { ChevronDown, Clock3, Phone, RefreshCcw, Search, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { AdminCard } from "../components/AdminCard";
import { AdminModal } from "../components/AdminModal";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { fetchSuperadminUserHistory, fetchSuperadminUsers, type SuperadminUserHistoryResponse, type SuperadminUserSummary } from "../session";

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
}

function formatStatus(user: SuperadminUserSummary) {
  if (user.phone_verified && user.email_verified && user.bookings_count && user.bookings_count >= 3) {
    return "Постоянный";
  }
  if (user.phone_verified && user.email_verified) {
    return "Подтверждён";
  }
  if (user.phone_verified) {
    return "Телефон подтверждён";
  }
  return "Нужна проверка";
}

function formatEventData(payload: unknown) {
  if (!payload) {
    return "—";
  }
  if (typeof payload === "string") {
    return payload;
  }
  try {
    return JSON.stringify(payload, null, 0);
  } catch {
    return "Данные недоступны";
  }
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<SuperadminUserSummary[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [history, setHistory] = useState<SuperadminUserHistoryResponse | null>(null);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    fetchSuperadminUsers({ search, signal: controller.signal })
      .then((items) => setUsers(items))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setUsers([]);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить список пользователей");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, [reloadKey, search]);

  useEffect(() => {
    if (!selectedUserId) {
      setHistory(null);
      return;
    }

    const controller = new AbortController();
    setIsHistoryLoading(true);
    fetchSuperadminUserHistory(selectedUserId, controller.signal)
      .then((payload) => setHistory(payload))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setHistory(null);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить историю пользователя");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsHistoryLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedUserId]);

  const selectedUser = useMemo(() => users.find((user) => user.id === selectedUserId) ?? null, [selectedUserId, users]);

  const { isPageVisible } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Клиентская база</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">Пользователи</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Реальный список клиентов с телефонами, эл. почтой, подтверждением контактов и полной историей бронирований.
              </p>
            </div>

            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <label className="relative sm:min-w-80">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  className="admin-input pl-10"
                  placeholder="Поиск по имени, телефону или эл. почте"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </label>
              <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
                <RefreshCcw className="h-4 w-4" />
                Обновить
              </button>
            </div>
          </div>
        </div>

        {errorMessage ? (
          <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div>
        ) : null}

        <div className="admin-table-shell">
          <table className="admin-table min-w-[940px]">
            <thead>
              <tr>
                {["ID", "Имя", "Телефон", "Эл. почта", "Статус", "Создан"].map((label) => (
                  <th key={label}>
                    <span className="inline-flex items-center gap-1">
                      {label}
                      <ChevronDown className="h-3.5 w-3.5" />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6}>Загружаем пользователей…</td>
                </tr>
              ) : users.length ? (
                users.map((user) => (
                  <tr key={user.id} className="cursor-pointer" onClick={() => setSelectedUserId(user.id)}>
                    <td>{user.id}</td>
                    <td className="font-medium text-foreground">{user.name || "Без имени"}</td>
                    <td>{user.phone || "—"}</td>
                    <td className="crm-copy-safe">{user.email || "—"}</td>
                    <td>{formatStatus(user)}</td>
                    <td>{formatDateTime(user.created_at)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>Пользователи не найдены.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={Boolean(selectedUser)}
        onClose={() => setSelectedUserId(null)}
        title={selectedUser ? `Пользователь #${selectedUser.id} — ${selectedUser.name || "Без имени"}` : ""}
        description="Детали профиля, история бронирований и события по аккаунту."
        panelClassName="max-w-5xl"
      >
        {selectedUser ? (
          isHistoryLoading ? (
            <div className="py-10 text-center text-sm text-muted-foreground">Загружаем историю пользователя…</div>
          ) : history ? (
            <div className="space-y-6">
              <div className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-3xl border border-border bg-background/65 p-5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-500">
                      <UserRound className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-foreground">{history.user.name || "Без имени"}</p>
                      <p className="text-xs text-muted-foreground">Профиль пользователя</p>
                    </div>
                  </div>
                  <div className="mt-4 space-y-3 text-sm">
                    <p className="inline-flex items-center gap-2 text-foreground">
                      <Phone className="h-4 w-4 text-blue-500" />
                      {history.user.phone || "Телефон не указан"}
                    </p>
                    <p className="crm-copy-safe text-muted-foreground">{history.user.email || "Эл. почта не указана"}</p>
                    <p className="text-muted-foreground">Создан: {formatDateTime(history.user.created_at)}</p>
                  </div>
                </div>

                <div className="rounded-3xl border border-border bg-background/65 p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Статус</p>
                  <div className="mt-3">
                    <AdminStatusBadge tone={history.user.email_verified ? "info" : "neutral"}>{formatStatus(selectedUser)}</AdminStatusBadge>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-muted-foreground">
                    Бронирований: {history.bookings.length}. Событий в журнале: {history.events.length}.
                  </p>
                </div>

                <div className="rounded-3xl border border-border bg-background/65 p-5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-300">
                      <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-foreground">Проверка профиля</p>
                      <p className="text-xs text-muted-foreground">Состояние контактных данных</p>
                    </div>
                  </div>
                  <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                    <p>Телефон: {history.user.phone_verified ? "подтверждён" : "не подтверждён"}</p>
                    <p>Эл. почта: {history.user.email_verified ? "подтверждена" : "не подтверждена"}</p>
                    <p>Последняя активность: {formatDateTime(history.events[0]?.created_at)}</p>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-blue-500" />
                  <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Бронирования</h3>
                </div>
                <div className="admin-table-shell">
                  <table className="admin-table min-w-[820px]">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>База</th>
                        <th>Номер</th>
                        <th>Даты</th>
                        <th>Гостей</th>
                        <th>Статус</th>
                        <th>Создано</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.bookings.length ? (
                        history.bookings.map((booking) => (
                          <tr key={booking.id}>
                            <td>#{booking.id}</td>
                            <td className="font-medium text-foreground">{booking.camp_name || "—"}</td>
                            <td>{booking.room_name || "—"}</td>
                            <td>
                              {booking.check_in && booking.check_out ? `${booking.check_in} — ${booking.check_out}` : "—"}
                            </td>
                            <td>{booking.guests_count ?? "—"}</td>
                            <td>
                              <AdminStatusBadge tone={booking.status?.toLowerCase().includes("подтверж") ? "success" : "warning"}>
                                {booking.status || "Без статуса"}
                              </AdminStatusBadge>
                            </td>
                            <td>{formatDateTime(booking.created_at)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={7}>Нет бронирований.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-blue-500" />
                  <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">События</h3>
                </div>
                <div className="admin-table-shell">
                  <table className="admin-table min-w-[760px]">
                    <thead>
                      <tr>
                        <th>Время</th>
                        <th>Событие</th>
                        <th>Данные</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.events.length ? (
                        history.events.map((event) => (
                          <tr key={`${event.id}-${event.created_at}`}>
                            <td>{formatDateTime(event.created_at)}</td>
                            <td className="font-medium text-foreground">{event.event_type}</td>
                            <td className="crm-copy-safe">{formatEventData(event.payload)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3}>Пока нет событий по пользователю.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-10 text-center text-sm text-muted-foreground">История пользователя недоступна.</div>
          )
        ) : null}
      </AdminModal>
    </PageMotion>
  );
}
