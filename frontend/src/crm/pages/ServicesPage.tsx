import { Car, Coffee, MapPin, Plus, Search, Shield, Trash2, Wifi } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageLoadingState } from "../components/PageLoadingState";
import { PageMotion } from "../components/PageMotion";
import { usePageLoadState } from "../components/usePageLoadState";
import { SectionHeading } from "../components/SectionHeading";
import {
  createCrmService,
  deleteCrmService,
  fetchCrmCamps,
  fetchCrmServices,
  updateCrmService,
  type CrmCamp,
  type CrmService,
  type CrmServiceUpsertPayload,
} from "../session";

const serviceStatusLabels: Record<string, string> = {
  draft: "Черновик",
  active: "Активна",
  hidden: "Скрыта",
  sold_out: "Нет мест",
  paused: "Остановлена",
  archived: "Архив",
};

const serviceStatusClasses: Record<string, string> = {
  draft: "border-slate-500/20 bg-slate-500/10 text-slate-300",
  active: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  hidden: "border-violet-500/20 bg-violet-500/10 text-violet-300",
  sold_out: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  paused: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  archived: "border-border bg-background/70 text-muted-foreground",
};

const responsibleScopeLabels: Record<string, string> = {
  shift_admins: "Администраторы смены",
  responsible_admin: "Назначенный сотрудник",
  provider: "Внешний подрядчик",
};

type ServiceForm = {
  categoryName: string;
  name: string;
  providerName: string;
  providerPhone: string;
  providerTelegram: string;
  responsibleScope: string;
  description: string;
  status: string;
  requiresBooking: boolean;
  allowsStandalone: boolean;
  locationHint: string;
  durationMinutes: string;
  coverPhotoUrl: string;
  coverVideoUrl: string;
};

const emptyServiceForm: ServiceForm = {
  categoryName: "",
  name: "",
  providerName: "",
  providerPhone: "",
  providerTelegram: "",
  responsibleScope: "shift_admins",
  description: "",
  status: "draft",
  requiresBooking: false,
  allowsStandalone: true,
  locationHint: "",
  durationMinutes: "",
  coverPhotoUrl: "",
  coverVideoUrl: "",
};

function formatPrice(value: number | null) {
  if (!value) {
    return "Цена не задана";
  }
  return `${new Intl.NumberFormat("ru-RU").format(value)} ₽`;
}

function pickServiceTone(service: CrmService) {
  const haystack = `${service.category_name || ""} ${service.name} ${service.provider_name || ""}`.toLowerCase();
  if (haystack.includes("трансфер") || haystack.includes("аренд") || haystack.includes("квадро")) {
    return { icon: Car, wrap: "bg-sky-500/10", iconColor: "text-sky-300" };
  }
  if (haystack.includes("безопас") || haystack.includes("баня") || haystack.includes("страх")) {
    return { icon: Shield, wrap: "bg-emerald-500/10", iconColor: "text-emerald-300" };
  }
  if (haystack.includes("wifi") || haystack.includes("интернет") || haystack.includes("связ")) {
    return { icon: Wifi, wrap: "bg-violet-500/10", iconColor: "text-violet-300" };
  }
  return { icon: Coffee, wrap: "bg-amber-500/10", iconColor: "text-amber-300" };
}

function mapServiceForm(service: CrmService): ServiceForm {
  return {
    categoryName: service.category_name || "",
    name: service.name,
    providerName: service.provider_name || "",
    providerPhone: service.provider_contact_phone || "",
    providerTelegram: service.provider_contact_telegram || "",
    responsibleScope: service.responsible_scope || "shift_admins",
    description: service.description || "",
    status: service.status || "draft",
    requiresBooking: service.requires_booking,
    allowsStandalone: service.allows_standalone,
    locationHint: service.location_hint || "",
    durationMinutes: service.duration_minutes ? String(service.duration_minutes) : "",
    coverPhotoUrl: service.cover_photo_url || "",
    coverVideoUrl: service.cover_video_url || "",
  };
}

function toServicePayload(form: ServiceForm): CrmServiceUpsertPayload {
  return {
    category_name: form.categoryName || undefined,
    provider_name: form.providerName || undefined,
    provider_contact_phone: form.providerPhone || undefined,
    provider_contact_telegram: form.providerTelegram || undefined,
    responsible_scope: form.responsibleScope,
    name: form.name,
    description: form.description || undefined,
    status: form.status,
    requires_booking: form.requiresBooking,
    allows_standalone: form.requiresBooking ? false : form.allowsStandalone,
    location_hint: form.locationHint || undefined,
    duration_minutes: form.durationMinutes ? Number(form.durationMinutes) : null,
    cover_photo_url: form.coverPhotoUrl || undefined,
    cover_video_url: form.coverVideoUrl || undefined,
  };
}

export default function ServicesPage() {
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [services, setServices] = useState<CrmService[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingService, setEditingService] = useState<CrmService | null>(null);
  const [form, setForm] = useState<ServiceForm>(emptyServiceForm);
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [archivingId, setArchivingId] = useState<number | null>(null);

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
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить список баз");
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
      setServices([]);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");

    fetchCrmServices(selectedCampId, controller.signal)
      .then((items) => {
        setServices(items);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить услуги");
        setServices([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedCampId, reloadKey]);

  const filteredServices = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return services.filter((service) => {
      if (statusFilter && service.status !== statusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [
        service.name,
        service.category_name,
        service.provider_name,
        service.location_hint,
        service.description,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }, [services, searchQuery, statusFilter]);

  const hasCampOptions = camps.length > 0;
  const hasServices = filteredServices.length > 0;

  function openCreateModal() {
    setEditingService(null);
    setForm(emptyServiceForm);
    setFormError("");
    setIsEditorOpen(true);
  }

  function openEditModal(service: CrmService) {
    setEditingService(service);
    setForm(mapServiceForm(service));
    setFormError("");
    setIsEditorOpen(true);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId) {
      setFormError("Сначала выберите базу отдыха.");
      return;
    }
    if (!form.name.trim()) {
      setFormError("Укажите название услуги.");
      return;
    }

    try {
      setIsSubmitting(true);
      setFormError("");
      const payload = toServicePayload(form);
      if (editingService) {
        await updateCrmService(selectedCampId, editingService.id, payload);
      } else {
        await createCrmService(selectedCampId, payload);
      }
      setIsEditorOpen(false);
      setEditingService(null);
      setForm(emptyServiceForm);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Не удалось сохранить услугу");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleArchive(service: CrmService) {
    if (!selectedCampId) {
      return;
    }
    try {
      setArchivingId(service.id);
      setErrorMessage("");
      await deleteCrmService(selectedCampId, service.id);
      if (editingService?.id === service.id) {
        setIsEditorOpen(false);
        setEditingService(null);
      }
      setReloadKey((value) => value + 1);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось отправить услугу в архив");
    } finally {
      setArchivingId(null);
    }
  }

  const { showInitialSkeleton } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={!showInitialSkeleton}>
      <SectionHeading
        title="Каталог услуг базы"
        description="Реальные услуги, которые менеджеры могут продвигать вместе с проживанием или продавать отдельно по поставщикам."
        actions={
          <button type="button" className="brand-button w-full gap-2 sm:w-auto" onClick={openCreateModal} disabled={!selectedCampId}>
            <Plus className="h-4 w-4" />
            Добавить услугу
          </button>
        }
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_260px_220px_auto] xl:items-center">
          <div className="relative min-w-0">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              className="soft-input pl-11"
              placeholder="Поиск по услуге, категории, поставщику или локации"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <select
            className="soft-input disabled:cursor-not-allowed disabled:opacity-60"
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

          <select className="soft-input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">Все статусы</option>
            {Object.entries(serviceStatusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          <button type="button" className="soft-button w-full sm:w-auto" onClick={() => setReloadKey((value) => value + 1)}>
            Обновить каталог
          </button>
        </div>
      </section>

      {errorMessage ? (
        <section className="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
          {errorMessage}
        </section>
      ) : null}

      {isLoading ? (
        <section className="glass-card p-6">
          <PageLoadingState blocks={3} columnsClassName="md:grid-cols-2 xl:grid-cols-3" blockHeightClassName="h-60" />
        </section>
      ) : !hasCampOptions ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={Coffee}
            title="Нет доступных баз"
            description="Когда вам назначат базу, здесь появится её каталог услуг и рекламных предложений."
          />
        </section>
      ) : hasServices ? (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {filteredServices.map((service) => {
            const tone = pickServiceTone(service);
            const Icon = tone.icon;
            return (
              <article key={service.id} className="glass-card group p-5 transition hover:-translate-y-0.5">
                <div className="flex items-start justify-between gap-3">
                  <div className={`rounded-2xl border border-border p-3 ${tone.wrap}`}>
                    <Icon className={`h-5 w-5 ${tone.iconColor}`} />
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${serviceStatusClasses[service.status] || serviceStatusClasses.draft}`}>
                    {serviceStatusLabels[service.status] || "Черновик"}
                  </span>
                </div>

                <div className="mt-6 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    {service.category_name || "Без категории"}
                  </p>
                  <h2 className="line-clamp-2 text-xl font-semibold tracking-[-0.04em] text-foreground transition group-hover:text-[#E5D3B3]">
                    {service.name}
                  </h2>
                  <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">
                    {service.description || "Описание пока не заполнено. Добавьте смысл услуги, чтобы команда и гости понимали её ценность."}
                  </p>
                </div>

                <div className="mt-5 flex flex-wrap gap-2">
                  <span className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-foreground">
                    {service.requires_booking ? "Только с проживанием" : service.allows_standalone ? "Можно отдельно" : "Внутри базы"}
                  </span>
                  <span className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-foreground">
                    {responsibleScopeLabels[service.responsible_scope] || "Ответственный не указан"}
                  </span>
                  <span className="rounded-full border border-border bg-background/70 px-3 py-1 text-xs text-foreground">
                    Слотов: {service.active_slots_count}/{service.slots_count}
                  </span>
                </div>

                <div className="mt-5 space-y-2 rounded-3xl border border-border bg-background/65 p-4">
                  <p className="text-sm font-medium text-foreground">{formatPrice(service.min_price)}</p>
                  <div className="space-y-1 text-sm text-muted-foreground">
                    <p>Поставщик: {service.provider_name || "Без подрядчика"}</p>
                    <p>Локация: {service.location_hint || "Не указана"}</p>
                    <p>Длительность: {service.duration_minutes ? `${service.duration_minutes} мин.` : "Не задана"}</p>
                  </div>
                </div>

                <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <button type="button" className="soft-button w-full px-4 py-2.5 sm:w-auto" onClick={() => openEditModal(service)}>
                    Изменить
                  </button>
                  <button
                    type="button"
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                    onClick={() => handleArchive(service)}
                    disabled={archivingId === service.id}
                  >
                    <Trash2 className="h-4 w-4" />
                    {archivingId === service.id ? "Архивируем..." : "В архив"}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <section className="glass-card p-6">
          <EmptyState
            icon={Coffee}
            title="Услуги пока не добавлены"
            description="Создайте первые услуги базы, чтобы продвигать их в приложении, в CRM и продавать как отдельный источник выручки."
          />
        </section>
      )}

      <ModalShell
        open={isEditorOpen}
        onClose={() => {
          setIsEditorOpen(false);
          setEditingService(null);
          setFormError("");
        }}
        title={editingService ? "Редактирование услуги" : "Новая услуга"}
        description="Заполните коммерческое предложение услуги: как она продаётся, кто отвечает и где гость её получает."
      >
        <form className="space-y-5" onSubmit={handleSubmit}>
          {formError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{formError}</div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Категория</span>
              <input
                className="soft-input"
                value={form.categoryName}
                onChange={(event) => setForm((current) => ({ ...current, categoryName: event.target.value }))}
                placeholder="Например, Активный отдых"
              />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Название услуги</span>
              <input
                className="soft-input"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="Например, Аренда квадроциклов"
                required
              />
            </label>
          </div>

          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Описание</span>
            <textarea
              className="soft-input min-h-28 resize-y"
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="Коротко опишите пользу услуги, условия и что получает гость."
            />
          </label>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Поставщик или подрядчик</span>
              <input
                className="soft-input"
                value={form.providerName}
                onChange={(event) => setForm((current) => ({ ...current, providerName: event.target.value }))}
                placeholder="Например, Турклуб Ангара"
              />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Контактный телефон</span>
              <input
                className="soft-input"
                value={form.providerPhone}
                onChange={(event) => setForm((current) => ({ ...current, providerPhone: event.target.value }))}
                placeholder="+7 999 000-00-00"
              />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Telegram поставщика</span>
              <input
                className="soft-input"
                value={form.providerTelegram}
                onChange={(event) => setForm((current) => ({ ...current, providerTelegram: event.target.value }))}
                placeholder="@provider"
              />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Локация оказания</span>
              <div className="relative">
                <MapPin className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  className="soft-input pl-11"
                  value={form.locationHint}
                  onChange={(event) => setForm((current) => ({ ...current, locationHint: event.target.value }))}
                  placeholder="Например, пирс у корпуса А"
                />
              </div>
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Статус</span>
              <select
                className="soft-input"
                value={form.status}
                onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}
              >
                {Object.entries(serviceStatusLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Ответственный контур</span>
              <select
                className="soft-input"
                value={form.responsibleScope}
                onChange={(event) => setForm((current) => ({ ...current, responsibleScope: event.target.value }))}
              >
                {Object.entries(responsibleScopeLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Длительность, минут</span>
              <input
                type="number"
                min="0"
                className="soft-input"
                value={form.durationMinutes}
                onChange={(event) => setForm((current) => ({ ...current, durationMinutes: event.target.value }))}
                placeholder="60"
              />
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Обложка фото</span>
              <input
                className="soft-input"
                value={form.coverPhotoUrl}
                onChange={(event) => setForm((current) => ({ ...current, coverPhotoUrl: event.target.value }))}
                placeholder="/static/uploads/..."
              />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Обложка видео</span>
              <input
                className="soft-input"
                value={form.coverVideoUrl}
                onChange={(event) => setForm((current) => ({ ...current, coverVideoUrl: event.target.value }))}
                placeholder="https://..."
              />
            </label>
          </div>

          <div className="grid gap-3 rounded-3xl border border-border bg-background/65 p-4">
            <label className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-foreground">Только с проживанием</p>
                <p className="text-sm text-muted-foreground">Услуга доступна только гостям с подтверждённой бронью.</p>
              </div>
              <input
                type="checkbox"
                className="h-5 w-5 rounded border-border bg-background"
                checked={form.requiresBooking}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    requiresBooking: event.target.checked,
                    allowsStandalone: event.target.checked ? false : current.allowsStandalone,
                  }))
                }
              />
            </label>

            <label className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-foreground">Можно продавать отдельно</p>
                <p className="text-sm text-muted-foreground">Гость сможет заказать услугу без брони проживания.</p>
              </div>
              <input
                type="checkbox"
                className="h-5 w-5 rounded border-border bg-background"
                checked={form.requiresBooking ? false : form.allowsStandalone}
                disabled={form.requiresBooking}
                onChange={(event) => setForm((current) => ({ ...current, allowsStandalone: event.target.checked }))}
              />
            </label>
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              className="soft-button"
              onClick={() => {
                setIsEditorOpen(false);
                setEditingService(null);
                setFormError("");
              }}
            >
              Отмена
            </button>
            <button type="submit" className="brand-button justify-center gap-2" disabled={isSubmitting}>
              <Plus className="h-4 w-4" />
              {isSubmitting ? "Сохраняем..." : editingService ? "Сохранить услугу" : "Создать услугу"}
            </button>
          </div>
        </form>
      </ModalShell>
    </PageMotion>
  );
}
