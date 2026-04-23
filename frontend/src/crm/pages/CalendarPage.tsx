import { BedDouble, CalendarDays, ChevronDown, ChevronLeft, ChevronRight, PencilLine, Users } from "lucide-react";
import { type PointerEvent as ReactPointerEvent, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { EmptyState } from "../components/EmptyState";
import { ModalShell } from "../components/ModalShell";
import { PageMotion } from "../components/PageMotion";
import { PageLoadingState } from "../components/PageLoadingState";
import { PageRefreshOverlay } from "../components/PageRefreshOverlay";
import { SectionHeading } from "../components/SectionHeading";
import { usePageLoadState } from "../components/usePageLoadState";
import { getProductionDayTone } from "../productionCalendar";
import {
  createCrmBooking,
  fetchCrmCalendarFeed,
  fetchCrmCampRooms,
  fetchCrmCamps,
  updateCrmRoom,
  type CrmCalendarFeed,
  type CrmCamp,
  type CrmCreateBookingPayload,
  type CrmRoomOption,
  type CrmRoomUpsertPayload,
} from "../session";

const statusClasses = {
  processing: "border-amber-500/30 bg-amber-500/20 text-amber-200",
  confirmed: "border-emerald-500/30 bg-emerald-500/20 text-emerald-200",
  cancelled: "border-rose-500/30 bg-rose-500/20 text-rose-200",
  completed: "border-slate-500/30 bg-slate-500/20 text-slate-200",
} as const;

const statusDotClasses = {
  processing: "bg-amber-400",
  confirmed: "bg-emerald-400",
  cancelled: "bg-rose-400",
  completed: "bg-slate-300",
} as const;

const emptyFeed: CrmCalendarFeed = {
  date_from: null,
  date_to: null,
  rooms: [],
};

const roomColumnWidth = 308;

type ViewMode = "month" | "week";

type BookingCreateForm = {
  guestName: string;
  guestPhone: string;
  guestEmail: string;
  guestsCount: string;
  checkIn: string;
  checkOut: string;
  status: string;
  paymentStatus: string;
  paymentRequired: boolean;
  comment: string;
};

type RoomEditForm = {
  name: string;
  roomType: string;
  price: string;
  priceAdult: string;
  priceChild: string;
  singleBeds: string;
  doubleBeds: string;
  description: string;
};

const emptyBookingForm: BookingCreateForm = {
  guestName: "",
  guestPhone: "",
  guestEmail: "",
  guestsCount: "1",
  checkIn: "",
  checkOut: "",
  status: "confirmed",
  paymentStatus: "unpaid",
  paymentRequired: false,
  comment: "",
};

const emptyRoomForm: RoomEditForm = {
  name: "",
  roomType: "",
  price: "0",
  priceAdult: "0",
  priceChild: "0",
  singleBeds: "0",
  doubleBeds: "0",
  description: "",
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

function getWeekdayLabel(value: Date) {
  return new Intl.DateTimeFormat("ru-RU", { weekday: "short" }).format(value).replace(".", "");
}

function formatDateLabel(value: string) {
  if (!value) {
    return "Не указано";
  }
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) {
    return value;
  }
  return `${day}.${month}.${year}`;
}

function formatCurrency(value: number | null | undefined) {
  return new Intl.NumberFormat("ru-RU").format(Number(value || 0)) + " ₽";
}

function mapBookingStatusToCalendarStatus(status: string): "processing" | "confirmed" | "cancelled" | "completed" {
  if (["confirmed", "checked_in"].includes(status)) {
    return "confirmed";
  }
  if (status === "completed") {
    return "completed";
  }
  if (["cancelled", "cancelled_by_user", "cancelled_by_base", "rejected", "expired_pending", "no_show"].includes(status)) {
    return "cancelled";
  }
  return "processing";
}

function isPaymentRequiredAvailable(paymentStatus: string) {
  return ["unpaid", "awaiting_prepayment", "partially_paid", "failed"].includes(paymentStatus);
}

function buildRoomPayload(room: CrmRoomOption, form: RoomEditForm): CrmRoomUpsertPayload {
  return {
    name: form.name,
    room_type: form.roomType || room.room_type || "Апартамент",
    floors: Number(room.floors ?? 1),
    floor: Number(room.floor ?? 1),
    beds_single: Number(form.singleBeds || 0),
    beds_double: Number(form.doubleBeds || 0),
    bath_type: room.bath_type || "Нет",
    wc_type: room.wc_type || "Нет",
    bbq_type: room.bbq_type || "Нет",
    kitchen_type: room.kitchen_type || "Нет",
    gazebo_type: room.gazebo_type || "Нет",
    terrace_type: room.terrace_type || "Нет",
    pool_type: room.pool_type || "Нет",
    balcony_type: room.balcony_type || "Нет",
    has_ac: Boolean(room.has_ac),
    price_adult: Number(form.priceAdult || 0),
    price_child: Number(form.priceChild || 0),
    price: Number(form.price || 0),
    discount_pct: Number(room.discount_pct ?? 0),
    discount_from_nights: Number(room.discount_from_nights ?? 0),
    description: form.description,
    media: room.media,
  };
}

function buildRoomForm(room: CrmRoomOption): RoomEditForm {
  return {
    name: room.name || "",
    roomType: room.room_type || "Апартамент",
    price: String(room.price ?? 0),
    priceAdult: String(room.price_adult ?? 0),
    priceChild: String(room.price_child ?? 0),
    singleBeds: String(room.beds_single ?? 0),
    doubleBeds: String(room.beds_double ?? 0),
    description: room.description || "",
  };
}

export default function CalendarPage() {
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [focusDate, setFocusDate] = useState(() => new Date());
  const [camps, setCamps] = useState<CrmCamp[]>([]);
  const [selectedCampId, setSelectedCampId] = useState<number | null>(null);
  const [selectedRoomId, setSelectedRoomId] = useState("");
  const [highlightedRoomId, setHighlightedRoomId] = useState("");
  const [feed, setFeed] = useState<CrmCalendarFeed>(emptyFeed);
  const [roomOptions, setRoomOptions] = useState<CrmRoomOption[]>([]);
  const [isMetaLoading, setIsMetaLoading] = useState(true);
  const [isFeedLoading, setIsFeedLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [hasHorizontalOverflow, setHasHorizontalOverflow] = useState(false);
  const [isScrollIndicatorActive, setIsScrollIndicatorActive] = useState(false);
  const [isGridDragging, setIsGridDragging] = useState(false);
  const [scrollThumbWidth, setScrollThumbWidth] = useState(0);
  const [scrollThumbOffset, setScrollThumbOffset] = useState(0);
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
  const [bookingModalOpen, setBookingModalOpen] = useState(false);
  const [bookingForm, setBookingForm] = useState<BookingCreateForm>(emptyBookingForm);
  const [bookingRoomId, setBookingRoomId] = useState<number | null>(null);
  const [bookingRoomLabel, setBookingRoomLabel] = useState("");
  const [bookingError, setBookingError] = useState("");
  const [isBookingSaving, setIsBookingSaving] = useState(false);
  const [roomModalOpen, setRoomModalOpen] = useState(false);
  const [isRoomEditing, setIsRoomEditing] = useState(false);
  const [roomModalError, setRoomModalError] = useState("");
  const [isRoomSaving, setIsRoomSaving] = useState(false);
  const [activeRoomDetailsId, setActiveRoomDetailsId] = useState<number | null>(null);
  const [roomEditForm, setRoomEditForm] = useState<RoomEditForm>(emptyRoomForm);
  const [bookingDetailsOpen, setBookingDetailsOpen] = useState(false);
  const [activeBooking, setActiveBooking] = useState<CrmCalendarFeed["rooms"][number]["bookings"][number] | null>(null);
  const [activeBookingRoomTitle, setActiveBookingRoomTitle] = useState("");

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
  const dayColumnWidth = viewMode === "week" ? 88 : 56;
  const calendarContentWidth = roomColumnWidth + visibleDates.length * dayColumnWidth;
  const dateFrom = formatDateParam(periodStart);
  const dateTo = formatDateParam(periodEnd);
  const periodLabel = viewMode === "week" ? getWeekLabel(periodStart, periodEnd) : getMonthLabel(periodStart);

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

  useEffect(() => {
    const controller = new AbortController();
    setIsMetaLoading(true);
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
          setIsMetaLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedCampId) {
      setFeed(emptyFeed);
      setRoomOptions([]);
      return;
    }

    const controller = new AbortController();
    setIsFeedLoading(true);
    setErrorMessage("");

    Promise.all([
      fetchCrmCalendarFeed(
        {
          campId: selectedCampId,
          dateFrom,
          dateTo,
        },
        controller.signal,
      ),
      fetchCrmCampRooms(selectedCampId, controller.signal),
    ])
      .then(([payload, roomItems]) => {
        setFeed(payload);
        setRoomOptions(roomItems);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить календарь");
        setFeed(emptyFeed);
        setRoomOptions([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsFeedLoading(false);
        }
      });

    return () => controller.abort();
  }, [dateFrom, dateTo, reloadKey, selectedCampId]);

  useEffect(() => {
    if (!selectedRoomId) {
      return;
    }
    if (!feed.rooms.some((room) => room.id === selectedRoomId)) {
      setSelectedRoomId("");
    }
  }, [feed.rooms, selectedRoomId]);

  useEffect(() => {
    if (!highlightedRoomId) {
      return;
    }
    if (!feed.rooms.some((room) => room.id === highlightedRoomId)) {
      setHighlightedRoomId("");
    }
  }, [feed.rooms, highlightedRoomId]);

  useEffect(() => {
    if (!successMessage || typeof window === "undefined") {
      return;
    }
    const timeoutId = window.setTimeout(() => setSuccessMessage(""), 2200);
    return () => window.clearTimeout(timeoutId);
  }, [successMessage]);

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
  }, [calendarContentWidth, feed.rooms.length, selectedRoomId, viewMode]);

  useEffect(() => {
    updateScrollMetrics();
  }, [hasHorizontalOverflow]);

  useEffect(() => {
    return () => {
      if (scrollIndicatorTimeoutRef.current !== null && typeof window !== "undefined") {
        window.clearTimeout(scrollIndicatorTimeoutRef.current);
      }
      gridDragActiveRef.current = false;
      setIsGridDragging(false);
    };
  }, []);

  const hasCampOptions = camps.length > 0;
  const hasRoomOptions = feed.rooms.length > 0;
  const visibleRooms = selectedRoomId ? feed.rooms.filter((room) => room.id === selectedRoomId) : feed.rooms;
  const roomOptionsById = useMemo(() => new Map(roomOptions.map((room) => [room.id, room])), [roomOptions]);
  const activeRoom = activeRoomDetailsId ? roomOptionsById.get(activeRoomDetailsId) || null : null;
  const pageIsLoading = isMetaLoading || isFeedLoading;
  const { showInitialSkeleton, showRefreshOverlay, isPageVisible } = usePageLoadState(pageIsLoading);

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
    if (target.closest("[data-booking-block='true']") || target.closest("[data-calendar-no-drag='true']")) {
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
    // Defer setPointerCapture until movement threshold is exceeded,
    // so double-click on empty cells still fires normally.
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

  const openRoomDetails = (roomId: number | null) => {
    if (!roomId) {
      return;
    }
    const room = roomOptionsById.get(roomId);
    if (!room) {
      return;
    }
    setActiveRoomDetailsId(roomId);
    setRoomEditForm(buildRoomForm(room));
    setRoomModalError("");
    setIsRoomEditing(false);
    setRoomModalOpen(true);
  };

  const closeRoomDetails = () => {
    if (isRoomSaving) {
      return;
    }
    setRoomModalOpen(false);
    setIsRoomEditing(false);
    setRoomModalError("");
    setActiveRoomDetailsId(null);
    setRoomEditForm(emptyRoomForm);
  };

  const openCreateBooking = (room: CrmCalendarFeed["rooms"][number], date: Date) => {
    if (!room.room_id) {
      setErrorMessage("Для этого апартамента пока нельзя создать бронь: не найден ID номера.");
      return;
    }
    const nextDay = addDays(date, 1);
    setHighlightedRoomId(room.id);
    setBookingRoomId(room.room_id);
    setBookingRoomLabel(room.title);
    setBookingForm({
      ...emptyBookingForm,
      checkIn: formatDateParam(date),
      checkOut: formatDateParam(nextDay),
    });
    setBookingError("");
    setBookingModalOpen(true);
  };

  const openBookingDetails = (room: CrmCalendarFeed["rooms"][number], booking: CrmCalendarFeed["rooms"][number]["bookings"][number]) => {
    setHighlightedRoomId(room.id);
    setActiveBooking(booking);
    setActiveBookingRoomTitle(room.title);
    setBookingDetailsOpen(true);
  };

  const closeCreateBooking = () => {
    if (isBookingSaving) {
      return;
    }
    setBookingModalOpen(false);
    setBookingError("");
    setBookingForm(emptyBookingForm);
    setBookingRoomId(null);
    setBookingRoomLabel("");
  };

  const handleCreateBookingSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCampId || !bookingRoomId) {
      setBookingError("Сначала выберите базу и апартамент.");
      return;
    }
    if (!bookingForm.guestName.trim()) {
      setBookingError("Укажите имя гостя.");
      return;
    }
    if (!bookingForm.guestPhone.trim()) {
      setBookingError("Укажите телефон гостя.");
      return;
    }

    const payload: CrmCreateBookingPayload = {
      camp_id: selectedCampId,
      room_id: bookingRoomId,
      check_in: bookingForm.checkIn,
      check_out: bookingForm.checkOut,
      guests_count: Number(bookingForm.guestsCount || 1),
      status: bookingForm.status,
      payment_status: bookingForm.paymentStatus,
      payment_required: isPaymentRequiredAvailable(bookingForm.paymentStatus) ? bookingForm.paymentRequired : false,
      guest_name: bookingForm.guestName.trim(),
      guest_phone: bookingForm.guestPhone.trim(),
      guest_email: bookingForm.guestEmail.trim() || undefined,
      comment: bookingForm.comment.trim() || undefined,
    };

    try {
      setIsBookingSaving(true);
      setBookingError("");
      const response = await createCrmBooking(payload);
      setFeed((current) => ({
        ...current,
        rooms: current.rooms.map((room) =>
          room.room_id === bookingRoomId
            ? {
                ...room,
                bookings: [
                  ...room.bookings,
                  {
                    id: response.id,
                    label: payload.guest_name || "Новая бронь",
                    status: mapBookingStatusToCalendarStatus(payload.status),
                    start_day: Math.max(1, visibleDates.findIndex((item) => formatDateParam(item) === payload.check_in) + 1),
                    span_days: Math.max(1, Math.round((new Date(payload.check_out).getTime() - new Date(payload.check_in).getTime()) / 86400000)),
                    check_in: payload.check_in,
                    check_out: payload.check_out,
                    source: "crm",
                  },
                ],
              }
            : room,
        ),
      }));
      closeCreateBooking();
      setSuccessMessage("Бронь добавлена в календарь.");
    } catch (error) {
      setBookingError(error instanceof Error ? error.message : "Не удалось создать бронь");
    } finally {
      setIsBookingSaving(false);
    }
  };

  const handleRoomSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCampId || !activeRoomDetailsId || !activeRoom) {
      setRoomModalError("Не удалось определить апартамент.");
      return;
    }

    try {
      setIsRoomSaving(true);
      setRoomModalError("");
      const payload = buildRoomPayload(activeRoom, roomEditForm);
      await updateCrmRoom(selectedCampId, activeRoomDetailsId, payload);
      const updatedRoom: CrmRoomOption = {
        ...activeRoom,
        name: payload.name,
        room_type: payload.room_type || activeRoom.room_type,
        beds_single: payload.beds_single,
        beds_double: payload.beds_double,
        price: payload.price,
        price_adult: payload.price_adult,
        price_child: payload.price_child,
        description: payload.description || "",
      };
      setRoomOptions((current) => current.map((room) => (room.id === activeRoomDetailsId ? updatedRoom : room)));
      setFeed((current) => ({
        ...current,
        rooms: current.rooms.map((room) =>
          room.room_id === activeRoomDetailsId
            ? {
                ...room,
                title: payload.name,
                category: payload.room_type || room.category,
              }
            : room,
        ),
      }));
      setIsRoomEditing(false);
      setSuccessMessage("Карточка апартамента обновлена.");
    } catch (error) {
      setRoomModalError(error instanceof Error ? error.message : "Не удалось обновить апартамент");
    } finally {
      setIsRoomSaving(false);
    }
  };

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      {showInitialSkeleton ? (
        <>
          <SectionHeading title="Календарь размещения" description="Живой календарь показывает реальные бронирования по выбранной базе, чтобы быстро видеть загрузку и конфликты." />
          <section className="glass-card p-5 md:p-6">
            <PageLoadingState blocks={2} columnsClassName="grid-cols-1" blockHeightClassName="h-44" />
            <div className="mt-5">
              <PageLoadingState blocks={1} columnsClassName="grid-cols-1" blockHeightClassName="h-[26rem]" />
            </div>
          </section>
        </>
      ) : <>
      {successMessage ? (
        <div className="fixed inset-x-0 top-20 z-40 flex justify-center px-4">
          <div className="rounded-2xl border border-emerald-500/35 bg-emerald-500/14 px-5 py-3 text-sm font-medium text-emerald-200 shadow-lg shadow-black/10 backdrop-blur-xl dark:text-emerald-100">
            {successMessage}
          </div>
        </div>
      ) : null}

      <SectionHeading title="Календарь размещения" description="Живой календарь показывает реальные бронирования по выбранной базе, чтобы быстро видеть загрузку и конфликты." />

      {showRefreshOverlay ? <PageRefreshOverlay /> : null}
        <section className="glass-card p-5 md:p-6">
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

            <div className="ml-0 rounded-2xl border border-border bg-background/70 p-1 sm:ml-2">
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

            <h2 className="text-xl font-semibold tracking-[-0.04em] text-foreground sm:ml-2">{periodLabel}</h2>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:flex xl:flex-wrap xl:items-center">
            <div className="relative">
              <select
                className="soft-input w-full min-w-0 appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-52"
                value={selectedCampId ?? ""}
                onChange={(event) => {
                  setSelectedCampId(event.target.value ? Number(event.target.value) : null);
                  setSelectedRoomId("");
                }}
                disabled={!hasCampOptions || isMetaLoading}
              >
                {hasCampOptions ? (
                  camps.map((camp) => (
                    <option key={camp.id} value={camp.id}>
                      {camp.name}
                    </option>
                  ))
                ) : (
                  <option value="">Нет подключённых баз</option>
                )}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>

            <div className="relative">
              <select
                className="soft-input w-full min-w-0 appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-44"
                value={selectedRoomId}
                onChange={(event) => setSelectedRoomId(event.target.value)}
                disabled={!hasRoomOptions || isFeedLoading}
              >
                {hasRoomOptions ? (
                  <>
                    <option value="">Все апартаменты</option>
                    {feed.rooms.map((room) => (
                      <option key={room.id} value={room.id}>
                        {room.title}
                      </option>
                    ))}
                  </>
                ) : (
                  <option value="">Апартаменты не найдены</option>
                )}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>
        </div>

        <p className="mt-4 text-sm text-muted-foreground md:hidden">На телефоне календарь прокручивается по горизонтали. Ниже появится бегунок, если сетка шире экрана.</p>

        <div className="mt-5 flex flex-wrap items-center gap-4 text-xs font-medium text-muted-foreground">
          {[
            ["processing", "Нужно обработать"],
            ["confirmed", "Подтверждено"],
            ["cancelled", "Отменено"],
            ["completed", "Завершено"],
          ].map(([status, label]) => (
            <div key={status} className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${statusDotClasses[status as keyof typeof statusDotClasses]}`} />
              {label}
            </div>
          ))}
        </div>

        {errorMessage ? (
          <div className="mt-6 rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-200">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p>{errorMessage}</p>
              <button type="button" onClick={() => setReloadKey((value) => value + 1)} className="soft-button shrink-0">
                Повторить
              </button>
            </div>
          </div>
        ) : null}

        {!hasCampOptions ? (
          <div className="mt-6">
            <EmptyState icon={ChevronRight} title="У вас пока нет подключённых баз" description="После выдачи доступа к базе здесь появятся её апартаменты и бронирования." />
          </div>
        ) : !feed.rooms.length ? (
          <div className="mt-6">
            <EmptyState
              icon={ChevronRight}
              title="Номерной фонд ещё не заполнен"
              description="Добавьте апартаменты в CRM или через superadmin, и календарь сразу начнёт отображать сетку размещения."
            />
          </div>
        ) : (
          <>
            <div
              ref={gridScrollRef}
              onScroll={syncScrollFromGrid}
              onPointerDown={handleGridPointerDown}
              onPointerMove={handleGridPointerMove}
              onPointerUp={stopGridDragging}
              onPointerCancel={stopGridDragging}
              className={`crm-calendar-grid-scroll mt-6 overflow-x-auto rounded-3xl border border-border bg-background/55 ${isGridDragging ? "crm-calendar-grid-scroll--dragging" : ""}`}
            >
              <div style={{ minWidth: calendarContentWidth }}>
                <div className="flex border-b border-border bg-card/70">
                  <div className="sticky left-0 z-30 shrink-0 border-r border-border bg-white px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground dark:bg-[#171b24]" style={{ width: roomColumnWidth }}>
                    Апартамент
                  </div>
                  <div className="grid flex-1" style={{ gridTemplateColumns: `repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}>
                    {visibleDates.map((value) => (
                      <div
                        key={formatDateParam(value)}
                        className={`border-r border-border px-2 py-3 text-center last:border-r-0 ${
                          getProductionDayTone(value) === "holiday"
                            ? "bg-rose-50/85 dark:bg-rose-500/10"
                            : getProductionDayTone(value) === "weekend"
                              ? "bg-[#FFF8EE]/85 dark:bg-[#E5D3B3]/6"
                              : ""
                        }`}
                      >
                        <div className="text-sm font-semibold text-foreground">{getDayNumberLabel(value)}</div>
                        <div className={`mt-1 text-[10px] uppercase tracking-[0.18em] ${getProductionDayTone(value) === "holiday" ? "text-rose-500 dark:text-rose-300" : "text-muted-foreground"}`}>{getWeekdayLabel(value)}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  {visibleRooms.map((room) => (
                    <div
                      key={room.id}
                      className="flex border-b border-border last:border-b-0"
                    >
                      <button
                        type="button"
                        data-calendar-no-drag="true"
                        onClick={() => setHighlightedRoomId(room.id)}
                        onDoubleClick={() => openRoomDetails(room.room_id)}
                        className={`sticky left-0 z-30 flex shrink-0 cursor-pointer flex-col justify-center border-r border-border px-5 py-5 text-left transition ${
                          highlightedRoomId === room.id
                            ? "bg-[#F8F0E2] shadow-[inset_0_0_0_1px_rgba(229,211,179,0.26)] dark:bg-[#1b202b] dark:shadow-[inset_0_0_0_1px_rgba(229,211,179,0.16)]"
                            : "bg-white hover:bg-accent/55 dark:bg-[#171b24]"
                        }`}
                        style={{ width: roomColumnWidth }}
                      >
                        <span className="text-sm font-semibold text-foreground">{room.title}</span>
                        <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{room.category}</span>
                      </button>

                      <div
                        className="relative grid flex-1"
                        style={{ gridTemplateColumns: `repeat(${visibleDates.length}, minmax(${dayColumnWidth}px, 1fr))` }}
                      >
                        {visibleDates.map((value) => (
                          <button
                            key={`${room.id}-${formatDateParam(value)}`}
                            type="button"
                            onDoubleClick={() => openCreateBooking(room, value)}
                            className={`h-18 border-r border-border/80 text-transparent last:border-r-0 ${
                              getProductionDayTone(value) === "holiday"
                                ? "bg-rose-50/70 dark:bg-rose-500/6"
                                : getProductionDayTone(value) === "weekend"
                                  ? "bg-[#FFF8EE]/70 dark:bg-[#E5D3B3]/4"
                                  : highlightedRoomId === room.id
                                    ? "bg-[#E5D3B3]/5 dark:bg-[#E5D3B3]/3"
                                    : "bg-transparent"
                            }`}
                            aria-label={`Создать бронь для ${room.title} на ${formatDateLabel(formatDateParam(value))}`}
                          >
                            ·
                          </button>
                        ))}

                        <div className="pointer-events-none absolute inset-0 px-1 py-2">
                          {room.bookings.map((booking) => (
                            <button
                              key={`${room.id}-${booking.id}`}
                              type="button"
                              data-booking-block="true"
                              onClick={() => openBookingDetails(room, booking)}
                              className={`pointer-events-auto absolute top-2 flex h-[calc(100%-1rem)] items-center rounded-2xl border px-3 text-left text-xs font-medium shadow-lg shadow-black/10 transition hover:brightness-105 ${statusClasses[booking.status]}`}
                              style={{
                                left: `calc((100% / ${visibleDates.length}) * ${booking.start_day - 1} + 4px)`,
                                width: `calc((100% / ${visibleDates.length}) * ${booking.span_days} - 8px)`,
                              }}
                              title={`${booking.label}: ${booking.check_in} → ${booking.check_out}`}
                            >
                              <span className="truncate">{booking.label}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {hasHorizontalOverflow ? (
              <div
                className={`mt-4 transition-opacity duration-300 ${isScrollIndicatorActive ? "opacity-100" : "pointer-events-none opacity-0"}`}
              >
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
                    className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-gradient-to-r from-[#E5D3B3]/55 via-sky-400/35 to-[#E5D3B3]/55 shadow-[0_0_0_1px_rgba(17,24,39,0.16)] transition-[opacity,box-shadow] duration-200 hover:shadow-[0_0_0_1px_rgba(17,24,39,0.28)]"
                    style={{ width: scrollThumbWidth, left: scrollThumbOffset }}
                  />
                </div>
              </div>
            ) : null}
          </>
        )}
        </section>

      <ModalShell
        open={roomModalOpen}
        onClose={closeRoomDetails}
        title={activeRoom ? activeRoom.name || "Карточка апартамента" : "Карточка апартамента"}
        description={activeRoom ? `${activeRoom.room_type || "Апартамент"} · ${formatCurrency(activeRoom.price)}` : "Подробная информация по апартаменту."}
      >
        {activeRoom ? (
          isRoomEditing ? (
            <form onSubmit={handleRoomSave} className="space-y-4">
              {roomModalError ? (
                <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{roomModalError}</div>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <label className="space-y-2 md:col-span-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Название</span>
                  <input className="soft-input" value={roomEditForm.name} onChange={(event) => setRoomEditForm((current) => ({ ...current, name: event.target.value }))} required />
                </label>

                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Тип</span>
                  <input className="soft-input" value={roomEditForm.roomType} onChange={(event) => setRoomEditForm((current) => ({ ...current, roomType: event.target.value }))} />
                </label>

                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Цена за апартамент</span>
                  <input type="number" min="0" className="soft-input" value={roomEditForm.price} onChange={(event) => setRoomEditForm((current) => ({ ...current, price: event.target.value }))} />
                </label>

                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Цена взрослого</span>
                  <input type="number" min="0" className="soft-input" value={roomEditForm.priceAdult} onChange={(event) => setRoomEditForm((current) => ({ ...current, priceAdult: event.target.value }))} />
                </label>

                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Цена ребёнка</span>
                  <input type="number" min="0" className="soft-input" value={roomEditForm.priceChild} onChange={(event) => setRoomEditForm((current) => ({ ...current, priceChild: event.target.value }))} />
                </label>

                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Односпальные кровати</span>
                  <input type="number" min="0" className="soft-input" value={roomEditForm.singleBeds} onChange={(event) => setRoomEditForm((current) => ({ ...current, singleBeds: event.target.value }))} />
                </label>

                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Двуспальные кровати</span>
                  <input type="number" min="0" className="soft-input" value={roomEditForm.doubleBeds} onChange={(event) => setRoomEditForm((current) => ({ ...current, doubleBeds: event.target.value }))} />
                </label>

                <label className="space-y-2 md:col-span-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Описание</span>
                  <textarea className="soft-input min-h-28 resize-none" value={roomEditForm.description} onChange={(event) => setRoomEditForm((current) => ({ ...current, description: event.target.value }))} />
                </label>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <button type="button" className="soft-button" onClick={() => setIsRoomEditing(false)} disabled={isRoomSaving}>
                  Отмена
                </button>
                <button type="submit" className="brand-button disabled:cursor-not-allowed disabled:opacity-60" disabled={isRoomSaving}>
                  {isRoomSaving ? "Сохраняем..." : "Сохранить изменения"}
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-5">
              {activeRoom.photos?.length || activeRoom.photo_main ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {(activeRoom.photos?.length ? activeRoom.photos.map((item) => item.url) : activeRoom.photo_main ? [activeRoom.photo_main] : []).slice(0, 6).map((url, index) => (
                    <div key={`${url}-${index}`} className="overflow-hidden rounded-2xl border border-border bg-background/65">
                      <img src={url} alt={`${activeRoom.name || "Апартамент"} ${index + 1}`} className="h-40 w-full object-cover" />
                    </div>
                  ))}
                </div>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-border bg-background/65 p-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    <BedDouble className="h-4 w-4 text-[#E5D3B3]" />
                    Формат
                  </div>
                  <p className="mt-2 text-lg font-semibold text-foreground">{activeRoom.room_type || "Апартамент"}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {Number(activeRoom.beds_single ?? 0)} односпальных · {Number(activeRoom.beds_double ?? 0)} двуспальных
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-background/65 p-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    <Users className="h-4 w-4 text-[#E5D3B3]" />
                    Вместимость и цены
                  </div>
                  <p className="mt-2 text-lg font-semibold text-foreground">{activeRoom.capacity ?? "—"} гостей</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Апартамент: {formatCurrency(activeRoom.price)} · Взрослый: {formatCurrency(activeRoom.price_adult)} · Ребёнок: {formatCurrency(activeRoom.price_child)}
                  </p>
                </div>
                <div className="rounded-2xl border border-border bg-background/65 p-4 md:col-span-2">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    <CalendarDays className="h-4 w-4 text-[#E5D3B3]" />
                    Описание и размещение
                  </div>
                  <p className="mt-2 text-sm leading-6 text-foreground">{activeRoom.description || "Описание ещё не заполнено."}</p>
                </div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <button type="button" className="soft-button" onClick={closeRoomDetails}>
                  Закрыть
                </button>
                <button type="button" className="brand-button gap-2" onClick={() => setIsRoomEditing(true)}>
                  <PencilLine className="h-4 w-4" />
                  Редактировать
                </button>
              </div>
            </div>
          )
        ) : null}
      </ModalShell>

      <ModalShell
        open={bookingModalOpen}
        onClose={closeCreateBooking}
        title="Новая бронь"
        description={bookingRoomLabel ? `Быстрое создание брони для апартамента «${bookingRoomLabel}».` : "Быстрое создание брони из календаря."}
      >
        <form onSubmit={handleCreateBookingSubmit} className="space-y-4">
          {bookingError ? <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{bookingError}</div> : null}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Гость</span>
              <input className="soft-input" value={bookingForm.guestName} onChange={(event) => setBookingForm((current) => ({ ...current, guestName: event.target.value }))} placeholder="Имя гостя" required />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Телефон</span>
              <input className="soft-input" value={bookingForm.guestPhone} onChange={(event) => setBookingForm((current) => ({ ...current, guestPhone: event.target.value }))} placeholder="+7 (999) 000-00-00" required />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Эл. почта</span>
              <input type="email" className="soft-input" value={bookingForm.guestEmail} onChange={(event) => setBookingForm((current) => ({ ...current, guestEmail: event.target.value }))} placeholder="guest@example.ru" />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Гостей</span>
              <input type="number" min="1" className="soft-input" value={bookingForm.guestsCount} onChange={(event) => setBookingForm((current) => ({ ...current, guestsCount: event.target.value }))} />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Заезд</span>
              <input type="date" className="soft-input" value={bookingForm.checkIn} onChange={(event) => setBookingForm((current) => ({ ...current, checkIn: event.target.value }))} required />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Выезд</span>
              <input type="date" className="soft-input" value={bookingForm.checkOut} onChange={(event) => setBookingForm((current) => ({ ...current, checkOut: event.target.value }))} required />
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Статус брони</span>
              <select className="soft-input appearance-none" value={bookingForm.status} onChange={(event) => setBookingForm((current) => ({ ...current, status: event.target.value }))}>
                <option value="confirmed">Подтверждена</option>
                <option value="awaiting_payment">Ожидает оплаты</option>
                <option value="awaiting_confirmation">Ожидает подтверждения</option>
                <option value="pending">Новая заявка</option>
              </select>
            </label>

            <label className="space-y-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Статус оплаты</span>
              <select
                className="soft-input appearance-none"
                value={bookingForm.paymentStatus}
                onChange={(event) =>
                  setBookingForm((current) => ({
                    ...current,
                    paymentStatus: event.target.value,
                    paymentRequired: isPaymentRequiredAvailable(event.target.value) ? current.paymentRequired : false,
                  }))
                }
              >
                <option value="unpaid">Не оплачено</option>
                <option value="awaiting_prepayment">Требуется предоплата</option>
                <option value="partially_paid">Частично оплачено</option>
                <option value="paid">Оплачено полностью</option>
                <option value="cash">Оплата на месте</option>
              </select>
            </label>

            <label className="flex items-center gap-3 rounded-2xl border border-border bg-background/60 px-4 py-3 md:col-span-2">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border bg-background"
                checked={bookingForm.paymentRequired}
                onChange={(event) => setBookingForm((current) => ({ ...current, paymentRequired: event.target.checked }))}
                disabled={!isPaymentRequiredAvailable(bookingForm.paymentStatus)}
              />
              <span className="text-sm text-foreground">Нужна предоплата</span>
            </label>

            <label className="space-y-2 md:col-span-2">
              <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
              <textarea className="soft-input min-h-28 resize-none" value={bookingForm.comment} onChange={(event) => setBookingForm((current) => ({ ...current, comment: event.target.value }))} placeholder="Особые пожелания, нюансы по оплате или заселению" />
            </label>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
            <button type="button" className="soft-button" onClick={closeCreateBooking} disabled={isBookingSaving}>
              Отмена
            </button>
            <button type="submit" className="brand-button disabled:cursor-not-allowed disabled:opacity-60" disabled={isBookingSaving}>
              {isBookingSaving ? "Сохраняем бронь..." : "Создать бронь"}
            </button>
          </div>
        </form>
      </ModalShell>

      <ModalShell
        open={bookingDetailsOpen}
        onClose={() => {
          setBookingDetailsOpen(false);
          setActiveBooking(null);
          setActiveBookingRoomTitle("");
        }}
        title={activeBooking ? activeBooking.label : "Карточка брони"}
        description={activeBooking ? `${activeBookingRoomTitle} · ${formatDateLabel(activeBooking.check_in)} → ${formatDateLabel(activeBooking.check_out)}` : "Подробности бронирования."}
      >
        {activeBooking ? (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-border bg-background/65 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Статус</p>
                <p className="mt-2 text-lg font-semibold text-foreground">{activeBooking.label}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {activeBooking.check_in} → {activeBooking.check_out}
                </p>
              </div>
              <div className="rounded-2xl border border-border bg-background/65 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Источник</p>
                <p className="mt-2 text-lg font-semibold text-foreground">{activeBooking.source || "CRM"}</p>
                <p className="mt-2 text-sm text-muted-foreground">Апартамент: {activeBookingRoomTitle}</p>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                className="soft-button"
                onClick={() => {
                  setBookingDetailsOpen(false);
                  navigate(`/bookings?search=${encodeURIComponent(String(activeBooking.id))}`);
                }}
              >
                Перейти в брони
              </button>
            </div>
          </div>
        ) : null}
      </ModalShell>
      </>}
    </PageMotion>
  );
}
