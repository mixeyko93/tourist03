import { AlarmClockCheck, CalendarClock, ChevronDown, MoonStar, Plus, Save, Search, Trash2, UserRoundCheck } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import {
  createCrmShiftRule,
  deleteCrmShiftRule,
  fetchCrmCamps,
  fetchCrmShifts,
  saveCrmShiftSettings,
  updateCrmShiftRule,
  type CrmCamp,
  type CrmShiftRule,
  type CrmShiftRuleUpsertPayload,
  type CrmShiftSettings,
  type CrmShiftStaffOption,
} from "../session";

type ShiftSettingsForm = {
  timeZone: string;
  bookingHoldHours: string;
  nightReleaseAfterShiftMinutes: string;
  escalationStepMinutes: string;
  escalationRepeatsBeforeManager: string;
};

type ShiftRuleForm = {
  adminId: string;
  weekday: string;
  startsAt: string;
  endsAt: string;
  isNightShift: boolean;
  isActive: boolean;
  comment: string;
};

const weekdayLabels = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

const emptySettingsForm: ShiftSettingsForm = {
  timeZone: "Asia/Irkutsk",
  bookingHoldHours: "4",
  nightReleaseAfterShiftMinutes: "60",
  escalationStepMinutes: "15",
  escalationRepeatsBeforeManager: "2",
};

const emptyRuleForm: ShiftRuleForm = {
  adminId: "",
  weekday: "0",
  startsAt: "09:00",
  endsAt: "18:00",
  isNightShift: false,
  isActive: true,
  comment: "",
};

function mapSettingsForm(settings: CrmShiftSettings): ShiftSettingsForm {
  return {
    timeZone: settings.time_zone || "Asia/Irkutsk",
    bookingHoldHours: String(settings.booking_hold_hours || 4),
    nightReleaseAfterShiftMinutes: String(settings.night_release_after_shift_minutes || 60),
    escalationStepMinutes: String(settings.escalation_step_minutes || 15),
    escalationRepeatsBeforeManager: String(settings.escalation_repeats_before_manager || 2),
  };
}

function toSettingsPayload(form: ShiftSettingsForm) {
  return {
    time_zone: form.timeZone,
    booking_hold_hours: Number(form.bookingHoldHours || 4),
    night_release_after_shift_minutes: Number(form.nightReleaseAfterShiftMinutes || 60),
    escalation_step_minutes: Number(form.escalationStepMinutes || 15),
    escalation_repeats_before_manager: Number(form.escalationRepeatsBeforeManager || 2),
  };
}

function mapRuleForm(rule: CrmShiftRule): ShiftRuleForm {
  return {
    adminId: String(rule.admin_id),
    weekday: String(rule.weekday),
    startsAt: rule.starts_at?.slice(0, 5) || "09:00",
    endsAt: rule.ends_at?.slice(0, 5) || "18:00",
    isNightShift: rule.is_night_shift,
    isActive: rule.is_active,
    comment: rule.comment || "",
  };
}

function toRulePayload(form: ShiftRuleForm): CrmShiftRuleUpsertPayload {
  return {
    admin_id: Number(form.adminId),
    weekday: Number(form.weekday),
    starts_at: form.startsAt,
    ends_at: form.endsAt,
    is_night_shift: form.isNightShift,
    is_active: form.isActive,
    comment: form.comment || undefined,
  };
}

function formatDateTime(value: string | null | undefined, timeZone?: string) {
  if (!value) {
    return "Не указано";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function describeRule(rule: CrmShiftRule) {
  return `${weekdayLabels[rule.weekday] || "День"} · ${rule.starts_at?.slice(0, 5) || rule.starts_at} → ${rule.ends_at?.slice(0, 5) || rule.ends_at}`;
}

export default function ShiftsPage() {
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [settingsForm, setSettingsForm] = useState<ShiftSettingsForm>(emptySettingsForm);
  const [rules, setRules] = useState<CrmShiftRule[]>([]);
  const [staff, setStaff] = useState<CrmShiftStaffOption[]>([]);
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof fetchCrmShifts>>["overview"] | null>(null);
  const [isBootLoading, setIsBootLoading] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CrmShiftRule | null>(null);
  const [ruleForm, setRuleForm] = useState<ShiftRuleForm>(emptyRuleForm);
  const [ruleError, setRuleError] = useState("");
  const [isSavingRule, setIsSavingRule] = useState(false);
  const [deletingRuleId, setDeletingRuleId] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setIsBootLoading(true);
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
          setIsBootLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedCampId) {
      setRules([]);
      setStaff([]);
      setOverview(null);
      setSettingsForm(emptySettingsForm);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    setSuccessMessage("");

    fetchCrmShifts(selectedCampId, controller.signal)
      .then((payload) => {
        setSettingsForm(mapSettingsForm(payload.settings));
        setRules(payload.rules);
        setStaff(payload.staff);
        setOverview(payload.overview);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить график смен");
        setRules([]);
        setStaff([]);
        setOverview(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [selectedCampId, reloadKey]);

  const filteredRules = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return rules;
    }
    return rules.filter((rule) =>
      [rule.admin_name, rule.admin_email, weekdayLabels[rule.weekday], rule.comment, rule.starts_at, rule.ends_at]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [rules, searchQuery]);

  function openCreateRuleModal() {
    setEditingRule(null);
    setRuleForm({
      ...emptyRuleForm,
      adminId: staff[0] ? String(staff[0].id) : "",
    });
    setRuleError("");
    setIsRuleModalOpen(true);
  }

  function openEditRuleModal(rule: CrmShiftRule) {
    setEditingRule(rule);
    setRuleForm(mapRuleForm(rule));
    setRuleError("");
    setIsRuleModalOpen(true);
  }

  async function handleSaveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId) {
      setErrorMessage("Сначала выберите базу.");
      return;
    }
    try {
      setIsSavingSettings(true);
      setErrorMessage("");
      setSuccessMessage("");
      await saveCrmShiftSettings(selectedCampId, toSettingsPayload(settingsForm));
      setSuccessMessage("Параметры смен обновлены.");
      setReloadKey((value) => value + 1);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось сохранить параметры смен");
    } finally {
      setIsSavingSettings(false);
    }
  }

  async function handleSaveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId) {
      setRuleError("Сначала выберите базу.");
      return;
    }
    if (!ruleForm.adminId) {
      setRuleError("Выберите сотрудника.");
      return;
    }
    try {
      setIsSavingRule(true);
      setRuleError("");
      const payload = toRulePayload(ruleForm);
      if (editingRule) {
        await updateCrmShiftRule(selectedCampId, editingRule.id, payload);
      } else {
        await createCrmShiftRule(selectedCampId, payload);
      }
      setIsRuleModalOpen(false);
      setEditingRule(null);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setRuleError(error instanceof Error ? error.message : "Не удалось сохранить правило смены");
    } finally {
      setIsSavingRule(false);
    }
  }

  async function handleDeleteRule(rule: CrmShiftRule) {
    if (!selectedCampId) {
      return;
    }
    try {
      setDeletingRuleId(rule.id);
      setErrorMessage("");
      await deleteCrmShiftRule(selectedCampId, rule.id);
      setSuccessMessage(`Правило смены удалено: ${describeRule(rule)}`);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось удалить правило смены");
    } finally {
      setDeletingRuleId(null);
    }
  }

  const activeRules = overview?.active_rules || [];
  const nextRule = overview?.next_rule || null;
  const timeZone = overview?.timezone || settingsForm.timeZone;
  const hasCampOptions = camps.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Смены"
        title="График смен и дежурств"
        description="Рабочий экран базы: кто сейчас на смене, когда следующая пересменка и как CRM должна обрабатывать ночные заявки."
        actions={
          <button type="button" className="brand-button w-full gap-2 sm:w-auto" onClick={openCreateRuleModal} disabled={!selectedCampId || !staff.length}>
            <Plus className="h-4 w-4" />
            Добавить смену
          </button>
        }
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 xl:grid-cols-[260px_minmax(0,1fr)_auto] xl:items-center">
          <div className="relative">
            <select
              className="soft-input appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60"
              value={selectedCampId ?? ""}
              onChange={(event) => setSelectedCampId(event.target.value ? Number(event.target.value) : null)}
              disabled={!hasCampOptions || isBootLoading}
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

          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              className="soft-input pl-11"
              placeholder="Поиск по сотруднику, дню недели или комментарию"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <button type="button" className="soft-button" onClick={() => setReloadKey((value) => value + 1)}>
            Обновить смены
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
          <EmptyState
            icon={CalendarClock}
            title="Загружаем график смен"
            description="Подтягиваем текущее дежурство, расписание базы и параметры ночной обработки заявок."
          />
        </section>
      ) : !hasCampOptions ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={CalendarClock}
            title="Нет доступных баз"
            description="Когда вам выдадут базу, здесь появится её график дежурств и правила обработки заявок."
          />
        </section>
      ) : (
        <>
          <div className="grid gap-4 xl:grid-cols-3">
            <section className="glass-card p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <UserRoundCheck className="h-4 w-4 text-[#E5D3B3]" />
                Кто сейчас отвечает
              </div>
              {activeRules.length ? (
                <div className="mt-4 space-y-3">
                  {activeRules.map((rule) => (
                    <div key={`${rule.rule_id}-${rule.starts_at}`} className="rounded-3xl border border-border bg-background/65 p-4">
                      <p className="text-sm font-semibold text-foreground">{rule.admin_name}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {rule.starts_time} → {rule.ends_time}
                        {rule.is_night_shift ? " · Ночная смена" : ""}
                      </p>
                      {rule.comment ? <p className="mt-2 text-sm text-foreground/90">{rule.comment}</p> : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm leading-6 text-muted-foreground">
                  Сейчас никто не назначен на смену. Ночная логика будет держать заявку до начала следующей смены плюс ещё {settingsForm.nightReleaseAfterShiftMinutes} минут.
                </p>
              )}
            </section>

            <section className="glass-card p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <AlarmClockCheck className="h-4 w-4 text-[#E5D3B3]" />
                Следующая пересменка
              </div>
              {nextRule ? (
                <div className="mt-4 rounded-3xl border border-border bg-background/65 p-4">
                  <p className="text-sm font-semibold text-foreground">{nextRule.admin_name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {nextRule.weekday_label} · {nextRule.starts_time} → {nextRule.ends_time}
                  </p>
                  <p className="mt-3 text-sm text-foreground">Старт: {formatDateTime(nextRule.starts_at, timeZone)}</p>
                  <p className="mt-1 text-sm text-muted-foreground">Часовой пояс базы: {timeZone}</p>
                </div>
              ) : (
                <p className="mt-4 text-sm leading-6 text-muted-foreground">
                  Следующее правило смены пока не задано. Добавьте график, чтобы CRM понимала, кто обрабатывает новые заявки.
                </p>
              )}
            </section>

            <section className="glass-card p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <MoonStar className="h-4 w-4 text-[#E5D3B3]" />
                Ночная логика CRM
              </div>
              <div className="mt-4 space-y-3 rounded-3xl border border-border bg-background/65 p-4 text-sm text-muted-foreground">
                <p>Заморозка заявки: <span className="font-medium text-foreground">{settingsForm.bookingHoldHours} ч.</span></p>
                <p>Ночной запас после смены: <span className="font-medium text-foreground">{settingsForm.nightReleaseAfterShiftMinutes} мин.</span></p>
                <p>Шаг эскалации: <span className="font-medium text-foreground">{settingsForm.escalationStepMinutes} мин.</span></p>
                <p>Повторов до управляющего: <span className="font-medium text-foreground">{settingsForm.escalationRepeatsBeforeManager}</span></p>
              </div>
            </section>
          </div>

          <section className="glass-card p-6">
            <form onSubmit={handleSaveSettings} className="space-y-5">
              <div className="flex items-center gap-3">
                <CalendarClock className="h-5 w-5 text-[#E5D3B3]" />
                <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Параметры графика и SLA</h2>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Часовой пояс</span>
                  <input className="soft-input" value={settingsForm.timeZone} onChange={(event) => setSettingsForm((current) => ({ ...current, timeZone: event.target.value }))} />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Заморозка заявки, ч.</span>
                  <input type="number" min="1" className="soft-input" value={settingsForm.bookingHoldHours} onChange={(event) => setSettingsForm((current) => ({ ...current, bookingHoldHours: event.target.value }))} />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Ночной запас, мин.</span>
                  <input type="number" min="0" className="soft-input" value={settingsForm.nightReleaseAfterShiftMinutes} onChange={(event) => setSettingsForm((current) => ({ ...current, nightReleaseAfterShiftMinutes: event.target.value }))} />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Шаг эскалации, мин.</span>
                  <input type="number" min="1" className="soft-input" value={settingsForm.escalationStepMinutes} onChange={(event) => setSettingsForm((current) => ({ ...current, escalationStepMinutes: event.target.value }))} />
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Повторы до управляющего</span>
                  <input type="number" min="1" className="soft-input" value={settingsForm.escalationRepeatsBeforeManager} onChange={(event) => setSettingsForm((current) => ({ ...current, escalationRepeatsBeforeManager: event.target.value }))} />
                </label>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <button type="submit" className="brand-button gap-2" disabled={isSavingSettings}>
                  <Save className="h-4 w-4" />
                  {isSavingSettings ? "Сохраняем..." : "Сохранить параметры"}
                </button>
              </div>
            </form>
          </section>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
            <section className="glass-card p-6">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Недельный график</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Повторяющиеся смены, по которым CRM определяет ответственных сотрудников.</p>
                </div>
                <button type="button" className="soft-button" onClick={openCreateRuleModal} disabled={!staff.length}>
                  Добавить правило
                </button>
              </div>

              <div className="mt-5 space-y-3">
                {filteredRules.length ? (
                  filteredRules.map((rule) => (
                    <article key={rule.id} className="rounded-3xl border border-border bg-background/65 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-foreground">{rule.admin_name}</p>
                          <p className="mt-1 text-sm text-muted-foreground">{describeRule(rule)}</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <span className={`rounded-full border px-3 py-1 text-xs font-medium ${rule.is_active ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-slate-500/25 bg-slate-500/10 text-slate-300"}`}>
                              {rule.is_active ? "Активно" : "Выключено"}
                            </span>
                            {rule.is_night_shift ? (
                              <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-3 py-1 text-xs font-medium text-violet-300">
                                Ночная смена
                              </span>
                            ) : null}
                          </div>
                          {rule.comment ? <p className="mt-3 text-sm text-foreground/90">{rule.comment}</p> : null}
                        </div>
                        <div className="flex flex-col gap-2 sm:min-w-[140px]">
                          <button type="button" className="soft-button" onClick={() => openEditRuleModal(rule)}>
                            Изменить
                          </button>
                          <button
                            type="button"
                            className="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60"
                            onClick={() => handleDeleteRule(rule)}
                            disabled={deletingRuleId === rule.id}
                          >
                            <Trash2 className="h-4 w-4" />
                            {deletingRuleId === rule.id ? "Удаляем..." : "Удалить"}
                          </button>
                        </div>
                      </div>
                    </article>
                  ))
                ) : (
                  <EmptyState
                    icon={CalendarClock}
                    compact
                    title="График ещё не настроен"
                    description="Добавьте повторяющиеся смены, чтобы CRM понимала, кто отвечает за новые заявки днём и ночью."
                  />
                )}
              </div>
            </section>

            <section className="glass-card p-6">
              <div className="flex items-center gap-3">
                <AlarmClockCheck className="h-5 w-5 text-[#E5D3B3]" />
                <div>
                  <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Ближайшие дежурства</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Следующие окна, в которые CRM будет назначать ответственного по заявкам.</p>
                </div>
              </div>

              <div className="mt-5 space-y-3">
                {overview?.upcoming_windows?.length ? (
                  overview.upcoming_windows.map((windowItem) => (
                    <article key={`${windowItem.rule_id}-${windowItem.starts_at}`} className="rounded-3xl border border-border bg-background/65 p-4">
                      <p className="text-sm font-semibold text-foreground">{windowItem.admin_name}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {windowItem.weekday_label} · {windowItem.starts_time} → {windowItem.ends_time}
                      </p>
                      <p className="mt-2 text-sm text-foreground">{formatDateTime(windowItem.starts_at, timeZone)}</p>
                      {windowItem.is_night_shift ? (
                        <p className="mt-2 text-xs font-medium uppercase tracking-[0.18em] text-violet-300">Ночная смена</p>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <EmptyState
                    icon={AlarmClockCheck}
                    compact
                    title="Нет ближайших окон"
                    description="После настройки правил здесь появится ближайшая смена и последовательность дежурств."
                  />
                )}
              </div>
            </section>
          </div>
        </>
      )}

      <ModalShell
        open={isRuleModalOpen}
        onClose={() => {
          setIsRuleModalOpen(false);
          setEditingRule(null);
          setRuleError("");
        }}
        title={editingRule ? "Редактирование смены" : "Новое правило смены"}
        description="Настройте повторяющееся окно дежурства. По этим правилам CRM будет определять активную смену и ночной сценарий."
      >
        <form className="space-y-5" onSubmit={handleSaveRule}>
          {ruleError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{ruleError}</div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Сотрудник</span>
              <select className="soft-input" value={ruleForm.adminId} onChange={(event) => setRuleForm((current) => ({ ...current, adminId: event.target.value }))}>
                <option value="">Выберите сотрудника</option>
                {staff.map((member) => (
                  <option key={member.id} value={member.id}>
                    {member.display_name} · {member.role_label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">День недели</span>
              <select className="soft-input" value={ruleForm.weekday} onChange={(event) => setRuleForm((current) => ({ ...current, weekday: event.target.value }))}>
                {weekdayLabels.map((label, index) => (
                  <option key={label} value={index}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Начало смены</span>
              <input type="time" className="soft-input" value={ruleForm.startsAt} onChange={(event) => setRuleForm((current) => ({ ...current, startsAt: event.target.value }))} />
            </label>
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Конец смены</span>
              <input type="time" className="soft-input" value={ruleForm.endsAt} onChange={(event) => setRuleForm((current) => ({ ...current, endsAt: event.target.value }))} />
            </label>
          </div>

          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий к смене</span>
            <textarea className="soft-input min-h-24 resize-y" value={ruleForm.comment} onChange={(event) => setRuleForm((current) => ({ ...current, comment: event.target.value }))} placeholder="Например, дежурство по ночным заселениям." />
          </label>

          <div className="grid gap-3 rounded-3xl border border-border bg-background/65 p-4 sm:grid-cols-2">
            <label className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 px-4 py-3">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border bg-background"
                checked={ruleForm.isNightShift}
                onChange={(event) => setRuleForm((current) => ({ ...current, isNightShift: event.target.checked }))}
              />
              <span className="text-sm text-foreground">Ночная смена</span>
            </label>
            <label className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 px-4 py-3">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border bg-background"
                checked={ruleForm.isActive}
                onChange={(event) => setRuleForm((current) => ({ ...current, isActive: event.target.checked }))}
              />
              <span className="text-sm text-foreground">Правило активно</span>
            </label>
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              className="soft-button"
              onClick={() => {
                setIsRuleModalOpen(false);
                setEditingRule(null);
                setRuleError("");
              }}
            >
              Отмена
            </button>
            <button type="submit" className="brand-button gap-2 justify-center" disabled={isSavingRule}>
              <Save className="h-4 w-4" />
              {isSavingRule ? "Сохраняем..." : editingRule ? "Сохранить правило" : "Создать правило"}
            </button>
          </div>
        </form>
      </ModalShell>
    </PageMotion>
  );
}
