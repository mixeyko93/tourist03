import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { calendarRooms, campOptions, roomOptions } from "../mock-data";

const statusClasses = {
  processing: "border-amber-500/30 bg-amber-500/20 text-amber-200",
  confirmed: "border-emerald-500/30 bg-emerald-500/20 text-emerald-200",
  cancelled: "border-rose-500/30 bg-rose-500/20 text-rose-200",
  completed: "border-slate-500/30 bg-slate-500/20 text-slate-200",
} as const;

export default function CalendarPage() {
  const today = new Date();
  const days = Array.from({ length: new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate() }, (_, index) => index + 1);
  const monthLabelRaw = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" }).format(today);
  const monthLabel = `${monthLabelRaw.charAt(0).toUpperCase()}${monthLabelRaw.slice(1)}`;
  const hasCampOptions = campOptions.length > 0;
  const hasRoomOptions = roomOptions.length > 0;
  const hasCalendarRooms = calendarRooms.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Календарь"
        title="Календарь размещения"
        description="Недельный обзор помогает быстро увидеть конфликты, плотность заселения и статусы по каждому номеру."
      />

      <section className="glass-card p-5 md:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="soft-button h-11 w-11 px-0">
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button type="button" className="soft-button">
              Сегодня
            </button>
            <button type="button" className="soft-button h-11 w-11 px-0">
              <ChevronRight className="h-4 w-4" />
            </button>

            <div className="ml-0 rounded-2xl border border-border bg-background/70 p-1 sm:ml-2">
              <button type="button" className="rounded-xl px-4 py-2 text-sm text-muted-foreground transition hover:text-foreground">
                Месяц
              </button>
              <button type="button" className="rounded-xl border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 px-4 py-2 text-sm font-medium text-foreground">
                Неделя
              </button>
            </div>

            <h2 className="text-xl font-semibold tracking-[-0.04em] text-foreground sm:ml-2">{monthLabel}</h2>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:flex xl:flex-wrap xl:items-center">
            <div className="relative">
              <select
                className="soft-input w-full min-w-0 appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-52"
                disabled={!hasCampOptions}
              >
                {hasCampOptions ? (
                  campOptions.map((camp) => (
                    <option key={camp} value={camp}>
                      {camp}
                    </option>
                  ))
                ) : (
                  <option>Нет подключённых баз</option>
                )}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
            <div className="relative">
              <select
                className="soft-input w-full min-w-0 appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-44"
                disabled={!hasRoomOptions}
              >
                {hasRoomOptions ? (
                  <>
                    <option value="">Все номера</option>
                    {roomOptions.map((room) => (
                      <option key={room} value={room}>
                        {room}
                      </option>
                    ))}
                  </>
                ) : (
                  <option>Номерной фонд не настроен</option>
                )}
              </select>
              <ChevronDown className="pointer-events-none absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>
        </div>

        <p className="mt-4 text-sm text-muted-foreground md:hidden">
          На телефоне календарь прокручивается горизонтально, чтобы сохранить читаемость размещений по дням.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-4 text-xs font-medium text-muted-foreground">
          {[
            ["processing", "В обработке"],
            ["confirmed", "Подтверждено"],
            ["cancelled", "Отменено"],
            ["completed", "Завершено"],
          ].map(([status, label]) => (
            <div key={status} className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${statusClasses[status as keyof typeof statusClasses].split(" ")[1]}`} />
              {label}
            </div>
          ))}
        </div>

        {hasCalendarRooms ? (
          <div className="mt-6 overflow-x-auto rounded-3xl border border-border bg-background/55">
            <div className="min-w-[1480px]">
              <div className="flex border-b border-border bg-card/70">
                <div className="sticky left-0 z-10 w-56 shrink-0 border-r border-border bg-card/90 px-5 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  Номер
                </div>
                <div className="grid flex-1" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(46px, 1fr))` }}>
                  {days.map((day) => (
                    <div key={day} className="border-r border-border px-2 py-3 text-center last:border-r-0">
                      <div className="text-sm font-semibold text-foreground">{day}</div>
                      <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">день</div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                {calendarRooms.map((room) => (
                  <div key={room.id} className="flex border-b border-border last:border-b-0">
                    <div className="sticky left-0 z-10 flex w-56 shrink-0 flex-col justify-center border-r border-border bg-card/85 px-5 py-5">
                      <span className="text-sm font-semibold text-foreground">{room.title}</span>
                      <span className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{room.category}</span>
                    </div>

                    <div className="relative grid flex-1" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(46px, 1fr))` }}>
                      {days.map((day) => (
                        <div key={`${room.id}-${day}`} className="h-18 border-r border-border/80 last:border-r-0" />
                      ))}

                      <div className="pointer-events-none absolute inset-0 px-1 py-2">
                        {room.bookings.map((booking) => (
                          <div
                            key={`${room.id}-${booking.label}-${booking.start}`}
                            className={`absolute top-2 flex h-[calc(100%-1rem)] items-center rounded-2xl border px-3 text-xs font-medium shadow-lg shadow-black/10 ${statusClasses[booking.status]}`}
                            style={{
                              left: `calc((100% / ${days.length}) * ${booking.start - 1} + 4px)`,
                              width: `calc((100% / ${days.length}) * ${booking.span} - 8px)`,
                            }}
                          >
                            <span className="truncate">{booking.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="mt-6">
            <EmptyState
              icon={ChevronRight}
              title="Календарь пока пуст"
              description="После подключения базы, номеров и первых бронирований здесь появится реальная сетка размещения по дням."
            />
          </div>
        )}
      </section>
    </PageMotion>
  );
}
