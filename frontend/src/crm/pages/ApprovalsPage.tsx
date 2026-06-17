import { CheckCheck, MessageSquareWarning, RotateCcw, Search, ShieldAlert, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { EmptyState } from "../components/EmptyState";
import { PageLoadingState } from "../components/PageLoadingState";
import { ModalShell } from "../components/ModalShell";
import { PageMotion } from "../components/PageMotion";
import { usePageLoadState } from "../components/usePageLoadState";
import { SectionHeading } from "../components/SectionHeading";
import { fetchCrmCamps, fetchCrmChangeRequests, updateCrmChangeRequest, type CrmCamp, type CrmChangeRequest, type CrmChangeRequestDecisionPayload } from "../session";

const fallbackStatusLabels: Record<string, string> = {
  pending_review: "На подтверждении",
  approved: "Подтверждено",
  rejected: "Отклонено",
  needs_clarification: "Нужно уточнение",
  applied_with_responsibility: "Применено под ответственность",
  rolled_back: "Откат выполнен",
};

const fallbackKindLabels: Record<string, string> = {
  shift_schedule: "График смен",
  pricing: "Цены",
  cancellation_policy: "Правила отмены",
  camp_visibility: "Публикация базы",
  archive: "Архивирование",
};

const statusClasses: Record<string, string> = {
  pending_review: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  approved: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  rejected: "border-rose-500/25 bg-rose-500/10 text-rose-300",
  needs_clarification: "border-sky-500/25 bg-sky-500/10 text-sky-300",
  applied_with_responsibility: "border-[#2F80ED]/25 bg-[#2F80ED]/10 text-[#2F80ED]",
  rolled_back: "border-slate-500/25 bg-slate-500/10 text-slate-300",
};

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Не указано";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? "");
  }
}

export default function ApprovalsPage() {
  const [searchParams] = useSearchParams();
  const requestedId = Number(searchParams.get("request_id") || 0) || null;
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [kindFilter, setKindFilter] = useState("");
  const [items, setItems] = useState<CrmChangeRequest[]>([]);
  const [selectedItem, setSelectedItem] = useState<CrmChangeRequest | null>(null);
  const [statusLabels, setStatusLabels] = useState<Record<string, string>>(fallbackStatusLabels);
  const [kindLabels, setKindLabels] = useState<Record<string, string>>(fallbackKindLabels);
  const [isBootLoading, setIsBootLoading] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [actionModalOpen, setActionModalOpen] = useState(false);
  const [actionType, setActionType] = useState<CrmChangeRequestDecisionPayload["action"]>("approve");
  const [actionComment, setActionComment] = useState("");
  const [updatingId, setUpdatingId] = useState<number | null>(null);

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
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить список баз");
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
    fetchCrmChangeRequests(
      {
        campId: selectedCampId,
        search: searchQuery.trim() || undefined,
        status: statusFilter || undefined,
        changeKind: kindFilter || undefined,
        limit: 250,
      },
      controller.signal,
    )
      .then((payload) => {
        setItems(payload.items);
        setStatusLabels(payload.status_labels || fallbackStatusLabels);
        setKindLabels(payload.change_kind_labels || fallbackKindLabels);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить согласования");
        setItems([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [selectedCampId, searchQuery, statusFilter, kindFilter, reloadKey]);

  useEffect(() => {
    if (!items.length) {
      setSelectedItem(null);
      return;
    }
    if (requestedId) {
      const matched = items.find((item) => item.id === requestedId);
      if (matched) {
        setSelectedItem(matched);
        return;
      }
    }
    setSelectedItem((current) => {
      if (current && items.some((item) => item.id === current.id)) {
        return items.find((item) => item.id === current.id) || null;
      }
      return items[0] || null;
    });
  }, [items, requestedId]);

  const counts = useMemo(
    () => ({
      pending: items.filter((item) => item.status === "pending_review").length,
      clarification: items.filter((item) => item.status === "needs_clarification").length,
      responsibility: items.filter((item) => item.status === "applied_with_responsibility").length,
      total: items.length,
    }),
    [items],
  );

  const canRollback = selectedItem ? ["approved", "applied_with_responsibility"].includes(selectedItem.status) : false;
  const canReview = selectedItem ? selectedItem.status === "pending_review" : false;

  async function submitAction() {
    if (!selectedItem) return;
    try {
      setUpdatingId(selectedItem.id);
      setErrorMessage("");
      setSuccessMessage("");
      const payload = await updateCrmChangeRequest(selectedItem.id, {
        action: actionType,
        comment: actionComment || undefined,
      });
      setItems((current) => current.map((item) => (item.id === payload.item.id ? payload.item : item)));
      setSelectedItem(payload.item);
      setActionModalOpen(false);
      setActionComment("");
      setSuccessMessage("Согласование обновлено.");
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("crm-events-changed"));
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось обновить согласование");
    } finally {
      setUpdatingId(null);
    }
  }

  const { isPageVisible } = usePageLoadState(isBootLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <SectionHeading
        title="Подтверждения и откаты"
        description="Живой контур изменений: что отправили на подтверждение, что применили под ответственность и что при необходимости можно откатить."
        actions={
          <button type="button" className="brand-outline w-full sm:w-auto" onClick={() => setReloadKey((value) => value + 1)}>
            Обновить список
          </button>
        }
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 xl:grid-cols-[240px_minmax(0,1fr)_220px_220px_auto] xl:items-center">
          <select
            className="soft-input disabled:cursor-not-allowed disabled:opacity-60"
            value={selectedCampId ?? ""}
            onChange={(event) => setSelectedCampId(event.target.value ? Number(event.target.value) : null)}
            disabled={!camps.length || isBootLoading}
          >
            <option value="">Все базы</option>
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
              placeholder="Поиск по базе, автору, комментарию или цели"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <select className="soft-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(statusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <select className="soft-input" value={kindFilter} onChange={(event) => setKindFilter(event.target.value)}>
            <option value="">Все типы</option>
            {Object.entries(kindLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <div className="rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm text-muted-foreground">
            На разборе: <span className="font-semibold text-foreground">{counts.pending + counts.clarification}</span>
          </div>
        </div>
      </section>

      {errorMessage ? <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">{errorMessage}</section> : null}
      {successMessage ? <section className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-4 text-sm text-emerald-200">{successMessage}</section> : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "На подтверждении", value: counts.pending, className: "border-amber-500/25 bg-amber-500/10 text-amber-300" },
          { label: "Нужно уточнение", value: counts.clarification, className: "border-sky-500/25 bg-sky-500/10 text-sky-300" },
          { label: "Под ответственность", value: counts.responsibility, className: "border-[#2F80ED]/25 bg-[#2F80ED]/10 text-[#2F80ED]" },
          { label: "Всего запросов", value: counts.total, className: "border-border bg-background/70 text-foreground" },
        ].map((item) => (
          <article key={item.label} className="glass-card p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{item.label}</p>
            <div className={`mt-4 inline-flex rounded-2xl border px-4 py-3 text-3xl font-semibold tracking-[-0.05em] ${item.className}`}>{item.value}</div>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        <div className="glass-card p-5">
          {isLoading ? (
            <PageLoadingState blocks={3} columnsClassName="grid-cols-1" blockHeightClassName="h-36" />
          ) : items.length ? (
            <div className="space-y-3">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedItem(item)}
                  className={`w-full rounded-[1.7rem] border p-4 text-left transition ${
                    selectedItem?.id === item.id ? "border-[#2F80ED]/40 bg-[#2F80ED]/10 shadow-sm" : "border-border bg-background/65 hover:bg-accent"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusClasses[item.status] || "border-border bg-background/70 text-foreground"}`}>
                      {statusLabels[item.status] || item.status}
                    </span>
                    <span className="rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground">
                      {kindLabels[item.change_kind] || item.change_kind}
                    </span>
                    <span className="text-xs text-muted-foreground">{formatDateTime(item.created_at)}</span>
                  </div>
                  <h2 className="mt-3 text-base font-semibold text-foreground">{item.summary}</h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Инициатор: {item.created_by_display || item.created_by_email || `Сотрудник #${item.created_by_admin_id}`}
                  </p>
                  {item.request_comment ? <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{item.request_comment}</p> : null}
                </button>
              ))}
            </div>
          ) : (
            <EmptyState icon={ShieldAlert} title="Согласований пока нет" description="Как только сотрудники отправят чувствительные изменения на подтверждение или применят их под ответственность, они появятся здесь." />
          )}
        </div>

        <section className="glass-card p-6">
          {selectedItem ? (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusClasses[selectedItem.status] || "border-border bg-background/70 text-foreground"}`}>
                  {statusLabels[selectedItem.status] || selectedItem.status}
                </span>
                <span className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs font-medium text-muted-foreground">
                  {kindLabels[selectedItem.change_kind] || selectedItem.change_kind}
                </span>
                {selectedItem.camp_name ? <span className="rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground">{selectedItem.camp_name}</span> : null}
              </div>

              <div>
                <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">{selectedItem.summary}</h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  Инициатор: {selectedItem.created_by_display || selectedItem.created_by_email || `Сотрудник #${selectedItem.created_by_admin_id}`}
                </p>
                <p className="text-sm leading-6 text-muted-foreground">Создано: {formatDateTime(selectedItem.created_at)}</p>
                {selectedItem.decided_at ? <p className="text-sm leading-6 text-muted-foreground">Решение: {formatDateTime(selectedItem.decided_at)}</p> : null}
              </div>

              {selectedItem.request_comment ? (
                <div className="rounded-3xl border border-border bg-background/65 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий инициатора</p>
                  <p className="mt-3 whitespace-pre-line text-sm leading-6 text-foreground">{selectedItem.request_comment}</p>
                </div>
              ) : null}

              {selectedItem.reviewer_comment ? (
                <div className="rounded-3xl border border-sky-500/25 bg-sky-500/10 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-sky-200">Комментарий управляющего</p>
                  <p className="mt-3 whitespace-pre-line text-sm leading-6 text-sky-50">{selectedItem.reviewer_comment}</p>
                </div>
              ) : null}

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-3xl border border-border bg-background/65 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Payload</p>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-foreground">{prettyJson(selectedItem.payload)}</pre>
                </div>
                <div className="rounded-3xl border border-border bg-background/65 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Применённый снимок</p>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-foreground">{prettyJson(selectedItem.applied_snapshot)}</pre>
                </div>
              </div>

              <div className="flex flex-col gap-3 border-t border-border pt-3 sm:flex-row sm:flex-wrap">
                {canReview ? (
                  <>
                    <button
                      type="button"
                      className="brand-button gap-2"
                      onClick={() => {
                        setActionType("approve");
                        setActionComment("");
                        setActionModalOpen(true);
                      }}
                    >
                      <CheckCheck className="h-4 w-4" />
                      Подтвердить
                    </button>
                    <button
                      type="button"
                      className="soft-button gap-2"
                      onClick={() => {
                        setActionType("clarify");
                        setActionComment("");
                        setActionModalOpen(true);
                      }}
                    >
                      <MessageSquareWarning className="h-4 w-4" />
                      Уточнить
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/16"
                      onClick={() => {
                        setActionType("reject");
                        setActionComment("");
                        setActionModalOpen(true);
                      }}
                    >
                      <XCircle className="h-4 w-4" />
                      Отклонить
                    </button>
                  </>
                ) : null}

                {canRollback ? (
                  <button
                    type="button"
                    className="inline-flex items-center justify-center gap-2 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-300 transition hover:bg-amber-500/16"
                    onClick={() => {
                      setActionType("rollback");
                      setActionComment("");
                      setActionModalOpen(true);
                    }}
                  >
                    <RotateCcw className="h-4 w-4" />
                    Откатить
                  </button>
                ) : null}
              </div>
            </div>
          ) : (
            <EmptyState icon={ShieldAlert} title="Выберите согласование" description="Откройте запрос слева, чтобы увидеть payload, комментарии и принять решение." />
          )}
        </section>
      </section>

      <ModalShell
        open={actionModalOpen}
        onClose={() => {
          if (!updatingId) {
            setActionModalOpen(false);
          }
        }}
        title={
          actionType === "approve"
            ? "Подтверждение изменения"
            : actionType === "reject"
              ? "Отклонение изменения"
              : actionType === "clarify"
                ? "Запрос уточнения"
                : "Подтверждение отката"
        }
        description={
          actionType === "rollback"
            ? "Откат вернёт систему к предыдущему состоянию. Действие будет залогировано и отправлено инициатору."
            : "Комментарий попадёт в журнал и будет показан инициатору в CRM и боте уведомлений."
        }
      >
        <div className="space-y-5">
          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
            <textarea
              className="soft-input min-h-28 resize-none"
              value={actionComment}
              onChange={(event) => setActionComment(event.target.value)}
              placeholder="Кратко поясните решение"
            />
          </label>

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
            <button type="button" className="soft-button" onClick={() => setActionModalOpen(false)} disabled={Boolean(updatingId)}>
              Отмена
            </button>
            <button type="button" className="brand-button" onClick={() => void submitAction()} disabled={Boolean(updatingId)}>
              {updatingId ? "Сохраняем..." : actionType === "approve" ? "Подтвердить изменение" : actionType === "reject" ? "Отклонить изменение" : actionType === "clarify" ? "Отправить уточнение" : "Подтвердить откат"}
            </button>
          </div>
        </div>
      </ModalShell>
    </PageMotion>
  );
}
