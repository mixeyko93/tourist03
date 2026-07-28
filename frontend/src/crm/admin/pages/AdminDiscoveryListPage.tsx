import { ExternalLink, Plus, RefreshCcw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { crmPath } from "../../paths";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { AdminCard } from "../components/AdminCard";
import { discoveryAdminApi, type EditorialCollection, type TourismRoute } from "../discovery";

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  in_review: "На проверке",
  published: "Опубликовано",
  disabled: "Скрыто",
  archived: "В архиве",
};

type Kind = "collections" | "routes";
type Item = EditorialCollection | TourismRoute;

export function AdminDiscoveryListPage({ kind }: { kind: Kind }) {
  const navigate = useNavigate();
  const [items, setItems] = useState<Item[]>([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const labels = kind === "collections"
    ? { eyebrow: "Редакционный контент", title: "Подборки", description: "Ручные, сезонные и динамические подборки опубликованных карточек.", create: "Создать подборку" }
    : { eyebrow: "Планирование путешествий", title: "Маршруты", description: "Редакционные маршруты с последовательностью точек, координатами и предпросмотром.", create: "Создать маршрут" };

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    discoveryAdminApi[kind].list({ search, status }, controller.signal)
      .then((payload) => setItems(payload))
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Не удалось загрузить материалы");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [kind, reload, search, status]);

  const counts = useMemo(() => ({
    total: items.length,
    published: items.filter((item) => item.status === "published").length,
    drafts: items.filter((item) => item.status === "draft" || item.status === "in_review").length,
  }), [items]);
  const { isPageVisible } = usePageLoadState(loading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-5 border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{labels.eyebrow}</p>
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">{labels.title}</h2>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{labels.description}</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <button className="admin-button gap-2" type="button" onClick={() => setReload((value) => value + 1)}><RefreshCcw className="h-4 w-4" />Обновить</button>
              <button className="admin-primary-button gap-2" type="button" onClick={() => navigate(crmPath(`/admin/${kind}/new`))}><Plus className="h-4 w-4" />{labels.create}</button>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {[["Всего", counts.total], ["Опубликовано", counts.published], ["Требуют внимания", counts.drafts]].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-border bg-background/65 px-4 py-3"><p className="text-xs text-muted-foreground">{label}</p><strong className="mt-1 block text-2xl">{value}</strong></div>
            ))}
          </div>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
            <label className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input className="admin-input pl-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по названию или slug" aria-label={`Поиск: ${labels.title.toLowerCase()}`} />
            </label>
            <select className="admin-input" value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Статус публикации">
              <option value="">Все статусы</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>
        {error ? <div className="m-5 rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">{error}</div> : null}
        <div className="grid gap-3 p-5 sm:p-6">
          {!loading && !items.length ? <div className="rounded-2xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">Материалов по выбранным условиям пока нет.</div> : null}
          {items.map((item) => {
            const detailCount = kind === "collections" ? (item as EditorialCollection).items.length : (item as TourismRoute).points.length;
            const publicHref = kind === "collections" ? `/collections/${item.slug}` : `/routes/${item.slug}`;
            return (
              <article key={item.id} className="grid gap-4 rounded-2xl border border-border bg-background/65 p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2"><h3 className="text-base font-semibold">{item.title}</h3><span className="rounded-full border border-border px-2 py-1 text-[11px] text-muted-foreground">{STATUS_LABELS[item.status] || item.status}</span></div>
                  <p className="mt-1 truncate text-sm text-muted-foreground">{item.short_description}</p>
                  <p className="mt-2 text-xs text-muted-foreground">/{item.slug} · {detailCount} {kind === "collections" ? "элементов" : "точек"} · версия {item.content_version}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {item.status === "published" ? <a className="admin-button gap-2" href={publicHref} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />Публичная страница</a> : null}
                  <button className="admin-primary-button" type="button" onClick={() => navigate(crmPath(`/admin/${kind}/${item.id}`))}>Редактировать</button>
                </div>
              </article>
            );
          })}
        </div>
      </AdminCard>
    </PageMotion>
  );
}
