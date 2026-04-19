import { AlarmClockCheck, CalendarClock, CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Clock3, PencilLine, Save, Trash2, UserRoundCheck } from "lucide-react";
import { type PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageMotion } from "../components/PageMotion";
import { PageRefreshOverlay } from "../components/PageRefreshOverlay";
import { SectionHeading } from "../components/SectionHeading";
import { SensitiveChangeModal } from "../components/SensitiveChangeModal";
import { usePageLoadState } from "../components/usePageLoadState";
import {
  createCrmChangeRequest,
  createCrmShiftRule,
  deleteCrmShiftRule,
  fetchCrmCamps,
  fetchCrmShifts,
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
  nightStartsAt: string;
  nightReleaseAfterShiftMinutes: string;
  escalationStepMinutes: string;
  escalationRepeatsBeforeManager: string;
};

type ShiftRuleForm = {
  startsAt: string;
  endsOnDate: string;
  endsAt: string;
  comment: string;
};

type ShiftPresetForm = {
  startsAt: string;
  endsAt: string;
};

type ShiftTarget = {
  adminId: number;
  adminName: string;
  shiftDate: string;
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
  nightStartsAt: "22:00",
  nightReleaseAfterShiftMinutes: "60",
  escalationStepMinutes: "15",
  escalationRepeatsBeforeManager: "2",
};

const emptyRuleForm: ShiftRuleForm = {
  startsAt: "09:00",
  endsOnDate: "",
  endsAt: "18:00",
  comment: "",
};

const emptyPresetForm: ShiftPresetForm = {
  startsAt: "09:00",
  endsAt: "18:00",
};

const monthLabels = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
const weekdayShortLabels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const timeMinuteOptions = ["00", "15", "30", "45"];

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

function parseDateParam(value: string) {
  const [year, month, day] = value.split("-").map((item) => Number(item));
  return new Date(year, (month || 1) - 1, day || 1);
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

function formatDateButtonLabel(value: string) {
  if (!value) {
    return "Выберите дату";
  }
  const date = parseDateParam(value);
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function getMonthGridStart(value: Date) {
  return startOfWeek(new Date(value.getFullYear(), value.getMonth(), 1));
}

function buildCalendarMatrix(viewDate: Date) {
  const start = getMonthGridStart(viewDate);
  return Array.from({ length: 35 }, (_, index) => addDays(start, index));
}

function splitTimeParts(value: string) {
  const [hours = "09", minutes = "00"] = value.split(":");
  return { hours, minutes };
}

type PopoverFieldShellProps = {
  label: string;
  open: boolean;
  onToggle: () => void;
  value: string;
  icon: ReactNode;
  children: ReactNode;
};

function PopoverFieldShell({ label, open, onToggle, value, icon, children }: PopoverFieldShellProps) {
  return (
    <div className="relative space-y-2">
      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <button type="button" className="soft-input flex items-center justify-between gap-3 py-3.5 text-left" onClick={onToggle}>
        <span className="text-base font-semibold text-foreground">{value}</span>
        <span className="shrink-0 text-foreground">{icon}</span>
      </button>
      {open ? (
        <div className="absolute left-0 top-[calc(100%+0.65rem)] z-30 w-full min-w-[18rem] rounded-3xl border border-border bg-card/98 p-4 shadow-2xl backdrop-blur-xl">
          {children}
        </div>
      ) : null}
    </div>
  );
}

type ShiftDateFieldProps = {
  label: string;
  value: string;
  min?: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onChange: (value: string) => void;
};

function ShiftDateField({ label, value, min, open, onToggle, onClose, onChange }: ShiftDateFieldProps) {
  const [viewDate, setViewDate] = useState(() => (value ? parseDateParam(value) : new Date()));

  useEffect(() => {
    if (open) {
      setViewDate(value ? parseDateParam(value) : min ? parseDateParam(min) : new Date());
    }
  }, [min, open, value]);

  const minDate = min ? parseDateParam(min) : null;
  const calendarDays = buildCalendarMatrix(viewDate);

  return (
    <PopoverFieldShell
      label={label}
      open={open}
      onToggle={onToggle}
      value={formatDateButtonLabel(value)}
      icon={<CalendarDays className="h-5 w-5" />}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <button type="button" className="soft-button h-11 w-11 rounded-2xl px-0" onClick={() => setViewDate((current) => new Date(current.getFullYear(), current.getMonth() - 1, 1))}>
            <ChevronLeft className="h-4 w-4" />
          </button>
          <div className="rounded-2xl border border-border bg-background/65 px-4 py-2 text-center">
            <div className="text-lg font-semibold text-foreground">{monthLabels[viewDate.getMonth()]}</div>
            <div className="text-sm text-muted-foreground">{viewDate.getFullYear()}</div>
          </div>
          <button type="button" className="soft-button h-11 w-11 rounded-2xl px-0" onClick={() => setViewDate((current) => new Date(current.getFullYear(), current.getMonth() + 1, 1))}>
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="grid grid-cols-7 gap-2 text-center text-sm font-medium text-muted-foreground">
          {weekdayShortLabels.map((day) => (
            <div key={day} className="py-2">
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-2">
          {calendarDays.map((day) => {
            const iso = formatDateParam(day);
            const isCurrentMonth = day.getMonth() === viewDate.getMonth();
            const isSelected = value === iso;
            const isDisabled = Boolean(minDate && day < minDate);
            return (
              <button
                key={iso}
                type="button"
                disabled={isDisabled}
                className={`flex h-11 items-center justify-center rounded-2xl border text-sm font-semibold transition ${
                  isSelected
                    ? "border-[#E5D3B3]/45 bg-[#E5D3B3] text-slate-900"
                    : isCurrentMonth
                      ? "border-border bg-background/65 text-foreground hover:border-[#E5D3B3]/35 hover:bg-[#E5D3B3]/10"
                      : "border-transparent bg-transparent text-muted-foreground/60 hover:border-border hover:bg-background/45"
                } ${isDisabled ? "cursor-not-allowed opacity-40" : ""}`}
                onClick={() => {
                  if (isDisabled) {
                    return;
                  }
                  onChange(iso);
                  onClose();
                }}
              >
                {day.getDate()}
              </button>
            );
          })}
        </div>
      </div>
    </PopoverFieldShell>
  );
}

type ShiftTimeFieldProps = {
  label: string;
  value: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onChange: (value: string) => void;
};

function ShiftTimeField({ label, value, open, onToggle, onClose, onChange }: ShiftTimeFieldProps) {
  const parts = splitTimeParts(value);

  return (
    <PopoverFieldShell
      label={label}
      open={open}
      onToggle={onToggle}
      value={value}
      icon={<Clock3 className="h-5 w-5" />}
    >
      <div className="space-y-4">
        <div className="rounded-2xl border border-border bg-background/65 px-4 py-3 text-center">
          <div className="text-2xl font-semibold tracking-[-0.04em] text-foreground">{value}</div>
          <div className="mt-1 text-sm text-muted-foreground">Выберите часы и минуты</div>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Часы</p>
          <div className="grid grid-cols-4 gap-2">
            {Array.from({ length: 24 }, (_, index) => `${index}`.padStart(2, "0")).map((hours) => {
              const next = `${hours}:${parts.minutes}`;
              const active = parts.hours === hours;
              return (
                <button
                  key={hours}
                  type="button"
                  className={`rounded-2xl border px-3 py-2 text-sm font-semibold transition ${
                    active ? "border-[#E5D3B3]/45 bg-[#E5D3B3] text-slate-900" : "border-border bg-background/65 text-foreground hover:border-[#E5D3B3]/35 hover:bg-[#E5D3B3]/10"
                  }`}
                  onClick={() => onChange(next)}
                >
                  {hours}
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Минуты</p>
          <div className="grid grid-cols-4 gap-2">
            {timeMinuteOptions.map((minutes) => {
              const next = `${parts.hours}:${minutes}`;
              const active = parts.minutes === minutes;
              return (
                <button
                  key={minutes}
                  type="button"
                  className={`rounded-2xl border px-3 py-2 text-sm font-semibold transition ${
                    active ? "border-[#E5D3B3]/45 bg-[#E5D3B3] text-slate-900" : "border-border bg-background/65 text-foreground hover:border-[#E5D3B3]/35 hover:bg-[#E5D3B3]/10"
                  }`}
                  onClick={() => {
                    onChange(next);
                    onClose();
                  }}
                >
                  {minutes}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </PopoverFieldShell>
  );
}

function mapSettingsForm(settings: CrmShiftSettings): ShiftSettingsForm {
  return {
    timeZone: settings.time_zone || "Asia/Irkutsk",
    bookingHoldHours: String(settings.booking_hold_hours || 4),
    nightStartsAt: settings.night_starts_at || "22:00",
    nightReleaseAfterShiftMinutes: String(settings.night_release_after_shift_minutes || 60),
    escalationStepMinutes: String(settings.escalation_step_minutes || 15),
    escalationRepeatsBeforeManager: String(settings.escalation_repeats_before_manager || 2),
  };
}

function toSettingsPayload(form: ShiftSettingsForm) {
  return {
    time_zone: form.timeZone,
    booking_hold_hours: Number(form.bookingHoldHours || 4),
    night_starts_at: form.nightStartsAt || "22:00",
    night_release_after_shift_minutes: Number(form.nightReleaseAfterShiftMinutes || 60),
    escalation_step_minutes: Number(form.escalationStepMinutes || 15),
    escalation_repeats_before_manager: Number(form.escalationRepeatsBeforeManager || 2),
  };
}

function mapRuleForm(rule: CrmShiftRule): ShiftRuleForm {
  return {
    startsAt: rule.starts_at?.slice(0, 5) || "09:00",
    endsOnDate: rule.ends_on_date || rule.shift_date || "",
    endsAt: rule.ends_at?.slice(0, 5) || "18:00",
    comment: rule.comment || "",
  };
}

function toRulePayload(form: ShiftRuleForm, target: ShiftTarget): CrmShiftRuleUpsertPayload {
  return {
    admin_id: target.adminId,
    shift_date: target.shiftDate,
    ends_on_date: form.endsOnDate || target.shiftDate,
    starts_at: form.startsAt,
    ends_at: form.endsAt,
    is_night_shift: target.existingRule?.is_night_shift || false,
    is_active: target.existingRule?.is_active ?? true,
    comment: form.comment.trim() || undefined,
  };
}

function describeRule(rule: CrmShiftRule) {
  const startDate = rule.shift_date;
  const endDate = rule.ends_on_date || rule.shift_date;
  const startTime = rule.starts_at?.slice(0, 5) || rule.starts_at;
  const endTime = rule.ends_at?.slice(0, 5) || rule.ends_at;
  if (startDate && endDate && startDate !== endDate) {
    return `${startDate} ${startTime} → ${endDate} ${endTime}`;
  }
  if (startDate) {
    return `${startDate} · ${startTime} → ${endTime}`;
  }
  return `${weekdayLabels[rule.weekday] || "День"} · ${startTime} → ${endTime}`;
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
  const [isPresetModalOpen, setIsPresetModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<CrmShiftRule | null>(null);
  const [activeTarget, setActiveTarget] = useState<ShiftTarget | null>(null);
  const [ruleForm, setRuleForm] = useState<ShiftRuleForm>(emptyRuleForm);
  const [presetForm, setPresetForm] = useState<ShiftPresetForm>(emptyPresetForm);
  const [ruleError, setRuleError] = useState("");
  const [isSavingRule, setIsSavingRule] = useState(false);
  const [deletingRuleId, setDeletingRuleId] = useState<number | null>(null);
  const [pendingChange, setPendingChange] = useState<PendingSensitiveChange | null>(null);
  const [isSubmittingChange, setIsSubmittingChange] = useState(false);
  const [activePresetTimeField, setActivePresetTimeField] = useState<"start" | "end" | null>(null);
  const [activeRulePicker, setActiveRulePicker] = useState<"start" | "date" | "end" | null>(null);
  const [activeSettingsTimeField, setActiveSettingsTimeField] = useState<"night-start" | null>(null);
  const [hasHorizontalOverflow, setHasHorizontalOverflow] = useState(false);
  const [isScrollIndicatorActive, setIsScrollIndicatorActive] = useState(false);
  const [isGridDragging, setIsGridDragging] = useState(false);
  const [scrollThumbWidth, setScrollThumbWidth] = useState(0);
  const [scrollThumbOffset, setScrollThumbOffset] = useState(0);
  const [tooltipFlip, setTooltipFlip] = useState<Map<number, boolean>>(new Map());
  const gridScrollRef = useRef<HTMLDivElement | null>(null);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const scrollIndicatorTimeoutRef = useRef<number | null>(null);
  const dragPointerIdRef = useRef<number | null>(null);
  const dragStartXRef = useRef(0);
  const dragStartScrollLeftRef = useRef(0);
  const gridDragPointerIdRef = useRef<number | null>(null);
  const gridDragStartXRef = useRef(0);
  const gridDragStartScrollLeftRef = useRef(0);

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
      if (!rule.shift_date) {
        return;
      }
      const startDate = parseDateParam(rule.shift_date);
      const endDate = parseDateParam(rule.ends_on_date || rule.shift_date);
      for (let cursor = new Date(startDate); cursor <= endDate; cursor = addDays(cursor, 1)) {
        const key = `${rule.admin_id}:${formatDateParam(cursor)}`;
        if (!map.has(key)) {
          map.set(key, []);
        }
        map.get(key)?.push(rule);
      }
    });

    Array.from(map.values()).forEach((items) => {
      items.sort((left, right) => `${left.starts_at}-${left.ends_at}`.localeCompare(`${right.starts_at}-${right.ends_at}`));
    });

    return map;
  }, [rules]);

  useEffect(() => {
    if (!successMessage && !errorMessage) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setSuccessMessage("");
      setErrorMessage("");
    }, 2600);
    return () => window.clearTimeout(timeoutId);
  }, [errorMessage, successMessage]);

  async function refreshShiftsSilently(campId: number) {
    try {
      const payload = await fetchCrmShifts(campId);
      setSettingsForm(mapSettingsForm(payload.settings));
      setRules(payload.rules);
      setStaff(payload.staff);
      setOverview(payload.overview);
    } catch {
      // Silent sync should not flash the whole page. The next hard reload will recover state.
    }
  }

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

  const updateScrollMetrics = () => {
    const gridNode = gridScrollRef.current;
    if (!gridNode) {
      setHasHorizontalOverflow(false);
      setScrollThumbWidth(0);
      setScrollThumbOffset(0);
      return;
    }

    const hasOverflow = gridNode.scrollWidth - gridNode.clientWidth > 8;
    setHasHorizontalOverflow(hasOverflow);
    if (!hasOverflow) {
      const trackWidth = trackRef.current?.clientWidth ?? 0;
      setScrollThumbWidth(trackWidth);
      setScrollThumbOffset(0);
      return;
    }

    const trackNode = trackRef.current;
    if (!trackNode || trackNode.clientWidth <= 0) {
      return;
    }

    const visibleRatio = gridNode.clientWidth / gridNode.scrollWidth;
    const nextThumbWidth = Math.max(44, Math.min(trackNode.clientWidth, trackNode.clientWidth * visibleRatio));
    const maxGridScroll = Math.max(1, gridNode.scrollWidth - gridNode.clientWidth);
    const maxThumbOffset = Math.max(0, trackNode.clientWidth - nextThumbWidth);

    setScrollThumbWidth(nextThumbWidth);
    setScrollThumbOffset(maxThumbOffset * (gridNode.scrollLeft / maxGridScroll));
  };

  const activateScrollIndicator = () => {
    setIsScrollIndicatorActive(true);
    if (typeof window === "undefined") {
      return;
    }
    if (scrollIndicatorTimeoutRef.current !== null) {
      window.clearTimeout(scrollIndicatorTimeoutRef.current);
    }
    scrollIndicatorTimeoutRef.current = window.setTimeout(() => {
      setIsScrollIndicatorActive(false);
      scrollIndicatorTimeoutRef.current = null;
    }, 1200);
  };

  const syncScrollFromGrid = () => {
    updateScrollMetrics();
    activateScrollIndicator();
  };

  const updateGridScrollFromPointer = (clientX: number, alignToCenter = false) => {
    const gridNode = gridScrollRef.current;
    const trackNode = trackRef.current;
    if (!gridNode || !trackNode || trackNode.clientWidth <= 0) {
      return;
    }

    const trackRect = trackNode.getBoundingClientRect();
    const trackWidth = trackRect.width;
    const thumbWidth = Math.max(44, scrollThumbWidth || trackWidth);
    const maxThumbOffset = Math.max(0, trackWidth - thumbWidth);
    const maxGridScroll = Math.max(0, gridNode.scrollWidth - gridNode.clientWidth);
    if (maxThumbOffset <= 0 || maxGridScroll <= 0) {
      return;
    }

    const pointerOffset = clientX - trackRect.left - (alignToCenter ? thumbWidth / 2 : 0);
    const boundedOffset = Math.max(0, Math.min(maxThumbOffset, pointerOffset));
    gridNode.scrollLeft = (boundedOffset / maxThumbOffset) * maxGridScroll;
    syncScrollFromGrid();
  };

  useEffect(() => {
    updateScrollMetrics();
    if (typeof window !== "undefined") {
      window.addEventListener("resize", updateScrollMetrics);
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("resize", updateScrollMetrics);
      }
    };
  }, [gridWidth, sortedStaff.length, viewMode]);

  useEffect(() => {
    updateScrollMetrics();
  }, [hasHorizontalOverflow]);

  useEffect(() => {
    return () => {
      if (scrollIndicatorTimeoutRef.current !== null && typeof window !== "undefined") {
        window.clearTimeout(scrollIndicatorTimeoutRef.current);
      }
    };
  }, []);

  function buildTarget(member: CrmShiftStaffOption, date: Date, existingRule?: CrmShiftRule | null): ShiftTarget {
    const shiftDate = existingRule?.shift_date || formatDateParam(date);
    return {
      adminId: member.id,
      adminName: member.display_name,
      shiftDate,
      dateLabel: formatTargetDate(parseDateParam(shiftDate)),
      existingRule,
    };
  }

  function openTargetModal(target: ShiftTarget, rule?: CrmShiftRule | null) {
    setActiveTarget(target);
    setEditingRule(rule || null);
    setRuleForm(
      rule
        ? mapRuleForm(rule)
        : {
            startsAt: presetForm.startsAt,
            endsOnDate: target.shiftDate,
            endsAt: presetForm.endsAt,
            comment: "",
          },
    );
    setRuleError("");
    setActiveRulePicker(null);
    setIsRuleModalOpen(true);
  }

  function openCreateRuleModal() {
    setActivePresetTimeField(null);
    setIsPresetModalOpen(true);
  }

  function openCellModal(member: CrmShiftStaffOption, date: Date, rule?: CrmShiftRule | null) {
    openTargetModal(buildTarget(member, date, rule), rule);
  }

  const handleTrackPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.dataset.thumb === "true") {
      dragPointerIdRef.current = event.pointerId;
      dragStartXRef.current = event.clientX;
      dragStartScrollLeftRef.current = gridScrollRef.current?.scrollLeft ?? 0;
      event.currentTarget.setPointerCapture(event.pointerId);
      activateScrollIndicator();
      return;
    }

    updateGridScrollFromPointer(event.clientX, true);
    activateScrollIndicator();
  };

  const handleTrackPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragPointerIdRef.current !== event.pointerId) {
      return;
    }
    const gridNode = gridScrollRef.current;
    const trackNode = trackRef.current;
    if (!gridNode || !trackNode) {
      return;
    }

    const thumbWidth = Math.max(44, scrollThumbWidth || trackNode.clientWidth);
    const maxThumbOffset = Math.max(1, trackNode.clientWidth - thumbWidth);
    const maxGridScroll = Math.max(0, gridNode.scrollWidth - gridNode.clientWidth);
    const deltaX = event.clientX - dragStartXRef.current;
    const scrollDelta = (deltaX / maxThumbOffset) * maxGridScroll;
    gridNode.scrollLeft = dragStartScrollLeftRef.current + scrollDelta;
    syncScrollFromGrid();
  };

  const handleTrackPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragPointerIdRef.current !== event.pointerId) {
      return;
    }
    dragPointerIdRef.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const handleGridPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.pointerType !== "mouse" || event.button !== 0) {
      return;
    }
    const target = event.target as HTMLElement;
    if (target.closest("[data-shift-cell='true']")) {
      return;
    }

    const gridNode = gridScrollRef.current;
    if (!gridNode || gridNode.scrollWidth <= gridNode.clientWidth) {
      return;
    }

    gridDragPointerIdRef.current = event.pointerId;
    gridDragStartXRef.current = event.clientX;
    gridDragStartScrollLeftRef.current = gridNode.scrollLeft;
    event.currentTarget.setPointerCapture(event.pointerId);
    setIsGridDragging(true);
    activateScrollIndicator();
  };

  const handleGridPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (gridDragPointerIdRef.current !== event.pointerId) {
      return;
    }
    const gridNode = gridScrollRef.current;
    if (!gridNode) {
      return;
    }
    const deltaX = event.clientX - gridDragStartXRef.current;
    gridNode.scrollLeft = gridDragStartScrollLeftRef.current - deltaX;
    syncScrollFromGrid();
  };

  const stopGridDragging = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (gridDragPointerIdRef.current !== event.pointerId) {
      return;
    }
    gridDragPointerIdRef.current = null;
    setIsGridDragging(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  async function handleSaveRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCampId || !activeTarget) {
      setRuleError("Сначала выберите базу и ячейку графика.");
      return;
    }
    try {
      setIsSavingRule(true);
      setRuleError("");
      setErrorMessage("");
      if (editingRule) {
        await updateCrmShiftRule(selectedCampId, editingRule.id, toRulePayload(ruleForm, activeTarget));
        setRules((current) =>
          current.map((item) =>
            item.id === editingRule.id
              ? {
                  ...item,
                  admin_id: activeTarget.adminId,
                  admin_name: activeTarget.adminName,
                  shift_date: activeTarget.shiftDate,
                  ends_on_date: ruleForm.endsOnDate || activeTarget.shiftDate,
                  weekday: getWeekdayIndex(parseDateParam(activeTarget.shiftDate)),
                  starts_at: ruleForm.startsAt,
                  ends_at: ruleForm.endsAt,
                  comment: ruleForm.comment.trim() || null,
                  comment_author_display: ruleForm.comment.trim() ? "Вы" : null,
                  comment_author_login: ruleForm.comment.trim() ? "you" : null,
                  updated_at: new Date().toISOString(),
                }
              : item,
          ),
        );
        setSuccessMessage("Параметры смены сохранены.");
      } else {
        const response = await createCrmShiftRule(selectedCampId, toRulePayload(ruleForm, activeTarget));
        setRules((current) => [
          ...current,
          {
            id: response.id,
            camp_id: selectedCampId,
            admin_id: activeTarget.adminId,
            admin_name: activeTarget.adminName,
            admin_email: "",
            shift_date: activeTarget.shiftDate,
            ends_on_date: ruleForm.endsOnDate || activeTarget.shiftDate,
            weekday: getWeekdayIndex(parseDateParam(activeTarget.shiftDate)),
            starts_at: ruleForm.startsAt,
            ends_at: ruleForm.endsAt,
            is_night_shift: false,
            is_active: true,
            comment: ruleForm.comment.trim() || null,
            comment_author_display: ruleForm.comment.trim() ? "Вы" : null,
            comment_author_login: ruleForm.comment.trim() ? "you" : null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]);
        setSuccessMessage("Смена назначена.");
      }
      setPresetForm((current) => ({
        ...current,
        startsAt: ruleForm.startsAt,
        endsAt: ruleForm.endsAt,
      }));
      setIsRuleModalOpen(false);
      setEditingRule(null);
      setActiveTarget(null);
      void refreshShiftsSilently(selectedCampId);
    } catch (error) {
      setRuleError(error instanceof Error ? error.message : "Не удалось сохранить параметры смены");
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
      setRuleError("");
      setErrorMessage("");
      await deleteCrmShiftRule(selectedCampId, rule.id);
      setRules((current) => current.filter((item) => item.id !== rule.id));
      setSuccessMessage(`Смена удалена: ${describeRule(rule)}`);
      setIsRuleModalOpen(false);
      setEditingRule(null);
      setActiveTarget(null);
      void refreshShiftsSilently(selectedCampId);
    } catch (error) {
      setRuleError(error instanceof Error ? error.message : "Не удалось удалить смену");
    } finally {
      setDeletingRuleId(null);
    }
  }

  async function handleQuickAssign(member: CrmShiftStaffOption, date: Date) {
    if (!selectedCampId) {
      return;
    }
    try {
      setErrorMessage("");
      const response = await createCrmShiftRule(
        selectedCampId,
        toRulePayload(
          {
            startsAt: presetForm.startsAt,
            endsOnDate: formatDateParam(date),
            endsAt: presetForm.endsAt,
            comment: "",
          },
          buildTarget(member, date),
        ),
      );
      setRules((current) => [
        ...current,
        {
          id: response.id,
          camp_id: selectedCampId,
          admin_id: member.id,
          admin_name: member.display_name,
          admin_email: "",
          shift_date: formatDateParam(date),
          ends_on_date: formatDateParam(date),
          weekday: getWeekdayIndex(date),
          starts_at: presetForm.startsAt,
          ends_at: presetForm.endsAt,
          is_night_shift: false,
          is_active: true,
          comment: null,
          comment_author_display: null,
          comment_author_login: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
      setSuccessMessage(`Смена назначена: ${member.display_name} · ${presetForm.startsAt} → ${presetForm.endsAt}`);
      void refreshShiftsSilently(selectedCampId);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось назначить смену");
    }
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
  const pageIsLoading = isBootLoading || isLoading;
  const { showInitialSkeleton, showRefreshOverlay, isPageVisible } = usePageLoadState(pageIsLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      {!showInitialSkeleton ? <>
      {successMessage || errorMessage ? (
        <div className="pointer-events-none fixed inset-x-0 top-4 z-40 flex justify-center px-4">
          <div
            className={`max-w-xl rounded-2xl border px-5 py-3 text-sm shadow-2xl backdrop-blur-xl transition ${
              errorMessage
                ? "border-rose-300 bg-rose-50/96 text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/18 dark:text-rose-100"
                : "border-emerald-300 bg-emerald-50/96 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/18 dark:text-emerald-100"
            }`}
          >
            {errorMessage || successMessage}
          </div>
        </div>
      ) : null}

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

      <div className="relative">
        {showRefreshOverlay ? <PageRefreshOverlay /> : null}

      {!hasCampOptions ? (
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
              <div className="flex min-h-11 items-start gap-2 text-sm font-medium text-foreground">
                <UserRoundCheck className="h-4 w-4 text-[#E5D3B3]" />
                Кто сейчас на смене
              </div>
              {activeRules.length ? (
                <div className="mt-4 flex-1 space-y-3">
                  {activeRules.map((rule) => (
                    <div key={`${rule.rule_id}-${rule.starts_at}`} className="rounded-3xl border border-border bg-white/92 p-4 dark:bg-background/65">
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
              <div className="flex min-h-11 items-start gap-2 text-sm font-medium text-foreground">
                <AlarmClockCheck className="h-4 w-4 text-[#E5D3B3]" />
                Следующая смена
              </div>
              {nextRule ? (
                <div className="mt-4 flex-1 rounded-3xl border border-border bg-white/92 p-4 dark:bg-background/65">
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
              <div className="flex min-h-11 items-start justify-between gap-3">
                <div className="flex items-start gap-2 text-sm font-medium text-foreground">
                  <Clock3 className="h-4 w-4 text-[#E5D3B3]" />
                  <span className="whitespace-nowrap">Время реакции обработки брони</span>
                </div>
                <button type="button" className="soft-button shrink-0 px-3.5 py-2 text-sm" onClick={() => setIsSettingsModalOpen(true)}>
                  Изменить
                </button>
              </div>
              <div className="mt-4 flex-1 space-y-3 rounded-3xl border border-border bg-white/92 p-4 text-sm text-muted-foreground dark:bg-background/65">
                <p>
                  Заморозка заявки: <span className="font-medium text-foreground">{settingsForm.bookingHoldHours} ч.</span>
                </p>
                <p>
                  Ночь начинается: <span className="font-medium text-foreground">{settingsForm.nightStartsAt}</span>
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
                      viewMode === "month"
                        ? "border border-[#D6BE8C] bg-[#FFF5DF] text-[#8E6E2C] dark:border-[#E5D3B3]/25 dark:bg-[#E5D3B3]/10 dark:text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Месяц
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("week")}
                    className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                      viewMode === "week"
                        ? "border border-[#D6BE8C] bg-[#FFF5DF] text-[#8E6E2C] dark:border-[#E5D3B3]/25 dark:bg-[#E5D3B3]/10 dark:text-foreground"
                        : "text-muted-foreground hover:text-foreground"
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

            <div
              ref={gridScrollRef}
              onScroll={syncScrollFromGrid}
              onPointerDown={handleGridPointerDown}
              onPointerMove={handleGridPointerMove}
              onPointerUp={stopGridDragging}
              onPointerCancel={stopGridDragging}
              className={`crm-calendar-grid-scroll mt-5 overflow-x-auto rounded-3xl border border-border bg-white/90 dark:bg-background/55 ${isGridDragging ? "crm-calendar-grid-scroll--dragging" : ""}`}
            >
              <div style={{ width: `${gridWidth}px`, minWidth: "100%" }}>
                <div
                  className="grid border-b border-border bg-white/94 dark:bg-card/70"
                  style={{ gridTemplateColumns: `${staffColumnWidth}px repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}
                >
                  <div className="sticky left-0 z-10 border-r border-border bg-white/96 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground dark:bg-card/90">
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
                      <div className="sticky left-0 z-10 border-r border-border bg-white/96 px-5 py-5 dark:bg-card/88">
                        <p className="text-sm font-semibold text-foreground">{member.display_name}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">{member.role_label}</p>
                      </div>

                      {visibleDates.map((date) => {
                        const dateKey = formatDateParam(date);
                        const cellRules = rulesByCell.get(`${member.id}:${dateKey}`) || [];

                        return (
                          <div key={`${member.id}-${dateKey}`} className="min-h-28 border-r border-border/80 p-2 last:border-r-0">
                            {cellRules.length ? (
                              <div className="flex h-full flex-col gap-2">
                                {cellRules.map((rule) => {
                                  return (
                                    <button
                                      key={rule.id}
                                      type="button"
                                      data-shift-cell="true"
                                      className="group relative flex min-h-24 w-full flex-1 flex-col items-center justify-center rounded-[1.9rem] border border-[#D6BE8C]/55 bg-[#FBF3E4] px-3 py-3 text-center shadow-sm transition hover:bg-[#F6ECD8] dark:border-[#E5D3B3]/22 dark:bg-[#E5D3B3]/10 dark:hover:bg-[#E5D3B3]/16"
                                      onMouseEnter={(event) => {
                                        if (rule.comment) {
                                          const rect = (event.currentTarget as HTMLButtonElement).getBoundingClientRect();
                                          const nearBottom = rect.bottom > window.innerHeight * 0.6;
                                          setTooltipFlip((prev) => {
                                            const next = new Map(prev);
                                            next.set(rule.id, nearBottom);
                                            return next;
                                          });
                                        }
                                      }}
                                      onMouseDown={(event) => {
                                        if (event.button === 2) {
                                          event.preventDefault();
                                        }
                                      }}
                                      onContextMenu={(event) => {
                                        event.preventDefault();
                                        openCellModal(member, date, rule);
                                      }}
                                    >
                                      {rule.comment ? <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[#E5D3B3]" /> : null}
                                      <span className="flex flex-col items-center justify-center text-[0.95rem] font-semibold leading-6 tracking-[-0.03em] text-foreground">
                                        {rule.starts_at?.slice(0, 5)}
                                        <br />
                                        <span aria-hidden="true">→</span>
                                        <br />
                                        {rule.ends_at?.slice(0, 5)}
                                      </span>
                                      {rule.comment ? (
                                        <span className={`pointer-events-none absolute left-1/2 z-20 hidden w-52 -translate-x-1/2 rounded-2xl border border-border bg-white px-3 py-2 text-[11px] leading-4 text-foreground shadow-xl dark:bg-slate-950 group-hover:block group-focus-visible:block ${tooltipFlip.get(rule.id) ? "bottom-full mb-2" : "top-full mt-2"}`}>
                                          <span className="block font-medium">{rule.comment_author_display || "Сотрудник"}</span>
                                          <span className="mt-1 block text-muted-foreground">{rule.comment}</span>
                                        </span>
                                      ) : null}
                                    </button>
                                  );
                                })}
                              </div>
                            ) : (
                              <button
                                type="button"
                                data-shift-cell="true"
                                className="flex h-full min-h-24 w-full items-center justify-center rounded-2xl border border-dashed border-[#D6BE8C]/75 bg-white/82 px-3 text-center text-xs leading-5 text-[#C6A163] shadow-sm transition hover:border-[#C7A25A]/80 hover:bg-[#FFF5E5] hover:text-[#8E6E2C] dark:border-border/70 dark:bg-background/35 dark:text-muted-foreground dark:hover:border-[#E5D3B3]/30 dark:hover:bg-background/55 dark:hover:text-foreground"
                                onClick={() => void handleQuickAssign(member, date)}
                                onMouseDown={(event) => {
                                  if (event.button === 2) {
                                    event.preventDefault();
                                  }
                                }}
                                onContextMenu={(event) => {
                                  event.preventDefault();
                                  openCellModal(member, date);
                                }}
                              >
                                <span className="text-lg leading-none text-[#C6A163] dark:text-[#E5D3B3]">+</span>
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

            {hasHorizontalOverflow ? (
              <div className={`mt-4 transition-opacity duration-300 ${isScrollIndicatorActive ? "opacity-100" : "pointer-events-none opacity-0"}`}>
                <div
                  ref={trackRef}
                  onPointerDown={handleTrackPointerDown}
                  onPointerMove={handleTrackPointerMove}
                  onPointerUp={handleTrackPointerUp}
                  onPointerCancel={handleTrackPointerUp}
                  className="crm-calendar-scrollbar relative h-3 rounded-full border border-border bg-card/70"
                >
                  <div
                    data-thumb="true"
                    className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-gradient-to-r from-[#C6A163]/70 via-sky-400/40 to-[#C6A163]/70 shadow-[0_0_0_1px_rgba(17,24,39,0.16)] transition-[opacity,box-shadow] duration-200 hover:shadow-[0_0_0_1px_rgba(17,24,39,0.28)] dark:from-[#E5D3B3]/55 dark:via-sky-400/35 dark:to-[#E5D3B3]/55"
                    style={{ width: scrollThumbWidth, left: scrollThumbOffset }}
                  />
                </div>
              </div>
            ) : null}
          </section>
        </>
      )}
      </div>

      <ModalShell
        open={isPresetModalOpen}
        onClose={() => {
          setIsPresetModalOpen(false);
          setActivePresetTimeField(null);
        }}
        title="Параметры смены"
      >
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            setPresetForm({
              startsAt: presetForm.startsAt,
              endsAt: presetForm.endsAt,
            });
            setSuccessMessage(`Параметры смены сохранены: ${presetForm.startsAt} → ${presetForm.endsAt}`);
            setIsPresetModalOpen(false);
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <ShiftTimeField
              label="Начало смены"
              value={presetForm.startsAt}
              open={activePresetTimeField === "start"}
              onToggle={() => setActivePresetTimeField((current) => (current === "start" ? null : "start"))}
              onClose={() => setActivePresetTimeField(null)}
              onChange={(value) => setPresetForm((current) => ({ ...current, startsAt: value }))}
            />
            <ShiftTimeField
              label="Конец смены"
              value={presetForm.endsAt}
              open={activePresetTimeField === "end"}
              onToggle={() => setActivePresetTimeField((current) => (current === "end" ? null : "end"))}
              onClose={() => setActivePresetTimeField(null)}
              onChange={(value) => setPresetForm((current) => ({ ...current, endsAt: value }))}
            />
          </div>

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
            <button type="button" className="soft-button px-4 py-2.5 text-sm" onClick={() => setIsPresetModalOpen(false)}>
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
        open={isSettingsModalOpen}
        onClose={() => {
          setIsSettingsModalOpen(false);
          setActiveSettingsTimeField(null);
        }}
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
            setActiveSettingsTimeField(null);
            setIsSettingsModalOpen(false);
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Заморозка заявки, ч.</span>
              <input type="number" min="1" className="soft-input" value={settingsForm.bookingHoldHours} onChange={(event) => setSettingsForm((current) => ({ ...current, bookingHoldHours: event.target.value }))} />
            </label>
            <ShiftTimeField
              label="Начало ночи"
              value={settingsForm.nightStartsAt}
              open={activeSettingsTimeField === "night-start"}
              onToggle={() => setActiveSettingsTimeField((current) => (current === "night-start" ? null : "night-start"))}
              onClose={() => setActiveSettingsTimeField(null)}
              onChange={(value) => setSettingsForm((current) => ({ ...current, nightStartsAt: value }))}
            />
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
          setActiveRulePicker(null);
        }}
        title="Параметры смены"
      >
        <form className="space-y-5" onSubmit={handleSaveRule}>
          {ruleError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{ruleError}</div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-3">
            <ShiftTimeField
              label="Начало смены"
              value={ruleForm.startsAt}
              open={activeRulePicker === "start"}
              onToggle={() => setActiveRulePicker((current) => (current === "start" ? null : "start"))}
              onClose={() => setActiveRulePicker(null)}
              onChange={(value) => setRuleForm((current) => ({ ...current, startsAt: value }))}
            />
            <ShiftDateField
              label="Дата окончания"
              value={ruleForm.endsOnDate || activeTarget?.shiftDate || ""}
              min={activeTarget?.shiftDate}
              open={activeRulePicker === "date"}
              onToggle={() => setActiveRulePicker((current) => (current === "date" ? null : "date"))}
              onClose={() => setActiveRulePicker(null)}
              onChange={(value) => setRuleForm((current) => ({ ...current, endsOnDate: value }))}
            />
            <ShiftTimeField
              label="Конец смены"
              value={ruleForm.endsAt}
              open={activeRulePicker === "end"}
              onToggle={() => setActiveRulePicker((current) => (current === "end" ? null : "end"))}
              onClose={() => setActiveRulePicker(null)}
              onChange={(value) => setRuleForm((current) => ({ ...current, endsAt: value }))}
            />
          </div>

          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
            <textarea
              className="soft-input min-h-24 resize-y"
              value={ruleForm.comment}
              onChange={(event) => setRuleForm((current) => ({ ...current, comment: event.target.value }))}
              placeholder="Комментарий к смене"
            />
          </label>

          <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {editingRule ? (
                <button
                  type="button"
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => void handleDeleteRule(editingRule)}
                  disabled={deletingRuleId === editingRule.id || isSavingRule}
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
                disabled={isSavingRule}
              >
                Отмена
              </button>
              <button type="submit" className="brand-button justify-center gap-2 px-5 py-2.5 text-sm" disabled={isSavingRule}>
                <Save className="h-4 w-4" />
                {isSavingRule ? "Сохраняем..." : "Сохранить параметры"}
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
      </> : null}
    </PageMotion>
  );
}
