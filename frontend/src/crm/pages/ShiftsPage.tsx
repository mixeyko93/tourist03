import { AlarmClockCheck, CalendarClock, CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Clock3, Expand, Minus, PencilLine, Plus, Save, Trash2, UserRoundCheck } from "lucide-react";
import { type PointerEvent as ReactPointerEvent, useEffect, useLayoutEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageMotion } from "../components/PageMotion";
import { PageLoadingState } from "../components/PageLoadingState";
import { PageRefreshOverlay } from "../components/PageRefreshOverlay";
import { SectionHeading } from "../components/SectionHeading";
import { SensitiveChangeModal } from "../components/SensitiveChangeModal";
import { usePageLoadState } from "../components/usePageLoadState";
import { getProductionDayTone } from "../productionCalendar";
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

type DerivedShiftWindow = {
  rule_id: number;
  admin_id: number;
  admin_name: string;
  shift_date: string;
  ends_on_date: string;
  starts_at: string;
  ends_at: string;
  starts_time: string;
  ends_time: string;
  starts_at_ms: number;
  ends_at_ms: number;
  is_night_shift: boolean;
};

type PendingRuleDeletion = {
  rule: CrmShiftRule;
  campId: number;
  expiresAt: number;
};

type ActiveTooltip = {
  key: string;
  top: number;
  left: number;
  flip: boolean;
  author: string;
  comment: string;
};

type ViewMode = "month" | "week";

const weekdayLabels = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

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

function formatTargetDate(value: Date) {
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(value);
}

function formatShortDateWithWeekday(value: string | null | undefined, timeZone?: string) {
  if (!value) {
    return "Не указано";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const day = new Intl.DateTimeFormat("ru-RU", { timeZone, day: "2-digit", month: "2-digit" }).format(date);
  const weekdayRaw = new Intl.DateTimeFormat("ru-RU", { timeZone, weekday: "long" }).format(date);
  const weekday = weekdayRaw ? `${weekdayRaw.charAt(0).toUpperCase()}${weekdayRaw.slice(1)}` : "";
  return `${day} (${weekday})`;
}

function toDateOnlyKey(value: string | null | undefined, timeZone?: string) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function formatDateButtonLabel(value: string) {
  if (!value) {
    return "Выберите дату";
  }
  const date = parseDateParam(value);
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(date);
}

function formatDisplayTime(value: string) {
  return value ? value.slice(0, 5).replace(/^0/, "") : "";
}

function formatShiftTime(value: string) {
  if (!value) {
    return "";
  }
  return value.slice(0, 5).replace(/^0/, "").replace(/:00$/, "");
}

function formatShiftSummary(
  rule: {
    shift_date?: string | null;
    starts_at: string;
    starts_time: string;
    ends_time: string;
    ends_on_date?: string | null;
  },
  timeZone?: string,
) {
  const startLabel = formatShortDateWithWeekday(rule.starts_at, timeZone);
  const startDateKey = rule.shift_date || toDateOnlyKey(rule.starts_at, timeZone);
  const endDateLabel =
    rule.ends_on_date && rule.ends_on_date !== startDateKey ? ` ${formatDateButtonLabel(rule.ends_on_date).slice(0, 5)}` : "";
  return `${startLabel} · с ${formatDisplayTime(rule.starts_time)} до ${formatDisplayTime(rule.ends_time)}${endDateLabel}`;
}

function getShiftCellLabel(rule: CrmShiftRule, dateKey: string) {
  const shiftDate = rule.shift_date || "";
  const endDate = rule.ends_on_date || shiftDate;
  const startTime = formatShiftTime(rule.starts_at);
  const endTime = formatShiftTime(rule.ends_at);
  if (shiftDate && endDate && shiftDate !== endDate && dateKey === endDate) {
    return `Конец смены в ${formatDisplayTime(rule.ends_at)}`;
  }
  return `${startTime} → ${endTime}`;
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

function buildRuleDateTime(value: string, time: string) {
  return new Date(`${value}T${time}`);
}


type ShiftDateFieldProps = {
  label: string;
  value: string;
  min?: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onChange: (value: string) => void;
  fieldClassName?: string;
};

function ShiftDateField({ label, value, min, open, onToggle, onClose, onChange, fieldClassName = "" }: ShiftDateFieldProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [viewDate, setViewDate] = useState(() => (value ? parseDateParam(value) : new Date()));
  const [popoverStyle, setPopoverStyle] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    if (open) {
      setViewDate(value ? parseDateParam(value) : min ? parseDateParam(min) : new Date());
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        const popW = 320;
        let left = rect.left + rect.width / 2 - popW / 2;
        left = Math.max(8, Math.min(left, window.innerWidth - popW - 8));
        setPopoverStyle({ top: rect.bottom + 10, left });
      }
    }
  }, [open, min, value]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) {
        return;
      }
      if (triggerRef.current?.contains(target) || popoverRef.current?.contains(target)) {
        return;
      }
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [onClose, open]);

  const minDate = min ? parseDateParam(min) : null;
  const calendarDays = buildCalendarMatrix(viewDate);

  return (
    <div className={`space-y-2 ${fieldClassName}`}>
      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <button ref={triggerRef} type="button" className="soft-input flex items-center justify-between gap-3 py-3.5 text-left" onClick={onToggle}>
        <span className="text-base font-semibold text-foreground">{formatDateButtonLabel(value)}</span>
        <span className="shrink-0 text-foreground"><CalendarDays className="h-5 w-5" /></span>
      </button>
      {open && popoverStyle ? createPortal(
        <div
          ref={popoverRef}
          style={{ position: "fixed", top: popoverStyle.top, left: popoverStyle.left, width: 320, zIndex: 9999 }}
          className="rounded-3xl border border-white/10 bg-[#18181b]/96 p-5 shadow-2xl backdrop-blur-xl"
        >
          <div className="mb-4 flex items-center justify-between gap-2">
            <button type="button" className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20" onClick={() => setViewDate((current) => new Date(current.getFullYear(), current.getMonth() - 1, 1))}>
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="text-center">
              <div className="text-base font-bold text-white">{monthLabels[viewDate.getMonth()]}</div>
              <div className="text-xs text-white/50">{viewDate.getFullYear()}</div>
            </div>
            <button type="button" className="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20" onClick={() => setViewDate((current) => new Date(current.getFullYear(), current.getMonth() + 1, 1))}>
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="mb-1 grid grid-cols-7 text-center text-[11px] font-medium text-white/40">
            {weekdayShortLabels.map((day) => <div key={day} className="py-1">{day}</div>)}
          </div>

          <div className="grid grid-cols-7 gap-1">
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
                  className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold transition mx-auto ${
                    isSelected
                      ? "bg-[#E5D3B3] text-slate-900"
                      : isCurrentMonth
                        ? "text-white hover:bg-white/15"
                        : "text-white/25 hover:bg-white/8"
                  } ${isDisabled ? "cursor-not-allowed opacity-30" : ""}`}
                  onClick={() => { if (!isDisabled) { onChange(iso); onClose(); } }}
                >
                  {day.getDate()}
                </button>
              );
            })}
          </div>
        </div>,
        document.body,
      ) : null}
    </div>
  );
}

type ShiftTimeFieldProps = {
  label: string;
  value: string;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
  onChange: (value: string) => void;
  fieldClassName?: string;
};

function DrumColumn({ items, selected, onSelect }: { items: string[]; selected: string; onSelect: (v: string) => void }) {
  const ITEM_H = 44;
  const VISIBLE = 5;
  const containerRef = useRef<HTMLDivElement>(null);
  const isScrollingByCode = useRef(false);

  const selectedIndex = items.indexOf(selected);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    isScrollingByCode.current = true;
    el.scrollTo({ top: selectedIndex * ITEM_H, behavior: "smooth" });
    const t = setTimeout(() => { isScrollingByCode.current = false; }, 400);
    return () => clearTimeout(t);
  }, [selectedIndex]);

  const handleScroll = () => {
    if (isScrollingByCode.current) return;
    const el = containerRef.current;
    if (!el) return;
    const idx = Math.round(el.scrollTop / ITEM_H);
    const clamped = Math.max(0, Math.min(idx, items.length - 1));
    if (items[clamped] !== selected) onSelect(items[clamped]);
  };

  return (
    <div className="relative flex-1">
      <div
        ref={containerRef}
        onScroll={handleScroll}
        style={{ height: ITEM_H * VISIBLE, scrollSnapType: "y mandatory", overflowY: "scroll", scrollbarWidth: "none" } as React.CSSProperties}
        className="[-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
      >
        {Array.from({ length: Math.floor(VISIBLE / 2) }).map((_, i) => (
          <div key={`pad-top-${i}`} style={{ height: ITEM_H }} />
        ))}
        {items.map((item) => (
          <div
            key={item}
            style={{ height: ITEM_H, scrollSnapAlign: "center" } as React.CSSProperties}
            className={`flex cursor-pointer items-center justify-center text-xl font-semibold transition-all ${item === selected ? "scale-110 text-white" : "scale-90 text-white/30"}`}
            onClick={() => onSelect(item)}
          >
            {item}
          </div>
        ))}
        {Array.from({ length: Math.floor(VISIBLE / 2) }).map((_, i) => (
          <div key={`pad-bot-${i}`} style={{ height: ITEM_H }} />
        ))}
      </div>
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[88px] bg-gradient-to-b from-[#18181b]/95 to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[88px] bg-gradient-to-t from-[#18181b]/95 to-transparent" />
      <div className="pointer-events-none absolute inset-x-2 top-1/2 h-11 -translate-y-1/2 rounded-xl border border-white/10 bg-white/8" />
    </div>
  );
}

const hourItems = Array.from({ length: 24 }, (_, i) => `${i}`.padStart(2, "0"));
const minuteItems = Array.from({ length: 60 }, (_, i) => `${i}`.padStart(2, "0"));

function ShiftTimeField({ label, value, open, onToggle, onClose, onChange, fieldClassName = "" }: ShiftTimeFieldProps) {
  const parts = splitTimeParts(value);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [manualValue, setManualValue] = useState(value);
  const [popoverStyle, setPopoverStyle] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    setManualValue(value);
  }, [value]);

  useEffect(() => {
    if (open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const popW = 220;
      let left = rect.left + rect.width / 2 - popW / 2;
      left = Math.max(8, Math.min(left, window.innerWidth - popW - 8));
      setPopoverStyle({ top: rect.bottom + 10, left });
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (!target) {
        return;
      }
      if (triggerRef.current?.contains(target) || popoverRef.current?.contains(target)) {
        return;
      }
      onClose();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [onClose, open]);

  return (
    <div className={`space-y-2 ${fieldClassName}`}>
      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <button ref={triggerRef} type="button" className="soft-input flex h-14 items-center justify-between gap-3 rounded-[1.35rem] px-4 py-1 text-left" onClick={onToggle}>
        <input
          type="text"
          inputMode="numeric"
          value={manualValue}
          onChange={(event) => setManualValue(event.target.value)}
          onBlur={() => {
            const normalized = manualValue.trim();
            if (/^\d{1,2}:\d{2}$/.test(normalized)) {
              const [hours, minutes] = normalized.split(":").map(Number);
              if (hours >= 0 && hours <= 23 && minutes >= 0 && minutes <= 59) {
                onChange(`${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`);
                return;
              }
            }
            setManualValue(value);
          }}
          onClick={(event) => event.stopPropagation()}
          className="w-20 bg-transparent text-base font-semibold text-foreground outline-none"
          aria-label={label}
        />
        <span className="shrink-0 text-foreground"><Clock3 className="h-5 w-5" /></span>
      </button>
      {open && popoverStyle ? createPortal(
        <div
          ref={popoverRef}
          style={{ position: "fixed", top: popoverStyle.top, left: popoverStyle.left, width: 220, zIndex: 9999 }}
          className="overflow-hidden rounded-3xl border border-white/10 bg-[#18181b]/96 shadow-2xl backdrop-blur-xl"
        >
          <div className="px-4 pt-4 pb-2 text-center text-2xl font-bold tracking-[-0.04em] text-white">
            {parts.hours}:{parts.minutes}
          </div>
          <div className="flex gap-0 px-2 pb-3">
            <DrumColumn
              items={hourItems}
              selected={parts.hours}
              onSelect={(h) => onChange(`${h}:${parts.minutes}`)}
            />
            <div className="flex items-center justify-center text-xl font-bold text-white/40 px-1">:</div>
            <DrumColumn
              items={minuteItems}
              selected={parts.minutes}
              onSelect={(m) => onChange(`${parts.hours}:${m}`)}
            />
          </div>
        </div>,
        document.body,
      ) : null}
    </div>
  );
}

type StepperFieldProps = {
  label: string;
  value: string;
  min: number;
  max?: number;
  step?: number;
  suffix?: string;
  onChange: (value: string) => void;
  className?: string;
};

function StepperField({ label, value, min, max, step = 1, suffix, onChange, className = "" }: StepperFieldProps) {
  const numericValue = Number(value || min);
  const safeValue = Number.isFinite(numericValue) ? numericValue : min;
  const commit = (next: number) => {
    const clamped = Math.max(min, max === undefined ? next : Math.min(next, max));
    onChange(String(clamped));
  };

  return (
    <div className={`space-y-2 ${className}`.trim()}>
      <span className="block text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <div className="soft-input flex h-14 items-center gap-2 rounded-[1.35rem] px-2 py-1">
        <button type="button" className="soft-button h-9 w-9 shrink-0 px-0 py-0" onClick={() => commit(safeValue - step)} aria-label={`Уменьшить: ${label}`}>
          <Minus className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1 text-center">
          <input
            type="text"
            inputMode="numeric"
            value={safeValue}
            onChange={(event) => {
              const nextValue = event.target.value.replace(/[^\d-]/g, "");
              if (!nextValue) {
                commit(min);
                return;
              }
              commit(Number(nextValue));
            }}
            className="w-16 appearance-none bg-transparent text-center text-lg font-semibold text-foreground outline-none"
          />
          {suffix ? <div className="-mt-1 text-center text-xs font-medium text-muted-foreground">{suffix}</div> : null}
        </div>
        <button type="button" className="soft-button h-9 w-9 shrink-0 px-0 py-0" onClick={() => commit(safeValue + step)} aria-label={`Увеличить: ${label}`}>
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
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
  const nextComment = form.comment.trim();
  return {
    admin_id: target.adminId,
    shift_date: target.shiftDate,
    ends_on_date: form.endsOnDate || target.shiftDate,
    starts_at: form.startsAt,
    ends_at: form.endsAt,
    is_night_shift: target.existingRule?.is_night_shift || false,
    is_active: target.existingRule?.is_active ?? true,
    comment: nextComment || undefined,
    comment_date: nextComment ? target.shiftDate : undefined,
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

function shiftCellTooltipKey(ruleId: number, dateKey: string) {
  return `${ruleId}:${dateKey}`;
}

export default function ShiftsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [focusDate, setFocusDate] = useState(() => new Date());
  const [showShiftTimes, setShowShiftTimes] = useState(() => {
    if (typeof window === "undefined") {
      return true;
    }
    const saved = window.localStorage.getItem("tourist03.crm.shifts.show-times");
    return saved !== "0";
  });
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
  const [, setDeletingRuleId] = useState<number | null>(null);
  const [pendingChange, setPendingChange] = useState<PendingSensitiveChange | null>(null);
  const [isSubmittingChange, setIsSubmittingChange] = useState(false);
  const [activePresetTimeField, setActivePresetTimeField] = useState<"start" | "end" | null>(null);
  const [activeRulePicker, setActiveRulePicker] = useState<"start" | "date" | "end" | null>(null);
  const [activeSettingsTimeField, setActiveSettingsTimeField] = useState<"night-start" | null>(null);
  const [isBoardModalOpen, setIsBoardModalOpen] = useState(false);
  const [hasHorizontalOverflow, setHasHorizontalOverflow] = useState(false);
  const [isScrollIndicatorActive, setIsScrollIndicatorActive] = useState(false);
  const [isGridDragging, setIsGridDragging] = useState(false);
  const [scrollThumbWidth, setScrollThumbWidth] = useState(0);
  const [scrollThumbOffset, setScrollThumbOffset] = useState(0);
  const [activeTooltip, setActiveTooltip] = useState<ActiveTooltip | null>(null);
  const [pendingDeletion, setPendingDeletion] = useState<PendingRuleDeletion | null>(null);
  const [pendingDeletionSeconds, setPendingDeletionSeconds] = useState(5);
  const gridScrollRef = useRef<HTMLDivElement | null>(null);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const scrollIndicatorTimeoutRef = useRef<number | null>(null);
  const dragPointerIdRef = useRef<number | null>(null);
  const dragStartXRef = useRef(0);
  const dragStartScrollLeftRef = useRef(0);
  const gridDragPointerIdRef = useRef<number | null>(null);
  const gridDragStartXRef = useRef(0);
  const gridDragStartScrollLeftRef = useRef(0);
  const gridDragActiveRef = useRef(false);
  const suppressGridClickUntilRef = useRef(0);
  const pendingDeletionTimeoutRef = useRef<number | null>(null);
  const pendingDeletionIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem("tourist03.crm.shifts.show-times", showShiftTimes ? "1" : "0");
  }, [showShiftTimes]);

  function clearPendingDeletionTimers() {
    if (pendingDeletionTimeoutRef.current !== null) {
      window.clearTimeout(pendingDeletionTimeoutRef.current);
      pendingDeletionTimeoutRef.current = null;
    }
    if (pendingDeletionIntervalRef.current !== null) {
      window.clearInterval(pendingDeletionIntervalRef.current);
      pendingDeletionIntervalRef.current = null;
    }
  }

  async function commitPendingDeletion(deletion: PendingRuleDeletion, mode: "timeout" | "replace" = "timeout") {
    try {
      clearPendingDeletionTimers();
      setDeletingRuleId(deletion.rule.id);
      await deleteCrmShiftRule(deletion.campId, deletion.rule.id);
      setRules((current) => current.filter((item) => item.id !== deletion.rule.id));
      setPendingDeletion((current) => (current?.rule.id === deletion.rule.id ? null : current));
      setPendingDeletionSeconds(5);
      if (mode === "timeout") {
        setSuccessMessage(`Смена удалена: ${describeRule(deletion.rule)}`);
      }
      void refreshShiftsSilently(deletion.campId);
    } catch (error) {
      setPendingDeletion((current) => (current?.rule.id === deletion.rule.id ? null : current));
      setPendingDeletionSeconds(5);
      setErrorMessage(error instanceof Error ? error.message : "Не удалось удалить смену");
    } finally {
      setDeletingRuleId(null);
    }
  }

  function handleUndoPendingDeletion() {
    clearPendingDeletionTimers();
    setPendingDeletion(null);
    setPendingDeletionSeconds(5);
    setSuccessMessage("Удаление смены отменено.");
  }

  useEffect(() => {
    if (!pendingDeletion) {
      clearPendingDeletionTimers();
      return;
    }

    const tick = () => {
      setPendingDeletionSeconds(Math.max(0, Math.ceil((pendingDeletion.expiresAt - Date.now()) / 1000)));
    };
    tick();
    pendingDeletionIntervalRef.current = window.setInterval(tick, 250);
    pendingDeletionTimeoutRef.current = window.setTimeout(() => {
      void commitPendingDeletion(pendingDeletion, "timeout");
    }, Math.max(0, pendingDeletion.expiresAt - Date.now()));

    return () => clearPendingDeletionTimers();
  }, [pendingDeletion]);

  useEffect(() => () => clearPendingDeletionTimers(), []);

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

  const visibleRules = useMemo(
    () =>
      pendingDeletion && pendingDeletion.campId === selectedCampId
        ? rules.filter((rule) => rule.id !== pendingDeletion.rule.id)
        : rules,
    [pendingDeletion, rules, selectedCampId],
  );

  const rulesByCell = useMemo(() => {
    const map = new Map<string, CrmShiftRule[]>();
    visibleRules.forEach((rule) => {
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
  }, [visibleRules]);

  const currentTimestamp = useMemo(() => {
    const parsedNow = overview?.now ? new Date(overview.now) : new Date();
    return Number.isNaN(parsedNow.getTime()) ? Date.now() : parsedNow.getTime();
  }, [overview?.now]);

  const currentShiftDateKey = useMemo(
    () => toDateOnlyKey(overview?.now, overview?.timezone || settingsForm.timeZone),
    [overview?.now, overview?.timezone, settingsForm.timeZone],
  );

  const fallbackTodayDateKey = useMemo(() => formatDateParam(new Date()), []);
  const referenceDateKey = currentShiftDateKey || fallbackTodayDateKey;

  const derivedRuleWindows = useMemo<DerivedShiftWindow[]>(() => {
    return visibleRules
      .filter((rule) => rule.is_active && rule.shift_date)
      .map((rule) => {
        const shiftDate = rule.shift_date!;
        const endsOnDate = rule.ends_on_date || shiftDate;
        const startsAt = buildRuleDateTime(shiftDate, rule.starts_at);
        const endsAt = buildRuleDateTime(endsOnDate, rule.ends_at);
        return {
          rule_id: rule.id,
          admin_id: rule.admin_id,
          admin_name: rule.admin_name,
          shift_date: shiftDate,
          ends_on_date: endsOnDate,
          starts_at: `${shiftDate}T${rule.starts_at}`,
          ends_at: `${endsOnDate}T${rule.ends_at}`,
          starts_time: rule.starts_at.slice(0, 5) || rule.starts_at,
          ends_time: rule.ends_at.slice(0, 5) || rule.ends_at,
          starts_at_ms: startsAt.getTime(),
          ends_at_ms: endsAt.getTime(),
          is_night_shift: rule.is_night_shift,
        };
      })
      .filter((rule) => !Number.isNaN(rule.starts_at_ms) && !Number.isNaN(rule.ends_at_ms))
      .sort((left, right) => {
        if (left.starts_at_ms !== right.starts_at_ms) {
          return left.starts_at_ms - right.starts_at_ms;
        }
        if (left.ends_at_ms !== right.ends_at_ms) {
          return left.ends_at_ms - right.ends_at_ms;
        }
        return left.admin_name.localeCompare(right.admin_name, "ru");
      });
  }, [visibleRules]);

  const todayScheduledRules = useMemo(() => {
    if (!referenceDateKey) {
      return [];
    }
    return derivedRuleWindows
      .filter((rule) => rule.shift_date <= referenceDateKey && referenceDateKey <= rule.ends_on_date)
      .map((rule) => ({
        rule_id: rule.rule_id,
        admin_id: rule.admin_id,
        admin_name: rule.admin_name,
        weekday: getWeekdayIndex(parseDateParam(referenceDateKey)),
        weekday_label: weekdayLabels[getWeekdayIndex(parseDateParam(referenceDateKey))] || "Сегодня",
        shift_date: rule.shift_date,
        ends_on_date: rule.ends_on_date,
        starts_at: rule.starts_at,
        ends_at: rule.ends_at,
        starts_time: rule.starts_time,
        ends_time: rule.ends_time,
        is_night_shift: rule.is_night_shift,
        is_active: true,
        comment: "",
        timezone: overview?.timezone || settingsForm.timeZone,
      }));
  }, [derivedRuleWindows, overview?.timezone, referenceDateKey, settingsForm.timeZone]);

  const todayUpcomingRules = useMemo(
    () => (overview?.upcoming_windows || []).filter((rule) => rule.shift_date === referenceDateKey),
    [overview?.upcoming_windows, referenceDateKey],
  );

  const activeRules = useMemo(
    () =>
      derivedRuleWindows
        .filter((rule) => rule.starts_at_ms <= currentTimestamp && currentTimestamp < rule.ends_at_ms)
        .map((rule) => ({
          rule_id: rule.rule_id,
          admin_id: rule.admin_id,
          admin_name: rule.admin_name,
          weekday: getWeekdayIndex(parseDateParam(rule.shift_date)),
          weekday_label: weekdayLabels[getWeekdayIndex(parseDateParam(rule.shift_date))] || "Сегодня",
          shift_date: rule.shift_date,
          ends_on_date: rule.ends_on_date,
          starts_at: rule.starts_at,
          ends_at: rule.ends_at,
          starts_time: rule.starts_time,
          ends_time: rule.ends_time,
          is_night_shift: rule.is_night_shift,
          is_active: true,
          comment: "",
          timezone: overview?.timezone || settingsForm.timeZone,
        })),
    [currentTimestamp, derivedRuleWindows, overview?.timezone, settingsForm.timeZone],
  );

  const nextRuleGroup = useMemo(() => {
    const nextRule = derivedRuleWindows.find((rule) => rule.starts_at_ms > currentTimestamp);
    if (!nextRule) {
      return [];
    }
    return derivedRuleWindows.filter((rule) => rule.starts_at_ms === nextRule.starts_at_ms && rule.ends_at_ms === nextRule.ends_at_ms);
  }, [currentTimestamp, derivedRuleWindows]);

  const nextRule = nextRuleGroup[0] || null;
  const visibleActiveRules = activeRules.length ? activeRules : (todayUpcomingRules.length ? todayUpcomingRules : todayScheduledRules);
  const nextRuleSummaryLine = nextRule ? formatShiftSummary(nextRule, overview?.timezone || settingsForm.timeZone) : "";

  useEffect(() => {
    if (pendingDeletion) {
      return;
    }
    if (!successMessage && !errorMessage) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setSuccessMessage("");
      setErrorMessage("");
    }, 2600);
    return () => window.clearTimeout(timeoutId);
  }, [errorMessage, pendingDeletion, successMessage]);

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
  const staffColumnWidth = showShiftTimes ? 316 : 272;
  const dayColumnWidth = showShiftTimes
    ? (viewMode === "week" ? 140 : 92)
    : (viewMode === "week" ? 40 : 24);
  const gridWidth = staffColumnWidth + visibleDates.length * dayColumnWidth;
  const fullscreenStaffColumnWidth = 186;
  const fullscreenDayColumnWidth = 28;

  const fullscreenMonthStart = useMemo(() => new Date(focusDate.getFullYear(), focusDate.getMonth(), 1), [focusDate]);
  const fullscreenMonthEnd = useMemo(() => new Date(fullscreenMonthStart.getFullYear(), fullscreenMonthStart.getMonth() + 1, 0), [fullscreenMonthStart]);
  const fullscreenVisibleDates = useMemo(() => buildPeriodDates(fullscreenMonthStart, fullscreenMonthEnd), [fullscreenMonthEnd, fullscreenMonthStart]);
  const fullscreenPeriodLabel = getMonthLabel(fullscreenMonthStart);

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

  useLayoutEffect(() => {
    const gridNode = gridScrollRef.current;
    if (!gridNode) {
      return;
    }

    if (viewMode !== "month") {
      gridNode.scrollLeft = 0;
      syncScrollFromGrid();
      return;
    }

    const today = new Date();
    if (today.getFullYear() === focusDate.getFullYear() && today.getMonth() === focusDate.getMonth()) {
      const targetCell = gridNode.querySelector<HTMLElement>(`[data-grid-date='${formatDateParam(today)}']`);
      const targetScroll = targetCell ? Math.max(0, targetCell.offsetLeft - staffColumnWidth) : 0;
      gridNode.scrollLeft = targetScroll;
      syncScrollFromGrid();
    } else {
      gridNode.scrollLeft = 0;
      syncScrollFromGrid();
    }
  }, [dayColumnWidth, focusDate, viewMode]);

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
        ? {
            ...mapRuleForm(rule),
            comment: rule.comment_date === target.shiftDate ? rule.comment || "" : "",
          }
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
    if (target.closest("[data-shift-no-drag='true']")) {
      return;
    }

    const gridNode = gridScrollRef.current;
    if (!gridNode || gridNode.scrollWidth <= gridNode.clientWidth) {
      return;
    }

    gridDragPointerIdRef.current = event.pointerId;
    gridDragStartXRef.current = event.clientX;
    gridDragStartScrollLeftRef.current = gridNode.scrollLeft;
    gridDragActiveRef.current = false;
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
    if (!gridDragActiveRef.current) {
      if (Math.abs(deltaX) < 5) {
        return;
      }
      gridDragActiveRef.current = true;
      suppressGridClickUntilRef.current = Date.now() + 180;
      event.currentTarget.setPointerCapture(event.pointerId);
      setIsGridDragging(true);
      activateScrollIndicator();
    }
    gridNode.scrollLeft = gridDragStartScrollLeftRef.current - deltaX;
    syncScrollFromGrid();
  };

  const stopGridDragging = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (gridDragPointerIdRef.current !== event.pointerId) {
      return;
    }
    gridDragPointerIdRef.current = null;
    gridDragActiveRef.current = false;
    setIsGridDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
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
                  comment_date: ruleForm.comment.trim() ? activeTarget.shiftDate : null,
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
            comment_date: ruleForm.comment.trim() ? activeTarget.shiftDate : null,
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
      setRuleError("");
      setErrorMessage("");
      setSuccessMessage("");
      if (pendingDeletion) {
        await commitPendingDeletion(pendingDeletion, "replace");
      }
      setPendingDeletion({
        rule,
        campId: selectedCampId,
        expiresAt: Date.now() + 5000,
      });
      setIsRuleModalOpen(false);
      setEditingRule(null);
      setActiveTarget(null);
    } catch (error) {
      setRuleError(error instanceof Error ? error.message : "Не удалось удалить смену");
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
          comment_date: null,
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

  const hasCampOptions = camps.length > 0;
  const pageIsLoading = isBootLoading || isLoading;
  const { showInitialSkeleton, showRefreshOverlay, isPageVisible } = usePageLoadState(pageIsLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      {showInitialSkeleton ? (
        <>
          <SectionHeading title="График смен и дежурств" description="Рабочий экран базы: кто сейчас на смене, когда начинается следующая смена и как CRM должна обрабатывать ночные заявки." />
          <div className="grid gap-4 xl:grid-cols-3">
            <PageLoadingState blocks={3} columnsClassName="xl:grid-cols-3" blockHeightClassName="h-40" />
          </div>
          <section className="glass-card p-5 md:p-6">
            <PageLoadingState blocks={1} columnsClassName="grid-cols-1" blockHeightClassName="h-[24rem]" />
          </section>
        </>
      ) : <>
      {pendingDeletion || successMessage || errorMessage ? (
        <div className="pointer-events-none fixed inset-x-0 top-4 z-[10001] flex justify-center px-4">
          <div
            className={`pointer-events-auto relative flex max-w-xl items-center gap-3 overflow-hidden rounded-2xl border px-5 py-3 text-sm shadow-2xl backdrop-blur-xl transition ${
              errorMessage
                ? "border-rose-300 bg-rose-50/96 text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/18 dark:text-rose-100"
                : pendingDeletion
                  ? "border-amber-300 bg-amber-50/96 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/18 dark:text-amber-100"
                : "border-emerald-300 bg-emerald-50/96 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/18 dark:text-emerald-100"
            }`}
          >
            <span className="min-w-0 flex-1">
              {pendingDeletion
                ? `Смена будет удалена через ${pendingDeletionSeconds} сек.`
                : errorMessage || successMessage}
            </span>
            {pendingDeletion ? (
              <button
                type="button"
                className="soft-button px-3 py-1.5 text-xs"
                onClick={handleUndoPendingDeletion}
              >
                Отменить
              </button>
            ) : null}
            {pendingDeletion ? (
              <span className="pointer-events-none absolute inset-x-3 bottom-2 h-1 overflow-hidden rounded-full bg-amber-200/35 dark:bg-amber-200/10">
                <span
                  className="absolute inset-y-0 left-0 rounded-full bg-amber-400/80"
                  style={{ width: `${Math.max(0, (pendingDeletionSeconds / 5) * 100)}%`, transition: "width 250ms linear" }}
                />
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {activeTooltip
        ? createPortal(
            <div
              style={{
                position: "fixed",
                top: activeTooltip.top,
                left: activeTooltip.left,
                width: 240,
                zIndex: 9999,
                transform: activeTooltip.flip ? "translateY(-100%)" : undefined,
                pointerEvents: "none",
              }}
              className="rounded-2xl border border-border bg-white px-3 py-2 text-[11px] leading-4 text-foreground shadow-xl dark:bg-slate-950"
            >
              <span className="block font-medium">{activeTooltip.author}</span>
              <span className="mt-1 block break-words whitespace-normal text-muted-foreground">{activeTooltip.comment}</span>
            </div>,
            document.body,
          )
        : null}

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
          <div className="grid gap-4 xl:grid-cols-3 xl:items-stretch">
            <section className="glass-card flex min-h-[172px] flex-col p-4">
              <div className="flex items-start gap-2 text-sm font-medium text-foreground">
                <UserRoundCheck className="h-4 w-4 text-[#E5D3B3]" />
                Кто сейчас на смене
              </div>
              {visibleActiveRules.length ? (
                <div className="mt-3 rounded-3xl border border-border bg-white/92 p-3 dark:bg-background/65">
                  <div className="space-y-2">
                    {visibleActiveRules.slice(0, 2).map((rule) => (
                      <div key={`${rule.rule_id}-${rule.starts_at}`}>
                        <p className="text-sm font-semibold text-foreground">{rule.admin_name}</p>
                        <p className="mt-0.5 text-sm text-muted-foreground">
                          {formatShiftSummary(rule, overview?.timezone || settingsForm.timeZone)}
                          {rule.is_night_shift ? " · Ночная" : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  Сейчас никто не назначен на смену. Ночная логика будет держать заявку до начала следующей смены плюс ещё {settingsForm.nightReleaseAfterShiftMinutes} минут.
                </p>
              )}
            </section>

            <section className="glass-card flex min-h-[172px] flex-col p-4">
              <div className="flex items-start gap-2 text-sm font-medium text-foreground">
                <AlarmClockCheck className="h-4 w-4 text-[#E5D3B3]" />
                Следующая смена
              </div>
              {nextRule ? (
                <div className="mt-3 rounded-3xl border border-border bg-white/92 p-3 dark:bg-background/65">
                  <div className="space-y-2">
                    {(nextRuleGroup.length ? nextRuleGroup : [nextRule]).map((rule) => (
                      <div key={`${rule.rule_id}-${rule.admin_id}-${rule.starts_at}`}>
                        <p className="text-sm font-semibold text-foreground">{rule.admin_name}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{nextRuleSummaryLine}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  Следующее правило смены пока не задано. Добавьте график, чтобы CRM понимала, кто обрабатывает новые заявки.
                </p>
              )}
            </section>

            <section className="glass-card relative flex min-h-[172px] flex-col p-4">
              <button
                type="button"
                aria-label="Изменить параметры реакции"
                className="soft-button absolute right-2.5 top-2.5 flex h-6 w-6 items-center justify-center rounded-full px-0 py-0"
                onClick={() => setIsSettingsModalOpen(true)}
              >
                <PencilLine className="h-2.5 w-2.5" />
              </button>
              <div className="flex items-start gap-2 pr-14 text-sm font-medium text-foreground">
                  <Clock3 className="h-4 w-4 text-[#E5D3B3]" />
                  <span className="whitespace-nowrap">Время реакции обработки брони</span>
              </div>
              <div className="mt-3 grid gap-3 rounded-3xl border border-border bg-white/92 p-3 text-sm text-muted-foreground dark:bg-background/65 sm:grid-cols-2">
                <p>
                  Заморозка заявки: <span className="font-medium text-foreground">{settingsForm.bookingHoldHours} ч.</span>
                </p>
                <p>
                  Ночь начинается: <span className="font-medium text-foreground">{settingsForm.nightStartsAt}</span>
                </p>
                <p>
                  Ночной запас: <span className="font-medium text-foreground">{settingsForm.nightReleaseAfterShiftMinutes} мин.</span>
                </p>
                <p>
                  Шаг эскалации: <span className="font-medium text-foreground">{settingsForm.escalationStepMinutes} мин.</span>
                </p>
                <p className="sm:col-span-2">
                  Повторов до управляющего: <span className="font-medium text-foreground">{settingsForm.escalationRepeatsBeforeManager}</span>
                </p>
              </div>
            </section>
          </div>

          <section className="glass-card p-5">
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

                <h2 className="text-xl font-semibold tracking-[-0.04em] text-foreground sm:ml-2">{periodLabel}</h2>
              </div>

              <div className="flex flex-wrap items-center gap-3 xl:justify-end">
                <button
                  type="button"
                  onClick={() => setShowShiftTimes((current) => !current)}
                  className="soft-button gap-3 px-3 py-2.5 text-sm"
                  aria-pressed={showShiftTimes}
                >
                  <span className="text-muted-foreground">{showShiftTimes ? "Время в ячейках" : "Компактный вид"}</span>
                  <span
                    className={`relative h-6 w-11 rounded-full border transition-colors duration-300 ${
                      showShiftTimes
                        ? "border-[#D6BE8C] bg-[#FFF5DF] dark:border-[#E5D3B3]/30 dark:bg-[#E5D3B3]/10"
                        : "border-border bg-background/70"
                    }`}
                  >
                    <span
                      className={`absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-foreground transition-all duration-300 ${
                        showShiftTimes ? "left-[22px]" : "left-[4px]"
                      }`}
                    />
                  </span>
                </button>

                <button type="button" className="soft-button gap-2 px-4 py-2.5 text-sm" onClick={() => setIsBoardModalOpen(true)}>
                  <Expand className="h-4 w-4" />
                  Полный экран
                </button>

                <button type="button" className="soft-button gap-2 px-4 py-2.5 text-sm" onClick={openCreateRuleModal} disabled={!sortedStaff.length}>
                  <PencilLine className="h-4 w-4" />
                  Параметры
                </button>
              </div>
            </div>

            <div
              ref={gridScrollRef}
              onScroll={syncScrollFromGrid}
              onPointerDown={handleGridPointerDown}
              onPointerMove={handleGridPointerMove}
              onPointerUp={stopGridDragging}
              onPointerCancel={stopGridDragging}
              className={`crm-calendar-grid-scroll mt-4 overflow-x-auto overflow-y-hidden rounded-3xl border border-border bg-white dark:bg-background/55 ${isGridDragging ? "crm-calendar-grid-scroll--dragging" : ""}`}
            >
              <div style={{ width: `${gridWidth}px`, minWidth: "100%" }}>
                <div
                  className="grid border-b border-border bg-white dark:bg-card"
                  style={{ gridTemplateColumns: `${staffColumnWidth}px repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}
                >
                  <div className="sticky left-0 z-[80] flex min-h-[96px] items-center border-r border-border bg-white px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground shadow-[10px_0_0_0_rgba(255,255,255,1)] dark:bg-[#171b24] dark:shadow-[10px_0_0_0_rgba(23,27,36,1)]">
                    Сотрудник
                  </div>
                  {visibleDates.map((date) => (
                    <div
                      key={formatDateParam(date)}
                      data-grid-date={formatDateParam(date)}
                      className={`border-r border-border px-2 py-3 text-center last:border-r-0 ${
                        getProductionDayTone(date) === "holiday"
                          ? "bg-rose-50/85 dark:bg-rose-500/10"
                          : getProductionDayTone(date) === "weekend"
                            ? "bg-[#FFF8EE]/85 dark:bg-[#E5D3B3]/6"
                            : ""
                      }`}
                    >
                      <div className="text-base font-semibold text-foreground">{getDayNumberLabel(date)}</div>
                      <div className={`mt-1 text-[11px] uppercase tracking-[0.18em] ${getProductionDayTone(date) === "holiday" ? "text-rose-500 dark:text-rose-300" : "text-muted-foreground"}`}>{getWeekdayShortLabel(date)}</div>
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
                      <div className="sticky left-0 z-[80] flex min-h-[92px] flex-col justify-center border-r border-border bg-white px-5 py-5 shadow-[10px_0_0_0_rgba(255,255,255,1)] dark:bg-[#171b24] dark:shadow-[10px_0_0_0_rgba(23,27,36,1)]">
                        <p className="text-[1.28rem] font-semibold leading-tight text-foreground">{member.display_name}</p>
                        <p className="mt-2 text-[8px] uppercase tracking-[0.16em] text-muted-foreground">{member.role_label}</p>
                      </div>

                      {visibleDates.map((date) => {
                        const dateKey = formatDateParam(date);
                        const cellRules = rulesByCell.get(`${member.id}:${dateKey}`) || [];

                        return (
                          <div
                            key={`${member.id}-${dateKey}`}
                            className={`min-h-[34px] border-r border-border/80 px-1 py-1 last:border-r-0 ${
                              getProductionDayTone(date) === "holiday"
                                ? "bg-rose-50/65 dark:bg-rose-500/6"
                                : getProductionDayTone(date) === "weekend"
                                  ? "bg-[#FFF8EE]/65 dark:bg-[#E5D3B3]/4"
                                  : ""
                            }`}
                          >
                            {cellRules.length ? (
                              <div className="flex h-full flex-col gap-1">
                                {cellRules.map((rule) => {
                                  return (
                                    <div key={rule.id} className="group relative flex-1">
                                      <button
                                        type="button"
                                        data-shift-cell="true"
                                        data-shift-interactive="true"
                                        className={`relative flex h-full w-full items-center justify-center overflow-visible border border-[#D6BE8C]/55 bg-[#FBF3E4] text-center shadow-sm transition-[background-color,border-color,min-height,padding,opacity,transform,border-radius] duration-300 ease-out hover:bg-[#F6ECD8] dark:border-[#E5D3B3]/22 dark:bg-[#E5D3B3]/10 dark:hover:bg-[#E5D3B3]/16 ${showShiftTimes ? "min-h-[36px] rounded-2xl px-2 py-1" : "min-h-[24px] rounded-xl px-1 py-0.5"}`}
                                        onMouseEnter={(event) => {
                                          if (rule.comment) {
                                            const rect = (event.currentTarget as HTMLButtonElement).getBoundingClientRect();
                                            const tooltipWidth = 240;
                                            const flip = rect.bottom > window.innerHeight * 0.6;
                                            const shiftRight = rect.left < staffColumnWidth + 120;
                                            const left = shiftRight
                                              ? Math.min(window.innerWidth - tooltipWidth - 8, rect.right + 8)
                                              : Math.max(staffColumnWidth + 12, Math.min(window.innerWidth - tooltipWidth - 8, rect.left + rect.width / 2 - tooltipWidth / 2));
                                            setActiveTooltip({
                                              key: shiftCellTooltipKey(rule.id, dateKey),
                                              top: flip ? rect.top - 8 : rect.bottom + 8,
                                              left,
                                              flip,
                                              author: rule.comment_author_display || "Сотрудник",
                                              comment: rule.comment,
                                            });
                                          }
                                        }}
                                        onMouseLeave={() => {
                                          setActiveTooltip((current) =>
                                            current?.key === shiftCellTooltipKey(rule.id, dateKey) ? null : current,
                                          );
                                        }}
                                        onClick={(event) => {
                                          if (Date.now() < suppressGridClickUntilRef.current) {
                                            event.preventDefault();
                                            return;
                                          }
                                          openCellModal(member, date, rule);
                                        }}
                                      >
                                        {rule.comment && rule.comment_date === dateKey ? <span className="absolute -left-1 -top-1 z-10 h-1 w-1 rounded-full bg-[#E5D3B3] shadow-[0_0_0_2px_rgba(15,23,42,0.7)]" /> : null}
                                        {showShiftTimes ? (
                                          <span className="flex min-w-0 items-center gap-0.5 overflow-hidden text-[0.75rem] font-semibold tracking-[-0.02em] text-foreground transition-opacity duration-200">
                                            <span className="truncate">{getShiftCellLabel(rule, dateKey)}</span>
                                          </span>
                                        ) : (
                                          <span className="sr-only">Смена назначена</span>
                                        )}
                                      </button>
                                      <button
                                        type="button"
                                        aria-label="Удалить смену"
                                        data-shift-no-drag="true"
                                        className="pointer-events-none absolute -left-1 -top-1 z-20 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-white opacity-0 shadow-md transition group-hover:pointer-events-auto group-hover:opacity-90 hover:bg-rose-600 hover:opacity-100"
                                        onPointerDown={(event) => {
                                          event.stopPropagation();
                                        }}
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          void handleDeleteRule(rule);
                                        }}
                                      >
                                        <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                                          <line x1="2.5" y1="2.5" x2="7.5" y2="7.5" /><line x1="7.5" y1="2.5" x2="2.5" y2="7.5" />
                                        </svg>
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <button
                                type="button"
                                data-shift-cell="true"
                                data-shift-interactive="true"
                                className={`flex h-full w-full items-center justify-center border border-dashed border-[#D6BE8C]/75 bg-white/82 text-center text-xs leading-5 text-[#C6A163] shadow-sm transition-[background-color,border-color,min-height,padding,opacity,transform,border-radius] duration-300 ease-out hover:border-[#C7A25A]/80 hover:bg-[#FFF5E5] hover:text-[#8E6E2C] dark:border-border/70 dark:bg-background/35 dark:text-muted-foreground dark:hover:border-[#E5D3B3]/30 dark:hover:bg-background/55 dark:hover:text-foreground ${showShiftTimes ? "min-h-[36px] rounded-xl px-2" : "min-h-[24px] rounded-lg px-1"}`}
                                onClick={() => {
                                  if (Date.now() < suppressGridClickUntilRef.current) {
                                    return;
                                  }
                                  void handleQuickAssign(member, date);
                                }}
                              >
                                <span className="text-base leading-none text-[#C6A163] dark:text-[#E5D3B3]">+</span>
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

      <ModalShell
        open={isBoardModalOpen}
        onClose={() => setIsBoardModalOpen(false)}
        title={fullscreenPeriodLabel}
        panelClassName="max-w-[min(1860px,calc(100vw-2rem))]"
        bodyClassName="overflow-hidden"
      >
        <div className="overflow-hidden rounded-3xl border border-border bg-white dark:bg-[#171b24]">
          <div
            className="grid border-b border-border bg-white dark:bg-[#171b24]"
            style={{ gridTemplateColumns: `${fullscreenStaffColumnWidth}px repeat(${fullscreenVisibleDates.length}, minmax(${fullscreenDayColumnWidth}px, 1fr))` }}
          >
            <div className="sticky left-0 z-[80] flex min-h-[72px] items-center border-r border-border bg-white px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground shadow-[10px_0_0_0_rgba(255,255,255,1)] dark:bg-[#171b24] dark:shadow-[10px_0_0_0_rgba(23,27,36,1)]">
              Сотрудник
            </div>
            {fullscreenVisibleDates.map((date) => (
              <div
                key={`fullscreen-${formatDateParam(date)}`}
                className={`border-r border-border px-1 py-3 text-center last:border-r-0 ${
                  getProductionDayTone(date) === "holiday"
                    ? "bg-rose-50/85 dark:bg-rose-500/10"
                    : getProductionDayTone(date) === "weekend"
                      ? "bg-[#FFF8EE]/85 dark:bg-[#E5D3B3]/6"
                      : ""
                }`}
              >
                <div className="text-sm font-semibold text-foreground">{getDayNumberLabel(date)}</div>
                <div className={`mt-1 text-[10px] uppercase tracking-[0.18em] ${getProductionDayTone(date) === "holiday" ? "text-rose-500 dark:text-rose-300" : "text-muted-foreground"}`}>{getWeekdayShortLabel(date)}</div>
              </div>
            ))}
          </div>

          {sortedStaff.length ? sortedStaff.map((member) => (
            <div
              key={`fullscreen-${member.id}`}
              className="grid border-b border-border last:border-b-0"
              style={{ gridTemplateColumns: `${fullscreenStaffColumnWidth}px repeat(${fullscreenVisibleDates.length}, minmax(${fullscreenDayColumnWidth}px, 1fr))` }}
            >
              <div className="sticky left-0 z-[80] flex min-h-[88px] flex-col justify-center border-r border-border bg-white px-5 py-5 shadow-[10px_0_0_0_rgba(255,255,255,1)] dark:bg-[#171b24] dark:shadow-[10px_0_0_0_rgba(23,27,36,1)]">
                <p className="text-[1.1rem] font-semibold leading-tight text-foreground">{member.display_name}</p>
                <p className="mt-2 text-[8px] uppercase tracking-[0.16em] text-muted-foreground">{member.role_label}</p>
              </div>
              {fullscreenVisibleDates.map((date) => {
                const dateKey = formatDateParam(date);
                const cellRules = rulesByCell.get(`${member.id}:${dateKey}`) || [];
                return (
                  <div
                    key={`fullscreen-${member.id}-${dateKey}`}
                    className={`min-h-[48px] overflow-visible border-r border-border/80 px-0.5 py-0.5 last:border-r-0 ${
                      getProductionDayTone(date) === "holiday"
                        ? "bg-rose-50/65 dark:bg-rose-500/6"
                        : getProductionDayTone(date) === "weekend"
                          ? "bg-[#FFF8EE]/65 dark:bg-[#E5D3B3]/4"
                          : ""
                    }`}
                  >
                    {cellRules.length ? (
                      <div className="flex h-full flex-col gap-1">
                        {cellRules.map((rule) => (
                          <div key={`fullscreen-rule-${rule.id}-${dateKey}`} className="group relative flex-1">
                            <button
                              type="button"
                              data-shift-cell="true"
                              className="relative flex h-full w-full items-center justify-center overflow-visible rounded-xl border border-[#D6BE8C]/55 bg-[#FBF3E4] px-1 py-1 text-center shadow-sm transition hover:bg-[#F6ECD8] dark:border-[#E5D3B3]/22 dark:bg-[#E5D3B3]/10 dark:hover:bg-[#E5D3B3]/16 min-h-[40px]"
                              onClick={() => {
                                if (Date.now() < suppressGridClickUntilRef.current) {
                                  return;
                                }
                                openCellModal(member, date, rule);
                              }}
                            >
                              {rule.comment && rule.comment_date === dateKey ? <span className="absolute -left-1 -top-1 z-10 h-1 w-1 rounded-full bg-[#E5D3B3] shadow-[0_0_0_2px_rgba(15,23,42,0.7)]" /> : null}
                              <span className="text-[12px] font-semibold leading-[1rem] text-foreground">
                                {formatShiftTime(rule.starts_at).replace(":", "")}
                                <br />
                                {formatShiftTime(rule.ends_at).replace(":", "")}
                              </span>
                            </button>
                            <button
                              type="button"
                              aria-label="Удалить смену"
                              data-shift-no-drag="true"
                              className="pointer-events-none absolute -left-1 -top-1 z-20 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-white opacity-0 shadow-md transition group-hover:pointer-events-auto group-hover:opacity-90 hover:bg-rose-600 hover:opacity-100"
                              onPointerDown={(event) => {
                                event.stopPropagation();
                              }}
                              onClick={(event) => {
                                event.stopPropagation();
                                void handleDeleteRule(rule);
                              }}
                            >
                              <svg viewBox="0 0 10 10" className="h-2 w-2" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                                <line x1="2.5" y1="2.5" x2="7.5" y2="7.5" /><line x1="7.5" y1="2.5" x2="2.5" y2="7.5" />
                              </svg>
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <button
                        type="button"
                        data-shift-cell="true"
                        className="flex h-full w-full items-center justify-center rounded-lg border border-dashed border-[#D6BE8C]/75 bg-white/82 px-1 text-center text-xs leading-5 text-[#C6A163] shadow-sm transition hover:border-[#C7A25A]/80 hover:bg-[#FFF5E5] hover:text-[#8E6E2C] dark:border-border/70 dark:bg-background/35 dark:text-muted-foreground dark:hover:border-[#E5D3B3]/30 dark:hover:bg-background/55 dark:hover:text-foreground"
                        onClick={() => {
                          if (Date.now() < suppressGridClickUntilRef.current) {
                            return;
                          }
                          void handleQuickAssign(member, date);
                        }}
                      >
                        <span className="text-sm leading-none text-[#C6A163] dark:text-[#E5D3B3]">+</span>
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )) : (
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
      </ModalShell>

      <ModalShell
        open={isPresetModalOpen}
        onClose={() => {
          setIsPresetModalOpen(false);
          setActivePresetTimeField(null);
        }}
        title="Параметры смены"
        panelClassName="w-[min(620px,calc(100vw-2rem))] max-w-none"
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
          <div className="mx-auto grid max-w-[420px] gap-4 md:grid-cols-[180px_180px] md:items-start md:justify-center md:gap-6">
            <ShiftTimeField
              label="Начало смены"
              value={presetForm.startsAt}
              open={activePresetTimeField === "start"}
              onToggle={() => setActivePresetTimeField((current) => (current === "start" ? null : "start"))}
              onClose={() => setActivePresetTimeField(null)}
              onChange={(value) => setPresetForm((current) => ({ ...current, startsAt: value }))}
              fieldClassName="w-full"
            />
            <ShiftTimeField
              label="Конец смены"
              value={presetForm.endsAt}
              open={activePresetTimeField === "end"}
              onToggle={() => setActivePresetTimeField((current) => (current === "end" ? null : "end"))}
              onClose={() => setActivePresetTimeField(null)}
              onChange={(value) => setPresetForm((current) => ({ ...current, endsAt: value }))}
              fieldClassName="w-full"
            />
          </div>

          <div className="mx-auto flex w-full max-w-[420px] flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-center">
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
        panelClassName="w-[min(680px,calc(100vw-2rem))] max-w-none"
        bodyClassName="px-5 py-5 sm:px-6 sm:py-5"
      >
        <form
          className="space-y-4"
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
          <div className="mx-auto grid max-w-[560px] gap-x-4 gap-y-4 sm:grid-cols-2">
            <StepperField
              label="Заморозка заявки, ч."
              value={settingsForm.bookingHoldHours}
              min={1}
              suffix="ч."
              onChange={(value) => setSettingsForm((current) => ({ ...current, bookingHoldHours: value }))}
            />
            <ShiftTimeField
              label="Начало ночи"
              value={settingsForm.nightStartsAt}
              open={activeSettingsTimeField === "night-start"}
              onToggle={() => setActiveSettingsTimeField((current) => (current === "night-start" ? null : "night-start"))}
              onClose={() => setActiveSettingsTimeField(null)}
              onChange={(value) => setSettingsForm((current) => ({ ...current, nightStartsAt: value }))}
            />
            <StepperField
              label="Ночной запас, мин."
              value={settingsForm.nightReleaseAfterShiftMinutes}
              min={0}
              suffix="мин."
              onChange={(value) => setSettingsForm((current) => ({ ...current, nightReleaseAfterShiftMinutes: value }))}
            />
            <StepperField
              label="Шаг эскалации, мин."
              value={settingsForm.escalationStepMinutes}
              min={1}
              suffix="мин."
              onChange={(value) => setSettingsForm((current) => ({ ...current, escalationStepMinutes: value }))}
            />
            <StepperField
              label="Повторы до управляющего"
              value={settingsForm.escalationRepeatsBeforeManager}
              min={1}
              onChange={(value) => setSettingsForm((current) => ({ ...current, escalationRepeatsBeforeManager: value }))}
            />
          </div>

          <div className="mx-auto flex max-w-[560px] flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:justify-end">
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
        panelClassName="w-[min(820px,calc(100vw-2rem))] max-w-none"
      >
        <form className="space-y-4" onSubmit={handleSaveRule}>
          {ruleError ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{ruleError}</div>
          ) : null}

          <div className="mx-auto grid max-w-[660px] gap-4 md:grid-cols-[minmax(0,180px)_minmax(0,220px)_minmax(0,180px)] md:items-start md:justify-center">
            <ShiftTimeField
              label="Начало смены"
              value={ruleForm.startsAt}
              open={activeRulePicker === "start"}
              onToggle={() => setActiveRulePicker((current) => (current === "start" ? null : "start"))}
              onClose={() => setActiveRulePicker(null)}
              onChange={(value) => setRuleForm((current) => ({ ...current, startsAt: value }))}
              fieldClassName="w-full"
            />
            <ShiftDateField
              label="Дата окончания"
              value={ruleForm.endsOnDate || activeTarget?.shiftDate || ""}
              min={activeTarget?.shiftDate}
              open={activeRulePicker === "date"}
              onToggle={() => setActiveRulePicker((current) => (current === "date" ? null : "date"))}
              onClose={() => setActiveRulePicker(null)}
              onChange={(value) => setRuleForm((current) => ({ ...current, endsOnDate: value }))}
              fieldClassName="w-full"
            />
            <ShiftTimeField
              label="Конец смены"
              value={ruleForm.endsAt}
              open={activeRulePicker === "end"}
              onToggle={() => setActiveRulePicker((current) => (current === "end" ? null : "end"))}
              onClose={() => setActiveRulePicker(null)}
              onChange={(value) => setRuleForm((current) => ({ ...current, endsAt: value }))}
              fieldClassName="w-full"
            />
          </div>

          <label className="mx-auto block max-w-[660px] space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
            <textarea
              className="soft-input min-h-24 resize-y"
              value={ruleForm.comment}
              onChange={(event) => setRuleForm((current) => ({ ...current, comment: event.target.value }))}
              placeholder="Комментарий к смене"
            />
          </label>

          <div className="mx-auto flex max-w-[660px] flex-col gap-3 border-t border-border pt-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {editingRule && ruleForm.comment.trim() ? (
                <button
                  type="button"
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={() => setRuleForm((current) => ({ ...current, comment: "" }))}
                  disabled={isSavingRule}
                >
                  <Trash2 className="h-4 w-4" />
                  Удалить комментарий
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
      </>}
    </PageMotion>
  );
}
