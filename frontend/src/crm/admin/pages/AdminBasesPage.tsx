import { Compass, PencilLine, Plus, RefreshCcw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { crmPath } from "../../paths";
import { AdminCard } from "../components/AdminCard";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import {
  bulkUpdateSuperadminEntities,
  fetchCatalogDictionaries,
  fetchSuperadminEntities,
  fetchSuperadminEvents,
  type SuperadminBaseSummary,
  type SuperadminEntityKind,
  type SuperadminPlaceType,
  type SuperadminSystemEvent,
} from "../session";

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

const publicationLabels: Record<string, string> = {
  draft: "Черновик",
  in_review: "На проверке",
  published: "Опубликован",
  disabled: "Скрыт",
  archived: "В архиве",
  rejected: "Отклонён",
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
  const [entityKind, setEntityKind] = useState("");
  const [subtype, setSubtype] = useState("");
  const [publicationStatus, setPublicationStatus] = useState("");
  const [entityKinds, setEntityKinds] = useState<SuperadminEntityKind[]>([]);
  const [placeTypes, setPlaceTypes] = useState<SuperadminPlaceType[]>([]);
  const [quickMode, setQuickMode] = useState<"all" | "active" | "published">("all");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [bulkStatus, setBulkStatus] = useState<"draft" | "disabled" | "published" | "archived">("published");
  const [isBulkSaving, setIsBulkSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");

    Promise.all([
      fetchSuperadminEntities({ search, entityKind, subtype, publicationStatus, signal: controller.signal }),
      fetchSuperadminEvents({ limit: 6, signal: controller.signal }),
      fetchCatalogDictionaries(controller.signal),
    ])
      .then(([bases, systemEvents, dictionaries]) => {
        setItems(bases);
        setEvents(systemEvents);
        setPlaceTypes(dictionaries.placeTypes);
        setEntityKinds(dictionaries.entityKinds);
        setSelectedIds(new Set());
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
  }, [reloadKey, search, entityKind, subtype, publicationStatus]);

  const summary = useMemo(() => {
    return items.reduce(
      (accumulator, item) => {
        const status = (item.status || "").toLowerCase();
        accumulator.total += 1;
        if (status === "active") accumulator.active += 1;
        if (status === "disabled") accumulator.disabled += 1;
        if (item.publication_status === "published") accumulator.published += 1;
        return accumulator;
      },
      { total: 0, active: 0, disabled: 0, published: 0 },
    );
  }, [items]);
  const visibleItems = useMemo(() => {
    const next = [...items];
    if (quickMode === "active") {
      return next.filter((item) => (item.status || "").toLowerCase() === "active");
    }
    if (quickMode === "published") {
      return next.filter((item) => item.publication_status === "published");
    }
    return next;
  }, [items, quickMode]);
  const visibleIds = visibleItems.map((item) => item.id);
  const allVisibleSelected = Boolean(visibleIds.length) && visibleIds.every((id) => selectedIds.has(id));
  const filteredPlaceTypes = placeTypes.filter((type) => !entityKind || type.entity_kind === entityKind);

  function toggleEntity(entityId: number) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(entityId)) next.delete(entityId);
      else next.add(entityId);
      return next;
    });
  }

  async function applyBulkStatus() {
    if (!selectedIds.size) return;
    if (!window.confirm(`Изменить статус ${selectedIds.size} карточек?`)) return;
    try {
      setIsBulkSaving(true);
      setErrorMessage("");
      await bulkUpdateSuperadminEntities([...selectedIds], bulkStatus);
      setSelectedIds(new Set());
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось изменить карточки");
    } finally {
      setIsBulkSaving(false);
    }
  }

  const { isPageVisible } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Универсальный каталог</p>
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Карточки</h2>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                Объекты размещения, услуги и активности с едиными статусами, поиском и модерацией.
              </p>
            </div>

            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
              <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
                <RefreshCcw className="h-4 w-4" />
                Обновить
              </button>
              <button type="button" className="admin-primary-button w-full gap-2 sm:w-auto" onClick={() => navigate(crmPath("/admin/entities/new"))}>
                <Plus className="h-4 w-4" />
                Добавить карточку
              </button>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_repeat(3,minmax(170px,220px))]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                className="admin-input pl-10"
                aria-label="Поиск по каталогу"
                placeholder="Поиск по названию, адресу или владельцу"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>

            <select
              className="admin-input"
              value={entityKind}
              onChange={(event) => {
                setEntityKind(event.target.value);
                setSubtype("");
              }}
              aria-label="Категория карточки"
            >
              <option value="">Все категории</option>
              {entityKinds.map((kind) => <option key={kind.id} value={kind.key}>{kind.name}</option>)}
            </select>

            <select className="admin-input" value={subtype} onChange={(event) => setSubtype(event.target.value)} aria-label="Подтип карточки">
              <option value="">Все подтипы</option>
              {filteredPlaceTypes.map((type) => <option key={type.id} value={type.slug}>{type.name}</option>)}
            </select>

            <select className="admin-input" value={publicationStatus} onChange={(event) => setPublicationStatus(event.target.value)} aria-label="Статус публикации">
              <option value="">Все публикации</option>
              {Object.entries(publicationLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>

          </div>

          <div className="grid gap-3 sm:grid-cols-3">

            {[
              { label: "Всего карточек", value: summary.total, key: "all" as const },
              { label: "Активных", value: summary.active, key: "active" as const },
              { label: "Опубликовано", value: summary.published, key: "published" as const },
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

          <div className="flex flex-col gap-3 rounded-2xl border border-border bg-background/65 p-4 sm:flex-row sm:items-center">
            <span className="text-sm text-muted-foreground">Выбрано: <b className="text-foreground">{selectedIds.size}</b></span>
            <select
              className="admin-input sm:ml-auto sm:max-w-56"
              aria-label="Новый статус выбранных карточек"
              value={bulkStatus}
              onChange={(event) => setBulkStatus(event.target.value as typeof bulkStatus)}
            >
              <option value="published">Опубликовать</option>
              <option value="draft">Сделать черновиками</option>
              <option value="disabled">Скрыть</option>
              <option value="archived">Архивировать</option>
            </select>
            <button
              type="button"
              className="admin-primary-button"
              disabled={!selectedIds.size || isBulkSaving}
              onClick={() => void applyBulkStatus()}
            >
              {isBulkSaving ? "Применяем…" : "Применить"}
            </button>
          </div>
        </div>

        {errorMessage ? (
          <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div>
        ) : null}

        <div className="admin-table-shell">
          <table className="admin-table min-w-[1440px]">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    aria-label="Выбрать все карточки на странице"
                    checked={allVisibleSelected}
                    onChange={() => {
                      setSelectedIds((current) => {
                        const next = new Set(current);
                        visibleIds.forEach((id) => {
                          if (allVisibleSelected) next.delete(id);
                          else next.add(id);
                        });
                        return next;
                      });
                    }}
                  />
                </th>
                <th>Статус</th>
                <th>ID</th>
                <th>Название</th>
                <th>Slug</th>
                <th>Категория</th>
                <th>Подтип</th>
                <th>Публикация</th>
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
                  <td colSpan={15}>Загружаем карточки…</td>
                </tr>
              ) : visibleItems.length ? (
                visibleItems.map((base) => {
                  const statusKey = (base.status || "").toLowerCase();
                  const linkedAdmins = base.linked_admins || [];
                  return (
                    <tr key={base.id}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Выбрать карточку ${base.name || `#${base.id}`}`}
                          checked={selectedIds.has(base.id)}
                          onChange={() => toggleEntity(base.id)}
                        />
                      </td>
                      <td>
                        <AdminStatusBadge tone={statusTones[statusKey] || "neutral"}>{formatStatus(base.status)}</AdminStatusBadge>
                      </td>
                      <td className="text-muted-foreground">#{base.id}</td>
                      <td className="crm-copy-safe font-medium text-foreground">{base.name || "Без названия"}</td>
                      <td className="crm-copy-safe text-muted-foreground">{base.slug || "—"}</td>
                      <td>{base.entity_kind_name || base.entity_kind || "—"}</td>
                      <td>{base.place_type_name || "—"}</td>
                      <td>
                        <AdminStatusBadge tone={base.publication_status === "published" ? "success" : base.publication_status === "in_review" ? "warning" : "neutral"}>
                          {publicationLabels[base.publication_status || ""] || "Без статуса"}
                        </AdminStatusBadge>
                      </td>
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
                        <button type="button" className="admin-button gap-2" onClick={() => navigate(crmPath(`/admin/entities/${base.id}`))}>
                          <PencilLine className="h-4 w-4" />
                          Редактировать
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={15}>По текущим фильтрам карточки не найдены.</td>
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
