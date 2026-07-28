import { Send, X } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useBlocker } from "react-router";

import { ownerApi, type ChangeDiff, type EntitySchema, type OwnerChange } from "./api";
import { OwnerRouteLoading } from "./components";
import { parseOwnerCoordinates } from "./coordinates";
import SchemaAttributeFields from "./SchemaAttributeFields";

const DiffViewer = lazy(() => import("./DiffViewer").then((module) => ({ default: module.DiffViewer })));
const OwnerMediaEditor = lazy(() => import("./OwnerMediaEditor"));

type DetailData = {
  camp: Record<string, unknown>;
  amenity_catalog: Array<{ id: number; name: string; category: string }>;
};

export default function OwnerEditor({
  detail,
  schema,
  initialChange,
  onChange,
  onSubmitted,
  onMessage,
  onError,
}: {
  detail: DetailData;
  schema?: EntitySchema | null;
  initialChange: OwnerChange;
  onChange: (change: OwnerChange) => void;
  onSubmitted: () => void;
  onMessage: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [change, setChange] = useState(initialChange);
  const [proposal, setProposal] = useState<Record<string, unknown>>(initialChange.proposed_payload || {});
  const [coordinateError, setCoordinateError] = useState("");
  const [isMutating, setIsMutating] = useState(false);
  const savedProposal = useRef(JSON.stringify(initialChange.proposed_payload || {}));
  const dirty = JSON.stringify(proposal) !== savedProposal.current;
  const blocker = useBlocker(dirty);
  const isAccommodation = String(detail.camp.entity_kind || "accommodation") === "accommodation";

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
    const useLocalProposal = dirty || !change.diff_payload?.length;
    const items = !useLocalProposal
      ? [...(change.diff_payload || [])]
      : Object.entries(proposal)
        .filter(([key]) => key !== "attributes")
        .filter(([key, value]) => JSON.stringify(detail.camp[key]) !== JSON.stringify(value))
        .map(([field, after]) => ({
          field,
          label: { name: "Название", short_description: "Краткое описание", description: "Описание", region: "Регион", district: "Район", city: "Город", address: "Адрес", lat: "Широта", lng: "Долгота", min_price: "Минимальная цена", seasonality: "Сезонность", working_hours: "Режим работы", working_hours_mode: "Формат режима работы", surroundings: "Окрестности", contacts: "Контакты", amenities: "Удобства", rooms: "Варианты размещения", video_urls: "Видео", attributes: "Характеристики", request_publication: "Повторная публикация" }[field] || field,
          before: detail.camp[field],
          after,
        }));
    const proposedAttributes = proposal.attributes;
    if (
      useLocalProposal
      && proposedAttributes
      && typeof proposedAttributes === "object"
      && !Array.isArray(proposedAttributes)
    ) {
      const beforeAttributes = detail.camp.attributes && typeof detail.camp.attributes === "object" && !Array.isArray(detail.camp.attributes)
        ? detail.camp.attributes as Record<string, unknown>
        : {};
      const nextAttributes = proposedAttributes as Record<string, unknown>;
      for (const field of schema?.fields || []) {
        if (
          JSON.stringify(beforeAttributes[field.key])
          === JSON.stringify(nextAttributes[field.key])
        ) continue;
        items.push({
          field: `attributes.${field.key}`,
          label: field.label,
          before: beforeAttributes[field.key],
          after: nextAttributes[field.key],
        });
      }
    }
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
  }, [change, detail.camp, dirty, proposal, schema?.fields]);

  function updateChange(next: OwnerChange) {
    setChange(next);
    onChange(next);
  }

  function currentValue(key: string) {
    return Object.prototype.hasOwnProperty.call(proposal, key)
      ? proposal[key]
      : detail.camp[key];
  }

  function currentList<T>(key: string): T[] {
    const value = currentValue(key);
    return Array.isArray(value) ? value as T[] : [];
  }

  function currentAttributes() {
    const value = currentValue("attributes");
    return value && typeof value === "object" && !Array.isArray(value)
      ? value as Record<string, unknown>
      : {};
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

  function workingHoursText() {
    const value = currentValue("working_hours");
    if (!value || typeof value !== "object" || Array.isArray(value)) return "";
    const schedule = value as Record<string, unknown>;
    return String(schedule.text || schedule.daily || schedule.reception || "");
  }

  function workingHoursMode() {
    return String(currentValue("working_hours_mode") || "schedule");
  }

  function updateWorkingHoursMode(mode: string) {
    const presets: Record<string, string> = {
      always_open: "Круглосуточно",
      by_appointment: "По предварительной записи",
      closed: "Временно закрыто",
    };
    const text = presets[mode] ?? workingHoursText();
    setProposal({
      ...proposal,
      working_hours_mode: mode,
      working_hours: text ? { text } : {},
    });
  }

  function proposalForMutation() {
    const parsed = parseOwnerCoordinates(currentValue("lat"), currentValue("lng"));
    if (parsed.error) {
      setCoordinateError(parsed.error);
      throw new Error(parsed.error);
    }
    setCoordinateError("");
    if (
      !Object.prototype.hasOwnProperty.call(proposal, "lat")
      && !Object.prototype.hasOwnProperty.call(proposal, "lng")
    ) {
      return proposal;
    }
    return { ...proposal, lat: parsed.lat, lng: parsed.lng };
  }

  async function saveAndPreview() {
    try {
      setIsMutating(true);
      const nextProposal = proposalForMutation();
      const result = await ownerApi.saveChange(change.id, change.content_version, nextProposal);
      updateChange(result.change);
      const saved = result.change.proposed_payload || nextProposal;
      setProposal(saved);
      savedProposal.current = JSON.stringify(saved);
      onMessage("Черновик сохранён. Проверьте сравнение перед отправкой.");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Не удалось сохранить");
    } finally {
      setIsMutating(false);
    }
  }

  async function submit() {
    try {
      setIsMutating(true);
      const nextProposal = proposalForMutation();
      const result = await ownerApi.submitChange(
        change.id,
        change.content_version,
        nextProposal,
      );
      updateChange(result.change);
      const submitted = result.change.proposed_payload || nextProposal;
      setProposal(submitted);
      savedProposal.current = JSON.stringify(submitted);
      onMessage("Изменения отправлены на проверку");
      onSubmitted();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "Не удалось отправить");
    } finally {
      setIsMutating(false);
    }
  }

  return (
    <div className="owner-editor-grid">
      <section className="owner-card owner-editor">
        <div className="owner-section-heading"><div><p className="owner-eyebrow">Редактор</p><h2>Данные карточки</h2></div></div>
        {[["name", "Название"], ["short_description", "Краткое описание"], ["seasonality", "Сезонность"], ["surroundings", "Описание окрестностей"]].map(([key, label]) => <label key={key}>{label}<input value={String(currentValue(key) ?? "")} onChange={(event) => setProposal({ ...proposal, [key]: event.target.value })} /></label>)}
        <label>Подробное описание<textarea rows={8} value={String(currentValue("description") ?? "")} onChange={(event) => setProposal({ ...proposal, description: event.target.value })} /></label>
        <label>Минимальная цена<input type="number" min="0" disabled={["request", "free", "none"].includes(String(currentValue("price_mode") || "none"))} value={String(currentValue("min_price") ?? "")} onChange={(event) => setProposal({ ...proposal, min_price: event.target.value ? Number(event.target.value) : null })} /></label>
        <fieldset className="owner-editor-section">
          <legend>Стоимость</legend>
          <div className="owner-create-grid">
            <label>
              Как показывать стоимость
              <select
                value={String(currentValue("price_mode") || "none")}
                onChange={(event) => {
                  const mode = event.target.value;
                  setProposal({
                    ...proposal,
                    price_mode: mode,
                    ...(["request", "free", "none"].includes(mode) ? { min_price: null } : {}),
                  });
                }}
              >
                <option value="from">Цена от</option>
                <option value="fixed">Фиксированная цена</option>
                <option value="request">Стоимость по запросу</option>
                <option value="free">Бесплатно</option>
                <option value="none">Не показывать цену</option>
              </select>
            </label>
            <label>
              Валюта
              <select
                value={String(currentValue("currency") || "RUB")}
                onChange={(event) => setProposal({ ...proposal, currency: event.target.value })}
              >
                <option value="RUB">Российский рубль (RUB)</option>
                <option value="USD">Доллар США (USD)</option>
                <option value="EUR">Евро (EUR)</option>
              </select>
            </label>
          </div>
        </fieldset>
        <fieldset className="owner-editor-section">
          <legend>Адрес и точка на карте</legend>
          <div className="owner-create-grid">
            {[["region", "Регион"], ["district", "Район"], ["city", "Город"], ["address", "Адрес"]].map(([key, label]) => (
              <label key={key}>{label}<input value={String(currentValue(key) ?? "")} onChange={(event) => setProposal({ ...proposal, [key]: event.target.value })} /></label>
            ))}
            <label>
              Широта
              <input
                type="text"
                inputMode="decimal"
                aria-invalid={Boolean(coordinateError)}
                value={String(currentValue("lat") ?? "")}
                onChange={(event) => {
                  setCoordinateError("");
                  setProposal({ ...proposal, lat: event.target.value });
                }}
              />
            </label>
            <label>
              Долгота
              <input
                type="text"
                inputMode="decimal"
                aria-invalid={Boolean(coordinateError)}
                value={String(currentValue("lng") ?? "")}
                onChange={(event) => {
                  setCoordinateError("");
                  setProposal({ ...proposal, lng: event.target.value });
                }}
              />
            </label>
          </div>
          {coordinateError ? <p className="owner-alert danger" role="alert">{coordinateError}</p> : null}
        </fieldset>
        <fieldset className="owner-editor-section">
          <legend>Режим работы</legend>
          <div className="owner-create-grid">
            <label>
              Формат
              <select value={workingHoursMode()} onChange={(event) => updateWorkingHoursMode(event.target.value)}>
                <option value="schedule">По расписанию</option>
                <option value="always_open">Круглосуточно</option>
                <option value="by_appointment">По предварительной записи</option>
                <option value="seasonal">Сезонный график</option>
                <option value="closed">Временно закрыто</option>
              </select>
            </label>
            <label>
              Как показать посетителю
              <input
                maxLength={500}
                value={workingHoursText()}
                onChange={(event) => setProposal({
                  ...proposal,
                  working_hours: event.target.value ? { text: event.target.value } : {},
                })}
                placeholder="Например, ежедневно 09:00–21:00"
              />
            </label>
          </div>
        </fieldset>
        {schema?.fields.length ? (
          <fieldset className="owner-editor-section">
            <legend>{schema.name}</legend>
            <SchemaAttributeFields
              schema={schema}
              values={currentAttributes()}
              onChange={(attributes) => setProposal({ ...proposal, attributes })}
            />
          </fieldset>
        ) : null}
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
        {isAccommodation ? <fieldset className="owner-editor-section">
          <legend>Варианты размещения</legend>
          <div className="owner-room-list">
            {currentList<Record<string, unknown>>("rooms").map((room, index) => <div key={String(room.id || room.client_id || index)} className="owner-room-row"><label>Название<input value={String(room.name || "")} onChange={(event) => updateRoom(index, "name", event.target.value)} /></label><label>Цена<input type="number" min="0" value={String(room.price || "")} onChange={(event) => updateRoom(index, "price", Number(event.target.value) || null)} /></label><label className="wide">Описание<textarea rows={3} value={String(room.description || "")} onChange={(event) => updateRoom(index, "description", event.target.value)} /></label><button type="button" className="owner-room-remove" onClick={() => setProposal({ ...proposal, rooms: currentList<Record<string, unknown>>("rooms").filter((_, itemIndex) => itemIndex !== index) })}><X /> Удалить вариант</button></div>)}
            <button type="button" className="owner-secondary" onClick={() => setProposal({ ...proposal, rooms: [...currentList<Record<string, unknown>>("rooms"), { client_id: crypto.randomUUID(), name: "Новый вариант", description: "", price: null }] })}>Добавить вариант</button>
          </div>
        </fieldset> : null}
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
        <div className="owner-editor-actions"><button type="button" className="owner-secondary" disabled={isMutating} onClick={() => void saveAndPreview()}>{isMutating ? "Сохраняем…" : "Сохранить черновик"}</button><button type="button" className="owner-primary" disabled={isMutating || !diff.length} onClick={() => void submit()}><Send /> {isMutating ? "Сохраняем…" : "Отправить на проверку"}</button></div>
      </section>
      <Suspense fallback={<OwnerRouteLoading label="Готовим сравнение…" />}>
        <DiffViewer items={diff} />
      </Suspense>
    </div>
  );
}
