import { AlarmClockCheck, CalendarClock, ChevronDown, Clock3, PencilLine, Save, Search, Trash2, UserRoundCheck } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { SensitiveChangeModal } from "../components/SensitiveChangeModal";
import {
  createCrmChangeRequest,
  fetchCrmCamps,
  fetchCrmShifts,
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

type PendingSensitiveChange = {
  title: string;
  description: string;
  operation: string;
  payload: Record<string, unknown>;
  successPending: string;
  successApplied: string;
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
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CrmShiftRule | null>(null);
  const [ruleForm, setRuleForm] = useState<ShiftRuleForm>(emptyRuleForm);
  const [ruleError, setRuleError] = useState("");
  const [isSavingRule, setIsSavingRule] = useState(false);
  const [deletingRuleId, setDeletingRuleId] = useState<number | null>(null);
  const [pendingChange, setPendingChange] = useState<PendingSensitiveChange | null>(null);
  const [isSubmittingChange, setIsSubmittingChange] = useState(false);

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

  const groupedRules = useMemo(() => {
    const rows = new Map<number, { adminId: number; adminName: string; adminLogin: string; days: CrmShiftRule[][] }>();
    filteredRules.forEach((rule) => {
      if (!rows.has(rule.admin_id)) {
        rows.set(rule.admin_id, {
          adminId: rule.admin_id,
          adminName: rule.admin_name,
          adminLogin: rule.admin_email,
          days: Array.from({ length: 7 }, () => []),
        });
      }
      rows.get(rule.admin_id)?.days[rule.weekday]?.push(rule);
    });

    return Array.from(rows.values())
      .map((row) => ({
        ...row,
        days: row.days.map((dayRules) =>
          [...dayRules].sort((left, right) => `${left.starts_at}-${left.ends_at}`.localeCompare(`${right.starts_at}-${right.ends_at}`)),
        ),
      }))
      .sort((left, right) => left.adminName.localeCompare(right.adminName, "ru"));
  }, [filteredRules]);

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
    setPendingChange({
      title: editingRule ? "Согласование изменения смены" : "Согласование новой смены",
      description: "График смен влияет на ночной сценарий, эскалации и распределение заявок. Это изменение должно быть подтверждено или применено под ответственность инициатора.",
      operation: editingRule ? "shift_rule_update" : "shift_rule_create",
      payload: editingRule
        ? ({ rule_id: editingRule.id, data: toRulePayload(ruleForm) } as Record<string, unknown>)
        : (toRulePayload(ruleForm) as Record<string, unknown>),
      successPending: editingRule ? "Изменение смены отправлено на подтверждение." : "Новая смена отправлена на подтверждение.",
      successApplied: editingRule ? "Изменение смены применено под вашу ответственность." : "Новая смена применена под вашу ответственность.",
    });
    setIsRuleModalOpen(false);
    setEditingRule(null);
    setRuleError("");
  }

  async function handleDeleteRule(rule: CrmShiftRule) {
    if (!selectedCampId) {
      return;
    }
    setDeletingRuleId(rule.id);
    setPendingChange({
      title: "Согласование удаления смены",
      description: "Удаление смены меняет логику назначения ответственного и ночную обработку заявок. Это действие нужно согласовать или применить под ответственность.",
      operation: "shift_rule_delete",
      payload: { rule_id: rule.id },
      successPending: `Удаление смены отправлено на подтверждение: ${describeRule(rule)}`,
      successApplied: `Удаление смены применено под вашу ответственность: ${describeRule(rule)}`,
    });
  }

  async function submitSensitiveChange(applyMode: "pending_review" | "apply_with_responsibility", comment: string) {
    if (!selectedCampId || !pendingChange) {
      return;
    }
    try {
      setIsSubmittingChange(true);
      setErrorMessage("");
      setSuccessMessage("");
      await createCrmChangeRequest(selectedCampId, {
        operation: pendingChange.operation,
        payload: pendingChange.payload,
        request_comment: comment || undefined,
        apply_mode: applyMode,
      });
      setSuccessMessage(applyMode === "pending_review" ? pendingChange.successPending : pendingChange.successApplied);
      if (applyMode === "apply_with_responsibility") {
        setReloadKey((value) => value + 1);
      }
      setPendingChange(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось обработать чувствительное изменение");
    } finally {
      setIsSubmittingChange(false);
      setDeletingRuleId(null);
      setIsSavingRule(false);
    }
  }

  const activeRules = overview?.active_rules || [];
  const nextRule = overview?.next_rule || null;
  const hasCampOptions = camps.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        title="График смен и дежурств"
        description="Рабочий экран базы: кто сейчас на смене, когда следующая пересменка и как CRM должна обрабатывать ночные заявки."
        actions={
          <>
            <div className="relative w-full min-w-0 sm:min-w-60">
              <select
                className="soft-input w-full appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60"
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
            <button type="button" className="soft-button w-full sm:w-auto" onClick={() => setReloadKey((value) => value + 1)}>
              Обновить смены
            </button>
          </>
        }
      />

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
                Кто сейчас на смене
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
                Следующая смена
              </div>
              {nextRule ? (
                <div className="mt-4 rounded-3xl border border-border bg-background/65 p-4">
                  <p className="text-sm font-semibold text-foreground">{nextRule.admin_name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {nextRule.weekday_label} · {nextRule.starts_time} → {nextRule.ends_time}
                  </p>
                  <p className="mt-3 text-sm text-foreground">Старт: {formatDateTime(nextRule.starts_at, overview?.timezone || settingsForm.timeZone)}</p>
                </div>
              ) : (
                <p className="mt-4 text-sm leading-6 text-muted-foreground">
                  Следующее правило смены пока не задано. Добавьте график, чтобы CRM понимала, кто обрабатывает новые заявки.
                </p>
              )}
            </section>

            <section className="glass-card p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Clock3 className="h-4 w-4 text-[#E5D3B3]" />
                  Время реакции
                </div>
                <button type="button" className="soft-button px-3 py-2 text-xs" onClick={() => setIsSettingsModalOpen(true)}>
                  Изменить
                </button>
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
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Сменный график</h2>
                <p className="mt-1 text-sm text-muted-foreground">Помесячный принцип здесь не нужен: CRM использует повторяющийся недельный график и определяет, кто на какой смене работает по дням недели.</p>
              </div>
              <div className="flex w-full flex-col gap-3 xl:w-auto xl:min-w-[520px] xl:flex-row">
                <div className="relative min-w-0 flex-1">
                  <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="search"
                    className="soft-input pl-11"
                    placeholder="Поиск по сотруднику, дню недели или комментарию"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                </div>
                <button type="button" className="soft-button gap-2" onClick={openCreateRuleModal} disabled={!staff.length}>
                  <PencilLine className="h-4 w-4" />
                  Редактировать график
                </button>
              </div>
            </div>

            <div className="mt-5 overflow-x-auto rounded-3xl border border-border bg-background/55">
              <div className="min-w-[980px]">
                <div className="grid border-b border-border bg-card/70" style={{ gridTemplateColumns: "260px repeat(7, minmax(0, 1fr))" }}>
                  <div className="sticky left-0 z-10 border-r border-border bg-card/90 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    Сотрудник
                  </div>
                  {weekdayLabels.map((label) => (
                    <div key={label} className="border-r border-border px-4 py-4 text-sm font-semibold text-foreground last:border-r-0">
                      {label}
                    </div>
                  ))}
                </div>

                {groupedRules.length ? (
                  groupedRules.map((row) => (
                    <div key={row.adminId} className="grid border-b border-border last:border-b-0" style={{ gridTemplateColumns: "260px repeat(7, minmax(0, 1fr))" }}>
                      <div className="sticky left-0 z-10 border-r border-border bg-card/88 px-5 py-5">
                        <p className="text-sm font-semibold text-foreground">{row.adminName}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">{row.adminLogin}</p>
                      </div>

                      {row.days.map((dayRules, weekdayIndex) => (
                        <div key={`${row.adminId}-${weekdayIndex}`} className="min-h-36 border-r border-border/80 p-3 last:border-r-0">
                          {dayRules.length ? (
                            <div className="space-y-2">
                              {dayRules.map((rule) => (
                                <article key={rule.id} className="rounded-2xl border border-border bg-card/75 p-3">
                                  <p className="text-sm font-semibold text-foreground">
                                    {rule.starts_at?.slice(0, 5)} → {rule.ends_at?.slice(0, 5)}
                                  </p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${rule.is_active ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300" : "border-slate-500/25 bg-slate-500/10 text-slate-300"}`}>
                                      {rule.is_active ? "Активно" : "Выключено"}
                                    </span>
                                    {rule.is_night_shift ? (
                                      <span className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2.5 py-1 text-[11px] font-medium text-violet-300">
                                        Ночная
                                      </span>
                                    ) : null}
                                  </div>
                                  {rule.comment ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{rule.comment}</p> : null}
                                  <div className="mt-3 flex gap-2">
                                    <button type="button" className="soft-button px-3 py-2 text-xs" onClick={() => openEditRuleModal(rule)}>
                                      Изменить
                                    </button>
                                    <button
                                      type="button"
                                      className="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-300 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60"
                                      onClick={() => handleDeleteRule(rule)}
                                      disabled={deletingRuleId === rule.id}
                                    >
                                      <Trash2 className="h-3.5 w-3.5" />
                                      {deletingRuleId === rule.id ? "Удаляем..." : "Удалить"}
                                    </button>
                                  </div>
                                </article>
                              ))}
                            </div>
                          ) : (
                            <div className="flex h-full min-h-30 items-center justify-center rounded-2xl border border-dashed border-border/70 bg-background/35 px-3 text-center text-xs leading-5 text-muted-foreground">
                              Смена не назначена
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ))
                ) : (
                  <div className="p-6">
                    <EmptyState
                      icon={CalendarClock}
                      compact
                      title="Сменный график ещё не настроен"
                      description="Добавьте правила смен, чтобы CRM понимала, кто работает в каждый день недели и как обрабатывать ночные заявки."
                    />
                  </div>
                )}
              </div>
            </div>
          </section>
        </>
      )}

      <ModalShell
        open={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        title="Время реакции CRM"
        description="Настройте SLA обработки заявок: сколько держать бронь, когда включать эскалацию и сколько повторов отправлять до уведомления управляющего."
      >
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (!selectedCampId) {
              setErrorMessage("Сначала выберите базу.");
              return;
            }
            setPendingChange({
              title: "Чувствительное изменение времени реакции",
              description: "Изменение SLA влияет на заморозку заявок, ночную обработку и эскалации. Решите, отправлять ли его управляющему на подтверждение или применять сразу под свою ответственность.",
              operation: "shift_settings_update",
              payload: toSettingsPayload(settingsForm) as Record<string, unknown>,
              successPending: "Параметры времени реакции отправлены на подтверждение.",
              successApplied: "Параметры времени реакции применены под вашу ответственность.",
            });
            setIsSettingsModalOpen(false);
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
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

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
            <button type="button" className="soft-button" onClick={() => setIsSettingsModalOpen(false)}>
              Отмена
            </button>
            <button type="submit" className="brand-button gap-2 justify-center">
              <Save className="h-4 w-4" />
              Сохранить параметры
            </button>
          </div>
        </form>
      </ModalShell>

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

      <SensitiveChangeModal
        open={Boolean(pendingChange)}
        title={pendingChange?.title || "Чувствительное изменение"}
        description={pendingChange?.description || ""}
        loading={isSubmittingChange}
        onClose={() => {
          if (!isSubmittingChange) {
            setPendingChange(null);
            setDeletingRuleId(null);
          }
        }}
        onConfirm={(comment) => submitSensitiveChange("pending_review", comment)}
        onApply={(comment) => submitSensitiveChange("apply_with_responsibility", comment)}
      />
    </PageMotion>
  );
}
