import { Send, X } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useBlocker } from "react-router";

import { ownerApi, type ChangeDiff, type OwnerChange } from "./api";
import { OwnerRouteLoading } from "./components";

const DiffViewer = lazy(() => import("./DiffViewer").then((module) => ({ default: module.DiffViewer })));
const OwnerMediaEditor = lazy(() => import("./OwnerMediaEditor"));

type DetailData = {
  camp: Record<string, unknown>;
  amenity_catalog: Array<{ id: number; name: string; category: string }>;
};

export default function OwnerEditor({
  detail,
  initialChange,
  onChange,
  onSubmitted,
  onMessage,
  onError,
}: {
  detail: DetailData;
  initialChange: OwnerChange;
  onChange: (change: OwnerChange) => void;
  onSubmitted: () => void;
  onMessage: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [change, setChange] = useState(initialChange);
  const [proposal, setProposal] = useState<Record<string, unknown>>(initialChange.proposed_payload || {});
  const savedProposal = useRef(JSON.stringify(initialChange.proposed_payload || {}));
  const dirty = JSON.stringify(proposal) !== savedProposal.current;
  const blocker = useBlocker(dirty);

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm("Есть несохранённые изменения. Покинуть редактор?")) blocker.proceed();
    else blocker.reset();
  }, [blocker]);

  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  const diff = useMemo<ChangeDiff[]>(() => {
    const items = change.diff_payload?.length
      ? [...change.diff_payload]
      : Object.entries(proposal)
        .filter(([key, value]) => detail.camp[key] !== value)
        .map(([field, after]) => ({
          field,
          label: { name: "Название", short_description: "Краткое описание", description: "Описание", min_price: "Минимальная цена", seasonality: "Сезонность", working_hours: "Режим работы", surroundings: "Окрестности", contacts: "Контакты", amenities: "Удобства", rooms: "Варианты размещения", video_urls: "Видео", request_publication: "Повторная публикация" }[field] || field,
          before: detail.camp[field],
          after,
        }));
    if (change.staged_media?.length && !items.some((item) => item.field === "media")) {
      const added = change.staged_media.filter((item) => item.action !== "remove").length;
      const removed = change.staged_media.filter((item) => item.action === "remove").length;
      items.push({
        field: "media",
        label: "Фото",
        before: removed ? `Будет удалено: ${removed}` : "Без удалений",
        after: added ? `Будет добавлено: ${added}` : "Без новых фотографий",
      });
    }
    return items;
  }, [change, detail.camp, proposal]);

  function updateChange(next: OwnerChange) {
    setChange(next);
    onChange(next);
  }

  function currentList<T>(key: string): T[] {
    const value = proposal[key] ?? detail.camp[key];
    return Array.isArray(value) ? value as T[] : [];
  }

  function updateContact(contactType: string, value: string) {
    const contacts = currentList<Record<string, unknown>>("contacts").filter((item) => String(item.contact_type) !== contactType);
    if (value.trim()) {
      contacts.push({
        contact_type: contactType,
        label: { phone: "Телефон", telegram: "Telegram", whatsapp: "WhatsApp", max: "MAX" }[contactType],
        value: value.trim(),
        is_public: true,
        sort_order: contacts.length * 10,
      });
    }
    setProposal({ ...proposal, contacts });
  }

  function contactValue(contactType: string) {
    return String(currentList<Record<string, unknown>>("contacts").find((item) => String(item.contact_type) === contactType)?.value || "");
  }

  function toggleAmenity(amenityId: number) {
    const amenities = currentList<Record<string, unknown>>("amenities");
    const present = amenities.some((item) => Number(item.amenity_id) === amenityId);
    setProposal({
      ...proposal,
      amenities: present
        ? amenities.filter((item) => Number(item.amenity_id) !== amenityId)
        : [...amenities, { amenity_id: amenityId, value: null }],
    });
  }

  function updateRoom(index: number, key: string, value: unknown) {
    const rooms = currentList<Record<string, unknown>>("rooms").map((room) => ({ ...room }));
    rooms[index] = { ...rooms[index], [key]: value };
    setProposal({ ...proposal, rooms });
  }

  async function saveAndPreview() {
    try {
      const result = await ownerApi.saveChange(change.id, change.content_version, proposal);
      updateChange(result.change);
      savedProposal.current = JSON.stringify(proposal);
      onMessage("Черновик сохранён. Проверьте сравнение перед отправкой.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Не удалось сохранить");
    }
  }

  async function submit() {
    try {
      const result = await ownerApi.submitChange(change.id);
      updateChange(result.change);
      savedProposal.current = JSON.stringify(proposal);
      onMessage("Изменения отправлены на проверку");
      onSubmitted();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Не удалось отправить");
    }
  }

  return (
    <div className="owner-editor-grid">
      <section className="owner-card owner-editor">
        <div className="owner-section-heading"><div><p className="owner-eyebrow">Редактор</p><h2>Данные карточки</h2></div></div>
        {[["name", "Название"], ["short_description", "Краткое описание"], ["seasonality", "Сезонность"], ["working_hours", "Режим работы"], ["surroundings", "Описание окрестностей"]].map(([key, label]) => <label key={key}>{label}<input value={String(proposal[key] ?? detail.camp[key] ?? "")} onChange={(event) => setProposal({ ...proposal, [key]: event.target.value })} /></label>)}
        <label>Подробное описание<textarea rows={8} value={String(proposal.description ?? detail.camp.description ?? "")} onChange={(event) => setProposal({ ...proposal, description: event.target.value })} /></label>
        <label>Минимальная цена<input type="number" min="0" value={String(proposal.min_price ?? detail.camp.min_price ?? "")} onChange={(event) => setProposal({ ...proposal, min_price: event.target.value ? Number(event.target.value) : null })} /></label>
        <fieldset className="owner-editor-section">
          <legend>Публичные контакты</legend>
          <label>Телефон<input placeholder="+7 999 000-00-00" value={contactValue("phone")} onChange={(event) => updateContact("phone", event.target.value)} /></label>
          <label>Telegram<input placeholder="https://t.me/..." value={contactValue("telegram")} onChange={(event) => updateContact("telegram", event.target.value)} /></label>
          <label>WhatsApp<input placeholder="https://wa.me/..." value={contactValue("whatsapp")} onChange={(event) => updateContact("whatsapp", event.target.value)} /></label>
          <label>MAX<input placeholder="https://max.ru/..." value={contactValue("max")} onChange={(event) => updateContact("max", event.target.value)} /></label>
        </fieldset>
        <fieldset className="owner-editor-section">
          <legend>Удобства</legend>
          <div className="owner-amenity-grid">{detail.amenity_catalog.map((amenity) => {
            const checked = currentList<Record<string, unknown>>("amenities").some((item) => Number(item.amenity_id) === amenity.id);
            return <label key={amenity.id} className={checked ? "selected" : ""}><input type="checkbox" checked={checked} onChange={() => toggleAmenity(amenity.id)} />{amenity.name}</label>;
          })}</div>
        </fieldset>
        <fieldset className="owner-editor-section">
          <legend>Варианты размещения</legend>
          <div className="owner-room-list">
            {currentList<Record<string, unknown>>("rooms").map((room, index) => <div key={String(room.id || room.client_id || index)} className="owner-room-row"><label>Название<input value={String(room.name || "")} onChange={(event) => updateRoom(index, "name", event.target.value)} /></label><label>Цена<input type="number" min="0" value={String(room.price || "")} onChange={(event) => updateRoom(index, "price", Number(event.target.value) || null)} /></label><label className="wide">Описание<textarea rows={3} value={String(room.description || "")} onChange={(event) => updateRoom(index, "description", event.target.value)} /></label><button type="button" className="owner-room-remove" onClick={() => setProposal({ ...proposal, rooms: currentList<Record<string, unknown>>("rooms").filter((_, itemIndex) => itemIndex !== index) })}><X /> Удалить вариант</button></div>)}
            <button type="button" className="owner-secondary" onClick={() => setProposal({ ...proposal, rooms: [...currentList<Record<string, unknown>>("rooms"), { client_id: crypto.randomUUID(), name: "Новый вариант", description: "", price: null }] })}>Добавить вариант</button>
          </div>
        </fieldset>
        <Suspense fallback={<OwnerRouteLoading label="Открываем медиа…" />}>
          <OwnerMediaEditor
            change={change}
            publishedMedia={currentList<Record<string, unknown>>("media")}
            onChange={updateChange}
            onMessage={onMessage}
            onError={onError}
          />
        </Suspense>
        <label>Ссылка на видео<input placeholder="YouTube, Rutube, VK Video" value={String(currentList<string>("video_urls")[0] || "")} onChange={(event) => setProposal({ ...proposal, video_urls: event.target.value ? [event.target.value] : [] })} /></label>
        <div className="owner-editor-actions"><button className="owner-secondary" onClick={() => void saveAndPreview()}>Сохранить черновик</button><button className="owner-primary" disabled={!diff.length} onClick={() => void submit()}><Send /> Отправить на проверку</button></div>
      </section>
      <Suspense fallback={<OwnerRouteLoading label="Готовим сравнение…" />}>
        <DiffViewer items={diff} />
      </Suspense>
    </div>
  );
}
