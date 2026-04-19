import { Compass, PencilLine, Plus, RefreshCcw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { crmPath } from "../../paths";
import { AdminCard } from "../components/AdminCard";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { fetchSuperadminBases, fetchSuperadminEvents, type SuperadminBaseSummary, type SuperadminSystemEvent } from "../session";

const statusLabels: Record<string, string> = {
  active: "Активна",
  disabled: "Отключена",
  archived: "В архиве",
};

const statusTones: Record<string, "success" | "warning" | "neutral"> = {
  active: "success",
  disabled: "warning",
  archived: "neutral",
};

const severityTones: Record<string, "info" | "warning" | "danger" | "neutral"> = {
  info: "info",
  warning: "warning",
  critical: "danger",
};

function formatCurrency(value: number | null | undefined) {
  if (!value) {
    return "Не указана";
  }
  return `${new Intl.NumberFormat("ru-RU").format(value)} ₽`;
}

function formatCoordinates(base: SuperadminBaseSummary) {
  if (base.lat == null || base.lng == null) {
    return "Координаты не заданы";
  }
  return `${base.lat}, ${base.lng}`;
}

function formatStatus(status?: string | null) {
  return statusLabels[(status || "").toLowerCase()] || "Без статуса";
}

export default function AdminBasesPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<SuperadminBaseSummary[]>([]);
  const [events, setEvents] = useState<SuperadminSystemEvent[]>([]);
  const [search, setSearch] = useState("");
  const [quickMode, setQuickMode] = useState<"all" | "active" | "rooms">("all");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");

    Promise.all([
      fetchSuperadminBases({ search, signal: controller.signal }),
      fetchSuperadminEvents({ limit: 6, signal: controller.signal }),
    ])
      .then(([bases, systemEvents]) => {
        setItems(bases);
        setEvents(systemEvents);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить данные суперадмина");
        setItems([]);
        setEvents([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey, search]);

  const summary = useMemo(() => {
    return items.reduce(
      (accumulator, item) => {
        const status = (item.status || "").toLowerCase();
        accumulator.total += 1;
        if (status === "active") accumulator.active += 1;
        if (status === "disabled") accumulator.disabled += 1;
        accumulator.rooms += Number(item.rooms_count || 0);
        return accumulator;
      },
      { total: 0, active: 0, disabled: 0, rooms: 0 },
    );
  }, [items]);
  const visibleItems = useMemo(() => {
    const next = [...items];
    if (quickMode === "active") {
      return next.filter((item) => (item.status || "").toLowerCase() === "active");
    }
    if (quickMode === "rooms") {
      return next.sort((left, right) => Number(right.rooms_count || 0) - Number(left.rooms_count || 0));
    }
    return next;
  }, [items, quickMode]);

  const { showInitialSkeleton } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={!showInitialSkeleton}>
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Справочник баз</p>
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Базы отдыха и номерной фонд</h2>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                Живая витрина объектов с реальными статусами, координатами, ценами и последними сигналами из CRM.
              </p>
            </div>

            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
                <RefreshCcw className="h-4 w-4" />
                Обновить
              </button>
              <button type="button" className="admin-primary-button w-full gap-2 sm:w-auto" onClick={() => navigate(crmPath("/admin/bases/new"))}>
                <Plus className="h-4 w-4" />
                Добавить базу
              </button>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_repeat(3,minmax(180px,220px))]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                className="admin-input pl-10"
                placeholder="Поиск по базе, озеру, владельцу или адресу"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>

            {[
              { label: "Всего баз", value: summary.total, key: "all" as const },
              { label: "Активных", value: summary.active, key: "active" as const },
              { label: "Апартаментов", value: summary.rooms, key: "rooms" as const },
            ].map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => setQuickMode(item.key)}
                className={`rounded-2xl border bg-background/70 px-4 py-3 text-left transition hover:-translate-y-0.5 hover:border-blue-500/40 hover:bg-accent ${
                  quickMode === item.key ? "border-blue-500/55 ring-1 ring-blue-500/30" : "border-border"
                }`}
              >
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{item.label}</div>
                <div className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">{item.value}</div>
              </button>
            ))}
          </div>
        </div>

        {errorMessage ? (
          <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div>
        ) : null}

        <div className="admin-table-shell">
          <table className="admin-table min-w-[1240px]">
            <thead>
              <tr>
                <th>Статус</th>
                <th>ID</th>
                <th>Название</th>
                <th>Озеро</th>
                <th>Координаты</th>
                <th>Владелец</th>
                <th>Управляющий</th>
                <th>Связанные учётки</th>
                <th>Мин. цена</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={10}>Загружаем базы отдыха…</td>
                </tr>
              ) : visibleItems.length ? (
                visibleItems.map((base) => {
                  const statusKey = (base.status || "").toLowerCase();
                  const linkedAdmins = base.linked_admins || [];
                  return (
                    <tr key={base.id}>
                      <td>
                        <AdminStatusBadge tone={statusTones[statusKey] || "neutral"}>{formatStatus(base.status)}</AdminStatusBadge>
                      </td>
                      <td className="text-muted-foreground">#{base.id}</td>
                      <td className="crm-copy-safe font-medium text-foreground">{base.name || "Без названия"}</td>
                      <td>{base.lake_name || "—"}</td>
                      <td>
                        <span className="inline-flex items-center gap-2">
                          <Compass className="h-4 w-4 text-muted-foreground" />
                          {formatCoordinates(base)}
                        </span>
                      </td>
                      <td className="crm-copy-safe max-w-[260px] leading-6">{base.owner || "Не указан"}</td>
                      <td className="crm-copy-safe max-w-[260px] leading-6">{base.manager || "Не указан"}</td>
                      <td>
                        {linkedAdmins.length ? (
                          <div className="flex max-w-[260px] flex-wrap gap-2">
                            {linkedAdmins.map((account) => (
                              <span key={account.id} className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-foreground">
                                {account.display_name || account.login || `#${account.id}`}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">Не назначены</span>
                        )}
                      </td>
                      <td className="font-medium text-foreground">{formatCurrency(base.min_price)}</td>
                      <td className="text-right">
                        <button type="button" className="admin-button gap-2" onClick={() => navigate(crmPath(`/admin/bases/${base.id}`))}>
                          <PencilLine className="h-4 w-4" />
                          Редактировать
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={10}>По текущим фильтрам базы не найдены.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-4 sm:px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Контроль изменений</p>
          <h3 className="mt-2 text-lg font-semibold tracking-[-0.03em] text-foreground">Последние события из CRM</h3>
        </div>
        <div className="divide-y divide-border">
          {events.length ? (
            events.map((event) => (
              <div key={event.id} className="flex flex-col gap-3 px-5 py-4 sm:px-6 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <AdminStatusBadge tone={severityTones[(event.severity || "").toLowerCase()] || "neutral"}>
                      {event.severity === "critical" ? "Критично" : event.severity === "warning" ? "Внимание" : "Инфо"}
                    </AdminStatusBadge>
                    {event.camp_name ? <span className="text-sm font-medium text-foreground">{event.camp_name}</span> : null}
                  </div>
                  <p className="text-sm font-semibold text-foreground">{event.title || "Системное событие"}</p>
                  <p className="text-sm leading-6 text-muted-foreground">{event.body || "Без описания"}</p>
                </div>
                <div className="flex shrink-0 flex-col items-start gap-2 text-xs text-muted-foreground lg:items-end">
                  <span>{event.created_at ? new Date(event.created_at).toLocaleString("ru-RU") : "—"}</span>
                  <span className="crm-copy-safe">{event.action_url ? "Открыть в CRM" : "Без действия"}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="px-5 py-6 text-sm text-muted-foreground sm:px-6">Пока нет событий для отображения.</div>
          )}
        </div>
      </AdminCard>
    </PageMotion>
  );
}
