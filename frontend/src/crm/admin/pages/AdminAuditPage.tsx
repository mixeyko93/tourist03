import { ChevronDown, RefreshCcw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminModal } from "../components/AdminModal";
import {
  fetchSuperadminAuditLog,
  fetchSuperadminBases,
  type SuperadminAuditRecord,
  type SuperadminBaseSummary,
} from "../session";

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
}

function prettyJson(value: unknown) {
  if (value == null) return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "Данные недоступны";
  }
}

export default function AdminAuditPage() {
  const [items, setItems] = useState<SuperadminAuditRecord[]>([]);
  const [bases, setBases] = useState<SuperadminBaseSummary[]>([]);
  const [selectedItem, setSelectedItem] = useState<SuperadminAuditRecord | null>(null);
  const [search, setSearch] = useState("");
  const [actorType, setActorType] = useState("");
  const [targetType, setTargetType] = useState("");
  const [campId, setCampId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    Promise.all([
      fetchSuperadminAuditLog({
        search,
        actorType: actorType || undefined,
        targetType: targetType || undefined,
        campId: campId ? Number(campId) : undefined,
        limit: 200,
        signal: controller.signal,
      }),
      fetchSuperadminBases({ signal: controller.signal }),
    ])
      .then(([records, baseItems]) => {
        setItems(records);
        setBases(baseItems);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setItems([]);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить системный журнал");
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [search, actorType, targetType, campId, reloadKey]);

  const actorTypes = useMemo(
    () => Array.from(new Set(items.map((item) => item.actor_type).filter(Boolean))).sort((left, right) => left.localeCompare(right, "ru")),
    [items],
  );
  const targetTypes = useMemo(
    () => Array.from(new Set(items.map((item) => item.target_type).filter(Boolean))).sort((left, right) => left.localeCompare(right, "ru")),
    [items],
  );

  const { isPageVisible } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Root-only раздел</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">Системный журнал действий</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                  Полный аудит действий CRM, superadmin и системных процессов с фильтрами для быстрого поиска.
                </p>
              </div>

              <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
                <RefreshCcw className="h-4 w-4" />
                Обновить
              </button>
            </div>

            <div className="grid gap-3 lg:grid-cols-4">
              <label className="relative lg:col-span-2">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  className="admin-input pl-10"
                  placeholder="Поиск по действию, актору, объекту или комментарию"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </label>

              <AdminField label="Тип актора">
                <div className="relative">
                  <select className="admin-input appearance-none pr-10" value={actorType} onChange={(event) => setActorType(event.target.value)}>
                    <option value="">Все</option>
                    {actorTypes.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                </div>
              </AdminField>

              <AdminField label="Тип объекта">
                <div className="relative">
                  <select className="admin-input appearance-none pr-10" value={targetType} onChange={(event) => setTargetType(event.target.value)}>
                    <option value="">Все</option>
                    {targetTypes.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                </div>
              </AdminField>

              <AdminField label="База">
                <div className="relative">
                  <select className="admin-input appearance-none pr-10" value={campId} onChange={(event) => setCampId(event.target.value)}>
                    <option value="">Все базы</option>
                    {bases.map((base) => (
                      <option key={base.id} value={base.id}>
                        {base.name || `База #${base.id}`}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                </div>
              </AdminField>
            </div>
          </div>
        </div>

        {errorMessage ? <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div> : null}

        <div className="admin-table-shell">
          <table className="admin-table min-w-[1180px]">
            <thead>
              <tr>
                <th>Время</th>
                <th>Актор</th>
                <th>Действие</th>
                <th>Объект</th>
                <th>База</th>
                <th>Комментарий</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6}>Загружаем системный журнал…</td>
                </tr>
              ) : items.length ? (
                items.map((item) => (
                  <tr key={item.id} className="cursor-pointer" onClick={() => setSelectedItem(item)}>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>
                      <div className="font-medium text-foreground">{item.actor_display || item.actor_type}</div>
                      <div className="text-xs text-muted-foreground">{item.actor_type}</div>
                    </td>
                    <td>
                      <div className="font-medium text-foreground">{item.action_label}</div>
                      <div className="text-xs text-muted-foreground">{item.action_type}</div>
                    </td>
                    <td>
                      <div className="font-medium text-foreground">{item.target_type}</div>
                      <div className="text-xs text-muted-foreground">{item.target_id || "—"}</div>
                    </td>
                    <td>{item.camp_name || "—"}</td>
                    <td className="max-w-[360px] truncate">{item.comment || "—"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6}>По текущим фильтрам записи не найдены.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={Boolean(selectedItem)}
        onClose={() => setSelectedItem(null)}
        title={selectedItem ? selectedItem.action_label : ""}
        description={selectedItem ? `${selectedItem.actor_display || selectedItem.actor_type} • ${formatDateTime(selectedItem.created_at)}` : ""}
        panelClassName="max-w-4xl"
      >
        {selectedItem ? (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { label: "Актор", value: selectedItem.actor_display || selectedItem.actor_type },
                { label: "Тип актора", value: selectedItem.actor_type },
                { label: "Объект", value: `${selectedItem.target_type}${selectedItem.target_id ? ` #${selectedItem.target_id}` : ""}` },
                { label: "База", value: selectedItem.camp_name || "—" },
                { label: "Чувствительное действие", value: selectedItem.is_sensitive ? "Да" : "Нет" },
                { label: "Автоприменение", value: selectedItem.was_auto_applied ? "Да" : "Нет" },
              ].map((item) => (
                <div key={item.label} className="rounded-2xl border border-border bg-background/70 p-4">
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{item.label}</div>
                  <div className="mt-2 text-sm font-medium text-foreground">{item.value}</div>
                </div>
              ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <div className="rounded-3xl border border-border bg-background/70 p-4 lg:col-span-1">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Комментарий</div>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-foreground">{selectedItem.comment || "Комментарий не указан."}</p>
              </div>

              <div className="rounded-3xl border border-border bg-background/70 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Старое значение</div>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-muted-foreground">{prettyJson(selectedItem.old_value)}</pre>
              </div>

              <div className="rounded-3xl border border-border bg-background/70 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Новое значение</div>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-6 text-muted-foreground">{prettyJson(selectedItem.new_value)}</pre>
              </div>
            </div>
          </div>
        ) : null}
      </AdminModal>
    </PageMotion>
  );
}
