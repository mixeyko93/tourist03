import { AlarmClockCheck, CalendarClock, ChevronDown, ChevronLeft, ChevronRight, Clock3, PencilLine, Save, Trash2, UserRoundCheck } from "lucide-react";
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
  startsAt: string;
  endsAt: string;
};

type ShiftTarget = {
  adminId: number;
  adminName: string;
  weekday: number;
  dateLabel: string;
  existingRule?: CrmShiftRule | null;
};

type PendingSensitiveChange = {
  title: string;
  description: string;
  operation: string;
  payload: Record<string, unknown>;
  successPending: string;
  successApplied: string;
};

type ViewMode = "month" | "week";

const weekdayLabels = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
const staffColumnWidth = 240;

const emptySettingsForm: ShiftSettingsForm = {
  timeZone: "Asia/Irkutsk",
  bookingHoldHours: "4",
  nightReleaseAfterShiftMinutes: "60",
  escalationStepMinutes: "15",
  escalationRepeatsBeforeManager: "2",
};

const emptyRuleForm: ShiftRuleForm = {
  startsAt: "09:00",
  endsAt: "18:00",
};

function formatDateParam(value: Date) {
  const year = value.getFullYear();
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getMonthLabel(value: Date) {
  const monthLabelRaw = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" }).format(value);
  return `${monthLabelRaw.charAt(0).toUpperCase()}${monthLabelRaw.slice(1)}`;
}

function startOfWeek(value: Date) {
  const next = new Date(value);
  const weekday = next.getDay() || 7;
  next.setHours(0, 0, 0, 0);
  next.setDate(next.getDate() - weekday + 1);
  return next;
}

function addDays(value: Date, amount: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + amount);
  return next;
}

function buildPeriodDates(start: Date, end: Date) {
  const result: Date[] = [];
  for (let cursor = new Date(start); cursor <= end; cursor = addDays(cursor, 1)) {
    result.push(new Date(cursor));
  }
  return result;
}

function getWeekLabel(start: Date, end: Date) {
  const startDay = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(start);
  const endDay = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(end);
  return `${startDay} — ${endDay}`;
}

function getDayNumberLabel(value: Date) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric" }).format(value);
}

function getWeekdayShortLabel(value: Date) {
  return new Intl.DateTimeFormat("ru-RU", { weekday: "short" }).format(value).replace(".", "");
}

function getWeekdayIndex(value: Date) {
  return (value.getDay() + 6) % 7;
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

function formatTargetDate(value: Date) {
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(value);
}

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
    startsAt: rule.starts_at?.slice(0, 5) || "09:00",
    endsAt: rule.ends_at?.slice(0, 5) || "18:00",
  };
}

function toRulePayload(form: ShiftRuleForm, target: ShiftTarget): CrmShiftRuleUpsertPayload {
  return {
    admin_id: target.adminId,
    weekday: target.weekday,
    starts_at: form.startsAt,
    ends_at: form.endsAt,
    is_night_shift: target.existingRule?.is_night_shift || false,
    is_active: target.existingRule?.is_active ?? true,
    comment: target.existingRule?.comment || undefined,
  };
}

function describeRule(rule: CrmShiftRule) {
  return `${weekdayLabels[rule.weekday] || "День"} · ${rule.starts_at?.slice(0, 5) || rule.starts_at} → ${rule.ends_at?.slice(0, 5) || rule.ends_at}`;
}

export default function ShiftsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [focusDate, setFocusDate] = useState(() => new Date());
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
  const [reloadKey, setReloadKey] = useState(0);
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CrmShiftRule | null>(null);
  const [activeTarget, setActiveTarget] = useState<ShiftTarget | null>(null);
  const [ruleForm, setRuleForm] = useState<ShiftRuleForm>(emptyRuleForm);
  const [ruleError, setRuleError] = useState("");
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

  const sortedStaff = useMemo(
    () => [...staff].sort((left, right) => left.display_name.localeCompare(right.display_name, "ru")),
    [staff],
  );

  const rulesByCell = useMemo(() => {
    const map = new Map<string, CrmShiftRule[]>();
    rules.forEach((rule) => {
      const key = `${rule.admin_id}:${rule.weekday}`;
      if (!map.has(key)) {
        map.set(key, []);
      }
      map.get(key)?.push(rule);
    });

    Array.from(map.values()).forEach((items) => {
      items.sort((left, right) => `${left.starts_at}-${left.ends_at}`.localeCompare(`${right.starts_at}-${right.ends_at}`));
    });

    return map;
  }, [rules]);

  const periodStart = useMemo(() => {
    if (viewMode === "week") {
      return startOfWeek(focusDate);
    }
    return new Date(focusDate.getFullYear(), focusDate.getMonth(), 1);
  }, [focusDate, viewMode]);

  const periodEnd = useMemo(() => {
    if (viewMode === "week") {
      return addDays(periodStart, 6);
    }
    return new Date(periodStart.getFullYear(), periodStart.getMonth() + 1, 0);
  }, [periodStart, viewMode]);

  const visibleDates = useMemo(() => buildPeriodDates(periodStart, periodEnd), [periodEnd, periodStart]);
  const periodLabel = viewMode === "week" ? getWeekLabel(periodStart, periodEnd) : getMonthLabel(periodStart);
  const dayColumnWidth = viewMode === "week" ? 140 : 92;
  const gridWidth = staffColumnWidth + visibleDates.length * dayColumnWidth;

  function buildTarget(member: CrmShiftStaffOption, date: Date, existingRule?: CrmShiftRule | null): ShiftTarget {
    return {
      adminId: member.id,
      adminName: member.display_name,
      weekday: getWeekdayIndex(date),
      dateLabel: formatTargetDate(date),
      existingRule,
    };
  }

  function openTargetModal(target: ShiftTarget, rule?: CrmShiftRule | null) {
    setActiveTarget(target);
    setEditingRule(rule || null);
    setRuleForm(rule ? mapRuleForm(rule) : emptyRuleForm);
    setRuleError("");
    setIsRuleModalOpen(true);
  }

  function openCreateRuleModal() {
    if (!sortedStaff.length) {
      return;
    }
    const todayKey = formatDateParam(new Date());
    const initialDate = visibleDates.find((item) => formatDateParam(item) === todayKey) || visibleDates[0] || new Date();
    openTargetModal(buildTarget(sortedStaff[0], initialDate));
  }

  function openCellModal(member: CrmShiftStaffOption, date: Date, rule?: CrmShiftRule | null) {
    openTargetModal(buildTarget(member, date, rule), rule);
  }

  async function handleSaveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId || !activeTarget) {
      setRuleError("Сначала выберите базу и ячейку графика.");
      return;
    }

    setPendingChange({
      title: editingRule ? "Согласование изменения смены" : "Согласование параметров смены",
      description: "График смен влияет на ночной сценарий, эскалации и распределение заявок. Это изменение должно быть подтверждено или применено под ответственность инициатора.",
      operation: editingRule ? "shift_rule_update" : "shift_rule_create",
      payload: editingRule
        ? ({ rule_id: editingRule.id, data: toRulePayload(ruleForm, activeTarget) } as Record<string, unknown>)
        : (toRulePayload(ruleForm, activeTarget) as Record<string, unknown>),
      successPending: editingRule ? "Параметры смены отправлены на подтверждение." : "Параметры смены отправлены на подтверждение.",
      successApplied: editingRule ? "Параметры смены применены под вашу ответственность." : "Параметры смены применены под вашу ответственность.",
    });
    setIsRuleModalOpen(false);
    setEditingRule(null);
    setActiveTarget(null);
    setRuleError("");
  }

  async function handleDeleteRule(rule: CrmShiftRule) {
    setDeletingRuleId(rule.id);
    setPendingChange({
      title: "Согласование удаления смены",
      description: "Удаление смены меняет логику назначения ответственного и ночную обработку заявок. Это действие нужно согласовать или применить под ответственность.",
      operation: "shift_rule_delete",
      payload: { rule_id: rule.id },
      successPending: `Удаление смены отправлено на подтверждение: ${describeRule(rule)}`,
      successApplied: `Удаление смены применено под вашу ответственность: ${describeRule(rule)}`,
    });
    setIsRuleModalOpen(false);
    setEditingRule(null);
    setActiveTarget(null);
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
    }
  }

  const activeRules = overview?.active_rules || [];
  const nextRule = overview?.next_rule || null;
  const hasCampOptions = camps.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        title="График смен и дежурств"
        description="Рабочий экран базы: кто сейчас на смене, когда начинается следующая смена и как CRM должна обрабатывать ночные заявки."
        actions={
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
            <section className="glass-card flex h-full flex-col p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <UserRoundCheck className="h-4 w-4 text-[#E5D3B3]" />
                Кто сейчас на смене
              </div>
              {activeRules.length ? (
                <div className="mt-4 flex-1 space-y-3">
                  {activeRules.map((rule) => (
                    <div key={`${rule.rule_id}-${rule.starts_at}`} className="rounded-3xl border border-border bg-background/65 p-4">
                      <p className="text-sm font-semibold text-foreground">{rule.admin_name}</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {rule.starts_time} → {rule.ends_time}
                        {rule.is_night_shift ? " · Ночная смена" : ""}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="mt-4 flex-1 text-sm leading-6 text-muted-foreground">
                  Сейчас никто не назначен на смену. Ночная логика будет держать заявку до начала следующей смены плюс ещё {settingsForm.nightReleaseAfterShiftMinutes} минут.
                </p>
              )}
            </section>

            <section className="glass-card flex h-full flex-col p-5">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <AlarmClockCheck className="h-4 w-4 text-[#E5D3B3]" />
                Следующая смена
              </div>
              {nextRule ? (
                <div className="mt-4 flex-1 rounded-3xl border border-border bg-background/65 p-4">
                  <p className="text-sm font-semibold text-foreground">{nextRule.admin_name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {nextRule.weekday_label} · {nextRule.starts_time} → {nextRule.ends_time}
                  </p>
                  <p className="mt-3 text-sm text-foreground">Старт: {formatDateTime(nextRule.starts_at, overview?.timezone || settingsForm.timeZone)}</p>
                </div>
              ) : (
                <p className="mt-4 flex-1 text-sm leading-6 text-muted-foreground">
                  Следующее правило смены пока не задано. Добавьте график, чтобы CRM понимала, кто обрабатывает новые заявки.
                </p>
              )}
            </section>

            <section className="glass-card flex h-full flex-col p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Clock3 className="h-4 w-4 text-[#E5D3B3]" />
                  <span className="whitespace-nowrap">Время реакции обработки брони</span>
                </div>
                <button type="button" className="soft-button shrink-0 px-3.5 py-2 text-sm" onClick={() => setIsSettingsModalOpen(true)}>
                  Изменить
                </button>
              </div>
              <div className="mt-4 flex-1 space-y-3 rounded-3xl border border-border bg-background/65 p-4 text-sm text-muted-foreground">
                <p>
                  Заморозка заявки: <span className="font-medium text-foreground">{settingsForm.bookingHoldHours} ч.</span>
                </p>
                <p>
                  Ночной запас после смены: <span className="font-medium text-foreground">{settingsForm.nightReleaseAfterShiftMinutes} мин.</span>
                </p>
                <p>
                  Шаг эскалации: <span className="font-medium text-foreground">{settingsForm.escalationStepMinutes} мин.</span>
                </p>
                <p>
                  Повторов до управляющего: <span className="font-medium text-foreground">{settingsForm.escalationRepeatsBeforeManager}</span>
                </p>
              </div>
            </section>
          </div>

          <section className="glass-card p-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setFocusDate((current) =>
                      viewMode === "week" ? addDays(current, -7) : new Date(current.getFullYear(), current.getMonth() - 1, 1),
                    )
                  }
                  className="soft-button h-11 w-11 px-0"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button type="button" onClick={() => setFocusDate(new Date())} className="soft-button">
                  Сегодня
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setFocusDate((current) =>
                      viewMode === "week" ? addDays(current, 7) : new Date(current.getFullYear(), current.getMonth() + 1, 1),
                    )
                  }
                  className="soft-button h-11 w-11 px-0"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>

                <div className="rounded-2xl border border-border bg-background/70 p-1">
                  <button
                    type="button"
                    onClick={() => setViewMode("month")}
                    className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                      viewMode === "month" ? "border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-foreground" : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Месяц
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("week")}
                    className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                      viewMode === "week" ? "border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-foreground" : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Неделя
                  </button>
                </div>

                <h2 className="text-xl font-semibold tracking-[-0.04em] text-foreground sm:ml-2">Сменный график · {periodLabel}</h2>
              </div>

              <button type="button" className="soft-button gap-2 px-4 py-2.5 text-sm" onClick={openCreateRuleModal} disabled={!sortedStaff.length}>
                <PencilLine className="h-4 w-4" />
                Параметры смены
              </button>
            </div>

            <div className="mt-5 overflow-x-auto rounded-3xl border border-border bg-background/55">
              <div style={{ width: `${gridWidth}px`, minWidth: "100%" }}>
                <div
                  className="grid border-b border-border bg-card/70"
                  style={{ gridTemplateColumns: `${staffColumnWidth}px repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}
                >
                  <div className="sticky left-0 z-10 border-r border-border bg-card/90 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    Сотрудник
                  </div>
                  {visibleDates.map((date) => (
                    <div key={formatDateParam(date)} className="border-r border-border px-3 py-3 text-center last:border-r-0">
                      <div className="text-base font-semibold text-foreground">{getDayNumberLabel(date)}</div>
                      <div className="mt-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{getWeekdayShortLabel(date)}</div>
                    </div>
                  ))}
                </div>

                {sortedStaff.length ? (
                  sortedStaff.map((member) => (
                    <div
                      key={member.id}
                      className="grid border-b border-border last:border-b-0"
                      style={{ gridTemplateColumns: `${staffColumnWidth}px repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}
                    >
                      <div className="sticky left-0 z-10 border-r border-border bg-card/88 px-5 py-5">
                        <p className="text-sm font-semibold text-foreground">{member.display_name}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">{member.role_label}</p>
                      </div>

                      {visibleDates.map((date) => {
                        const dateKey = formatDateParam(date);
                        const weekday = getWeekdayIndex(date);
                        const cellRules = rulesByCell.get(`${member.id}:${weekday}`) || [];

                        return (
                          <div key={`${member.id}-${dateKey}`} className="min-h-28 border-r border-border/80 p-2 last:border-r-0">
                            {cellRules.length ? (
                              <div className="space-y-2">
                                {cellRules.map((rule) => (
                                  <button
                                    key={rule.id}
                                    type="button"
                                    className="flex w-full flex-col rounded-2xl border border-[#E5D3B3]/22 bg-[#E5D3B3]/10 px-2.5 py-2 text-left transition hover:bg-[#E5D3B3]/16"
                                    onClick={() => openCellModal(member, date, rule)}
                                  >
                                    <span className="text-xs font-semibold text-foreground">
                                      {rule.starts_at?.slice(0, 5)} → {rule.ends_at?.slice(0, 5)}
                                    </span>
                                    <span className="mt-1 text-[11px] text-muted-foreground">
                                      {rule.is_night_shift ? "Ночная смена" : "Рабочее окно"}
                                    </span>
                                  </button>
                                ))}
                              </div>
                            ) : (
                              <button
                                type="button"
                                className="flex h-full min-h-24 w-full items-center justify-center rounded-2xl border border-dashed border-border/70 bg-background/35 px-3 text-center text-xs leading-5 text-muted-foreground transition hover:border-[#E5D3B3]/30 hover:text-foreground"
                                onClick={() => openCellModal(member, date)}
                              >
                                Назначить смену
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ))
                ) : (
                  <div className="p-6">
                    <EmptyState
                      icon={CalendarClock}
                      compact
                      title="Сменный график ещё не настроен"
                      description="Добавьте сотрудников в команду базы, чтобы CRM могла распределять смены и ночные заявки."
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
        title="Время реакции обработки брони"
        description="Настройте время реакции обработки заявок: сколько держать бронь, когда включать эскалацию и сколько повторов отправлять до уведомления управляющего."
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
              title: "Необходимо согласование управляющего",
              description: "Изменение этих параметров влияет на заморозку заявок, ночную обработку и эскалацию. Решите, отправлять ли его управляющему на подтверждение или применять сразу под свою ответственность.",
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
            <button type="button" className="soft-button px-4 py-2.5 text-sm" onClick={() => setIsSettingsModalOpen(false)}>
              Отмена
            </button>
            <button type="submit" className="brand-button justify-center gap-2 px-5 py-2.5 text-sm">
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
          setActiveTarget(null);
          setRuleError("");
        }}
        title="Параметры смены"
        description="Укажите только начало и конец смены для выбранной ячейки графика."
      >
        <form className="space-y-5" onSubmit={handleSaveRule}>
          {ruleError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{ruleError}</div>
          ) : null}

          {activeTarget ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-border bg-background/60 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Сотрудник</p>
                <p className="mt-1 text-sm font-medium text-foreground">{activeTarget.adminName}</p>
              </div>
              <div className="rounded-2xl border border-border bg-background/60 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">День</p>
                <p className="mt-1 text-sm font-medium text-foreground">{activeTarget.dateLabel}</p>
              </div>
            </div>
          ) : null}

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

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {editingRule ? (
                <button
                  type="button"
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => void handleDeleteRule(editingRule)}
                  disabled={deletingRuleId === editingRule.id}
                >
                  <Trash2 className="h-4 w-4" />
                  {deletingRuleId === editingRule.id ? "Удаляем..." : "Удалить"}
                </button>
              ) : null}
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                className="soft-button px-4 py-2.5 text-sm"
                onClick={() => {
                  setIsRuleModalOpen(false);
                  setEditingRule(null);
                  setActiveTarget(null);
                  setRuleError("");
                }}
              >
                Отмена
              </button>
              <button type="submit" className="brand-button justify-center gap-2 px-5 py-2.5 text-sm">
                <Save className="h-4 w-4" />
                Сохранить параметры
              </button>
            </div>
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
