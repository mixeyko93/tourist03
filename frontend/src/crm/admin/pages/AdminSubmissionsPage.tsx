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
const PAGE_SIZE = 25;

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
  const [placeTypeFilter, setPlaceTypeFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [photosFilter, setPhotosFilter] = useState("");
  const [spamFilter, setSpamFilter] = useState("");
  const [dateFromFilter, setDateFromFilter] = useState("");
  const [dateToFilter, setDateToFilter] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [total, setTotal] = useState(0);
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
    fetchPlacementSubmissions({
      status: statusFilter,
      search,
      placeTypeId: placeTypeFilter,
      region: regionFilter,
      applicantRole: roleFilter,
      assignedAdminId: assigneeFilter,
      hasPhotos: photosFilter,
      spamRisk: spamFilter,
      dateFrom: dateFromFilter,
      dateTo: dateToFilter,
      limit: PAGE_SIZE,
      offset: pageIndex * PAGE_SIZE,
      signal: controller.signal,
    })
      .then((payload) => {
        setItems(payload.items);
        setTotal(payload.total);
        if (!selectedId || !payload.items.some((item) => item.id === selectedId)) {
          setSelectedId(payload.items[0]?.id ?? null);
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Не удалось загрузить заявки");
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [
    reloadKey,
    search,
    statusFilter,
    placeTypeFilter,
    regionFilter,
    roleFilter,
    assigneeFilter,
    photosFilter,
    spamFilter,
    dateFromFilter,
    dateToFilter,
    pageIndex,
    selectedId,
  ]);

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
    { label: "Всего по фильтру", value: total, Icon: ClipboardList },
    { label: "Новые", value: summary.new, Icon: FilePlus2 },
    { label: "В работе", value: summary.review, Icon: CheckCircle2 },
    { label: "Высокий spam risk", value: summary.risk, Icon: ShieldAlert },
  ];
  const resetPage = () => setPageIndex(0);

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
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Проверка данных заявителя, будущей карточки, медиа и истории. Одобрение сразу публикует объект на карте.</p>
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
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <label className="relative md:col-span-2"><span className="sr-only">Поиск заявок</span><Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input className="admin-input pl-10" value={search} onChange={(event) => { setSearch(event.target.value); resetPage(); }} placeholder="Номер, объект, регион или заявитель" /></label>
          <label><span className="sr-only">Статус</span><select className="admin-input" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); resetPage(); }}>
            <option value="">Все статусы</option>
            {Object.entries(STATUS_LABELS).filter(([key]) => key !== "draft").map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label>
          <label><span className="sr-only">Роль заявителя</span><select className="admin-input" value={roleFilter} onChange={(event) => { setRoleFilter(event.target.value); resetPage(); }}>
            <option value="">Все роли</option>
            {Object.entries(ROLE_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></label>
          <label><span className="sr-only">ID типа объекта</span><input className="admin-input" inputMode="numeric" value={placeTypeFilter} onChange={(event) => { setPlaceTypeFilter(event.target.value.replace(/\D/g, "")); resetPage(); }} placeholder="ID типа объекта" /></label>
          <label><span className="sr-only">Регион</span><input className="admin-input" value={regionFilter} onChange={(event) => { setRegionFilter(event.target.value); resetPage(); }} placeholder="Регион (точно)" /></label>
          <label><span className="sr-only">ID модератора</span><input className="admin-input" inputMode="numeric" value={assigneeFilter} onChange={(event) => { setAssigneeFilter(event.target.value.replace(/\D/g, "")); resetPage(); }} placeholder="ID модератора" /></label>
          <label><span className="sr-only">Наличие фото</span><select className="admin-input" value={photosFilter} onChange={(event) => { setPhotosFilter(event.target.value); resetPage(); }}><option value="">Фото: любые</option><option value="true">С фото</option><option value="false">Без фото</option></select></label>
          <label><span className="sr-only">Spam risk</span><select className="admin-input" value={spamFilter} onChange={(event) => { setSpamFilter(event.target.value); resetPage(); }}><option value="">Spam risk: любой</option><option value="high">Высокий</option><option value="normal">Обычный</option></select></label>
          <label className="space-y-1 text-xs text-muted-foreground">Создана с<input className="admin-input" type="date" value={dateFromFilter} onChange={(event) => { setDateFromFilter(event.target.value); resetPage(); }} /></label>
          <label className="space-y-1 text-xs text-muted-foreground">Создана по<input className="admin-input" type="date" value={dateToFilter} onChange={(event) => { setDateToFilter(event.target.value); resetPage(); }} /></label>
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
          {total > PAGE_SIZE ? <div className="flex items-center justify-between gap-2 p-2 text-xs text-muted-foreground"><button type="button" className="admin-button" disabled={pageIndex === 0} onClick={() => setPageIndex((value) => Math.max(0, value - 1))}>Назад</button><span>{pageIndex * PAGE_SIZE + 1}–{Math.min(total, (pageIndex + 1) * PAGE_SIZE)} из {total}</span><button type="button" className="admin-button" disabled={(pageIndex + 1) * PAGE_SIZE >= total} onClick={() => setPageIndex((value) => value + 1)}>Далее</button></div> : null}
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
                    {detail.status === "in_review" ? <button disabled={busy} className="admin-primary-button" onClick={() => perform(() => runPlacementSubmissionAction(detail.id, "approve", "approved", { contentVersion: detail.content_version }), "Заявка одобрена, объект опубликован на карте.")}>Одобрить и опубликовать</button> : null}
                    {["new", "in_review", "needs_clarification"].includes(detail.status) ? <button disabled={busy} className="admin-button text-rose-300" onClick={() => { const reason = publicComment("Укажите причину отклонения"); if (reason) void perform(() => runPlacementSubmissionAction(detail.id, "reject", "rejected", { contentVersion: detail.content_version, publicComment: reason }), "Заявка отклонена."); }}>Отклонить</button> : null}
                    {detail.status === "approved" ? <button disabled={busy} className="admin-primary-button gap-2" onClick={() => perform(() => createPlacementObjectDraft(detail.id, crypto.randomUUID()), "Объект опубликован на карте.")}><CheckCircle2 className="h-4 w-4" />Опубликовать объект</button> : null}
                    {["published", "rejected", "withdrawn"].includes(detail.status) ? <button disabled={busy} className="admin-button" onClick={() => perform(() => runPlacementSubmissionAction(detail.id, "archive", "archived", { contentVersion: detail.content_version }), "Заявка перенесена в архив.")}>Архивировать</button> : null}
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

                  <section className="rounded-3xl border border-border bg-card/80 p-5 sm:p-6">
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="text-lg font-semibold">Предпросмотр публичной карточки</h3>
                      <span className="rounded-full border border-border px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">{detail.status === "published" ? "Опубликовано" : "Не опубликовано"}</span>
                    </div>
                    <article className="mt-4 overflow-hidden rounded-[28px] bg-[#f5f7f2] text-[#17211b] shadow-inner">
                      <div className="grid gap-6 p-6 md:grid-cols-[minmax(0,1fr)_220px] md:p-8">
                        <div>
                          <div className="flex items-center gap-2 text-[10px] font-extrabold uppercase tracking-[0.18em] text-[#138f9f]">
                            <img src="/static/brand/turistika-icon.svg" alt="" className="h-8 w-8 rounded-xl" />
                            Туристика · будущая карточка
                          </div>
                          <h4 className="mt-6 text-3xl font-extrabold tracking-[-0.065em]">{editName || "Название объекта"}</h4>
                          <p className="mt-3 text-sm font-semibold leading-6 text-[#617067]">{editShortDescription || "Короткое описание появится здесь после проверки."}</p>
                          <p className="mt-5 text-xs font-bold text-[#138f9f]">{[editRegion, detail.city, detail.locality].filter(Boolean).map(String).join(" · ") || "География не указана"}</p>
                        </div>
                        <div className="rounded-3xl bg-[#17211b] p-5 text-white">
                          <p className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-[#7fdce5]">Контакты и детали</p>
                          <strong className="mt-4 block text-2xl">{(detail.public_contacts || []).length}</strong>
                          <span className="text-xs text-white/65">публичных контактов</span>
                          <strong className="mt-5 block text-2xl">{(detail.amenities || []).length}</strong>
                          <span className="text-xs text-white/65">удобств отмечено</span>
                        </div>
                      </div>
                    </article>
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

                  <section className="rounded-3xl border border-border bg-card/80 p-5">
                    <h3 className="text-lg font-semibold">Проверки и согласия</h3>
                    <dl className="mt-4 grid gap-3 text-sm">
                      <div><dt className="text-xs text-muted-foreground">Spam score</dt><dd>{detail.spam_score} / 100</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Источник</dt><dd>{String(detail.source || "—")}</dd></div>
                      <div><dt className="text-xs text-muted-foreground">Согласия</dt><dd><JsonList value={Object.entries(detail.consents || {}).map(([name, accepted]) => ({ name, accepted }))} empty="Не зафиксированы." /></dd></div>
                    </dl>
                  </section>

                  <section className="rounded-3xl border border-border bg-card/80 p-5">
                    <h3 className="text-lg font-semibold">Audit</h3>
                    <ol className="mt-4 space-y-3">{(detail.audit || []).length ? (detail.audit || []).map((item, index) => <li key={String(item.id || index)} className="border-l-2 border-border pl-3 text-xs"><strong>{String(item.action_label || item.action_type || "Событие")}</strong><p className="mt-1 text-muted-foreground">{String(item.actor_display || item.actor_type || "Система")}</p><time className="mt-1 block text-muted-foreground">{formatDate(item.created_at)}</time></li>) : <li className="text-xs text-muted-foreground">Событий audit пока нет.</li>}</ol>
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
