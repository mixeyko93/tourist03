import { CheckCircle2, ClipboardList, ExternalLink, FilePlus2, MessageSquareText, RefreshCcw, Search, ShieldAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import {
  addPlacementSubmissionNote,
  changePlacementSubmissionStatus,
  createPlacementObjectDraft,
  fetchPlacementSubmission,
  fetchPlacementSubmissions,
  runPlacementSubmissionAction,
  updatePlacementSubmission,
  type PlacementSubmissionDetail,
  type PlacementSubmissionSummary,
} from "../session";

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  submitted: "Отправлена",
  new: "Новая",
  in_review: "В работе",
  needs_clarification: "Нужны уточнения",
  approved: "Одобрена",
  object_draft_created: "Создан черновик объекта",
  published: "Опубликована",
  rejected: "Отклонена",
  withdrawn: "Отозвана",
  archived: "Архивирована",
};

const ROLE_LABELS: Record<string, string> = {
  owner: "Собственник",
  representative: "Представитель",
  tourist: "Турист",
};

function formatDate(value?: unknown) {
  if (!value || typeof value !== "string") return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString("ru-RU");
}

function statusClass(status: string) {
  if (["approved", "object_draft_created", "published"].includes(status)) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (["rejected", "withdrawn"].includes(status)) return "border-rose-500/30 bg-rose-500/10 text-rose-300";
  if (status === "needs_clarification") return "border-amber-500/30 bg-amber-500/10 text-amber-300";
  return "border-blue-500/30 bg-blue-500/10 text-blue-300";
}

function SubmissionBadge({ status }: { status: string }) {
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusClass(status)}`}>{STATUS_LABELS[status] || status}</span>;
}

function JsonList({ value, empty = "Нет данных" }: { value: unknown; empty?: string }) {
  if (!Array.isArray(value) || !value.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <div className="grid gap-2">
      {value.map((item, index) => (
        <pre key={index} className="overflow-auto whitespace-pre-wrap rounded-xl border border-border bg-background/60 p-3 text-xs text-muted-foreground">
          {JSON.stringify(item, null, 2)}
        </pre>
      ))}
    </div>
  );
}

export default function AdminSubmissionsPage() {
  const [items, setItems] = useState<PlacementSubmissionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const value = Number(new URLSearchParams(window.location.search).get("submission") || 0);
    return value > 0 ? value : null;
  });
  const [detail, setDetail] = useState<PlacementSubmissionDetail | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [note, setNote] = useState("");
  const [notePublic, setNotePublic] = useState(false);
  const [editName, setEditName] = useState("");
  const [editRegion, setEditRegion] = useState("");
  const [editShortDescription, setEditShortDescription] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchPlacementSubmissions({ status: statusFilter, search, signal: controller.signal })
      .then((payload) => {
        setItems(payload.items);
        if (!selectedId && payload.items[0]) setSelectedId(payload.items[0].id);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Не удалось загрузить заявки");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reloadKey, search, statusFilter, selectedId]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    fetchPlacementSubmission(selectedId, controller.signal)
      .then((payload) => {
        setDetail(payload);
        setEditName(String(payload.place_name || ""));
        setEditRegion(String(payload.region || ""));
        setEditShortDescription(String(payload.short_description || ""));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Не удалось открыть заявку");
      })
      .finally(() => { if (!controller.signal.aborted) setDetailLoading(false); });
    return () => controller.abort();
  }, [selectedId, reloadKey]);

  const summary = useMemo(() => ({
    total: items.length,
    new: items.filter((item) => item.status === "new").length,
    review: items.filter((item) => item.status === "in_review").length,
    risk: items.filter((item) => item.spam_score >= 60).length,
  }), [items]);
  const summaryCards: Array<{ label: string; value: number; Icon: LucideIcon }> = [
    { label: "Всего в выдаче", value: summary.total, Icon: ClipboardList },
    { label: "Новые", value: summary.new, Icon: FilePlus2 },
    { label: "В работе", value: summary.review, Icon: CheckCircle2 },
    { label: "Высокий spam risk", value: summary.risk, Icon: ShieldAlert },
  ];

  async function perform(action: () => Promise<unknown>, success: string) {
    try {
      setBusy(true);
      setError("");
      setMessage("");
      await action();
      setMessage(success);
      setReloadKey((value) => value + 1);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Не удалось выполнить действие");
    } finally {
      setBusy(false);
    }
  }

  function publicComment(promptText: string) {
    return window.prompt(promptText, "")?.trim() || "";
  }

  return (
    <PageMotion className="space-y-6" isReady={!loading}>
      <section className="rounded-3xl border border-border bg-card/80 p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Этап 3.1</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.05em]">Заявки на размещение</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Проверка данных заявителя, будущей карточки, медиа и истории. Одобрение не публикует объект автоматически.</p>
          </div>
          <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}><RefreshCcw className="h-4 w-4" />Обновить</button>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {summaryCards.map(({ label, value, Icon }) => (
            <div key={label} className="rounded-2xl border border-border bg-background/60 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground"><Icon className="h-4 w-4" />{label}</div>
              <strong className="mt-2 block text-2xl">{value}</strong>
            </div>
          ))}
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-[minmax(0,1fr)_240px]">
          <label className="relative"><Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input className="admin-input pl-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Номер, объект, регион или заявитель" /></label>
          <select className="admin-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(STATUS_LABELS).filter(([key]) => key !== "draft").map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </div>
      </section>

      {error ? <div role="alert" className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div> : null}
      {message ? <div role="status" className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">{message}</div> : null}

      <div className="grid min-w-0 gap-5 xl:grid-cols-[390px_minmax(0,1fr)]">
        <aside className="max-h-[calc(100vh-210px)] space-y-2 overflow-auto rounded-3xl border border-border bg-card/70 p-3 xl:sticky xl:top-6">
          {loading ? <p className="p-5 text-sm text-muted-foreground">Загружаем заявки…</p> : items.length ? items.map((item) => (
            <button key={item.id} type="button" onClick={() => setSelectedId(item.id)} className={`w-full rounded-2xl border p-4 text-left transition ${selectedId === item.id ? "border-blue-500/60 bg-blue-500/10" : "border-border bg-background/55 hover:bg-accent"}`}>
              <div className="flex items-start justify-between gap-3"><strong className="text-sm">{item.public_number}</strong><SubmissionBadge status={item.status} /></div>
              <h3 className="mt-3 font-semibold">{item.place_name || "Без названия"}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{item.place_type_name || "Тип не указан"} · {item.region || "Регион не указан"}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground"><span>{ROLE_LABELS[item.applicant_role || ""] || "Роль не указана"}</span><span>Фото: {item.media_count}</span><span className={item.spam_score >= 60 ? "text-rose-300" : ""}>Spam: {item.spam_score}</span></div>
            </button>
          )) : <p className="p-5 text-sm text-muted-foreground">Заявок по фильтру нет.</p>}
        </aside>

        <section className="min-w-0">
          {detailLoading ? <div className="rounded-3xl border border-border bg-card/70 p-8 text-sm text-muted-foreground">Открываем заявку…</div> : detail ? (
            <div className="space-y-5">
              <div className="rounded-3xl border border-border bg-card/80 p-5 sm:p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div><div className="flex flex-wrap items-center gap-3"><h2 className="text-2xl font-semibold tracking-[-0.04em]">{detail.public_number}</h2><SubmissionBadge status={detail.status} /></div><p className="mt-2 text-sm text-muted-foreground">Создана {formatDate(detail.created_at)} · версия {detail.content_version}</p></div>
                  <div className="flex flex-wrap gap-2">
                    {detail.status === "new" ? <button disabled={busy} className="admin-primary-button" onClick={() => perform(() => changePlacementSubmissionStatus(detail.id, "in_review", { contentVersion: detail.content_version }), "Заявка взята в работу.")}>Взять в работу</button> : null}
                    {detail.status === "in_review" ? <button disabled={busy} className="admin-button" onClick={() => { const comment = publicComment("Что нужно уточнить?"); if (comment) void perform(() => runPlacementSubmissionAction(detail.id, "request-clarification", "needs_clarification", { contentVersion: detail.content_version, publicComment: comment }), "Запрос уточнений сохранён."); }}>Запросить уточнение</button> : null}
                    {["in_review", "needs_clarification"].includes(detail.status) ? <button disabled={busy} className="admin-primary-button" onClick={() => perform(() => runPlacementSubmissionAction(detail.id, "approve", "approved", { contentVersion: detail.content_version }), "Заявка одобрена. Объект ещё не опубликован.")}>Одобрить</button> : null}
                    {["new", "in_review", "needs_clarification"].includes(detail.status) ? <button disabled={busy} className="admin-button text-rose-300" onClick={() => { const reason = publicComment("Укажите причину отклонения"); if (reason) void perform(() => runPlacementSubmissionAction(detail.id, "reject", "rejected", { contentVersion: detail.content_version, publicComment: reason }), "Заявка отклонена."); }}>Отклонить</button> : null}
                    {detail.status === "approved" ? <button disabled={busy} className="admin-primary-button gap-2" onClick={() => perform(() => createPlacementObjectDraft(detail.id, crypto.randomUUID()), "Создан безопасный черновик объекта.")}><FilePlus2 className="h-4 w-4" />Создать черновик объекта</button> : null}
                    {detail.published_camp_id ? <a className="admin-button gap-2" href={`/admin/bases/${detail.published_camp_id}`}><ExternalLink className="h-4 w-4" />Открыть объект</a> : null}
                  </div>
                </div>
              </div>

              <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,.8fr)]">
                <div className="space-y-5">
                  <section className="rounded-3xl border border-border bg-card/80 p-5 sm:p-6">
                    <h3 className="text-lg font-semibold">Данные будущей карточки</h3>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <label className="space-y-2 text-xs font-semibold text-muted-foreground">Название<input className="admin-input" value={editName} onChange={(event) => setEditName(event.target.value)} /></label>
                      <label className="space-y-2 text-xs font-semibold text-muted-foreground">Регион<input className="admin-input" value={editRegion} onChange={(event) => setEditRegion(event.target.value)} /></label>
                      <label className="space-y-2 text-xs font-semibold text-muted-foreground sm:col-span-2">Короткое описание<textarea className="admin-input min-h-28 py-3" value={editShortDescription} onChange={(event) => setEditShortDescription(event.target.value)} /></label>
                    </div>
                    <button disabled={busy} className="admin-primary-button mt-4" onClick={() => perform(() => updatePlacementSubmission(detail.id, { content_version:detail.content_version, place_name:editName, region:editRegion, short_description:editShortDescription }), "Изменения заявки сохранены.")}>Сохранить изменения</button>
                    <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
                      <div><dt className="text-xs text-muted-foreground">Тип</dt><dd>{String(detail.place_type_name || "—")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Адрес</dt><dd>{String(detail.address || "—")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Город / населённый пункт</dt><dd>{String(detail.city || detail.locality || "—")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Координаты</dt><dd>{detail.lat != null && detail.lng != null ? `${detail.lat}, ${detail.lng}` : "—"}</dd></div>
                    </dl>
                  </section>

                  <section className="rounded-3xl border border-border bg-card/80 p-5 sm:p-6">
                    <h3 className="text-lg font-semibold">Фото</h3>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      {(detail.media || []).length ? (detail.media || []).map((media, index) => <figure key={String(media.id || index)} className="overflow-hidden rounded-2xl border border-border bg-background/60"><img src={String(media.public_preview_url || "")} alt="" className="aspect-[4/3] w-full object-cover" /><figcaption className="p-2 text-[10px] text-muted-foreground">{String(media.scope || "place")} · {media.is_cover ? "обложка" : `№${index + 1}`}</figcaption></figure>) : <p className="text-sm text-muted-foreground">Фото не загружены.</p>}
                    </div>
                  </section>

                  <section className="rounded-3xl border border-border bg-card/80 p-5 sm:p-6"><h3 className="text-lg font-semibold">Варианты размещения</h3><div className="mt-4"><JsonList value={detail.rooms_payload} empty="Варианты не добавлены." /></div></section>
                  <section className="rounded-3xl border border-border bg-card/80 p-5 sm:p-6"><h3 className="text-lg font-semibold">Удобства и видео</h3><div className="mt-4 grid gap-5 lg:grid-cols-2"><JsonList value={detail.amenities} empty="Удобства не выбраны." /><JsonList value={detail.video_urls} empty="Видео не добавлены." /></div></section>
                </div>

                <aside className="space-y-5">
                  <section className="rounded-3xl border border-border bg-card/80 p-5">
                    <h3 className="text-lg font-semibold">Заявитель</h3>
                    <dl className="mt-4 grid gap-3 text-sm">
                      <div><dt className="text-xs text-muted-foreground">Роль</dt><dd>{ROLE_LABELS[String(detail.applicant_role || "")] || "—"}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Имя</dt><dd>{String(detail.applicant_name || "—")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Телефон</dt><dd>{String(detail.applicant_phone || "—")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Email</dt><dd>{String(detail.applicant_email || "—")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Мессенджеры</dt><dd>{[detail.applicant_telegram,detail.applicant_whatsapp,detail.applicant_max].filter(Boolean).map(String).join(" · ") || "—"}</dd></div>
                    </dl>
                    <div className="mt-5 border-t border-border pt-4"><h4 className="text-sm font-semibold">Публичные контакты</h4><div className="mt-3"><JsonList value={detail.public_contacts} empty="Не указаны." /></div></div>
                  </section>

                  <section className="rounded-3xl border border-border bg-card/80 p-5">
                    <div className="flex items-center gap-2"><MessageSquareText className="h-4 w-4" /><h3 className="text-lg font-semibold">Заметки</h3></div>
                    <textarea className="admin-input mt-4 min-h-24 py-3" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Внутренняя заметка модератора" />
                    <label className="mt-3 flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={notePublic} onChange={(event) => setNotePublic(event.target.checked)} />Видна заявителю</label>
                    <button disabled={busy || !note.trim()} className="admin-button mt-3" onClick={() => perform(async () => { await addPlacementSubmissionNote(detail.id, note.trim(), notePublic); setNote(""); }, "Заметка добавлена.")}>Добавить заметку</button>
                    <div className="mt-4 space-y-2">{(detail.notes || []).map((item, index) => <div key={String(item.id || index)} className="rounded-xl border border-border bg-background/60 p-3 text-xs"><p className="whitespace-pre-wrap">{String(item.text || "")}</p><span className="mt-2 block text-muted-foreground">{formatDate(item.created_at)} · {item.is_visible_to_applicant ? "видна заявителю" : "внутренняя"}</span></div>)}</div>
                  </section>

                  <section className="rounded-3xl border border-border bg-card/80 p-5">
                    <h3 className="text-lg font-semibold">История статусов</h3>
                    <ol className="mt-4 space-y-3">{(detail.history || []).map((item, index) => <li key={String(item.id || index)} className="border-l-2 border-blue-500/40 pl-3 text-xs"><strong>{STATUS_LABELS[String(item.new_status || "")] || String(item.new_status || "")}</strong><p className="mt-1 text-muted-foreground">{String(item.public_comment || item.internal_comment || "")}</p><time className="mt-1 block text-muted-foreground">{formatDate(item.created_at)}</time></li>)}</ol>
                  </section>
                </aside>
              </div>
            </div>
          ) : <div className="rounded-3xl border border-dashed border-border bg-card/50 p-10 text-center text-sm text-muted-foreground">Выберите заявку слева.</div>}
        </section>
      </div>
    </PageMotion>
  );
}
