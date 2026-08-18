const STEPS = ["Заявитель", "Объект", "Контакты", "Удобства", "Размещение", "Медиа", "Согласия", "Проверка"];
const DB_NAME = "touristika-placement-submission";
const DB_VERSION = 1;
const STATE_KEY = "active-draft";
const form = document.querySelector("#submission-form");
const stepNodes = Array.from(document.querySelectorAll("[data-step]"));
const progress = document.querySelector("[data-progress]");
const saveStatus = document.querySelector("[data-save-status]");
const errorBox = document.querySelector("[data-form-error]");
const nextButton = document.querySelector("[data-next]");
const previousButton = document.querySelector("[data-prev]");
const submitButton = document.querySelector("[data-submit]");
const photoInput = document.querySelector("[data-photo-input]");
const uploadZone = document.querySelector("[data-upload-zone]");
const uploadList = document.querySelector("[data-upload-list]");
const roomsNode = document.querySelector("[data-rooms]");
const accommodationRoomsNode = document.querySelector("[data-accommodation-rooms]");
const nonAccommodationNote = document.querySelector("[data-non-accommodation-note]");
const addRoomButton = document.querySelector("[data-add-room]");
const entityFieldsNode = document.querySelector("[data-entity-fields]");
const schemaFieldsNode = document.querySelector("[data-schema-fields]");
const successNode = document.querySelector("[data-success]");
let database;
let currentStep = 1;
let config = null;
let serverDraft = null;
let mediaItems = [];
let roomItems = [];
let coordinateMap;
let coordinateMarker;
let syncTimer;
let syncChain = Promise.resolve();
let dirty = false;
let uploading = 0;
let submitIdempotencyKey = crypto.randomUUID();
let restoredNamedValues = {};

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("state")) db.createObjectStore("state");
      if (!db.objectStoreNames.contains("files")) db.createObjectStore("files");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function dbGet(storeName, key) {
  return new Promise((resolve, reject) => {
    const request = database.transaction(storeName).objectStore(storeName).get(key);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function dbPut(storeName, key, value) {
  return new Promise((resolve, reject) => {
    const request = database.transaction(storeName, "readwrite").objectStore(storeName).put(value, key);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function dbDelete(storeName, key) {
  return new Promise((resolve, reject) => {
    const request = database.transaction(storeName, "readwrite").objectStore(storeName).delete(key);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function dbClear() {
  const transaction = database.transaction(["state", "files"], "readwrite");
  transaction.objectStore("state").clear();
  transaction.objectStore("files").clear();
  return new Promise((resolve, reject) => {
    transaction.oncomplete = resolve;
    transaction.onerror = () => reject(transaction.error);
  });
}

function setStatus(message, state = "") {
  saveStatus.textContent = message;
  saveStatus.dataset.state = state;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
  errorBox.scrollIntoView({ behavior: "smooth", block: "center" });
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function inputValue(name) {
  return String(form.elements[name]?.value || "").trim();
}

function nullableNumber(name) {
  const value = inputValue(name);
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function coordinateInputState() {
  const rawLat = inputValue("lat");
  const rawLng = inputValue("lng");
  if (!rawLat && !rawLng) return { empty: true, valid: true, lat: null, lng: null };
  if (!rawLat || !rawLng) {
    return { empty: false, valid: false, message: "Укажите обе координаты объекта." };
  }
  const lat = Number(rawLat);
  const lng = Number(rawLng);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return { empty: false, valid: false, message: "Координаты указаны некорректно." };
  }
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    return { empty: false, valid: false, message: "Координаты выходят за допустимый диапазон." };
  }
  return { empty: false, valid: true, lat, lng };
}

function collectPublicContacts() {
  return Array.from(document.querySelectorAll("[data-contact]"))
    .map((input, index) => ({
      contact_type: input.dataset.contact,
      label: input.closest("label")?.firstChild?.textContent?.trim() || null,
      value: input.value.trim(),
      sort_order: index * 10,
    }))
    .filter((item) => item.value);
}

function selectedEntityType() {
  const placeTypeId = nullableNumber("place_type_id");
  return config?.place_types?.find((item) => Number(item.id) === Number(placeTypeId)) || null;
}

function selectedEntityKind() {
  return String(selectedEntityType()?.entity_kind || "accommodation").trim().toLowerCase();
}

function collectEntityAttributes() {
  const attributes = {};
  schemaFieldsNode?.querySelectorAll("[data-entity-attribute]").forEach((input) => {
    const key = input.dataset.entityAttribute;
    const kind = input.dataset.attributeType || "string";
    if (!key) return;
    if (kind === "boolean") {
      attributes[key] = Boolean(input.checked);
      return;
    }
    const raw = String(input.value || "").trim();
    if (!raw) return;
    if (kind === "integer" || kind === "number") {
      const value = Number(raw);
      if (Number.isFinite(value)) attributes[key] = value;
      return;
    }
    if (kind === "string_list") {
      attributes[key] = raw.split(/[,\n]/).map((value) => value.trim()).filter(Boolean);
      return;
    }
    if (kind === "enum" && Array.isArray(input.catalogOptions)) {
      const value = input.catalogOptions.find((option) => String(option) === raw);
      if (value !== undefined) attributes[key] = value;
      return;
    }
    attributes[key] = raw;
  });
  return attributes;
}

function collectRooms() {
  if (selectedEntityKind() !== "accommodation") return [];
  return Array.from(roomsNode.querySelectorAll("[data-room]")).map((roomNode) => {
    const value = (field) => roomNode.querySelector(`[data-room-field="${field}"]`)?.value?.trim() || "";
    const number = (field) => Number(value(field) || 0);
    return {
      client_id: roomNode.dataset.room,
      name: value("name"),
      room_type: value("room_type"),
      description: value("description"),
      floors: number("floors") || 1,
      floor: number("floor") || 1,
      beds_single: number("beds_single"),
      beds_double: number("beds_double"),
      capacity: number("capacity"),
      price: number("price"),
      bath_type: value("bath_type"),
      wc_type: value("wc_type"),
      kitchen_type: value("kitchen_type"),
      bbq_type: value("bbq_type"),
      has_ac: roomNode.querySelector('[data-room-field="has_ac"]')?.checked || false,
    };
  });
}

function collectPayload() {
  return {
    applicant_role: inputValue("applicant_role") || null,
    applicant_name: inputValue("applicant_name") || null,
    applicant_organization: inputValue("applicant_organization") || null,
    applicant_position: inputValue("applicant_position") || null,
    applicant_phone: inputValue("applicant_phone") || null,
    applicant_email: inputValue("applicant_email") || null,
    applicant_telegram: inputValue("applicant_telegram") || null,
    applicant_whatsapp: inputValue("applicant_whatsapp") || null,
    applicant_max: inputValue("applicant_max") || null,
    preferred_contact_type: inputValue("preferred_contact_type") || null,
    place_name: inputValue("place_name") || null,
    place_type_id: nullableNumber("place_type_id"),
    region: inputValue("region") || null,
    district: inputValue("district") || null,
    city: inputValue("city") || null,
    locality: inputValue("locality") || null,
    address: inputValue("address") || null,
    lat: nullableNumber("lat"),
    lng: nullableNumber("lng"),
    short_description: inputValue("short_description") || null,
    description: inputValue("description") || null,
    seasonality: inputValue("seasonality") || null,
    working_hours: inputValue("working_hours_text") ? { text: inputValue("working_hours_text") } : {},
    min_price: nullableNumber("min_price"),
    public_contacts: collectPublicContacts(),
    amenities: Array.from(document.querySelectorAll("[data-amenity]:checked")).map((input) => Number(input.value)),
    rooms_payload: collectRooms(),
    video_urls: inputValue("video_urls_text").split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
    extra_data: collectEntityAttributes(),
    consents: {
      publication: Boolean(form.elements.consent_publication?.checked),
      privacy: Boolean(form.elements.consent_privacy?.checked),
      photos: Boolean(form.elements.consent_photos?.checked),
      accuracy: Boolean(form.elements.consent_accuracy?.checked),
      representation: Boolean(form.elements.consent_representation?.checked),
    },
  };
}

function collectLocalState() {
  const named = {};
  Array.from(form.elements).forEach((element) => {
    if (!element.name || element.name === "website_confirm" || element.type === "file") return;
    named[element.name] = element.type === "checkbox" ? element.checked : element.value;
  });
  const contacts = Array.from(document.querySelectorAll("[data-contact]")).map((input) => input.value);
  return {
    formatVersion: 1,
    currentStep,
    named,
    contacts,
    amenities: Array.from(document.querySelectorAll("[data-amenity]:checked")).map((input) => input.value),
    rooms: collectRooms(),
    serverDraft,
    mediaItems,
    submitIdempotencyKey,
    savedAt: new Date().toISOString(),
  };
}

async function saveLocalState() {
  if (!database) return;
  await dbPut("state", STATE_KEY, collectLocalState());
  dirty = false;
  setStatus("Черновик сохранён на этом устройстве", "saved");
}

function scheduleSave() {
  dirty = true;
  setStatus("Сохраняем изменения…");
  window.clearTimeout(syncTimer);
  syncTimer = window.setTimeout(() => {
    saveLocalState().catch(() => setStatus("Не удалось сохранить локальный черновик", "error"));
    scheduleServerSync();
  }, 500);
}

function scheduleServerSync() {
  if (!serverDraft) return;
  const payload = collectPayload();
  syncChain = syncChain.catch(() => undefined).then(async () => {
    const expectedVersion = serverDraft.contentVersion;
    const response = await fetch(`/api/public/submissions/drafts/${encodeURIComponent(serverDraft.token)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ ...payload, content_version: expectedVersion }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 409) throw new Error("Черновик открыт в другой вкладке. Обновите страницу.");
      throw new Error(data.detail || "Серверный черновик не сохранён");
    }
    serverDraft.contentVersion = data.content_version;
    await saveLocalState();
  });
  syncChain.catch((error) => {
    setStatus(error instanceof Error ? error.message : "Серверный черновик не сохранён", "error");
  });
  return syncChain;
}

function restoreNamedValues(saved) {
  restoredNamedValues = { ...(saved.named || {}) };
  Object.entries(saved.named || {}).forEach(([name, value]) => {
    const input = form.elements[name];
    if (!input) return;
    if (input.type === "checkbox") input.checked = Boolean(value);
    else input.value = String(value ?? "");
  });
  Array.from(document.querySelectorAll("[data-contact]")).forEach((input, index) => {
    input.value = String(saved.contacts?.[index] || "");
  });
  roomItems = Array.isArray(saved.rooms) ? saved.rooms : [];
  renderRooms();
  mediaItems = Array.isArray(saved.mediaItems) ? saved.mediaItems : [];
  submitIdempotencyKey = saved.submitIdempotencyKey || crypto.randomUUID();
  serverDraft = saved.serverDraft || null;
  currentStep = Math.min(8, Math.max(1, Number(saved.currentStep) || 1));
}

function restoreAmenities(saved) {
  const selected = new Set((saved?.amenities || []).map(String));
  document.querySelectorAll("[data-amenity]").forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function renderProgress() {
  progress.replaceChildren();
  STEPS.forEach((label, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${index + 1}. ${label}`;
    button.dataset.current = String(currentStep === index + 1);
    button.dataset.complete = String(currentStep > index + 1);
    button.addEventListener("click", () => {
      if (index + 1 <= currentStep) showStep(index + 1);
      else if (index + 1 === currentStep + 1 && validateStep(currentStep)) showStep(index + 1);
    });
    progress.append(button);
  });
}

function showStep(step) {
  currentStep = Math.min(8, Math.max(1, step));
  stepNodes.forEach((node) => { node.hidden = Number(node.dataset.step) !== currentStep; });
  previousButton.hidden = currentStep === 1;
  nextButton.hidden = currentStep === 8;
  submitButton.hidden = currentStep !== 8;
  renderProgress();
  clearError();
  if (currentStep === 2) initialiseCoordinateMap();
  if (currentStep === 8) renderPreview();
  stepNodes[currentStep - 1]?.querySelector("h2")?.focus?.({ preventScroll: true });
  scheduleSave();
  window.scrollTo({ top: Math.max(0, form.offsetTop - 100), behavior: "smooth" });
}

function validateStep(step) {
  clearError();
  const scope = stepNodes[step - 1];
  const required = Array.from(scope.querySelectorAll("[required]"));
  const invalid = required.find((input) => !input.checkValidity());
  if (invalid) {
    invalid.setAttribute("aria-invalid", "true");
    invalid.reportValidity();
    invalid.focus();
    showError("Заполните обязательные поля этого шага.");
    return false;
  }
  if (step === 2) {
    const coordinates = coordinateInputState();
    if (!coordinates.valid) {
      const target = form.elements.lat.value ? form.elements.lng : form.elements.lat;
      form.elements.lat.setAttribute("aria-invalid", "true");
      form.elements.lng.setAttribute("aria-invalid", "true");
      target.focus();
      showError(coordinates.message);
      return false;
    }
  }
  if (step === 1) {
    const role = inputValue("applicant_role");
    const contacts = ["applicant_phone", "applicant_email", "applicant_telegram", "applicant_whatsapp", "applicant_max"].some(inputValue);
    if (["owner", "representative"].includes(role) && (!inputValue("applicant_phone") || !inputValue("applicant_email") || !inputValue("preferred_contact_type"))) {
      showError("Для собственника и представителя обязательны телефон, email и предпочтительный способ связи.");
      return false;
    }
    if (role === "tourist" && !contacts) {
      showError("Укажите хотя бы один способ связи.");
      return false;
    }
  }
  if (step === 7 && ["owner", "representative"].includes(inputValue("applicant_role")) && !form.elements.consent_representation.checked) {
    showError("Подтвердите право представлять объект.");
    return false;
  }
  return true;
}

function renderPlaceTypes(types) {
  const select = document.querySelector("[data-place-types]");
  const previous = select.value || String(restoredNamedValues.place_type_id || "");
  select.replaceChildren(new Option("Выберите тип", ""));
  const kindLabels = new Map(
    (config?.entity_kinds || []).map((kind) => [
      String(kind.key || kind.slug || ""),
      kind.plural_name || kind.name,
    ]),
  );
  const groups = new Map();
  types.forEach((item) => {
    const kind = String(item.entity_kind || "accommodation");
    if (!groups.has(kind)) groups.set(kind, []);
    groups.get(kind).push(item);
  });
  groups.forEach((items, kind) => {
    const parent = kindLabels.size
      ? Object.assign(document.createElement("optgroup"), { label: kindLabels.get(kind) || "Другое" })
      : select;
    items.forEach((item) => {
      const option = new Option(item.name, String(item.id));
      option.dataset.entityKind = kind;
      option.dataset.schemaKey = item.schema_key || "";
      option.dataset.schemaVersion = String(item.schema_version || 1);
      parent.append(option);
    });
    if (parent !== select) select.append(parent);
  });
  if (previous) select.value = previous;
}

function selectedEntitySchema() {
  const type = selectedEntityType();
  if (!type) return null;
  return (config?.entity_schemas || []).find((schema) => (
    String(schema.key || schema.schema_key || "") === String(type.schema_key || "")
    && Number(schema.version || 1) === Number(type.schema_version || 1)
  )) || null;
}

function renderEntityFields() {
  if (!schemaFieldsNode || !entityFieldsNode) return;
  const previous = collectEntityAttributes();
  const schema = selectedEntitySchema();
  const fields = Array.isArray(schema?.fields) ? schema.fields : [];
  schemaFieldsNode.replaceChildren();
  fields.forEach((field) => {
    if (!field || field.public === false || !field.key) return;
    const type = String(field.type || "string");
    const name = `attribute__${field.key}`;
    const savedValue = previous[field.key] ?? restoredNamedValues[name];
    const label = document.createElement("label");
    let input;
    if (type === "boolean") {
      label.className = "submission-attribute-boolean submission-field--wide";
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = Boolean(savedValue);
      label.append(input, document.createTextNode(field.label || field.key));
    } else {
      label.className = "submission-field";
      label.append(document.createTextNode(`${field.label || field.key}${field.unit ? `, ${field.unit}` : ""}`));
      if (type === "enum") {
        input = document.createElement("select");
        input.append(new Option("Выберите", ""));
        (field.options || []).forEach((option) => input.add(new Option(String(option), String(option))));
        input.catalogOptions = field.options || [];
      } else if (type === "string_list") {
        input = document.createElement("textarea");
        input.rows = 3;
        input.placeholder = "По одному значению в строке";
      } else {
        input = document.createElement("input");
        input.type = type === "integer" || type === "number" ? "number" : "text";
        if (type === "number") input.step = "any";
        if (field.min !== undefined) input.min = String(field.min);
        if (field.max !== undefined) input.max = String(field.max);
        if (field.max_length) input.maxLength = Number(field.max_length);
      }
      if (savedValue !== undefined && savedValue !== null) {
        input.value = Array.isArray(savedValue) ? savedValue.join("\n") : String(savedValue);
      }
      label.append(input);
    }
    input.name = name;
    input.dataset.entityAttribute = field.key;
    input.dataset.attributeType = type;
    if (field.required) input.required = true;
    schemaFieldsNode.append(label);
  });
  entityFieldsNode.hidden = schemaFieldsNode.childElementCount === 0;
}

function updateEntityTypeUI({ discardIncompatible = false } = {}) {
  const accommodation = selectedEntityKind() === "accommodation";
  if (accommodationRoomsNode) accommodationRoomsNode.hidden = !accommodation;
  if (nonAccommodationNote) nonAccommodationNote.hidden = accommodation;
  if (!accommodation && discardIncompatible) {
    roomItems = [];
    roomsNode.replaceChildren();
    mediaItems.filter((item) => item.scope === "room").forEach((item) => {
      void deleteMedia(item.id);
    });
  } else if (accommodation) {
    renderRooms();
  }
  renderEntityFields();
}

function renderAmenities(amenities) {
  const container = document.querySelector("[data-amenities]");
  container.replaceChildren();
  const groups = new Map();
  amenities.forEach((item) => {
    const key = item.category || "general";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  const labels = { connectivity:"Связь", transport:"Транспорт", food:"Питание", rules:"Правила", family:"Семья", accessibility:"Доступность", nature:"Природа", leisure:"Досуг", wellness:"Отдых и здоровье", comfort:"Комфорт", general:"Другое" };
  groups.forEach((items, key) => {
    const section = document.createElement("section");
    section.className = "amenity-group";
    const heading = document.createElement("h3");
    heading.textContent = labels[key] || key;
    const options = document.createElement("div");
    options.className = "amenity-options";
    items.forEach((item) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = String(item.id);
      input.dataset.amenity = "";
      const span = document.createElement("span");
      span.textContent = item.name;
      label.append(input, span);
      options.append(label);
    });
    section.append(heading, options);
    container.append(section);
  });
}

function makeRoomId() {
  return `room-${crypto.randomUUID()}`;
}

function renderRooms() {
  roomsNode.replaceChildren();
  roomItems.forEach((room, index) => {
    const node = document.createElement("article");
    node.className = "submission-room";
    node.dataset.room = room.client_id || makeRoomId();
    node.innerHTML = `
      <div class="submission-room__heading"><h3>Вариант ${index + 1}</h3><button class="submission-room__remove" type="button">Удалить</button></div>
      <label class="submission-field">Тип<input data-room-field="room_type" maxlength="120"></label>
      <label class="submission-field">Название<input data-room-field="name" maxlength="160"></label>
      <label class="submission-field">Вместимость<input data-room-field="capacity" type="number" min="0" max="1000"></label>
      <label class="submission-field">Односпальные кровати<input data-room-field="beds_single" type="number" min="0" max="100"></label>
      <label class="submission-field">Двуспальные кровати<input data-room-field="beds_double" type="number" min="0" max="100"></label>
      <label class="submission-field">Цена, ₽<input data-room-field="price" type="number" min="0"></label>
      <label class="submission-field">Этажность<input data-room-field="floors" type="number" min="1" max="100"></label>
      <label class="submission-field">Этаж<input data-room-field="floor" type="number" min="1" max="100"></label>
      <label class="submission-field">Душ / ванна<input data-room-field="bath_type" maxlength="120"></label>
      <label class="submission-field">Санузел<input data-room-field="wc_type" maxlength="120"></label>
      <label class="submission-field">Кухня<input data-room-field="kitchen_type" maxlength="120"></label>
      <label class="submission-field">BBQ<input data-room-field="bbq_type" maxlength="120"></label>
      <label class="submission-field submission-field--wide">Описание<textarea data-room-field="description" rows="3" maxlength="2000"></textarea></label>
      <label class="consent-list submission-field--wide"><span><input data-room-field="has_ac" type="checkbox"> Кондиционер</span></label>
      <label class="submission-field submission-field--wide">Фото варианта<input data-room-photo type="file" accept="image/jpeg,image/png,image/webp" multiple></label>
    `;
    Object.entries(room).forEach(([key, value]) => {
      const input = node.querySelector(`[data-room-field="${key}"]`);
      if (!input) return;
      if (input.type === "checkbox") input.checked = Boolean(value);
      else input.value = String(value ?? "");
    });
    node.querySelector(".submission-room__remove").addEventListener("click", () => {
      mediaItems.filter((item) => item.room_client_id === node.dataset.room).forEach((item) => void deleteMedia(item.id));
      roomItems = collectRooms().filter((item) => item.client_id !== node.dataset.room);
      renderRooms();
      scheduleSave();
    });
    node.querySelector("[data-room-photo]").addEventListener("change", (event) => {
      void handleFiles(Array.from(event.target.files || []), "room", node.dataset.room);
      event.target.value = "";
    });
    roomsNode.append(node);
  });
}

function renderUploads() {
  uploadList.replaceChildren();
  mediaItems.forEach((item) => {
    const card = document.createElement("article");
    card.className = "upload-item";
    const image = document.createElement("img");
    image.src = item.thumbnail_url || item.url;
    image.alt = "";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "upload-item__remove";
    remove.setAttribute("aria-label", "Удалить фотографию");
    remove.textContent = "×";
    remove.addEventListener("click", () => void deleteMedia(item.id));
    const meta = document.createElement("div");
    meta.className = "upload-item__meta";
    const strong = document.createElement("strong");
    strong.textContent = item.scope === "room" ? "Фото варианта" : item.is_cover ? "Обложка" : "Фото объекта";
    const detail = document.createElement("span");
    detail.textContent = `${item.width} × ${item.height}`;
    meta.append(strong, detail);
    card.append(image, remove, meta);
    uploadList.append(card);
  });
}

function uploadFile(file, localKey, scope, roomClientId, isCover) {
  return new Promise((resolve, reject) => {
    const body = new FormData();
    body.append("file", file);
    body.append("scope", scope);
    if (roomClientId) body.append("room_client_id", roomClientId);
    body.append("sort_order", String(mediaItems.filter((item) => item.scope === scope && item.room_client_id === roomClientId).length));
    body.append("is_cover", String(isCover));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/public/submissions/drafts/${encodeURIComponent(serverDraft.token)}/media`);
    xhr.responseType = "json";
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) setStatus(`Загружаем фото: ${Math.round(event.loaded / event.total * 100)}%`);
    };
    xhr.onload = () => {
      const payload = xhr.response || {};
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(payload.detail || "Не удалось загрузить фото"));
        return;
      }
      mediaItems.push(payload.media);
      dbDelete("files", localKey).catch(() => {});
      resolve(payload.media);
    };
    xhr.onerror = () => reject(new Error("Сеть недоступна. Фото сохранено на устройстве."));
    xhr.send(body);
  });
}

async function handleFiles(files, scope = "place", roomClientId = null) {
  if (!serverDraft || !files.length) return;
  clearError();
  for (const file of files) {
    const localKey = crypto.randomUUID();
    await dbPut("files", localKey, { file, scope, roomClientId, name:file.name });
    uploading += 1;
    try {
      const cover = scope === "place" && !mediaItems.some((item) => item.scope === "place");
      await uploadFile(file, localKey, scope, roomClientId, cover);
      renderUploads();
      await saveLocalState();
    } catch (error) {
      showError(error instanceof Error ? error.message : "Не удалось загрузить фото");
    } finally {
      uploading -= 1;
    }
  }
  setStatus("Фотографии сохранены", "saved");
}

async function retryPendingFiles() {
  if (!database || !serverDraft) return;
  const transaction = database.transaction("files");
  const store = transaction.objectStore("files");
  const request = store.openCursor();
  request.onsuccess = async () => {
    const cursor = request.result;
    if (!cursor) return;
    const value = cursor.value;
    try {
      await uploadFile(value.file, cursor.key, value.scope, value.roomClientId, false);
      renderUploads();
      await saveLocalState();
    } catch {
      // Файл остаётся в IndexedDB для следующей попытки.
    }
    cursor.continue();
  };
}

async function deleteMedia(mediaId) {
  const item = mediaItems.find((candidate) => candidate.id === mediaId);
  if (!item || !serverDraft) return;
  const response = await fetch(`/api/public/submissions/drafts/${encodeURIComponent(serverDraft.token)}/media/${mediaId}`, {
    method: "DELETE", headers: { Accept:"application/json" }, credentials:"same-origin",
  });
  if (!response.ok) {
    showError("Не удалось удалить фотографию");
    return;
  }
  mediaItems = mediaItems.filter((candidate) => candidate.id !== mediaId);
  renderUploads();
  scheduleSave();
}

function initialiseCoordinateMap() {
  if (coordinateMap || !window.L) {
    if (!coordinateMap) window.setTimeout(initialiseCoordinateMap, 60);
    return;
  }
  const mapNode = document.querySelector("[data-coordinate-map]");
  coordinateMap = window.L.map(mapNode, { zoomControl:true }).setView([55.3, 86.0], 4);
  window.TouristikaMapTiles.addBaseLayer(coordinateMap, { maxZoom:19 });
  const setMarker = (lat, lng) => {
    if (!coordinateMap) return;
    if (!coordinateMarker) coordinateMarker = window.L.marker([lat, lng]).addTo(coordinateMap);
    else coordinateMarker.setLatLng([lat, lng]);
  };
  const update = (lat, lng) => {
    form.elements.lat.value = Number(lat).toFixed(6);
    form.elements.lng.value = Number(lng).toFixed(6);
    setMarker(lat, lng);
    scheduleSave();
  };
  coordinateMap.on("click", (event) => update(event.latlng.lat, event.latlng.lng));
  const coordinates = coordinateInputState();
  if (coordinates.valid && !coordinates.empty) {
    setMarker(coordinates.lat, coordinates.lng);
    coordinateMap.setView([coordinates.lat, coordinates.lng], 11);
  }
  window.setTimeout(() => coordinateMap.invalidateSize(), 100);
}

function syncCoordinateMarkerFromInputs() {
  if (!coordinateMap) return;
  const coordinates = coordinateInputState();
  if (!coordinates.valid || coordinates.empty) {
    if (coordinateMarker) {
      coordinateMap.removeLayer(coordinateMarker);
      coordinateMarker = undefined;
    }
    return;
  }
  if (!coordinateMarker) coordinateMarker = window.L.marker([coordinates.lat, coordinates.lng]).addTo(coordinateMap);
  else coordinateMarker.setLatLng([coordinates.lat, coordinates.lng]);
}

function renderPreview() {
  const payload = collectPayload();
  const type = config?.place_types?.find((item) => Number(item.id) === Number(payload.place_type_id));
  const accommodation = selectedEntityKind() === "accommodation";
  const preview = document.querySelector("[data-preview]");
  preview.replaceChildren();
  const sections = [
    ["Объект", payload.place_name || "Название не указано", [type?.name, payload.region, payload.city || payload.locality].filter(Boolean).join(" · ")],
    ["Заявитель", payload.applicant_name || "Не указано", payload.applicant_role || ""],
    ["Описание", payload.short_description || "Не указано", payload.description || ""],
    ["Публичные контакты", `${payload.public_contacts.length} контактов`, "Контакты заявителя хранятся отдельно"],
    ["Характеристики", `${payload.amenities.length} удобств`, payload.min_price !== null ? `от ${payload.min_price.toLocaleString("ru-RU")} ₽` : "Цена не указана"],
    [
      accommodation ? "Размещение и медиа" : "Медиа",
      accommodation ? `${payload.rooms_payload.length} вариантов` : `${Object.keys(payload.extra_data).length} дополнительных полей`,
      `${mediaItems.length} фотографий · ${payload.video_urls.length} видео-ссылок`,
    ],
  ];
  sections.forEach(([label, title, text]) => {
    const article = document.createElement("article");
    const small = document.createElement("small");
    const strong = document.createElement("strong");
    const paragraph = document.createElement("p");
    small.textContent = label;
    strong.textContent = title;
    paragraph.textContent = text;
    article.append(small, strong, paragraph);
    preview.append(article);
  });
}

function updateRoleUI() {
  const ownerLike = ["owner", "representative"].includes(inputValue("applicant_role"));
  document.querySelector("[data-representation-consent]").hidden = !ownerLike;
}

async function createServerDraft() {
  const response = await fetch("/api/public/submissions/drafts", {
    method:"POST",
    headers:{ "Content-Type":"application/json", Accept:"application/json" },
    credentials:"same-origin",
    body:JSON.stringify({ locale:"ru", source:"web" }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Не удалось создать черновик");
  serverDraft = {
    token:payload.draft_token,
    publicNumber:payload.public_number,
    contentVersion:payload.content_version,
    expiresAt:payload.expires_at,
  };
  await saveLocalState();
}

async function captchaToken() {
  const runtime = window.__TOURISTIKA_SUBMISSION__ || {};
  if (runtime.testCaptcha) return runtime.captchaToken;
  const adapter = window.touristikaCaptcha;
  if (!adapter || typeof adapter.execute !== "function") {
    throw new Error("CAPTCHA ещё не настроена. Повторите отправку позднее.");
  }
  return adapter.execute();
}

async function submitForm(event) {
  event.preventDefault();
  if (!validateStep(7) || uploading) {
    if (uploading) showError("Дождитесь завершения загрузки фотографий.");
    return;
  }
  clearError();
  submitButton.disabled = true;
  submitButton.textContent = "Отправляем…";
  try {
    await saveLocalState();
    await scheduleServerSync();
    const token = await captchaToken();
    const response = await fetch("/api/public/submissions", {
      method:"POST",
      headers:{ "Content-Type":"application/json", Accept:"application/json" },
      credentials:"same-origin",
      body:JSON.stringify({
        draft_token:serverDraft.token,
        idempotency_key:submitIdempotencyKey,
        captcha_token:token,
        honeypot:inputValue("website_confirm"),
      }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Не удалось отправить заявку");
    await dbClear();
    form.hidden = true;
    progress.hidden = true;
    saveStatus.hidden = true;
    document.querySelector(".submission-intro").hidden = true;
    successNode.querySelector("[data-success-number]").textContent = payload.public_number;
    const trackingLink = successNode.querySelector("[data-tracking-link]");
    trackingLink.href = payload.tracking_url;
    successNode.hidden = false;
    successNode.focus();
    dirty = false;
  } catch (error) {
    showError(error instanceof Error ? error.message : "Не удалось отправить заявку");
  } finally {
    window.touristikaCaptcha?.reset?.();
    submitButton.disabled = false;
    submitButton.textContent = "Отправить заявку";
  }
}

async function clearDraft() {
  if (!window.confirm("Очистить локальный черновик и начать заново? Загруженные файлы будут удалены из формы.")) return;
  await dbClear();
  window.location.reload();
}

form.addEventListener("input", (event) => {
  event.target.removeAttribute?.("aria-invalid");
  if (event.target === form.elements.lat || event.target === form.elements.lng) {
    syncCoordinateMarkerFromInputs();
  }
  updateRoleUI();
  scheduleSave();
});
form.addEventListener("change", scheduleSave);
form.addEventListener("submit", submitForm);
document.querySelector("[data-place-types]")?.addEventListener("change", () => {
  updateEntityTypeUI({ discardIncompatible: true });
});
nextButton.addEventListener("click", () => { if (validateStep(currentStep)) showStep(currentStep + 1); });
previousButton.addEventListener("click", () => showStep(currentStep - 1));
document.querySelector("[data-clear-draft]").addEventListener("click", () => void clearDraft());
addRoomButton?.addEventListener("click", () => {
  roomItems = collectRooms();
  roomItems.push({ client_id:makeRoomId(), floors:1, floor:1 });
  renderRooms();
  scheduleSave();
});
photoInput.addEventListener("change", (event) => {
  void handleFiles(Array.from(event.target.files || []));
  event.target.value = "";
});
["dragenter", "dragover"].forEach((name) => uploadZone.addEventListener(name, (event) => {
  event.preventDefault(); uploadZone.dataset.dragging = "true";
}));
["dragleave", "drop"].forEach((name) => uploadZone.addEventListener(name, (event) => {
  event.preventDefault(); uploadZone.dataset.dragging = "false";
}));
uploadZone.addEventListener("drop", (event) => void handleFiles(Array.from(event.dataTransfer?.files || [])));
window.addEventListener("beforeunload", (event) => {
  if (!dirty && !uploading) return;
  event.preventDefault();
  event.returnValue = "";
});

async function initialise() {
  try {
    database = await openDatabase();
    const saved = await dbGet("state", STATE_KEY);
    if (saved?.formatVersion === 1) restoreNamedValues(saved);
    const response = await fetch("/api/public/submissions/config", { headers:{ Accept:"application/json" } });
    config = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(config.detail || "Форма временно недоступна");
    renderPlaceTypes(config.place_types || []);
    if (saved?.formatVersion === 1) restoreNamedValues(saved);
    updateEntityTypeUI({ discardIncompatible: true });
    restoredNamedValues = {};
    renderAmenities(config.amenities || []);
    if (saved?.formatVersion === 1) {
      restoreAmenities(saved);
      setStatus("Черновик восстановлен с этого устройства", "saved");
    }
    if (!serverDraft) await createServerDraft();
    renderUploads();
    updateRoleUI();
    showStep(currentStep);
    void retryPendingFiles();
  } catch (error) {
    showError(error instanceof Error ? error.message : "Не удалось открыть форму");
    setStatus("Форма недоступна", "error");
    nextButton.disabled = true;
  }
}

void initialise();
