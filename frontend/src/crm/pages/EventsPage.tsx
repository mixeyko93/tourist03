import { BellRing, CheckCheck, CircleAlert, CircleDot, ExternalLink, Search, ShieldAlert, Workflow } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { EmptyState } from "../components/EmptyState";
import { PageLoadingState } from "../components/PageLoadingState";
import { PageMotion } from "../components/PageMotion";
import { usePageLoadState } from "../components/usePageLoadState";
import { SectionHeading } from "../components/SectionHeading";
import { crmPath } from "../paths";
import {
  fetchCrmCamps,
  fetchCrmEventCenter,
  updateCrmEventStatus,
  type CrmCamp,
  type CrmEventCenterItem,
  type CrmEventCenterSummary,
} from "../session";

const statusOptions = [
  { value: "", label: "Все статусы" },
  { value: "new", label: "Новое" },
  { value: "viewed", label: "Просмотрено" },
  { value: "in_progress", label: "В работе" },
  { value: "closed", label: "Закрыто" },
];

const severityOptions = [
  { value: "", label: "Любой приоритет" },
  { value: "info", label: "Обычное" },
  { value: "warning", label: "Требует внимания" },
  { value: "critical", label: "Критично" },
];

const statusLabels: Record<string, string> = {
  new: "Новое",
  viewed: "Просмотрено",
  in_progress: "В работе",
  closed: "Закрыто",
};

const statusClasses: Record<string, string> = {
  new: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/25 dark:bg-sky-500/10 dark:text-sky-300",
  viewed: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-500/25 dark:bg-slate-500/10 dark:text-slate-300",
  in_progress: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-300",
  closed: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/25 dark:bg-emerald-500/10 dark:text-emerald-300",
};

const severityLabels: Record<string, string> = {
  info: "Обычное",
  warning: "Требует внимания",
  critical: "Критично",
};

const severityClasses: Record<string, string> = {
  info: "border-[#2F80ED] bg-[#EEF5FF] text-[#226ED1] dark:border-[#2F80ED]/25 dark:bg-[#2F80ED]/10 dark:text-[#2F80ED]",
  warning: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-300",
  critical: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-500/25 dark:bg-rose-500/10 dark:text-rose-300",
};

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Не указано";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function summaryValue(value: number | null | undefined) {
  return new Intl.NumberFormat("ru-RU").format(Number(value || 0));
}

export default function EventsPage() {
  const navigate = useNavigate();
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [items, setItems] = useState<CrmEventCenterItem[]>([]);
  const [summary, setSummary] = useState<CrmEventCenterSummary>({
    total_count: 0,
    new_count: 0,
    viewed_count: 0,
    in_progress_count: 0,
    closed_count: 0,
    warning_count: 0,
    critical_count: 0,
  });
  const [isBootLoading, setIsBootLoading] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [updatingEventId, setUpdatingEventId] = useState<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsBootLoading(true);
    setErrorMessage("");

    fetchCrmCamps(controller.signal)
      .then((campItems) => {
        setCamps(campItems);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить базы");
        setCamps([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsBootLoading(false);
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");

    fetchCrmEventCenter(
      {
        campId: selectedCampId,
        search: searchQuery.trim() || undefined,
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
        limit: 250,
      },
      controller.signal,
    )
      .then((payload) => {
        setItems(payload.items);
        setSummary(payload.summary);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить центр событий");
        setItems([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [selectedCampId, searchQuery, statusFilter, severityFilter, reloadKey]);

  const hasCampOptions = camps.length > 0;
  const headlineStats = useMemo(
    () => [
      {
        label: "Новых событий",
        value: summary.new_count,
        note: "Ещё не разобраны сотрудниками",
        icon: BellRing,
        className: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/25 dark:bg-sky-500/10 dark:text-sky-300",
        isActive: statusFilter === "new" && !severityFilter,
        onClick: () => {
          setStatusFilter("new");
          setSeverityFilter("");
        },
      },
      {
        label: "Событий в работе",
        value: summary.in_progress_count,
        note: "Требуют реакции по бронированиям",
        icon: Workflow,
        className: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-300",
        isActive: statusFilter === "in_progress" && !severityFilter,
        onClick: () => {
          setStatusFilter("in_progress");
          setSeverityFilter("");
        },
      },
      {
        label: "Критичных сигналов",
        value: summary.critical_count,
        note: "Срочные проблемы с заявками",
        icon: ShieldAlert,
        className: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-500/25 dark:bg-rose-500/10 dark:text-rose-300",
        isActive: severityFilter === "critical" && !statusFilter,
        onClick: () => {
          setSeverityFilter("critical");
          setStatusFilter("");
        },
      },
      {
        label: "Всего в ленте",
        value: summary.total_count,
        note: "Только заявки и бронирования",
        icon: CircleDot,
        className: "border-[#2F80ED] bg-[#EEF5FF] text-[#226ED1] dark:border-[#2F80ED]/25 dark:bg-[#2F80ED]/10 dark:text-[#2F80ED]",
        isActive: !statusFilter && !severityFilter,
        onClick: () => {
          setStatusFilter("");
          setSeverityFilter("");
        },
      },
    ],
    [severityFilter, statusFilter, summary],
  );

  async function handleStatusChange(item: CrmEventCenterItem, nextStatus: "new" | "viewed" | "in_progress" | "closed") {
    try {
      setUpdatingEventId(item.id);
      setErrorMessage("");
      setSuccessMessage("");
      const payload = await updateCrmEventStatus(item.id, { status: nextStatus });
      setItems((current) => current.map((entry) => (entry.id === item.id ? payload.item : entry)));
      setSummary((current) => {
        const next = { ...current };
        const previousStatus = item.status;
        if (previousStatus !== nextStatus) {
          if (previousStatus === "new") next.new_count = Math.max(0, next.new_count - 1);
          if (previousStatus === "viewed") next.viewed_count = Math.max(0, next.viewed_count - 1);
          if (previousStatus === "in_progress") next.in_progress_count = Math.max(0, next.in_progress_count - 1);
          if (previousStatus === "closed") next.closed_count = Math.max(0, next.closed_count - 1);

          if (nextStatus === "new") next.new_count += 1;
          if (nextStatus === "viewed") next.viewed_count += 1;
          if (nextStatus === "in_progress") next.in_progress_count += 1;
          if (nextStatus === "closed") next.closed_count += 1;
        }
        return next;
      });
      setSuccessMessage(`Событие переведено в статус «${statusLabels[nextStatus]}».`);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("crm-events-changed"));
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось обновить статус события");
    } finally {
      setUpdatingEventId(null);
    }
  }

  const { isPageVisible } = usePageLoadState(isBootLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <SectionHeading
        title="События по броням"
        description="Живая лента заявок и бронирований: новые обращения, изменения статусов и всё, что требует внимания по размещению."
        actions={
          <button type="button" className="brand-outline w-full sm:w-auto" onClick={() => setReloadKey((value) => value + 1)}>
            Обновить ленту
          </button>
        }
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 xl:grid-cols-[260px_minmax(0,1fr)_220px_220px_auto] xl:items-center">
          <select
            className="soft-input disabled:cursor-not-allowed disabled:opacity-60"
            value={selectedCampId ?? ""}
            onChange={(event) => setSelectedCampId(event.target.value ? Number(event.target.value) : null)}
            disabled={!hasCampOptions || isBootLoading}
          >
            <option value="">Все доступные базы</option>
            {camps.map((camp) => (
              <option key={camp.id} value={camp.id}>
                {camp.name}
              </option>
            ))}
          </select>

          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              className="soft-input pl-11"
              placeholder="Поиск по заголовку, описанию или базе"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <select className="soft-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            {statusOptions.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          <select className="soft-input" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
            {severityOptions.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          <div className="rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm text-muted-foreground">
            Открыто: <span className="font-semibold text-foreground">{summaryValue(summary.total_count - summary.closed_count)}</span>
          </div>
        </div>
      </section>

      {errorMessage ? (
        <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
          {errorMessage}
        </section>
      ) : null}

      {successMessage ? (
        <section className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-4 text-sm text-emerald-200">
          {successMessage}
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {headlineStats.map((stat) => {
          const Icon = stat.icon;
          return (
            <button
              key={stat.label}
              type="button"
              onClick={stat.onClick}
              className={`glass-card p-5 text-left transition hover:-translate-y-0.5 hover:border-[#2F80ED]/50 hover:bg-accent/25 ${
                stat.isActive ? "border-[#2F80ED]/60 ring-1 ring-[#2F80ED]/40" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{stat.label}</p>
                  <p className="mt-3 text-4xl font-semibold tracking-[-0.06em] text-foreground">{summaryValue(stat.value)}</p>
                </div>
                <span className={`rounded-2xl border p-3 ${stat.className}`}>
                  <Icon className="h-5 w-5" />
                </span>
              </div>
              <p className="mt-6 text-sm leading-6 text-muted-foreground">{stat.note}</p>
            </button>
          );
        })}
      </section>

      <section className="glass-card p-6">
        {isLoading ? (
          <PageLoadingState blocks={3} columnsClassName="grid-cols-1" blockHeightClassName="h-40" />
        ) : items.length ? (
          <div className="space-y-4">
            {items.map((item) => {
              const statusClass = statusClasses[item.status] || "border-border bg-background/60 text-foreground";
              const severityClass = severityClasses[item.severity] || "border-border bg-background/60 text-foreground";
              const actionUrl = item.action_url ? crmPath(item.action_url) : null;
              return (
                <article key={item.id} className="rounded-[1.9rem] border border-border bg-background/65 p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusClass}`}>
                          {statusLabels[item.status] || item.status}
                        </span>
                        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${severityClass}`}>
                          {severityLabels[item.severity] || item.severity}
                        </span>
                        {item.camp_name ? (
                          <span className="rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground">
                            {item.camp_name}
                          </span>
                        ) : null}
                        <span className="text-xs text-muted-foreground">{formatDateTime(item.created_at)}</span>
                      </div>

                      <h2 className="mt-4 text-xl font-semibold tracking-[-0.03em] text-foreground">{item.title}</h2>
                      <p className="mt-3 whitespace-pre-line text-sm leading-6 text-muted-foreground">{item.body}</p>

                      <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span>Тип: {item.event_type}</span>
                        {item.read_at ? <span>Просмотрено: {formatDateTime(item.read_at)}</span> : null}
                        {item.closed_at ? <span>Закрыто: {formatDateTime(item.closed_at)}</span> : null}
                      </div>
                    </div>

                    <div className="flex w-full shrink-0 flex-col gap-2 lg:w-[240px]">
                      {actionUrl ? (
                        <button
                          type="button"
                          className="brand-button justify-center gap-2"
                          onClick={() => navigate(actionUrl)}
                        >
                          <ExternalLink className="h-4 w-4" />
                          Открыть источник
                        </button>
                      ) : null}
                      <button
                        type="button"
                        className="soft-button justify-center"
                        disabled={updatingEventId === item.id || item.status === "viewed"}
                        onClick={() => handleStatusChange(item, "viewed")}
                      >
                        {updatingEventId === item.id ? "Сохраняем..." : "Отметить просмотренным"}
                      </button>
                      <button
                        type="button"
                        className="soft-button justify-center"
                        disabled={updatingEventId === item.id || item.status === "in_progress"}
                        onClick={() => handleStatusChange(item, "in_progress")}
                      >
                        Взять в работу
                      </button>
                      <button
                        type="button"
                        className="inline-flex items-center justify-center gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/16 disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={updatingEventId === item.id || item.status === "closed"}
                        onClick={() => handleStatusChange(item, "closed")}
                      >
                        <CheckCheck className="h-4 w-4" />
                        Закрыть событие
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            icon={CircleAlert}
            title="События не найдены"
            description="Лента пуста по выбранным фильтрам. Когда в CRM появятся новые действия, заявки или сигналы, они отобразятся здесь."
          />
        )}
      </section>
    </PageMotion>
  );
}
