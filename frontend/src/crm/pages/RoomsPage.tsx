import { BedDouble, Check, ChevronDown, Image as ImageIcon, Plus, Trash2, Users } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { MediaEditorSection } from "../components/MediaEditorSection";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageLoadingState } from "../components/PageLoadingState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { SensitiveChangeModal } from "../components/SensitiveChangeModal";
import { buildMediaItems, captureVideoPosterFile, splitMediaItems } from "../mediaTools";
import {
  createCrmChangeRequest,
  deleteCrmRoom,
  fetchCrmCampRooms,
  fetchCrmCamps,
  uploadCrmMedia,
  type CrmCamp,
  type CrmRoomOption,
  type CrmRoomUpsertPayload,
} from "../session";

type RoomFormState = {
  id: number | null;
  name: string;
  roomType: string;
  floors: string;
  floor: string;
  singleBeds: string;
  doubleBeds: string;
  bathType: string;
  wcType: string;
  bbqType: string;
  kitchenType: string;
  gazeboType: string;
  terraceType: string;
  poolType: string;
  balconyType: string;
  hasAc: boolean;
  priceAdult: string;
  priceChild: string;
  price: string;
  discountPct: string;
  discountFromNights: string;
  description: string;
  photos: string[];
  videoUrl: string;
  videoPosterUrl: string;
  videoSourceKind: "upload" | "external";
};

const emptyRoomForm: RoomFormState = {
  id: null,
  name: "",
  roomType: "Апартамент",
  floors: "1",
  floor: "1",
  singleBeds: "0",
  doubleBeds: "1",
  bathType: "Нет",
  wcType: "Нет",
  bbqType: "Нет",
  kitchenType: "Нет",
  gazeboType: "Нет",
  terraceType: "Нет",
  poolType: "Нет",
  balconyType: "Нет",
  hasAc: false,
  priceAdult: "0",
  priceChild: "0",
  price: "0",
  discountPct: "0",
  discountFromNights: "0",
  description: "",
  photos: [],
  videoUrl: "",
  videoPosterUrl: "",
  videoSourceKind: "upload",
};

function formatCurrency(value: number | null | undefined) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("ru-RU").format(amount) + " ₽";
}

function buildFeatureList(room: CrmRoomOption) {
  const features = [
    room.bath_type && room.bath_type !== "Нет" ? `Душ: ${room.bath_type}` : "",
    room.wc_type && room.wc_type !== "Нет" ? `WC: ${room.wc_type}` : "",
    room.bbq_type && room.bbq_type !== "Нет" ? `BBQ: ${room.bbq_type}` : "",
    room.kitchen_type && room.kitchen_type !== "Нет" ? `Кухня: ${room.kitchen_type}` : "",
    room.pool_type && room.pool_type !== "Нет" ? `Бассейн: ${room.pool_type}` : "",
    room.has_ac ? "Кондиционер" : "",
  ].filter(Boolean);
  return features.length ? features : ["Удобства пока не указаны"];
}

function toRoomForm(room: CrmRoomOption): RoomFormState {
  const media = splitMediaItems(room.media, (room.photos || []).map((item) => item.url));
  return {
    id: room.id,
    name: room.name || "",
    roomType: room.room_type || "Апартамент",
    floors: String(room.floors ?? 1),
    floor: String(room.floor ?? 1),
    singleBeds: String(room.beds_single ?? 0),
    doubleBeds: String(room.beds_double ?? 0),
    bathType: room.bath_type || "Нет",
    wcType: room.wc_type || "Нет",
    bbqType: room.bbq_type || "Нет",
    kitchenType: room.kitchen_type || "Нет",
    gazeboType: room.gazebo_type || "Нет",
    terraceType: room.terrace_type || "Нет",
    poolType: room.pool_type || "Нет",
    balconyType: room.balcony_type || "Нет",
    hasAc: Boolean(room.has_ac),
    priceAdult: String(room.price_adult ?? 0),
    priceChild: String(room.price_child ?? 0),
    price: String(room.price ?? 0),
    discountPct: String(room.discount_pct ?? 0),
    discountFromNights: String(room.discount_from_nights ?? 0),
    description: room.description || "",
    photos: media.photos,
    videoUrl: media.videoUrl,
    videoPosterUrl: media.videoPosterUrl,
    videoSourceKind: media.videoSourceKind,
  };
}

function toRoomPayload(form: RoomFormState): CrmRoomUpsertPayload {
  return {
    name: form.name,
    room_type: form.roomType,
    floors: Number(form.floors || 1),
    floor: Number(form.floor || 1),
    beds_single: Number(form.singleBeds || 0),
    beds_double: Number(form.doubleBeds || 0),
    bath_type: form.bathType,
    wc_type: form.wcType,
    bbq_type: form.bbqType,
    kitchen_type: form.kitchenType,
    gazebo_type: form.gazeboType,
    terrace_type: form.terraceType,
    pool_type: form.poolType,
    balcony_type: form.balconyType,
    has_ac: form.hasAc,
    price_adult: Number(form.priceAdult || 0),
    price_child: Number(form.priceChild || 0),
    price: Number(form.price || 0),
    discount_pct: Number(form.discountPct || 0),
    discount_from_nights: Number(form.discountFromNights || 0),
    description: form.description,
    media: buildMediaItems(form.photos, form.videoUrl, form.videoPosterUrl, form.videoSourceKind),
  };
}

export default function RoomsPage() {
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [rooms, setRooms] = useState<CrmRoomOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [roomUploadKey, setRoomUploadKey] = useState<null | "photos" | "video" | "poster">(null);
  const [deleteRoomId, setDeleteRoomId] = useState<number | null>(null);
  const [formError, setFormError] = useState("");
  const [roomForm, setRoomForm] = useState<RoomFormState>(emptyRoomForm);
  const [pendingApproval, setPendingApproval] = useState<null | { operation: string; payload: Record<string, unknown>; successPending: string; successApplied: string }>(null);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    fetchCrmCamps(controller.signal)
      .then((items) => {
        setCamps(items);
        setSelectedCampId((current) => {
          if (!items.length) {
            return null;
          }
          if (current && items.some((item) => item.id === current)) {
            return current;
          }
          return items[0].id;
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить базы");
        setCamps([]);
        setSelectedCampId(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedCampId) {
      setRooms([]);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    fetchCrmCampRooms(selectedCampId, controller.signal)
      .then((items) => {
        setRooms(items);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить апартаменты");
        setRooms([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedCampId, reloadKey]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId) {
      setFormError("Сначала выберите базу.");
      return;
    }
    try {
      setIsSaving(true);
      setFormError("");
      const payload = toRoomPayload(roomForm);
      setIsModalOpen(false);
      setPendingApproval({
        operation: roomForm.id ? "room_update" : "room_create",
        payload: roomForm.id ? ({ room_id: roomForm.id, data: payload } as Record<string, unknown>) : (payload as Record<string, unknown>),
        successPending: roomForm.id ? "Изменение тарифов отправлено на подтверждение." : "Новый апартамент отправлен на подтверждение.",
        successApplied: roomForm.id ? "Изменение тарифов применено под вашу ответственность." : "Новый апартамент применён под вашу ответственность.",
      });
      setRoomForm(emptyRoomForm);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось сохранить апартамент");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(roomId: number) {
    if (!selectedCampId) {
      return;
    }
    try {
      setDeleteRoomId(roomId);
      setErrorMessage("");
      setSuccessMessage("");
      await deleteCrmRoom(selectedCampId, roomId);
      setSuccessMessage("Апартамент удалён.");
      setReloadKey((value) => value + 1);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось удалить апартамент");
    } finally {
      setDeleteRoomId(null);
    }
  }

  async function uploadRoomPhotos(files: FileList | null) {
    if (!selectedCampId || !files?.length) {
      return;
    }
    try {
      setRoomUploadKey("photos");
      setFormError("");
      const uploaded = await Promise.all(
        Array.from(files)
          .slice(0, Math.max(0, 5 - roomForm.photos.length))
          .map((file) =>
            uploadCrmMedia(file, {
              campId: selectedCampId,
              roomIndex: roomForm.id ? Number(roomForm.id) : undefined,
            }),
          ),
      );
      setRoomForm((current) => ({
        ...current,
        photos: [...current.photos, ...uploaded.map((item) => item.url)].slice(0, 5),
      }));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось загрузить фотографии апартамента");
    } finally {
      setRoomUploadKey(null);
    }
  }

  async function uploadRoomVideo(files: FileList | null) {
    if (!selectedCampId || !files?.length) {
      return;
    }
    try {
      setRoomUploadKey("video");
      setFormError("");
      const uploaded = await uploadCrmMedia(files[0], {
        campId: selectedCampId,
        roomIndex: roomForm.id ? Number(roomForm.id) : undefined,
      });
      setRoomForm((current) => ({
        ...current,
        videoUrl: uploaded.url,
        videoSourceKind: "upload",
      }));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось загрузить видео апартамента");
    } finally {
      setRoomUploadKey(null);
    }
  }

  async function uploadRoomPoster(files: FileList | null) {
    if (!selectedCampId || !files?.length) {
      return;
    }
    try {
      setRoomUploadKey("poster");
      setFormError("");
      const uploaded = await uploadCrmMedia(files[0], {
        campId: selectedCampId,
        roomIndex: roomForm.id ? Number(roomForm.id) : undefined,
      });
      setRoomForm((current) => ({
        ...current,
        videoPosterUrl: uploaded.url,
      }));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось загрузить обложку видео");
    } finally {
      setRoomUploadKey(null);
    }
  }

  async function captureRoomPoster(videoEl: HTMLVideoElement | null) {
    if (!selectedCampId) {
      return;
    }
    try {
      setRoomUploadKey("poster");
      setFormError("");
      const file = await captureVideoPosterFile(videoEl, roomForm.id ? `room-${roomForm.id}` : "room-new");
      const uploaded = await uploadCrmMedia(file, {
        campId: selectedCampId,
        roomIndex: roomForm.id ? Number(roomForm.id) : undefined,
      });
      setRoomForm((current) => ({
        ...current,
        videoPosterUrl: uploaded.url,
      }));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось выбрать кадр для обложки");
    } finally {
      setRoomUploadKey(null);
    }
  }

  async function submitSensitiveRoomChange(applyMode: "pending_review" | "apply_with_responsibility", comment: string) {
    if (!selectedCampId || !pendingApproval) {
      return;
    }
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      await createCrmChangeRequest(selectedCampId, {
        operation: pendingApproval.operation,
        payload: pendingApproval.payload,
        request_comment: comment || undefined,
        apply_mode: applyMode,
      });
      setSuccessMessage(applyMode === "pending_review" ? pendingApproval.successPending : pendingApproval.successApplied);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось обработать чувствительное изменение");
    } finally {
      setIsSaving(false);
      setPendingApproval(null);
    }
  }

  const hasCampOptions = camps.length > 0;
  const hasRooms = rooms.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        title="Апартаменты и тарифы"
        description="Рабочий список реальных апартаментов по выбранной базе с редактированием тарифов, вместимости и удобств."
        actions={
          <button
            type="button"
            className="brand-button w-full gap-2 sm:w-auto disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => {
              setRoomForm(emptyRoomForm);
              setFormError("");
              setIsModalOpen(true);
            }}
            disabled={!selectedCampId}
          >
            <Plus className="h-4 w-4" />
            Добавить апартамент
          </button>
        }
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,260px)_auto] sm:items-center sm:justify-between">
          <div className="relative">
            <select
              className="soft-input appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60"
              value={selectedCampId ?? ""}
              onChange={(event) => setSelectedCampId(event.target.value ? Number(event.target.value) : null)}
              disabled={!hasCampOptions || isLoading}
            >
              {hasCampOptions ? (
                camps.map((camp) => (
                  <option key={camp.id} value={camp.id}>
                    {camp.name}
                  </option>
                ))
              ) : (
                <option value="">Нет доступных баз</option>
              )}
            </select>
            <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          </div>

          <button type="button" className="soft-button" onClick={() => setReloadKey((value) => value + 1)}>
            Обновить список
          </button>
        </div>
      </section>

      {errorMessage ? (
        <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
          {errorMessage}
        </section>
      ) : null}

      {successMessage ? (
        <section className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-4 text-sm text-emerald-200">
          {successMessage}
        </section>
      ) : null}

      {isLoading ? (
        <section className="glass-card p-6">
          <PageLoadingState blocks={2} columnsClassName="xl:grid-cols-2" blockHeightClassName="h-[23rem]" />
        </section>
      ) : hasRooms ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {rooms.map((room) => {
            const previewMedia = splitMediaItems(room.media, (room.photos || []).map((item) => item.url));
            const previewImage = room.photo_main || previewMedia.photos[0] || null;
            return (
            <article key={room.id} className="glass-card overflow-hidden transition hover:-translate-y-0.5">
              <div className="grid md:grid-cols-[220px_1fr]">
                <div className="relative flex min-h-56 items-center justify-center border-b border-border bg-background/70 md:border-b-0 md:border-r">
                  {previewImage ? (
                    <img src={previewImage} alt={room.name || "Апартамент"} className="absolute inset-0 h-full w-full object-cover" />
                  ) : (
                    <>
                      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(229,211,179,0.22),transparent_38%)]" />
                      <ImageIcon className="relative h-9 w-9 text-muted-foreground" />
                    </>
                  )}

                  <span className="absolute left-4 top-4 rounded-full border border-border bg-card/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    {room.room_type || "Апартамент"}
                  </span>
                </div>

                <div className="p-6">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <h2 className="truncate text-xl font-semibold tracking-[-0.04em] text-foreground">{room.name || `Апартамент #${room.id}`}</h2>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {room.description || "Описание пока не заполнено. Добавьте детали, чтобы менеджерам и клиентам было проще ориентироваться."}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-border bg-background/70 px-4 py-3 text-right">
                      <div className="text-lg font-semibold text-foreground">{formatCurrency(room.price)}</div>
                      <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">базовый тариф</div>
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-4 text-sm text-muted-foreground">
                    <span className="inline-flex items-center gap-2">
                      <Users className="h-4 w-4 text-[#E5D3B3]" />
                      до {room.capacity || 0} гостей
                    </span>
                    <span className="inline-flex items-center gap-2">
                      <BedDouble className="h-4 w-4 text-[#E5D3B3]" />
                      {room.beds_single || 0} односп., {room.beds_double || 0} двусп.
                    </span>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
                    {buildFeatureList(room).map((feature) => (
                      <span key={`${room.id}-${feature}`} className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-3 py-1.5 text-sm text-foreground">
                        <Check className="h-3.5 w-3.5 text-[#E5D3B3]" />
                        {feature}
                      </span>
                    ))}
                  </div>

                  <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <span className="rounded-2xl border border-border bg-background/70 px-4 py-2 text-sm text-muted-foreground">
                      Тарифы: <strong className="font-semibold text-foreground">{formatCurrency(room.price_adult ?? room.price)}</strong> взрослый,{" "}
                      <strong className="font-semibold text-foreground">{formatCurrency(room.price_child)}</strong> ребёнок
                    </span>
                    <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
                      <button
                        type="button"
                        className="soft-button w-full px-4 py-2.5 sm:w-auto"
                        onClick={() => {
                          setRoomForm(toRoomForm(room));
                          setFormError("");
                          setIsModalOpen(true);
                        }}
                      >
                        Изменить
                      </button>
                      <button
                        type="button"
                        className="flex w-full items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 sm:w-auto disabled:cursor-not-allowed disabled:opacity-60"
                        onClick={() => handleDelete(room.id)}
                        disabled={deleteRoomId === room.id}
                      >
                        <Trash2 className="h-4 w-4" />
                        {deleteRoomId === room.id ? "Удаляем..." : "Удалить"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </article>
            );
          })}
        </div>
      ) : (
        <section className="glass-card p-6">
          <EmptyState
            icon={ImageIcon}
            title="Номерной фонд ещё не заполнен"
            description="Добавьте реальный апартамент, и он сразу появится здесь и в календаре CRM."
          />
        </section>
      )}

      <ModalShell
        open={isModalOpen}
        onClose={() => {
          if (!isSaving) {
            setIsModalOpen(false);
          }
        }}
        title={roomForm.id ? "Редактирование апартамента" : "Новый апартамент"}
        description="Тарифы и медиаматериалы апартамента можно обновлять прямо из CRM. Публичный контент уходит на модерацию суперадмину."
      >
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            {formError ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200 md:col-span-2">
                {formError}
              </div>
            ) : null}

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Название</span>
              <input className="soft-input" value={roomForm.name} onChange={(event) => setRoomForm((current) => ({ ...current, name: event.target.value }))} required />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Тип</span>
              <input className="soft-input" value={roomForm.roomType} onChange={(event) => setRoomForm((current) => ({ ...current, roomType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Односпальных кроватей</span>
              <input type="number" min="0" className="soft-input" value={roomForm.singleBeds} onChange={(event) => setRoomForm((current) => ({ ...current, singleBeds: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Двуспальных кроватей</span>
              <input type="number" min="0" className="soft-input" value={roomForm.doubleBeds} onChange={(event) => setRoomForm((current) => ({ ...current, doubleBeds: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Тариф взрослый</span>
              <input type="number" min="0" className="soft-input" value={roomForm.priceAdult} onChange={(event) => setRoomForm((current) => ({ ...current, priceAdult: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Тариф ребёнок</span>
              <input type="number" min="0" className="soft-input" value={roomForm.priceChild} onChange={(event) => setRoomForm((current) => ({ ...current, priceChild: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Базовая цена</span>
              <input type="number" min="0" className="soft-input" value={roomForm.price} onChange={(event) => setRoomForm((current) => ({ ...current, price: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Скидка, %</span>
              <input type="number" min="0" className="soft-input" value={roomForm.discountPct} onChange={(event) => setRoomForm((current) => ({ ...current, discountPct: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Дней до скидки</span>
              <input type="number" min="0" className="soft-input" value={roomForm.discountFromNights} onChange={(event) => setRoomForm((current) => ({ ...current, discountFromNights: event.target.value }))} />
            </label>

            <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/60 px-4 py-3 md:self-end">
              <input type="checkbox" className="h-4 w-4 rounded border-border bg-background" checked={roomForm.hasAc} onChange={(event) => setRoomForm((current) => ({ ...current, hasAc: event.target.checked }))} />
              <span className="text-sm text-foreground">Есть кондиционер</span>
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Душ</span>
              <input className="soft-input" value={roomForm.bathType} onChange={(event) => setRoomForm((current) => ({ ...current, bathType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">WC</span>
              <input className="soft-input" value={roomForm.wcType} onChange={(event) => setRoomForm((current) => ({ ...current, wcType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">BBQ</span>
              <input className="soft-input" value={roomForm.bbqType} onChange={(event) => setRoomForm((current) => ({ ...current, bbqType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Кухня</span>
              <input className="soft-input" value={roomForm.kitchenType} onChange={(event) => setRoomForm((current) => ({ ...current, kitchenType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Беседка</span>
              <input className="soft-input" value={roomForm.gazeboType} onChange={(event) => setRoomForm((current) => ({ ...current, gazeboType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Терраса</span>
              <input className="soft-input" value={roomForm.terraceType} onChange={(event) => setRoomForm((current) => ({ ...current, terraceType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Бассейн</span>
              <input className="soft-input" value={roomForm.poolType} onChange={(event) => setRoomForm((current) => ({ ...current, poolType: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Балкон</span>
              <input className="soft-input" value={roomForm.balconyType} onChange={(event) => setRoomForm((current) => ({ ...current, balconyType: event.target.value }))} />
            </label>

            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Описание</span>
              <textarea className="soft-input min-h-32 resize-none" value={roomForm.description} onChange={(event) => setRoomForm((current) => ({ ...current, description: event.target.value }))} />
            </label>
          </div>

          <div className="mt-6">
            <MediaEditorSection
              title="Фото и видео апартамента"
              description="Добавляйте фото, видео и обложку прямо в карточку апартамента. Новый контент попадёт в очередь модерации суперадмину."
              photos={roomForm.photos}
              videoUrl={roomForm.videoUrl}
              videoPosterUrl={roomForm.videoPosterUrl}
              videoSourceKind={roomForm.videoSourceKind}
              uploadPhotoLabel="Добавить фото апартамента"
              photoLimitLabel="До 5 фотографий. Первое фото станет обложкой апартамента после модерации."
              photoUploading={roomUploadKey === "photos"}
              videoUploading={roomUploadKey === "video"}
              posterUploading={roomUploadKey === "poster"}
              onPhotosUpload={uploadRoomPhotos}
              onPhotoRemove={(index) =>
                setRoomForm((current) => ({
                  ...current,
                  photos: current.photos.filter((_, photoIndex) => photoIndex !== index),
                }))
              }
              onVideoUpload={uploadRoomVideo}
              onPosterUpload={uploadRoomPoster}
              onCapturePoster={captureRoomPoster}
              onVideoSourceKindChange={(next) => setRoomForm((current) => ({ ...current, videoSourceKind: next }))}
              onVideoUrlChange={(next) => setRoomForm((current) => ({ ...current, videoUrl: next }))}
            />
          </div>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
            <button type="button" className="soft-button" onClick={() => setIsModalOpen(false)} disabled={isSaving}>
              Отмена
            </button>
            <button type="submit" className="brand-button disabled:cursor-not-allowed disabled:opacity-60" disabled={isSaving}>
              {isSaving ? "Сохраняем..." : roomForm.id ? "Сохранить изменения" : "Создать апартамент"}
            </button>
          </div>
        </form>
      </ModalShell>

      <SensitiveChangeModal
        open={Boolean(pendingApproval)}
        title="Согласование тарифов апартамента"
        description="Цены и тарифы влияют на бронирование и витрину базы. Отправьте изменение управляющему или примените его под свою ответственность."
        loading={isSaving}
        onClose={() => {
          if (!isSaving) {
            setPendingApproval(null);
          }
        }}
        onConfirm={(comment) => submitSensitiveRoomChange("pending_review", comment)}
        onApply={(comment) => submitSensitiveRoomChange("apply_with_responsibility", comment)}
      />
    </PageMotion>
  );
}
