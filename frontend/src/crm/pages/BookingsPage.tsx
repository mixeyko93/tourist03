import { CalendarRange, ChevronDown, Filter, Plus, Search } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { bookingRows, campOptions, roomOptions } from "../mock-data";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { ModalShell } from "../components/ModalShell";

const statusClasses = {
  confirmed: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  processing: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  completed: "border-sky-500/25 bg-sky-500/10 text-sky-300",
} as const;

export default function BookingsPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const hasBookings = bookingRows.length > 0;
  const hasCampOptions = campOptions.length > 0;
  const hasRoomOptions = roomOptions.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Брони"
        title="Управление бронями"
        description="Фильтрация, контроль статусов и быстрое создание новой брони внутри одного интерфейса."
        actions={
          <button
            type="button"
            className="brand-button w-full gap-2 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
            onClick={() => setIsCreateOpen(true)}
            disabled={!hasRoomOptions}
          >
            <Plus className="h-4 w-4" />
            Создать бронь
          </button>
        }
      />

      <section className="glass-card p-5">
        <div className="grid gap-3 md:grid-cols-2 xl:flex xl:flex-wrap xl:items-center">
          <div className="relative min-w-0 flex-1 xl:max-w-xs">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input type="search" className="soft-input pl-11" placeholder="Поиск по гостю или номеру" />
          </div>

          <div className="relative min-w-0">
            <select
              className="soft-input appearance-none pr-10 disabled:cursor-not-allowed disabled:opacity-60"
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

          <label className="relative min-w-0">
            <CalendarRange className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input type="text" className="soft-input pl-11" placeholder="дд.мм.гггг" />
          </label>

          <label className="relative min-w-0">
            <CalendarRange className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input type="text" className="soft-input pl-11" placeholder="дд.мм.гггг" />
          </label>

          <button type="button" className="soft-button w-full gap-2 md:col-span-2 xl:w-auto">
            <Filter className="h-4 w-4 text-[#E5D3B3]" />
            Фильтровать
          </button>
        </div>
      </section>

      <section className="glass-card overflow-hidden md:hidden">
        {hasBookings ? (
          <div className="space-y-3 p-4">
            {bookingRows.map((booking) => (
              <article key={booking.id} className="rounded-[1.4rem] border border-border bg-background/65 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{booking.room}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">{booking.id}</p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusClasses[booking.status]}`}>
                    {booking.status}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 text-sm">
                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Даты</p>
                    <p className="mt-1 text-foreground">
                      {booking.checkIn}
                      {" -> "}
                      {booking.checkOut}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Гости</p>
                      <p className="mt-1 font-medium text-foreground">{booking.guests}</p>
                    </div>
                    <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Источник</p>
                      <p className="mt-1 font-medium text-foreground">{booking.source}</p>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Оплата</p>
                    <p className="mt-1 text-foreground">{booking.payment}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="p-4">
            <EmptyState
              icon={CalendarRange}
              compact
              title="Список броней пуст"
              description="После запуска продаж здесь появятся реальные заезды, источники заявок и статусы оплаты."
            />
          </div>
        )}
      </section>

      <section className="glass-card hidden overflow-hidden md:block">
        {hasBookings ? (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead className="bg-background/70">
                <tr className="border-b border-border">
                  {["Заезд", "Выезд", "Гости", "Номер", "Статус", "Оплата", "Источник"].map((cell) => (
                    <th key={cell} className="px-6 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bookingRows.map((booking) => (
                  <tr key={booking.id} className="border-b border-border/80 last:border-b-0 hover:bg-accent/40">
                    <td className="px-6 py-4 text-sm text-foreground">{booking.checkIn}</td>
                    <td className="px-6 py-4 text-sm text-foreground">{booking.checkOut}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{booking.guests}</td>
                    <td className="px-6 py-4 text-sm font-medium text-foreground">{booking.room}</td>
                    <td className="px-6 py-4">
                      <span className={`rounded-full border px-3 py-1 text-xs font-medium ${statusClasses[booking.status]}`}>
                        {booking.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{booking.payment}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{booking.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6">
            <EmptyState
              icon={CalendarRange}
              title="Пока нет ни одной брони"
              description="Сюда попадут только реальные заказы из CRM, сайта, Telegram Mini App и других подключённых каналов."
            />
          </div>
        )}
      </section>

      <ModalShell
        open={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Новая бронь"
        description="Модалка намеренно ограничена по высоте и прокручивается внутри, чтобы корректно работать на смартфоне."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Гость</span>
            <input className="soft-input" placeholder="Имя гостя" />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Телефон</span>
            <input className="soft-input" placeholder="+7 (999) 000-00-00" />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Заезд</span>
            <input className="soft-input" placeholder="02.04.2026" />
          </label>
          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Выезд</span>
            <input className="soft-input" placeholder="05.04.2026" />
          </label>
          <label className="space-y-2 md:col-span-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Номер</span>
            <select className="soft-input appearance-none disabled:cursor-not-allowed disabled:opacity-60" disabled={!hasRoomOptions}>
              {hasRoomOptions ? (
                roomOptions.map((room) => (
                  <option key={room} value={room}>
                    {room}
                  </option>
                ))
              ) : (
                <option>Номера появятся после настройки фонда</option>
              )}
            </select>
            {!hasRoomOptions ? (
              <p className="text-sm text-muted-foreground">Сначала добавьте категории номеров, чтобы можно было оформить бронь вручную.</p>
            ) : null}
          </label>
          <label className="space-y-2 md:col-span-2">
            <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
            <textarea className="soft-input min-h-32 resize-none" placeholder="Особые пожелания гостя" />
          </label>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button type="button" className="soft-button" onClick={() => setIsCreateOpen(false)}>
            Отмена
          </button>
          <button
            type="button"
            className="brand-button disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => setIsCreateOpen(false)}
            disabled={!hasRoomOptions}
          >
            Сохранить бронь
          </button>
        </div>
      </ModalShell>
    </PageMotion>
  );
}
