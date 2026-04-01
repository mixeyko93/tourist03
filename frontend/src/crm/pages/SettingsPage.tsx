import { Bell, Building2, ChevronDown, Link2, MapPinHouse, Phone, Save, ShieldCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { fetchCrmCampProfile, fetchCrmCamps, saveCrmCampProfile, type CrmCamp, type CrmCampProfileUpdatePayload } from "../session";

type ProfileForm = {
  name: string;
  lakeName: string;
  address: string;
  phone: string;
  siteUrl: string;
  description: string;
  timeZone: string;
  checkInTime: string;
  checkOutTime: string;
  cancellationPolicy: string;
  arrivalInstructions: string;
  paymentInstructions: string;
  adminContactPhone: string;
  supportWhatsapp: string;
  supportTelegram: string;
  notificationsEnabled: boolean;
};

const emptyProfileForm: ProfileForm = {
  name: "",
  lakeName: "",
  address: "",
  phone: "",
  siteUrl: "",
  description: "",
  timeZone: "Asia/Irkutsk",
  checkInTime: "",
  checkOutTime: "",
  cancellationPolicy: "",
  arrivalInstructions: "",
  paymentInstructions: "",
  adminContactPhone: "",
  supportWhatsapp: "",
  supportTelegram: "",
  notificationsEnabled: true,
};

function mapProfileForm(payload: Awaited<ReturnType<typeof fetchCrmCampProfile>>): ProfileForm {
  return {
    name: payload.camp.name || "",
    lakeName: payload.camp.lake_name || "",
    address: payload.camp.address || "",
    phone: payload.camp.phone || "",
    siteUrl: payload.camp.site_url || "",
    description: payload.camp.description || "",
    timeZone: payload.settings.time_zone || "Asia/Irkutsk",
    checkInTime: payload.settings.check_in_time || "",
    checkOutTime: payload.settings.check_out_time || "",
    cancellationPolicy: payload.settings.cancellation_policy || "",
    arrivalInstructions: payload.settings.arrival_instructions || "",
    paymentInstructions: payload.settings.payment_instructions || "",
    adminContactPhone: payload.settings.admin_contact_phone || "",
    supportWhatsapp: payload.settings.support_whatsapp || "",
    supportTelegram: payload.settings.support_telegram || "",
    notificationsEnabled: payload.settings.notifications_enabled ?? true,
  };
}

function toProfilePayload(form: ProfileForm): CrmCampProfileUpdatePayload {
  return {
    name: form.name,
    lake_name: form.lakeName,
    address: form.address,
    phone: form.phone,
    site_url: form.siteUrl,
    description: form.description,
    time_zone: form.timeZone,
    check_in_time: form.checkInTime,
    check_out_time: form.checkOutTime,
    cancellation_policy: form.cancellationPolicy,
    arrival_instructions: form.arrivalInstructions,
    payment_instructions: form.paymentInstructions,
    admin_contact_phone: form.adminContactPhone,
    support_whatsapp: form.supportWhatsapp,
    support_telegram: form.supportTelegram,
    notifications_enabled: form.notificationsEnabled,
  };
}

export default function SettingsPage() {
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [form, setForm] = useState<ProfileForm>(emptyProfileForm);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

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
      setForm(emptyProfileForm);
      return;
    }
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    setSuccessMessage("");
    fetchCrmCampProfile(selectedCampId, controller.signal)
      .then((payload) => {
        setForm(mapProfileForm(payload));
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить профиль базы");
        setForm(emptyProfileForm);
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
      setErrorMessage("Сначала выберите базу.");
      return;
    }
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      const response = await saveCrmCampProfile(selectedCampId, toProfilePayload(form));
      setForm(mapProfileForm(response.item));
      setSuccessMessage("Профиль базы сохранён.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось сохранить настройки");
    } finally {
      setIsSaving(false);
    }
  }

  const hasCampOptions = camps.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Настройки"
        title="Профиль базы и правила"
        description="Живые настройки базы отдыха: основные данные, правила заезда, контакты поддержки и тексты для бронирований."
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,280px)_auto] sm:items-center sm:justify-between">
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
            Обновить профиль
          </button>
        </div>
      </section>

      {isLoading ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={Building2}
            title="Загружаем профиль базы"
            description="Подтягиваем рабочие параметры, правила проживания и контакты поддержки."
          />
        </section>
      ) : !hasCampOptions ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={Building2}
            title="Нет доступных баз"
            description="Когда вам выдадут доступ к базе, её профиль и настройки появятся здесь."
          />
        </section>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
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

          <section className="glass-card p-6 md:p-8">
            <div className="flex items-center gap-3">
              <Building2 className="h-5 w-5 text-[#E5D3B3]" />
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Основная информация</h2>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Название базы отдыха</span>
                <input className="soft-input" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Озеро / локация</span>
                <input className="soft-input" value={form.lakeName} onChange={(event) => setForm((current) => ({ ...current, lakeName: event.target.value }))} placeholder="Например: Щучье" />
              </label>
              <label className="space-y-2 md:col-span-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Адрес</span>
                <input className="soft-input" value={form.address} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value }))} />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Контактный телефон базы</span>
                <input className="soft-input" value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Сайт базы</span>
                <input className="soft-input" value={form.siteUrl} onChange={(event) => setForm((current) => ({ ...current, siteUrl: event.target.value }))} placeholder="https://..." />
              </label>
              <label className="space-y-2 md:col-span-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Описание</span>
                <textarea className="soft-input min-h-32 resize-none" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
            </div>
          </section>

          <section className="glass-card p-6 md:p-8">
            <div className="flex items-center gap-3">
              <MapPinHouse className="h-5 w-5 text-[#E5D3B3]" />
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Правила проживания</h2>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Часовой пояс</span>
                <input className="soft-input" value={form.timeZone} onChange={(event) => setForm((current) => ({ ...current, timeZone: event.target.value }))} />
              </label>
              <div className="grid gap-5 sm:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Заезд</span>
                  <input type="time" className="soft-input" value={form.checkInTime} onChange={(event) => setForm((current) => ({ ...current, checkInTime: event.target.value }))} />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Выезд</span>
                  <input type="time" className="soft-input" value={form.checkOutTime} onChange={(event) => setForm((current) => ({ ...current, checkOutTime: event.target.value }))} />
                </label>
              </div>
              <label className="space-y-2 md:col-span-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Правила отмены</span>
                <textarea className="soft-input min-h-28 resize-none" value={form.cancellationPolicy} onChange={(event) => setForm((current) => ({ ...current, cancellationPolicy: event.target.value }))} />
              </label>
              <label className="space-y-2 md:col-span-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Инструкция перед заездом</span>
                <textarea className="soft-input min-h-28 resize-none" value={form.arrivalInstructions} onChange={(event) => setForm((current) => ({ ...current, arrivalInstructions: event.target.value }))} />
              </label>
              <label className="space-y-2 md:col-span-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Инструкция по оплате</span>
                <textarea className="soft-input min-h-28 resize-none" value={form.paymentInstructions} onChange={(event) => setForm((current) => ({ ...current, paymentInstructions: event.target.value }))} />
              </label>
            </div>
          </section>

          <section className="glass-card p-6 md:p-8">
            <div className="flex items-center gap-3">
              <Phone className="h-5 w-5 text-[#E5D3B3]" />
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Контакты и уведомления</h2>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Телефон администратора</span>
                <input className="soft-input" value={form.adminContactPhone} onChange={(event) => setForm((current) => ({ ...current, adminContactPhone: event.target.value }))} />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">WhatsApp поддержки</span>
                <input className="soft-input" value={form.supportWhatsapp} onChange={(event) => setForm((current) => ({ ...current, supportWhatsapp: event.target.value }))} />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Telegram поддержки</span>
                <input className="soft-input" value={form.supportTelegram} onChange={(event) => setForm((current) => ({ ...current, supportTelegram: event.target.value }))} />
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/65 px-4 py-3 md:self-end">
                <input type="checkbox" className="h-4 w-4 rounded border-border bg-background" checked={form.notificationsEnabled} onChange={(event) => setForm((current) => ({ ...current, notificationsEnabled: event.target.checked }))} />
                <div>
                  <p className="text-sm font-medium text-foreground">Уведомления базы включены</p>
                  <p className="text-xs text-muted-foreground">Отключение сохранится в CRM и будет видно в аудите.</p>
                </div>
              </label>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Bell className="h-4 w-4 text-[#E5D3B3]" />
                  Уведомления
                </div>
                <p className="mt-2 text-sm text-muted-foreground">Базовый переключатель already wired к серверным настройкам базы.</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Link2 className="h-4 w-4 text-[#E5D3B3]" />
                  Контакты
                </div>
                <p className="mt-2 text-sm text-muted-foreground">Эти контакты будут использоваться в клиентских уведомлениях и в разделе помощи.</p>
              </div>
              <div className="rounded-3xl border border-border bg-background/65 p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <ShieldCheck className="h-4 w-4 text-[#E5D3B3]" />
                  Аудит
                </div>
                <p className="mt-2 text-sm text-muted-foreground">Все сохранения профиля уже попадают в журнал действий CRM.</p>
              </div>
            </div>
          </section>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button type="submit" className="brand-button gap-2 disabled:cursor-not-allowed disabled:opacity-60" disabled={isSaving}>
              <Save className="h-4 w-4" />
              {isSaving ? "Сохраняем профиль..." : "Сохранить изменения"}
            </button>
            <button type="button" className="soft-button" onClick={() => setReloadKey((value) => value + 1)} disabled={isSaving}>
              Сбросить к серверной версии
            </button>
          </div>
        </form>
      )}
    </PageMotion>
  );
}
