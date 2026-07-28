import { ArrowDown, ArrowLeft, ArrowUp, Eye, GripVertical, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { crmPath } from "../../paths";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { discoveryAdminApi, type CollectionItem, type CollectionRule, type EditorialCollection, type EditorialStatus } from "../discovery";

const emptyCollection: EditorialCollection = {
  id: 0, slug: "", title: "", short_description: "", description: "", cover_url: "",
  collection_type: "manual", status: "draft", region: "", city: "", season: "", audience: "",
  editorial_weight: 0, editorial_exception: false, seo_title: "", seo_description: "",
  content_version: 1, items: [], rules: [],
};

function move<T>(items: T[], from: number, to: number) {
  if (to < 0 || to >= items.length) return items;
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item);
  return next;
}

function CollectionItems({ items, onChange }: { items: CollectionItem[]; onChange: (items: CollectionItem[]) => void }) {
  const [entityId, setEntityId] = useState("");
  const [dragged, setDragged] = useState<number | null>(null);
  const normalized = (next: CollectionItem[]) => onChange(next.map((item, position) => ({ ...item, position })));
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <input className="admin-input" type="number" min="1" value={entityId} onChange={(event) => setEntityId(event.target.value)} placeholder="ID карточки каталога" aria-label="ID добавляемой карточки" />
        <button className="admin-button gap-2" type="button" onClick={() => {
          const id = Number(entityId);
          if (!Number.isInteger(id) || id < 1 || items.some((item) => item.entity_id === id)) return;
          normalized([...items, { entity_id: id, position: items.length, editorial_note: "", custom_title: "", custom_description: "" }]);
          setEntityId("");
        }}><Plus className="h-4 w-4" />Прикрепить</button>
      </div>
      {!items.length ? <p className="rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">Добавьте карточки по их ID. Пустую ручную подборку опубликовать нельзя.</p> : null}
      {items.map((item, index) => (
        <article
          key={`${item.entity_id}-${index}`}
          draggable
          onDragStart={() => setDragged(index)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={() => { if (dragged !== null) normalized(move(items, dragged, index)); setDragged(null); }}
          className="grid gap-3 rounded-2xl border border-border bg-background/70 p-4 lg:grid-cols-[36px_110px_minmax(0,1fr)_auto]"
        >
          <GripVertical className="mt-3 h-5 w-5 cursor-grab text-muted-foreground" aria-hidden="true" />
          <label className="grid gap-1 text-xs text-muted-foreground">Карточка<input className="admin-input" value={item.entity_id} readOnly /></label>
          <div className="grid gap-2 md:grid-cols-2">
            <label className="grid gap-1 text-xs text-muted-foreground">Редакционный заголовок<input className="admin-input" value={item.custom_title || ""} onChange={(event) => normalized(items.map((value, position) => position === index ? { ...value, custom_title: event.target.value } : value))} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground">Заметка редактора<input className="admin-input" value={item.editorial_note || ""} onChange={(event) => normalized(items.map((value, position) => position === index ? { ...value, editorial_note: event.target.value } : value))} /></label>
            <label className="grid gap-1 text-xs text-muted-foreground md:col-span-2">Описание<textarea className="admin-input min-h-20" value={item.custom_description || ""} onChange={(event) => normalized(items.map((value, position) => position === index ? { ...value, custom_description: event.target.value } : value))} /></label>
          </div>
          <div className="flex gap-1 lg:flex-col">
            <button className="admin-button" type="button" aria-label="Поднять элемент" onClick={() => normalized(move(items, index, index - 1))}><ArrowUp className="h-4 w-4" /></button>
            <button className="admin-button" type="button" aria-label="Опустить элемент" onClick={() => normalized(move(items, index, index + 1))}><ArrowDown className="h-4 w-4" /></button>
            <button className="admin-button text-rose-300" type="button" aria-label="Удалить элемент" onClick={() => normalized(items.filter((_, position) => position !== index))}><Trash2 className="h-4 w-4" /></button>
          </div>
        </article>
      ))}
    </div>
  );
}

export default function AdminCollectionEditPage() {
  const params = useParams();
  const navigate = useNavigate();
  const id = params.id && params.id !== "new" ? Number(params.id) : null;
  const [draft, setDraft] = useState<EditorialCollection>(emptyCollection);
  const [rulesText, setRulesText] = useState("[]");
  const [loading, setLoading] = useState(Boolean(id));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    discoveryAdminApi.collections.detail(id, controller.signal)
      .then((payload) => { setDraft(payload); setRulesText(JSON.stringify(payload.rules || [], null, 2)); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Не удалось загрузить подборку"))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [id]);

  const seoTitle = draft.seo_title?.trim() || `${draft.title || "Новая подборка"} — Туристика`;
  const seoDescription = draft.seo_description?.trim() || draft.short_description || "Редакционная подборка Туристики.";
  const canPublish = draft.title.trim() && draft.slug.trim() && draft.short_description.trim()
    && (draft.collection_type !== "manual" || draft.items.length > 0)
    && (draft.collection_type !== "rule_based" || draft.rules.length > 0);

  function set<K extends keyof EditorialCollection>(key: K, value: EditorialCollection[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function parseRules(): CollectionRule[] {
    const parsed = JSON.parse(rulesText);
    if (!Array.isArray(parsed)) throw new Error("Правила должны быть JSON-массивом");
    return parsed.map((rule, index) => ({
      conditions: typeof rule.conditions === "object" && rule.conditions ? rule.conditions : {},
      sort: ["editorial", "newest", "name"].includes(rule.sort) ? rule.sort : "editorial",
      limit: Math.min(200, Math.max(1, Number(rule.limit || 24))),
      position: index,
    }));
  }

  async function save() {
    try {
      setSaving(true); setError(""); setMessage("");
      const rules = parseRules();
      if (draft.status === "published" && !canPublish) throw new Error("Для публикации заполните обязательные поля и добавьте элементы или правила.");
      const payload = {
        ...draft,
        content_version: id ? draft.content_version : undefined,
        items: draft.items.map((item, position) => ({
          entity_id: item.entity_id, position, editorial_note: item.editorial_note || null,
          custom_title: item.custom_title || null, custom_description: item.custom_description || null,
        })),
        rules,
      } as Omit<EditorialCollection, "id" | "published_at" | "updated_at">;
      const saved = await discoveryAdminApi.collections.save(id, payload);
      setDraft(saved); setRulesText(JSON.stringify(saved.rules || [], null, 2));
      setMessage("Подборка сохранена");
      if (!id) navigate(crmPath(`/admin/collections/${saved.id}`), { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось сохранить подборку");
    } finally { setSaving(false); }
  }

  async function showPreview() {
    if (!id) { setError("Сначала сохраните черновик"); return; }
    try { setError(""); setPreview(await discoveryAdminApi.collections.preview(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Не удалось открыть предпросмотр"); }
  }

  const input = "admin-input";
  if (loading) return <div className="p-8 text-sm text-muted-foreground">Загружаем редактор подборки…</div>;
  return (
    <PageMotion className="space-y-6" isReady>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div><button className="mb-3 flex items-center gap-2 text-sm text-muted-foreground" type="button" onClick={() => navigate(crmPath("/admin/collections"))}><ArrowLeft className="h-4 w-4" />К списку</button><p className="text-xs font-semibold uppercase tracking-[.2em] text-muted-foreground">Редактор подборки</p><h2 className="text-3xl font-semibold tracking-[-.05em]">{draft.title || "Новая подборка"}</h2></div>
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
              <label className="grid gap-1 text-sm">Обложка<input className={input} value={draft.cover_url || ""} onChange={(event) => set("cover_url", event.target.value)} placeholder="/static/uploads/…" /></label>
              <label className="grid gap-1 text-sm">Тип<select className={input} value={draft.collection_type} onChange={(event) => set("collection_type", event.target.value as EditorialCollection["collection_type"])}><option value="manual">Ручная</option><option value="rule_based">По правилам</option><option value="mixed">Смешанная</option></select></label>
              {(["region", "city", "season", "audience"] as const).map((key) => <label key={key} className="grid gap-1 text-sm">{{region:"Регион",city:"Город",season:"Сезон",audience:"Аудитория"}[key]}<input className={input} value={draft[key] || ""} onChange={(event) => set(key, event.target.value)} /></label>)}
            </div>
          </AdminCard>
          {draft.collection_type !== "rule_based" ? <AdminCard className="space-y-4 p-5 sm:p-6"><div><h3 className="text-lg font-semibold">Карточки в подборке</h3><p className="text-sm text-muted-foreground">Перетаскивайте строки или используйте кнопки для доступной клавиатурной сортировки.</p></div><CollectionItems items={draft.items} onChange={(items) => set("items", items)} /></AdminCard> : null}
          {draft.collection_type !== "manual" ? <AdminCard className="space-y-3 p-5 sm:p-6"><h3 className="text-lg font-semibold">Правила наполнения</h3><p className="text-sm text-muted-foreground">Versioned allowlist DSL: conditions, sort, limit. Результат проверяется сервером.</p><textarea className={`${input} min-h-64 font-mono text-xs`} value={rulesText} onChange={(event) => setRulesText(event.target.value)} onBlur={() => { try { const rules = parseRules(); set("rules", rules); setRulesText(JSON.stringify(rules, null, 2)); } catch {} }} /></AdminCard> : null}
        </div>
        <aside className="space-y-6">
          <AdminCard className="space-y-4 p-5">
            <h3 className="font-semibold">Публикация</h3>
            <label className="grid gap-1 text-sm">Статус<select className={input} value={draft.status} onChange={(event) => set("status", event.target.value as EditorialStatus)}><option value="draft">Черновик</option><option value="in_review">На проверке</option><option value="published" disabled={!canPublish}>Опубликовано</option><option value="disabled">Скрыто</option><option value="archived">В архиве</option></select></label>
            <label className="grid gap-1 text-sm">Редакционный вес<input className={input} type="number" min="0" max="100" value={draft.editorial_weight} onChange={(event) => set("editorial_weight", Number(event.target.value))} /></label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.editorial_exception} onChange={(event) => set("editorial_exception", event.target.checked)} />Редакционное исключение</label>
            <p className="text-xs text-muted-foreground">Версия {draft.content_version}. Optimistic locking защищает от перезаписи параллельных изменений.</p>
          </AdminCard>
          <AdminCard className="space-y-3 p-5">
            <h3 className="font-semibold">SEO-предпросмотр</h3>
            <label className="grid gap-1 text-sm">SEO title<input className={input} value={draft.seo_title || ""} onChange={(event) => set("seo_title", event.target.value)} /></label>
            <label className="grid gap-1 text-sm">SEO description<textarea className={`${input} min-h-24`} value={draft.seo_description || ""} onChange={(event) => set("seo_description", event.target.value)} /></label>
            <div className="rounded-xl border border-border bg-background/60 p-4"><p className="text-base font-medium text-blue-300">{seoTitle}</p><p className="text-xs text-emerald-300">turist03.ru/collections/{draft.slug || "slug"}</p><p className="mt-2 text-xs text-muted-foreground">{seoDescription}</p></div>
          </AdminCard>
          {preview ? <AdminCard className="space-y-2 p-5"><h3 className="font-semibold">Результат правил</h3><p className="text-xs text-muted-foreground">{Array.isArray(preview.items) ? `${preview.items.length} карточек в предпросмотре` : "Предпросмотр готов"}</p><pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">{JSON.stringify(preview, null, 2)}</pre></AdminCard> : null}
        </aside>
      </div>
    </PageMotion>
  );
}
