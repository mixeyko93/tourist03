import { ArrowDown, ArrowLeft, ArrowUp, Eye, GripVertical, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { crmPath } from "../../paths";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { discoveryAdminApi, type EditorialStatus, type RoutePoint, type TourismRoute } from "../discovery";

const emptyRoute: TourismRoute = {
  id: 0, slug: "", title: "", short_description: "", description: "", cover_url: "",
  route_type: "editorial", transport_mode: "mixed", duration_minutes: null, duration_text: "",
  distance_km: null, difficulty: null, season: "", region: "", city: "",
  start_lat: null, start_lng: null, end_lat: null, end_lng: null, geojson: null,
  status: "draft", editorial_weight: 0, editorial_exception: false,
  seo_title: "", seo_description: "", content_version: 1, points: [],
};

function move<T>(items: T[], from: number, to: number) {
  if (to < 0 || to >= items.length) return items;
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function nullableNumber(value: string) {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function RoutePreviewMap({ points }: { points: RoutePoint[] }) {
  const coordinates = points.filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lng));
  const plotted = useMemo(() => {
    if (!coordinates.length) return [];
    const lats = coordinates.map((point) => Number(point.lat));
    const lngs = coordinates.map((point) => Number(point.lng));
    const minLat = Math.min(...lats); const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs); const maxLng = Math.max(...lngs);
    return coordinates.map((point) => ({
      x: 24 + ((Number(point.lng) - minLng) / Math.max(.0001, maxLng - minLng)) * 352,
      y: 216 - ((Number(point.lat) - minLat) / Math.max(.0001, maxLat - minLat)) * 192,
    }));
  }, [coordinates]);
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-[#e1ebe0]">
      <svg viewBox="0 0 400 240" className="block w-full" role="img" aria-label="Схематичный предпросмотр точек маршрута">
        <path d="M0 50C100 10 160 90 250 55s100-10 150 10v175H0Z" fill="#ccddca" />
        {plotted.length > 1 ? <polyline points={plotted.map((point) => `${point.x},${point.y}`).join(" ")} fill="none" stroke="#167245" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" /> : null}
        {plotted.map((point, index) => <g key={`${point.x}-${point.y}-${index}`}><circle cx={point.x} cy={point.y} r="13" fill="#167245" stroke="white" strokeWidth="3" /><text x={point.x} y={point.y + 4} textAnchor="middle" fontSize="11" fontWeight="800" fill="white">{index + 1}</text></g>)}
      </svg>
      <p className="px-4 pb-4 text-xs text-muted-foreground">{plotted.length ? `${plotted.length} точек с координатами` : "Добавьте координаты для предпросмотра карты"}</p>
    </div>
  );
}

function RoutePoints({ points, onChange }: { points: RoutePoint[]; onChange: (points: RoutePoint[]) => void }) {
  const [dragged, setDragged] = useState<number | null>(null);
  const normalized = (next: RoutePoint[]) => onChange(next.map((point, position) => ({ ...point, position })));
  const update = (index: number, patch: Partial<RoutePoint>) => normalized(points.map((point, position) => position === index ? { ...point, ...patch } : point));
  return (
    <div className="space-y-3">
      <button className="admin-button gap-2" type="button" onClick={() => normalized([...points, { position: points.length, entity_id: null, custom_title: "", description: "", lat: null, lng: null, stay_minutes: null, overnight: false, transport_note: "" }])}><Plus className="h-4 w-4" />Добавить точку</button>
      {!points.length ? <p className="rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">Для публикации маршруту нужны минимум две точки.</p> : null}
      {points.map((point, index) => (
        <article
          key={index}
          draggable
          onDragStart={() => setDragged(index)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={() => { if (dragged !== null) normalized(move(points, dragged, index)); setDragged(null); }}
          className="grid gap-3 rounded-2xl border border-border bg-background/70 p-4 lg:grid-cols-[36px_minmax(0,1fr)_auto]"
        >
          <div className="flex flex-col items-center gap-1"><GripVertical className="h-5 w-5 cursor-grab text-muted-foreground" /><span className="grid h-7 w-7 place-items-center rounded-full bg-blue-500 text-xs font-bold text-white">{index + 1}</span></div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="grid gap-1 text-xs text-muted-foreground">ID карточки (необязательно)<input className="admin-input" type="number" min="1" value={point.entity_id || ""} onChange={(event) => update(index, { entity_id: nullableNumber(event.target.value) })} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground">Редакционное название<input className="admin-input" value={point.custom_title || ""} onChange={(event) => update(index, { custom_title: event.target.value })} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground md:col-span-2">Описание<textarea className="admin-input min-h-20" value={point.description || ""} onChange={(event) => update(index, { description: event.target.value })} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground">Широта<input className="admin-input" type="number" min="-90" max="90" step="any" value={point.lat ?? ""} onChange={(event) => update(index, { lat: nullableNumber(event.target.value) })} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground">Долгота<input className="admin-input" type="number" min="-180" max="180" step="any" value={point.lng ?? ""} onChange={(event) => update(index, { lng: nullableNumber(event.target.value) })} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground">Остановка, минут<input className="admin-input" type="number" min="0" value={point.stay_minutes ?? ""} onChange={(event) => update(index, { stay_minutes: nullableNumber(event.target.value) })} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground">Как добраться<input className="admin-input" value={point.transport_note || ""} onChange={(event) => update(index, { transport_note: event.target.value })} /></label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={point.overnight} onChange={(event) => update(index, { overnight: event.target.checked })} />Ночёвка</label>
          </div>
          <div className="flex gap-1 lg:flex-col">
            <button className="admin-button" type="button" aria-label="Поднять точку" onClick={() => normalized(move(points, index, index - 1))}><ArrowUp className="h-4 w-4" /></button>
            <button className="admin-button" type="button" aria-label="Опустить точку" onClick={() => normalized(move(points, index, index + 1))}><ArrowDown className="h-4 w-4" /></button>
            <button className="admin-button text-rose-300" type="button" aria-label="Удалить точку" onClick={() => normalized(points.filter((_, position) => position !== index))}><Trash2 className="h-4 w-4" /></button>
          </div>
        </article>
      ))}
    </div>
  );
}

export default function AdminRouteEditPage() {
  const params = useParams();
  const navigate = useNavigate();
  const id = params.id && params.id !== "new" ? Number(params.id) : null;
  const [draft, setDraft] = useState<TourismRoute>(emptyRoute);
  const [geojsonText, setGeojsonText] = useState("");
  const [loading, setLoading] = useState(Boolean(id));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    discoveryAdminApi.routes.detail(id, controller.signal)
      .then((payload) => { setDraft(payload); setGeojsonText(payload.geojson ? JSON.stringify(payload.geojson, null, 2) : ""); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Не удалось загрузить маршрут"))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [id]);

  function set<K extends keyof TourismRoute>(key: K, value: TourismRoute[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  const canPublish = draft.title.trim() && draft.slug.trim() && draft.short_description.trim() && draft.points.length >= 2;
  const seoTitle = draft.seo_title?.trim() || `${draft.title || "Новый маршрут"} — Туристика`;
  const seoDescription = draft.seo_description?.trim() || draft.short_description || "Редакционный маршрут Туристики.";

  async function save() {
    try {
      setSaving(true); setError(""); setMessage("");
      if (draft.status === "published" && !canPublish) throw new Error("Для публикации заполните обязательные поля и добавьте минимум две точки.");
      let geojson = null;
      if (geojsonText.trim()) geojson = JSON.parse(geojsonText);
      const payload = {
        ...draft,
        content_version: id ? draft.content_version : undefined,
        geojson,
        points: draft.points.map((point, position) => ({
          position, entity_id: point.entity_id || null, custom_title: point.custom_title || null,
          description: point.description || null, lat: point.lat ?? null, lng: point.lng ?? null,
          stay_minutes: point.stay_minutes ?? null, overnight: point.overnight,
          transport_note: point.transport_note || null,
        })),
      } as Omit<TourismRoute, "id" | "published_at" | "updated_at">;
      const saved = await discoveryAdminApi.routes.save(id, payload);
      setDraft(saved); setGeojsonText(saved.geojson ? JSON.stringify(saved.geojson, null, 2) : "");
      setMessage("Маршрут сохранён");
      if (!id) navigate(crmPath(`/admin/routes/${saved.id}`), { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось сохранить маршрут");
    } finally { setSaving(false); }
  }

  async function showPreview() {
    if (!id) { setError("Сначала сохраните черновик"); return; }
    try { setError(""); setPreview(await discoveryAdminApi.routes.preview(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Не удалось открыть предпросмотр"); }
  }

  const input = "admin-input";
  if (loading) return <div className="p-8 text-sm text-muted-foreground">Загружаем редактор маршрута…</div>;
  return (
    <PageMotion className="space-y-6" isReady>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div><button className="mb-3 flex items-center gap-2 text-sm text-muted-foreground" type="button" onClick={() => navigate(crmPath("/admin/routes"))}><ArrowLeft className="h-4 w-4" />К списку</button><p className="text-xs font-semibold uppercase tracking-[.2em] text-muted-foreground">Редактор маршрута</p><h2 className="text-3xl font-semibold tracking-[-.05em]">{draft.title || "Новый маршрут"}</h2></div>
        <div className="flex flex-wrap gap-2"><button className="admin-button gap-2" type="button" onClick={showPreview}><Eye className="h-4 w-4" />Предпросмотр</button><button className="admin-primary-button gap-2" type="button" disabled={saving} onClick={save}><Save className="h-4 w-4" />{saving ? "Сохраняем…" : "Сохранить"}</button></div>
      </div>
      {error ? <div role="alert" className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">{error}</div> : null}
      {message ? <div role="status" className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-300">{message}</div> : null}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <AdminCard className="space-y-4 p-5 sm:p-6">
            <h3 className="text-lg font-semibold">Основная информация</h3>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="grid gap-1 text-sm">Название<input className={input} value={draft.title} onChange={(event) => set("title", event.target.value)} /></label>
              <label className="grid gap-1 text-sm">Slug<input className={input} value={draft.slug} onChange={(event) => set("slug", event.target.value.toLowerCase().replace(/[^a-z0-9-]+/g, "-"))} /></label>
              <label className="grid gap-1 text-sm md:col-span-2">Краткое описание<textarea className={`${input} min-h-24`} maxLength={500} value={draft.short_description} onChange={(event) => set("short_description", event.target.value)} /></label>
              <label className="grid gap-1 text-sm md:col-span-2">Полное описание<textarea className={`${input} min-h-40`} value={draft.description || ""} onChange={(event) => set("description", event.target.value)} /></label>
              <label className="grid gap-1 text-sm">Обложка<input className={input} value={draft.cover_url || ""} onChange={(event) => set("cover_url", event.target.value)} /></label>
              <label className="grid gap-1 text-sm">Тип<select className={input} value={draft.route_type} onChange={(event) => set("route_type", event.target.value)}><option value="editorial">Редакционный</option><option value="walking">Пешеходный</option><option value="driving">Автомобильный</option><option value="cycling">Велосипедный</option><option value="water">Водный</option><option value="mixed">Смешанный</option></select></label>
              <label className="grid gap-1 text-sm">Передвижение<select className={input} value={draft.transport_mode} onChange={(event) => set("transport_mode", event.target.value)}><option value="walk">Пешком</option><option value="car">Автомобиль</option><option value="public_transport">Общественный транспорт</option><option value="bicycle">Велосипед</option><option value="boat">По воде</option><option value="mixed">Смешанный</option></select></label>
              <label className="grid gap-1 text-sm">Сложность<select className={input} value={draft.difficulty || ""} onChange={(event) => set("difficulty", event.target.value || null)}><option value="">Не указана</option><option value="easy">Лёгкая</option><option value="moderate">Средняя</option><option value="hard">Сложная</option></select></label>
              <label className="grid gap-1 text-sm">Длительность, минут<input className={input} type="number" min="1" value={draft.duration_minutes ?? ""} onChange={(event) => set("duration_minutes", nullableNumber(event.target.value))} /></label>
              <label className="grid gap-1 text-sm">Текст длительности<input className={input} value={draft.duration_text || ""} onChange={(event) => set("duration_text", event.target.value)} placeholder="2 дня" /></label>
              <label className="grid gap-1 text-sm">Расстояние, км<input className={input} type="number" min="0" step="0.1" value={draft.distance_km ?? ""} onChange={(event) => set("distance_km", nullableNumber(event.target.value))} /></label>
              {(["region", "city", "season"] as const).map((key) => <label key={key} className="grid gap-1 text-sm">{{region:"Регион",city:"Город",season:"Сезон"}[key]}<input className={input} value={draft[key] || ""} onChange={(event) => set(key, event.target.value)} /></label>)}
            </div>
          </AdminCard>
          <AdminCard className="space-y-4 p-5 sm:p-6"><div><h3 className="text-lg font-semibold">Точки маршрута</h3><p className="text-sm text-muted-foreground">Можно выбрать карточку каталога или создать редакционную точку. Перетаскивание и кнопки меняют порядок.</p></div><RoutePoints points={draft.points} onChange={(points) => set("points", points)} /></AdminCard>
          <AdminCard className="space-y-3 p-5 sm:p-6"><h3 className="text-lg font-semibold">GeoJSON линии</h3><p className="text-sm text-muted-foreground">Необязательный LineString/Feature. Размер и количество координат проверяются сервером.</p><textarea aria-label="GeoJSON линии маршрута" className={`${input} min-h-48 font-mono text-xs`} value={geojsonText} onChange={(event) => setGeojsonText(event.target.value)} /></AdminCard>
        </div>
        <aside className="space-y-6">
          <AdminCard className="space-y-4 p-5">
            <h3 className="font-semibold">Публикация</h3>
            <label className="grid gap-1 text-sm">Статус<select className={input} value={draft.status} onChange={(event) => set("status", event.target.value as EditorialStatus)}><option value="draft">Черновик</option><option value="in_review">На проверке</option><option value="published" disabled={!canPublish}>Опубликовано</option><option value="disabled">Скрыто</option><option value="archived">В архиве</option></select></label>
            <label className="grid gap-1 text-sm">Редакционный вес<input className={input} type="number" min="0" max="100" value={draft.editorial_weight} onChange={(event) => set("editorial_weight", Number(event.target.value))} /></label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.editorial_exception} onChange={(event) => set("editorial_exception", event.target.checked)} />Редакционное исключение</label>
            <p className="text-xs text-muted-foreground">Версия {draft.content_version}. Optimistic locking не позволит незаметно затереть чужую правку.</p>
          </AdminCard>
          <AdminCard className="space-y-3 p-5"><h3 className="font-semibold">Карта маршрута</h3><RoutePreviewMap points={draft.points} /></AdminCard>
          <AdminCard className="space-y-3 p-5">
            <h3 className="font-semibold">SEO-предпросмотр</h3>
            <label className="grid gap-1 text-sm">SEO title<input className={input} value={draft.seo_title || ""} onChange={(event) => set("seo_title", event.target.value)} /></label>
            <label className="grid gap-1 text-sm">SEO description<textarea className={`${input} min-h-24`} value={draft.seo_description || ""} onChange={(event) => set("seo_description", event.target.value)} /></label>
            <div className="rounded-xl border border-border bg-background/60 p-4"><p className="text-base font-medium text-blue-300">{seoTitle}</p><p className="text-xs text-emerald-300">turist03.ru/routes/{draft.slug || "slug"}</p><p className="mt-2 text-xs text-muted-foreground">{seoDescription}</p></div>
          </AdminCard>
          {preview ? <AdminCard className="space-y-2 p-5"><h3 className="font-semibold">Предпросмотр страницы</h3><p className="text-xs text-muted-foreground">{Array.isArray(preview.points) ? `${preview.points.length} точек` : "Предпросмотр готов"}</p><pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">{JSON.stringify(preview, null, 2)}</pre></AdminCard> : null}
        </aside>
      </div>
    </PageMotion>
  );
}
