import {
  Bath,
  BedDouble,
  ChevronDown,
  House,
  ImagePlus,
  MapPinned,
  Plus,
  Sailboat,
  Save,
  Star,
  TentTree,
  Trash2,
  Trees,
  Waves,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { PageMotion } from "../../components/PageMotion";
import { crmPath } from "../../paths";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import {
  createSuperadminCamp,
  deleteSuperadminCamp,
  fetchSuperadminBaseEditor,
  updateSuperadminCamp,
  updateSuperadminCampStatus,
  uploadSuperadminMedia,
  type SuperadminBaseEditor,
} from "../session";
import { type AdminBaseApartment, type AdminBaseDraft, createEmptyAdminBaseDraft, createEmptyApartment } from "../mockData";

const markerOptions = [
  { key: "tent", label: "Кемпинг", icon: TentTree, emoji: "🏕️" },
  { key: "house", label: "Домик", icon: House, emoji: "🏠" },
  { key: "trees", label: "Лес", icon: Trees, emoji: "🌲" },
  { key: "waves", label: "Берег", icon: Waves, emoji: "🌊" },
  { key: "ship", label: "Причал", icon: Sailboat, emoji: "⛵" },
] as const;

const accentBackgrounds = [
  "from-sky-500/25 to-blue-500/10",
  "from-emerald-500/25 to-teal-500/10",
  "from-amber-500/25 to-orange-500/10",
  "from-violet-500/25 to-fuchsia-500/10",
];

type ApartmentCardProps = {
  apartment: AdminBaseApartment;
  index: number;
  uploading: boolean;
  onChange: (next: AdminBaseApartment) => void;
  onRemove: () => void;
  onAddPhotos: (files: FileList | null, index: number) => void;
};

function numberFromText(value: string) {
  const normalized = value.replace(/[^\d-]/g, "");
  return normalized ? Number(normalized) : 0;
}

function formatPriceLabel(value?: number | null) {
  const amount = Number(value || 0);
  return `${new Intl.NumberFormat("ru-RU").format(amount)} ₽`;
}

function parseCoordinates(value: string) {
  const parts = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (parts.length !== 2) {
    return { lat: null, lng: null };
  }
  const lat = Number(parts[0].replace(",", "."));
  const lng = Number(parts[1].replace(",", "."));
  return {
    lat: Number.isFinite(lat) ? lat : null,
    lng: Number.isFinite(lng) ? lng : null,
  };
}

function splitContact(value?: string | null) {
  const raw = (value || "").trim();
  if (!raw) {
    return { name: "", phone: "" };
  }
  const commaParts = raw.split(",").map((part) => part.trim()).filter(Boolean);
  if (commaParts.length >= 2) {
    return {
      name: commaParts[0],
      phone: commaParts.slice(1).join(", "),
    };
  }
  const phoneMatch = raw.match(/(\+?\d[\d\s()-]{6,})$/);
  if (!phoneMatch) {
    return { name: raw, phone: "" };
  }
  const phone = phoneMatch[1].trim();
  const name = raw.slice(0, raw.lastIndexOf(phone)).replace(/[,\s]+$/, "").trim();
  return { name: name || raw, phone };
}

function joinContact(name: string, phone: string) {
  const normalizedName = name.trim();
  const normalizedPhone = phone.trim();
  if (normalizedName && normalizedPhone) {
    return `${normalizedName}, ${normalizedPhone}`;
  }
  return normalizedName || normalizedPhone;
}

function normalizePhones(value?: string | null) {
  const items = String(value || "")
    .split(/[\n,;]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  while (items.length < 3) {
    items.push("");
  }
  return items.slice(0, 3);
}

function statusToLabel(value?: string | null): AdminBaseDraft["status"] {
  if ((value || "").toLowerCase() === "disabled") return "Отключен";
  if ((value || "").toLowerCase() === "archived") return "В архиве";
  return "Активный";
}

function statusToApi(value: AdminBaseDraft["status"]) {
  if (value === "Отключен") return "disabled";
  if (value === "В архиве") return "archived";
  return "active";
}

function markerIconFromEmoji(value?: string | null): AdminBaseDraft["markerIcon"] {
  const match = markerOptions.find((item) => item.emoji === value);
  return match?.key || "tent";
}

function emojiFromMarkerIcon(value: AdminBaseDraft["markerIcon"]) {
  return markerOptions.find((item) => item.key === value)?.emoji || "🏕️";
}

function markerSizeFromApi(value?: string | null): AdminBaseDraft["markerSize"] {
  return (value || "").toLowerCase() === "vip" ? "VIP" : "Стандарт";
}

function markerSizeToApi(value: AdminBaseDraft["markerSize"]) {
  return value === "VIP" ? "vip" : "standard";
}

function housingTypeFromApi(value?: string | null) {
  if ((value || "").toLowerCase() === "houses") return "Домики";
  if ((value || "").toLowerCase() === "rooms") return "Отель";
  return "Апартаменты";
}

function housingTypeToApi(value: string) {
  if (value === "Домики") return "houses";
  if (value === "Отель") return "rooms";
  return "apartments";
}

function roomToApartment(room: SuperadminBaseEditor["rooms"][number], index: number): AdminBaseApartment {
  return {
    id: String(room.id || `room-${index + 1}`),
    unitType: room.room_type || "Апартамент",
    name: room.name || "",
    guests: String(room.capacity ?? 0),
    singleBeds: String(room.beds_single ?? 0),
    doubleBeds: String(room.beds_double ?? 0),
    shower: room.bath_type || room.wc_type || "Нет",
    bbq: room.bbq_type || "Нет",
    sauna: room.gazebo_type || "Нет",
    pool: room.pool_type || "Нет",
    conditioner: room.has_ac ? "Да" : "Нет",
    description: room.description || "",
    weekdayPrice: String(room.price ?? 0),
    weekendPrice: String(room.price_adult ?? room.price ?? 0),
    extraGuestPrice: String(room.price_child ?? 0),
    quantity: "1",
    bookingWindow: String(room.discount_from_nights ?? 0),
    photos: (room.photos || []).map((item) => item.url),
  };
}

function campEditorToDraft(payload: SuperadminBaseEditor): AdminBaseDraft {
  const camp = payload.camp;
  const owner = splitContact(camp.owner);
  const manager = splitContact(camp.manager);
  return {
    id: String(camp.id),
    status: statusToLabel(camp.status),
    name: camp.name || "",
    lake: camp.lake_name || "",
    coordinates: camp.lat != null && camp.lng != null ? `${camp.lat}, ${camp.lng}` : "",
    address: camp.address || "",
    ownerName: owner.name,
    ownerPhone: owner.phone,
    managerName: manager.name,
    managerPhone: manager.phone,
    adminPhones: normalizePhones(camp.admin_phones),
    site: camp.site_url || "",
    accommodationType: housingTypeFromApi(camp.housing_type),
    apartmentCount: String(payload.rooms.length || 0),
    beds: String(camp.beds_count ?? 0),
    bbqPrivate: String(camp.bbq_count ?? 0),
    bbqShared: String(camp.bbq_shared_count ?? 0),
    baths: String(camp.bath_count ?? 0),
    poolsPrivate: String(camp.pools_private_count ?? 0),
    poolsShared: String(camp.pools_shared_count ?? 0),
    saunas: String(camp.sauna_count ?? 0),
    markerSize: markerSizeFromApi(camp.emoji_size),
    markerIcon: markerIconFromEmoji(camp.emoji),
    description: camp.description || "",
    minPrice: formatPriceLabel(camp.min_price),
    gallery: payload.photos.map((photo) => photo.url),
    apartments: payload.rooms.length ? payload.rooms.map(roomToApartment) : [createEmptyApartment(1)],
  };
}

function apartmentToRoomPayload(apartment: AdminBaseApartment) {
  return {
    id: /^\d+$/.test(apartment.id) ? Number(apartment.id) : undefined,
    name: apartment.name.trim(),
    room_type: apartment.unitType.trim() || "Апартамент",
    floors: 1,
    floor: 1,
    beds_single: numberFromText(apartment.singleBeds),
    beds_double: numberFromText(apartment.doubleBeds),
    bath_type: apartment.shower.trim() || "Нет",
    wc_type: apartment.shower.trim() || "Нет",
    bbq_type: apartment.bbq.trim() || "Нет",
    kitchen_type: "Нет",
    gazebo_type: apartment.sauna.trim() || "Нет",
    terrace_type: "Нет",
    pool_type: apartment.pool.trim() || "Нет",
    balcony_type: "Нет",
    has_ac: apartment.conditioner.trim().toLowerCase() !== "нет",
    price: numberFromText(apartment.weekdayPrice),
    price_adult: numberFromText(apartment.weekendPrice),
    price_child: numberFromText(apartment.extraGuestPrice),
    discount_pct: 0,
    discount_from_nights: numberFromText(apartment.bookingWindow),
    description: apartment.description.trim(),
    photos: apartment.photos.map((url, photoIndex) => ({
      url,
      cover: photoIndex === 0,
      sort: photoIndex,
    })),
  };
}

function buildCampPayload(draft: AdminBaseDraft) {
  const coordinates = parseCoordinates(draft.coordinates);
  const rooms = draft.apartments
    .map(apartmentToRoomPayload)
    .filter((room) => {
      return Boolean(
        String(room.name || "").trim() ||
          String(room.description || "").trim() ||
          Number(room.price || 0) > 0 ||
          Number(room.price_adult || 0) > 0 ||
          Number(room.price_child || 0) > 0,
      );
    });
  return {
    name: draft.name.trim(),
    lake_name: draft.lake.trim(),
    address: draft.address.trim(),
    lat: coordinates.lat,
    lng: coordinates.lng,
    status: statusToApi(draft.status),
    emoji: emojiFromMarkerIcon(draft.markerIcon),
    emoji_size: markerSizeToApi(draft.markerSize),
    description: draft.description.trim(),
    housing_type: housingTypeToApi(draft.accommodationType),
    owner: joinContact(draft.ownerName, draft.ownerPhone),
    manager: joinContact(draft.managerName, draft.managerPhone),
    admin_phones: draft.adminPhones.map((phone) => phone.trim()).filter(Boolean).join(", "),
    site_url: draft.site.trim(),
    min_price: numberFromText(draft.minPrice),
    bbq_count: numberFromText(draft.bbqPrivate),
    bbq_shared_count: numberFromText(draft.bbqShared),
    bath_count: numberFromText(draft.baths),
    sauna_count: numberFromText(draft.saunas),
    pools_private_count: numberFromText(draft.poolsPrivate),
    pools_shared_count: numberFromText(draft.poolsShared),
    beds_count: numberFromText(draft.beds),
    photos: draft.gallery.map((url, index) => ({ url, cover: index === 0, sort: index })),
    rooms,
  };
}

function ApartmentCard({ apartment, index, uploading, onChange, onRemove, onAddPhotos }: ApartmentCardProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const update = <K extends keyof AdminBaseApartment>(field: K, value: AdminBaseApartment[K]) => {
    onChange({ ...apartment, [field]: value });
  };

  return (
    <div className="rounded-3xl border border-border bg-background/65 p-5">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          onAddPhotos(event.target.files, index);
          event.currentTarget.value = "";
        }}
      />

      <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Апартамент #{index + 1}</p>
          <h3 className="mt-1 text-lg font-semibold text-foreground">{apartment.name || "Новая карточка апартамента"}</h3>
        </div>
        <button type="button" className="admin-button gap-2 text-rose-300 hover:text-rose-200" onClick={onRemove}>
          <Trash2 className="h-4 w-4" />
          Удалить
        </button>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-8">
        <AdminField label="Тип размещения" className="xl:col-span-2">
          <div className="relative">
            <select className="admin-input appearance-none pr-10" value={apartment.unitType} onChange={(event) => update("unitType", event.target.value)}>
              {["Апартамент", "Домик", "Номер", "Шале"].map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>
        </AdminField>
        <AdminField label="Название" className="xl:col-span-2">
          <input className="admin-input" value={apartment.name} onChange={(event) => update("name", event.target.value)} />
        </AdminField>
        <AdminField label="Гостей">
          <input className="admin-input text-center" value={apartment.guests} onChange={(event) => update("guests", event.target.value)} />
        </AdminField>
        <AdminField label="Односпальных">
          <input className="admin-input text-center" value={apartment.singleBeds} onChange={(event) => update("singleBeds", event.target.value)} />
        </AdminField>
        <AdminField label="Двуспальных">
          <input className="admin-input text-center" value={apartment.doubleBeds} onChange={(event) => update("doubleBeds", event.target.value)} />
        </AdminField>
        <AdminField label="Количество">
          <input className="admin-input text-center" value={apartment.quantity} onChange={(event) => update("quantity", event.target.value)} />
        </AdminField>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        {[
          { field: "shower", label: "Душ / WC" },
          { field: "bbq", label: "BBQ" },
          { field: "sauna", label: "Сауна / зона" },
          { field: "pool", label: "Бассейн" },
          { field: "conditioner", label: "Кондиционер" },
        ].map((item) => (
          <AdminField key={item.field} label={item.label}>
            <div className="relative">
              <select
                className="admin-input appearance-none pr-10"
                value={apartment[item.field as keyof AdminBaseApartment] as string}
                onChange={(event) => update(item.field as keyof AdminBaseApartment, event.target.value)}
              >
                {[apartment[item.field as keyof AdminBaseApartment] as string, "Индивидуальный", "Общий", "Нет", "Да"]
                  .filter((option, optionIndex, all) => all.indexOf(option) === optionIndex)
                  .map((option) => (
                    <option key={option}>{option}</option>
                  ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </AdminField>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-6">
        <AdminField label="Описание" className="lg:col-span-2">
          <input className="admin-input" value={apartment.description} onChange={(event) => update("description", event.target.value)} />
        </AdminField>
        <AdminField label="Базовая цена, ₽">
          <input className="admin-input text-center" value={apartment.weekdayPrice} onChange={(event) => update("weekdayPrice", event.target.value)} />
        </AdminField>
        <AdminField label="Тариф взрослый, ₽">
          <input className="admin-input text-center" value={apartment.weekendPrice} onChange={(event) => update("weekendPrice", event.target.value)} />
        </AdminField>
        <AdminField label="Тариф ребёнок, ₽">
          <input className="admin-input text-center" value={apartment.extraGuestPrice} onChange={(event) => update("extraGuestPrice", event.target.value)} />
        </AdminField>
        <AdminField label="Ночей до скидки">
          <input className="admin-input text-center" value={apartment.bookingWindow} onChange={(event) => update("bookingWindow", event.target.value)} />
        </AdminField>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        {apartment.photos.map((photo, photoIndex) => (
          <div key={`${apartment.id}-${photo}`} className={`relative h-20 w-28 overflow-hidden rounded-2xl border border-border bg-gradient-to-br ${accentBackgrounds[photoIndex % accentBackgrounds.length]}`}>
            <img src={photo} alt={apartment.name || `Фото ${photoIndex + 1}`} className="absolute inset-0 h-full w-full object-cover" />
            {photoIndex === 0 ? (
              <div className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-card/85 px-2 py-1 text-[11px] font-semibold text-foreground">
                <Star className="h-3 w-3 text-blue-500" />
                Обложка
              </div>
            ) : null}
          </div>
        ))}
        <button type="button" className="admin-button min-h-20 min-w-28 justify-center gap-2" onClick={() => inputRef.current?.click()} disabled={uploading}>
          <ImagePlus className="h-4 w-4" />
          {uploading ? "Загрузка..." : "Фото"}
        </button>
      </div>
    </div>
  );
}

export default function AdminBaseEditPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isNew = !id || id === "new";
  const galleryInputRef = useRef<HTMLInputElement | null>(null);
  const [draft, setDraft] = useState<AdminBaseDraft>(() => createEmptyAdminBaseDraft());
  const [linkedAccounts, setLinkedAccounts] = useState<SuperadminBaseEditor["linked_accounts"]>([]);
  const [isLoading, setIsLoading] = useState(!isNew);
  const [isSaving, setIsSaving] = useState(false);
  const [uploadingTarget, setUploadingTarget] = useState<string | "camp" | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  function loadExistingBase(campId: number, signal?: AbortSignal) {
    setIsLoading(true);
    setErrorMessage("");
    return fetchSuperadminBaseEditor(campId, signal)
      .then((payload) => {
        setDraft(campEditorToDraft(payload));
        setLinkedAccounts(payload.linked_accounts);
      })
      .catch((error: unknown) => {
        if (signal?.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить карточку базы");
      })
      .finally(() => {
        if (!signal?.aborted) {
          setIsLoading(false);
        }
      });
  }

  useEffect(() => {
    if (isNew) {
      setDraft(createEmptyAdminBaseDraft());
      setLinkedAccounts([]);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    loadExistingBase(Number(id), controller.signal);

    return () => controller.abort();
  }, [id, isNew]);

  const updateField = <K extends keyof AdminBaseDraft>(field: K, value: AdminBaseDraft[K]) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const updateAdminPhone = (index: number, value: string) => {
    setDraft((current) => ({
      ...current,
      adminPhones: current.adminPhones.map((phone, phoneIndex) => (phoneIndex === index ? value : phone)),
    }));
  };

  const updateApartment = (index: number, apartment: AdminBaseApartment) => {
    setDraft((current) => ({
      ...current,
      apartments: current.apartments.map((item, itemIndex) => (itemIndex === index ? apartment : item)),
    }));
  };

  const addApartment = () => {
    setDraft((current) => ({
      ...current,
      apartments: [...current.apartments, createEmptyApartment(current.apartments.length + 1)],
      apartmentCount: String(current.apartments.length + 1),
    }));
  };

  const removeApartment = (index: number) => {
    setDraft((current) => {
      const apartments = current.apartments.length > 1 ? current.apartments.filter((_, itemIndex) => itemIndex !== index) : current.apartments;
      return {
        ...current,
        apartments,
        apartmentCount: String(apartments.length),
      };
    });
  };

  async function handleSave() {
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      if (!draft.name.trim()) {
        throw new Error("Укажите название базы");
      }

      const payload = buildCampPayload(draft);
      if (isNew) {
        const response = await createSuperadminCamp(payload);
        setSuccessMessage("База создана.");
        navigate(crmPath(`/admin/bases/${response.id}`), { replace: true });
        return;
      }

      await updateSuperadminCamp(Number(draft.id), payload);
      await loadExistingBase(Number(draft.id));
      setSuccessMessage("Карточка базы сохранена.");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось сохранить базу");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleArchive() {
    if (isNew) {
      return;
    }
    if (!window.confirm("Отправить базу в архив?")) {
      return;
    }
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      await updateSuperadminCampStatus(Number(draft.id), "archived");
      setDraft((current) => ({ ...current, status: "В архиве" }));
      setSuccessMessage("База отправлена в архив.");
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось архивировать базу");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (isNew) {
      return;
    }
    if (draft.status !== "В архиве") {
      setErrorMessage("Удалять можно только базу, которая уже находится в архиве.");
      return;
    }
    if (!window.confirm("Удалить архивную базу безвозвратно?")) {
      return;
    }
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      await deleteSuperadminCamp(Number(draft.id));
      navigate(crmPath("/admin/archive"), { replace: true });
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось удалить базу");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCampPhotoUpload(files: FileList | null) {
    if (!files?.length) {
      return;
    }
    try {
      setUploadingTarget("camp");
      setErrorMessage("");
      const campId = !isNew ? Number(draft.id) : undefined;
      const urls: string[] = [];
      for (const file of Array.from(files)) {
        const uploaded = await uploadSuperadminMedia(file, { campId });
        urls.push(uploaded.url);
      }
      setDraft((current) => ({
        ...current,
        gallery: [...current.gallery, ...urls].slice(0, 20),
      }));
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить фотографии базы");
    } finally {
      setUploadingTarget(null);
    }
  }

  async function handleApartmentPhotoUpload(files: FileList | null, apartmentIndex: number) {
    if (!files?.length) {
      return;
    }
    const targetId = draft.apartments[apartmentIndex]?.id || `room-${apartmentIndex}`;
    try {
      setUploadingTarget(targetId);
      setErrorMessage("");
      const campId = !isNew ? Number(draft.id) : undefined;
      const urls: string[] = [];
      for (const file of Array.from(files)) {
        const uploaded = await uploadSuperadminMedia(file, { campId, roomIndex: apartmentIndex });
        urls.push(uploaded.url);
      }
      setDraft((current) => ({
        ...current,
        apartments: current.apartments.map((apartment, index) =>
          index === apartmentIndex ? { ...apartment, photos: [...apartment.photos, ...urls].slice(0, 5) } : apartment,
        ),
      }));
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить фотографии апартамента");
    } finally {
      setUploadingTarget(null);
    }
  }

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="p-5 sm:p-6 lg:p-8">
        <input
          ref={galleryInputRef}
          type="file"
          multiple
          accept="image/*"
          className="hidden"
          onChange={(event) => {
            handleCampPhotoUpload(event.target.files);
            event.currentTarget.value = "";
          }}
        />

        <div className="flex flex-col gap-4 border-b border-border pb-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {draft.id === "new" ? "Новая база" : `База #${draft.id}`}
            </p>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">
              {draft.id === "new" ? "Создание базы отдыха" : `Редактирование базы «${draft.name || "Без названия"}»`}
            </h2>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Полный редактор каталога: контакты, публикация, фотографии, визуальный маркер и структура апартаментов.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button type="button" className="admin-button" onClick={handleArchive} disabled={isSaving || isNew}>
              В архив
            </button>
            <button type="button" className="admin-button text-rose-300 hover:text-rose-200" onClick={handleDelete} disabled={isSaving || isNew}>
              Удалить
            </button>
            <button type="button" className="admin-primary-button gap-2" onClick={handleSave} disabled={isSaving || isLoading}>
              <Save className="h-4 w-4" />
              {isSaving ? "Сохраняем..." : "Сохранить"}
            </button>
          </div>
        </div>

        {errorMessage ? (
          <div className="mt-6 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{errorMessage}</div>
        ) : null}
        {successMessage ? (
          <div className="mt-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">{successMessage}</div>
        ) : null}

        {isLoading ? (
          <div className="py-10 text-center text-sm text-muted-foreground">Загружаем карточку базы…</div>
        ) : (
          <div className="mt-6 space-y-8">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => updateField("status", "Активный")}
                className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                  draft.status === "Активный" ? "bg-emerald-500 text-white" : "border border-border bg-background/70 text-muted-foreground hover:bg-accent"
                }`}
              >
                Активный
              </button>
              <button
                type="button"
                onClick={() => updateField("status", "Отключен")}
                className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                  draft.status === "Отключен" ? "bg-amber-500 text-white" : "border border-border bg-background/70 text-muted-foreground hover:bg-accent"
                }`}
              >
                Отключен
              </button>
              <AdminStatusBadge tone={draft.status === "Активный" ? "success" : draft.status === "Отключен" ? "warning" : "neutral"}>
                {draft.status}
              </AdminStatusBadge>
              {linkedAccounts.length ? (
                <div className="flex flex-wrap gap-2">
                  {linkedAccounts.map((account) => (
                    <span key={account.id} className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-foreground">
                      {account.display_name || account.email || `#${account.id}`}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="grid gap-4 xl:grid-cols-4">
              <AdminField label="Название базы">
                <input className="admin-input" value={draft.name} onChange={(event) => updateField("name", event.target.value)} />
              </AdminField>
              <AdminField label="Озеро">
                <input className="admin-input" value={draft.lake} onChange={(event) => updateField("lake", event.target.value)} />
              </AdminField>
              <AdminField label="Координаты">
                <input className="admin-input" value={draft.coordinates} onChange={(event) => updateField("coordinates", event.target.value)} />
              </AdminField>
              <AdminField label="Минимальная цена">
                <input className="admin-input" value={draft.minPrice} onChange={(event) => updateField("minPrice", event.target.value)} />
              </AdminField>
            </div>

            <AdminField label="Адрес">
              <input className="admin-input" value={draft.address} onChange={(event) => updateField("address", event.target.value)} />
            </AdminField>

            <div className="grid gap-4 xl:grid-cols-4">
              <AdminField label="Владелец — ФИО">
                <input className="admin-input" value={draft.ownerName} onChange={(event) => updateField("ownerName", event.target.value)} />
              </AdminField>
              <AdminField label="Владелец — телефон">
                <input className="admin-input" value={draft.ownerPhone} onChange={(event) => updateField("ownerPhone", event.target.value)} />
              </AdminField>
              <AdminField label="Управляющий — ФИО">
                <input className="admin-input" value={draft.managerName} onChange={(event) => updateField("managerName", event.target.value)} />
              </AdminField>
              <AdminField label="Управляющий — телефон">
                <input className="admin-input" value={draft.managerPhone} onChange={(event) => updateField("managerPhone", event.target.value)} />
              </AdminField>
            </div>

            <div className="grid gap-4 xl:grid-cols-4">
              {draft.adminPhones.map((phone, index) => (
                <AdminField key={`phone-${index}`} label={`Телефон администратора №${index + 1}`}>
                  <input className="admin-input" value={phone} onChange={(event) => updateAdminPhone(index, event.target.value)} />
                </AdminField>
              ))}
              <AdminField label="Сайт базы">
                <input className="admin-input" value={draft.site} onChange={(event) => updateField("site", event.target.value)} />
              </AdminField>
            </div>

            <div className="space-y-5 border-t border-border pt-8">
              <div className="flex flex-wrap items-center gap-3">
                <MapPinned className="h-5 w-5 text-blue-500" />
                <h3 className="text-lg font-semibold text-foreground">Параметры размещения и инфраструктуры</h3>
              </div>

              <div className="grid gap-4 xl:grid-cols-6">
                <AdminField label="Тип жилья" className="xl:col-span-2">
                  <div className="relative">
                    <select
                      className="admin-input appearance-none pr-10"
                      value={draft.accommodationType}
                      onChange={(event) => updateField("accommodationType", event.target.value)}
                    >
                      {["Апартаменты", "Домики", "Отель"].map((option) => (
                        <option key={option}>{option}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  </div>
                </AdminField>
                <AdminField label="Количество апартаментов">
                  <input className="admin-input" value={draft.apartmentCount} onChange={(event) => updateField("apartmentCount", event.target.value)} />
                </AdminField>
                <AdminField label="Спальных мест">
                  <input className="admin-input" value={draft.beds} onChange={(event) => updateField("beds", event.target.value)} />
                </AdminField>
                <AdminField label="Зон BBQ индивидуальных">
                  <input className="admin-input" value={draft.bbqPrivate} onChange={(event) => updateField("bbqPrivate", event.target.value)} />
                </AdminField>
                <AdminField label="Зон BBQ общих">
                  <input className="admin-input" value={draft.bbqShared} onChange={(event) => updateField("bbqShared", event.target.value)} />
                </AdminField>
                <AdminField label="Бань">
                  <input className="admin-input" value={draft.baths} onChange={(event) => updateField("baths", event.target.value)} />
                </AdminField>
                <AdminField label="Бассейнов индивидуальных">
                  <input className="admin-input" value={draft.poolsPrivate} onChange={(event) => updateField("poolsPrivate", event.target.value)} />
                </AdminField>
                <AdminField label="Бассейнов общих">
                  <input className="admin-input" value={draft.poolsShared} onChange={(event) => updateField("poolsShared", event.target.value)} />
                </AdminField>
                <AdminField label="Саун">
                  <input className="admin-input" value={draft.saunas} onChange={(event) => updateField("saunas", event.target.value)} />
                </AdminField>
              </div>
            </div>

            <div className="space-y-5 border-t border-border pt-8">
              <div className="flex flex-wrap items-center gap-3">
                <Star className="h-5 w-5 text-blue-500" />
                <h3 className="text-lg font-semibold text-foreground">Фотографии и визуальный маркер</h3>
              </div>

              <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                <div className="rounded-3xl border border-border bg-background/60 p-5">
                  <div className="flex flex-wrap gap-3">
                    {draft.gallery.map((photo, photoIndex) => (
                      <div
                        key={photo}
                        className={`relative h-28 w-36 overflow-hidden rounded-2xl border border-border bg-gradient-to-br ${accentBackgrounds[photoIndex % accentBackgrounds.length]}`}
                      >
                        <img src={photo} alt={draft.name || `Фото ${photoIndex + 1}`} className="absolute inset-0 h-full w-full object-cover" />
                        <div className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-card/85 px-2.5 py-1 text-[11px] font-semibold text-foreground">
                          {photoIndex === 0 ? <Star className="h-3 w-3 text-blue-500" /> : null}
                          {photoIndex === 0 ? "Обложка" : `Фото ${photoIndex + 1}`}
                        </div>
                      </div>
                    ))}
                    <button type="button" className="admin-button min-h-28 min-w-36 justify-center gap-2" onClick={() => galleryInputRef.current?.click()} disabled={uploadingTarget === "camp"}>
                      <ImagePlus className="h-4 w-4" />
                      {uploadingTarget === "camp" ? "Загрузка..." : "Загрузить фото"}
                    </button>
                  </div>
                  <p className="mt-3 text-xs text-muted-foreground">До 20 фотографий. Первое фото используется как обложка в карточке базы.</p>
                </div>

                <div className="rounded-3xl border border-border bg-background/60 p-5">
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                      {(["Стандарт", "VIP"] as const).map((size) => (
                        <button
                          key={size}
                          type="button"
                          onClick={() => updateField("markerSize", size)}
                          className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                            draft.markerSize === size ? "bg-blue-500 text-white" : "border border-border bg-background/70 text-muted-foreground hover:bg-accent"
                          }`}
                        >
                          {size}
                        </button>
                      ))}
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      {markerOptions.map((option) => {
                        const Icon = option.icon;
                        const isSelected = draft.markerIcon === option.key;
                        return (
                          <button
                            key={option.key}
                            type="button"
                            onClick={() => updateField("markerIcon", option.key)}
                            className={`flex flex-col items-center gap-2 rounded-2xl border p-3 text-sm transition ${
                              isSelected ? "border-blue-500 bg-blue-500/10 text-foreground" : "border-border bg-background/75 text-muted-foreground hover:bg-accent"
                            }`}
                          >
                            <Icon className={`h-5 w-5 ${isSelected ? "text-blue-500" : "text-muted-foreground"}`} />
                            <span>{option.label}</span>
                          </button>
                        );
                      })}
                    </div>

                    <div className="rounded-2xl border border-border bg-card/75 p-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Предпросмотр карточки</p>
                      <div className="mt-3 flex items-center justify-between rounded-2xl border border-border bg-background/80 px-4 py-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">{draft.name || "Новая база"}</p>
                          <p className="text-xs text-muted-foreground">{draft.lake || "Озеро не указано"}</p>
                        </div>
                        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-500">
                          {(() => {
                            const SelectedIcon = markerOptions.find((option) => option.key === draft.markerIcon)?.icon ?? TentTree;
                            return <SelectedIcon className="h-5 w-5" />;
                          })()}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-3 border-t border-border pt-8">
              <div className="flex items-center gap-3">
                <Bath className="h-5 w-5 text-blue-500" />
                <h3 className="text-lg font-semibold text-foreground">Описание базы</h3>
              </div>
              <textarea className="admin-input min-h-28 resize-y" value={draft.description} onChange={(event) => updateField("description", event.target.value)} />
            </div>

            <div className="space-y-5 border-t border-border pt-8">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-3">
                  <BedDouble className="h-5 w-5 text-blue-500" />
                  <h3 className="text-lg font-semibold text-foreground">Описание апартаментов</h3>
                </div>
                <button type="button" className="admin-primary-button gap-2" onClick={addApartment}>
                  <Plus className="h-4 w-4" />
                  Добавить апартамент
                </button>
              </div>

              <div className="space-y-4">
                {draft.apartments.map((apartment, index) => (
                  <ApartmentCard
                    key={apartment.id}
                    apartment={apartment}
                    index={index}
                    uploading={uploadingTarget === apartment.id}
                    onChange={(next) => updateApartment(index, next)}
                    onRemove={() => removeApartment(index)}
                    onAddPhotos={handleApartmentPhotoUpload}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </AdminCard>
    </PageMotion>
  );
}
