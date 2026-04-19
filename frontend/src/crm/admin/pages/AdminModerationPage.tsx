import { Check, Clapperboard, Clock3, ExternalLink, Image as ImageIcon, RefreshCcw, Search, ShieldAlert, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminModal } from "../components/AdminModal";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { fetchSuperadminMediaQueue, updateSuperadminMediaModeration, type SuperadminMediaQueueItem } from "../session";

const statusOptions = [
  { value: "pending", label: "На модерации", tone: "warning" as const },
  { value: "approved", label: "Одобрено", tone: "success" as const },
  { value: "rejected", label: "Отклонено", tone: "danger" as const },
];

type DecisionState = {
  item: SuperadminMediaQueueItem;
  status: "pending" | "approved" | "rejected";
};

function statusMeta(status?: string | null) {
  return statusOptions.find((item) => item.value === (status || "").toLowerCase()) || statusOptions[0];
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
}

function moderationTitle(state: DecisionState | null) {
  if (!state) return "";
  if (state.status === "approved") return "Одобрить контент";
  if (state.status === "rejected") return "Отклонить контент";
  return "Вернуть на модерацию";
}

function ModerationPreview({ item }: { item: SuperadminMediaQueueItem }) {
  if (item.media_type === "image") {
    return <img src={item.url} alt={item.camp_name || "Изображение"} className="h-full w-full object-cover" />;
  }
  if (item.source_kind === "upload") {
    return <video src={item.url} poster={item.poster_url || undefined} className="h-full w-full object-cover" muted controls preload="metadata" />;
  }
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-background/80 px-3 text-center">
      {item.poster_url ? <img src={item.poster_url} alt="Обложка видео" className="absolute inset-0 h-full w-full object-cover opacity-50" /> : null}
      <Clapperboard className="relative h-5 w-5 text-blue-400" />
      <span className="relative line-clamp-2 text-xs font-medium text-foreground">Внешняя ссылка на видео</span>
    </div>
  );
}

export default function AdminModerationPage() {
  const [items, setItems] = useState<SuperadminMediaQueueItem[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("pending");
  const [mediaTypeFilter, setMediaTypeFilter] = useState<"" | "image" | "video">("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [decisionState, setDecisionState] = useState<DecisionState | null>(null);
  const [decisionComment, setDecisionComment] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    fetchSuperadminMediaQueue({
      search,
      status: statusFilter,
      limit: 200,
      signal: controller.signal,
    })
      .then((media) => setItems(media))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setItems([]);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить очередь модерации");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, [reloadKey, search, statusFilter]);

  const summary = useMemo(() => {
    return items.reduce(
      (accumulator, item) => {
        const key = (item.moderation_status || "pending").toLowerCase();
        if (key === "approved") accumulator.approved += 1;
        else if (key === "rejected") accumulator.rejected += 1;
        else accumulator.pending += 1;
        if (item.media_type === "video") accumulator.videos += 1;
        else accumulator.images += 1;
        return accumulator;
      },
      { pending: 0, approved: 0, rejected: 0, images: 0, videos: 0 },
    );
  }, [items]);
  const visibleItems = useMemo(() => {
    if (!mediaTypeFilter) {
      return items;
    }
    return items.filter((item) => item.media_type === mediaTypeFilter);
  }, [items, mediaTypeFilter]);

  function openDecision(item: SuperadminMediaQueueItem, status: "pending" | "approved" | "rejected") {
    setDecisionState({ item, status });
    setDecisionComment(status === "rejected" ? item.moderation_comment || "" : "");
  }

  async function submitDecision() {
    if (!decisionState) return;
    try {
      setBusyId(decisionState.item.media_id);
      setErrorMessage("");
      setSuccessMessage("");
      await updateSuperadminMediaModeration(decisionState.item.entity_type, decisionState.item.media_id, {
        status: decisionState.status,
        comment: decisionComment.trim() || undefined,
      });
      setDecisionState(null);
      setDecisionComment("");
      setSuccessMessage(
        decisionState.status === "approved"
          ? "Контент одобрен."
          : decisionState.status === "rejected"
            ? "Контент отклонён."
            : "Контент возвращён в очередь модерации.",
      );
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось изменить статус модерации");
    } finally {
      setBusyId(null);
    }
  }

  const { showInitialSkeleton } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={!showInitialSkeleton}>
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Публичный контент</p>
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Очередь модерации</h2>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                Проверка фото, видео и внешних ссылок до публикации в клиентском контуре. Новые материалы по умолчанию попадают сюда на одобрение.
              </p>
            </div>

            <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCcw className="h-4 w-4" />
              Обновить
            </button>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_repeat(4,minmax(170px,200px))]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                className="admin-input pl-10"
                placeholder="Поиск по базе, апартаменту, URL или комментарию"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <div className="relative">
              <select className="admin-input appearance-none pr-10" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="pending">На модерации</option>
                <option value="approved">Одобрено</option>
                <option value="rejected">Отклонено</option>
                <option value="all">Все статусы</option>
              </select>
              <ShieldAlert className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
            {[
              { label: "На модерации", value: summary.pending, icon: Clock3, key: "pending" as const },
              { label: "Изображения", value: summary.images, icon: ImageIcon, key: "images" as const },
              { label: "Видео", value: summary.videos, icon: Clapperboard, key: "videos" as const },
              { label: "Отклонено", value: summary.rejected, icon: X, key: "rejected" as const },
            ].map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => {
                    if (item.key === "pending") {
                      setStatusFilter("pending");
                      setMediaTypeFilter("");
                    } else if (item.key === "rejected") {
                      setStatusFilter("rejected");
                      setMediaTypeFilter("");
                    } else if (item.key === "images") {
                      setMediaTypeFilter("image");
                    } else if (item.key === "videos") {
                      setMediaTypeFilter("video");
                    }
                  }}
                  className={`rounded-2xl border bg-background/70 px-4 py-3 text-left transition hover:-translate-y-0.5 hover:border-blue-500/40 hover:bg-accent ${
                    (item.key === "pending" && statusFilter === "pending" && !mediaTypeFilter) ||
                    (item.key === "rejected" && statusFilter === "rejected" && !mediaTypeFilter) ||
                    (item.key === "images" && mediaTypeFilter === "image") ||
                    (item.key === "videos" && mediaTypeFilter === "video")
                      ? "border-blue-500/55 ring-1 ring-blue-500/30"
                      : "border-border"
                  }`}
                >
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </div>
                  <div className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">{item.value}</div>
                </button>
              );
            })}
          </div>
        </div>

        {errorMessage ? <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div> : null}
        {successMessage ? (
          <div className="border-b border-border bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 sm:px-6">{successMessage}</div>
        ) : null}

        <div className="admin-table-shell">
          <table className="admin-table min-w-[1280px]">
            <thead>
              <tr>
                <th>Материал</th>
                <th>Объект</th>
                <th>Источник</th>
                <th>Статус</th>
                <th>Комментарий</th>
                <th>Добавлен</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7}>Загружаем очередь модерации…</td>
                </tr>
              ) : visibleItems.length ? (
                visibleItems.map((item) => {
                  const meta = statusMeta(item.moderation_status);
                  return (
                    <tr key={`${item.entity_type}-${item.media_id}`}>
                      <td>
                        <div className="flex items-center gap-4">
                          <div className="relative h-20 w-32 overflow-hidden rounded-2xl border border-border bg-card/70">
                            <ModerationPreview item={item} />
                          </div>
                          <div className="min-w-0 space-y-1">
                            <div className="flex items-center gap-2">
                              <AdminStatusBadge tone={item.media_type === "video" ? "info" : "neutral"}>
                                {item.media_type === "video" ? "Видео" : "Фото"}
                              </AdminStatusBadge>
                              {item.cover ? <AdminStatusBadge tone="warning">Обложка</AdminStatusBadge> : null}
                            </div>
                            <p className="crm-copy-safe max-w-[260px] truncate text-sm font-medium text-foreground">{item.url}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="space-y-1">
                          <p className="font-medium text-foreground">{item.camp_name || `База #${item.camp_id}`}</p>
                          <p className="text-sm text-muted-foreground">
                            {item.entity_type === "room" ? item.room_name || `Апартамент #${item.room_id}` : "Общий контент базы"}
                          </p>
                        </div>
                      </td>
                      <td>
                        <div className="space-y-1 text-sm text-muted-foreground">
                          <p>{item.source_kind === "external" ? "Внешняя ссылка" : "Файл на сервере"}</p>
                          {item.source_kind === "external" ? (
                            <a href={item.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300">
                              Открыть
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <AdminStatusBadge tone={meta.tone}>{meta.label}</AdminStatusBadge>
                      </td>
                      <td className="max-w-[260px] whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                        {item.moderation_comment || "—"}
                      </td>
                      <td>{formatDateTime(item.created_at)}</td>
                      <td className="text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            className="admin-button gap-2"
                            onClick={() => openDecision(item, "approved")}
                            disabled={busyId === item.media_id || item.moderation_status === "approved"}
                          >
                            <Check className="h-4 w-4" />
                            Одобрить
                          </button>
                          <button
                            type="button"
                            className="admin-button gap-2 text-rose-300 hover:text-rose-200"
                            onClick={() => openDecision(item, "rejected")}
                            disabled={busyId === item.media_id || item.moderation_status === "rejected"}
                          >
                            <X className="h-4 w-4" />
                            Отклонить
                          </button>
                          <button
                            type="button"
                            className="admin-button gap-2"
                            onClick={() => openDecision(item, "pending")}
                            disabled={busyId === item.media_id || item.moderation_status === "pending"}
                          >
                            <Clock3 className="h-4 w-4" />
                            Вернуть
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7}>По текущим фильтрам очередь модерации пуста.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={Boolean(decisionState)}
        onClose={() => {
          if (!busyId) {
            setDecisionState(null);
          }
        }}
        title={moderationTitle(decisionState)}
        description={
          decisionState
            ? decisionState.status === "approved"
              ? "После одобрения материал сможет участвовать в публичной выдаче базы."
              : decisionState.status === "rejected"
                ? "Отклонённый материал не будет использоваться в публичном контуре."
                : "Материал снова вернётся в очередь проверки."
            : ""
        }
        panelClassName="max-w-xl"
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" className="admin-button" onClick={() => setDecisionState(null)} disabled={Boolean(busyId)}>
              Отмена
            </button>
            <button type="button" className="admin-primary-button" onClick={submitDecision} disabled={Boolean(busyId)}>
              {busyId ? "Сохраняем..." : "Применить"}
            </button>
          </div>
        }
      >
        {decisionState ? (
          <div className="space-y-5">
            <div className="rounded-2xl border border-border bg-background/70 p-4">
              <p className="text-sm font-semibold text-foreground">{decisionState.item.camp_name || "База"}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {decisionState.item.entity_type === "room"
                  ? `Апартамент: ${decisionState.item.room_name || `#${decisionState.item.room_id}`}`
                  : "Контент относится ко всей базе"}
              </p>
            </div>
            <AdminField
              label="Комментарий модератора"
              hint={decisionState.status === "rejected" ? "Причина отказа будет сохранена и видна в системе." : "Необязательное пояснение для истории изменений."}
            >
              <textarea className="admin-input min-h-28 resize-y" value={decisionComment} onChange={(event) => setDecisionComment(event.target.value)} />
            </AdminField>
          </div>
        ) : null}
      </AdminModal>
    </PageMotion>
  );
}
