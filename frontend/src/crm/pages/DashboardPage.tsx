import { BedDouble, CalendarClock, CircleDollarSign, Sparkles, TrendingUp, Users } from "lucide-react";
import { dashboardStats, recentBookings, revenueSeries } from "../mock-data";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";

const statusClasses: Record<(typeof recentBookings)[number]["status"], string> = {
  confirmed: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  processing: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  completed: "border-sky-500/25 bg-sky-500/10 text-sky-300",
};

export default function DashboardPage() {
  const maxRevenue = Math.max(...revenueSeries.map((item) => item.revenue));

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Сводка"
        title="Сводка по базе"
        description="Премиальный обзор текущей загрузки, динамики выручки и ближайших бронирований без переключения между разделами."
        actions={
          <>
            <select className="soft-input min-w-52 pr-10">
              <option>Гостиный Дворъ</option>
              <option>Ангир</option>
              <option>Байкал Резиденс</option>
            </select>
            <button type="button" className="brand-outline">
              Скачать отчёт
            </button>
          </>
        }
      />

      <section className="grid gap-4 md:grid-cols-3">
        {dashboardStats.map((stat, index) => {
          const Icon = [CalendarClock, Users, BedDouble][index] ?? Sparkles;
          return (
            <article key={stat.label} className="glass-card p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{stat.label}</p>
                  <p className="text-4xl font-semibold tracking-[-0.06em] text-foreground">{stat.value}</p>
                </div>
                <span className="rounded-2xl border border-[#E5D3B3]/30 bg-[#E5D3B3]/10 p-3 text-[#E5D3B3]">
                  <Icon className="h-5 w-5" />
                </span>
              </div>
              <div className="mt-6 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{stat.note}</span>
                <span className="font-semibold text-[#E5D3B3]">{stat.delta}</span>
              </div>
            </article>
          );
        })}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <article className="glass-card p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Доход и загрузка</p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-0.04em] text-foreground">Динамика на полгода</h2>
            </div>
            <div className="rounded-2xl border border-border bg-background/70 px-4 py-2 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">3,04 млн ₽</span> суммарно
            </div>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_220px]">
            <div className="flex items-end gap-3">
              {revenueSeries.map((item) => (
                <div key={item.month} className="flex flex-1 flex-col items-center gap-3">
                  <div className="flex h-64 w-full items-end rounded-[1.6rem] border border-border bg-background/55 p-2">
                    <div
                      className="w-full rounded-[1.1rem] bg-gradient-to-t from-[#E5D3B3] via-[#E5D3B3]/70 to-white/30 shadow-lg shadow-[#E5D3B3]/10"
                      style={{ height: `${(item.revenue / maxRevenue) * 100}%` }}
                    />
                  </div>
                  <div className="space-y-1 text-center">
                    <p className="text-sm font-medium text-foreground">{item.month}</p>
                    <p className="text-xs text-muted-foreground">{item.revenue} тыс.</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-3 rounded-[1.8rem] border border-border bg-background/65 p-4">
              <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 p-4">
                <CircleDollarSign className="h-5 w-5 text-[#E5D3B3]" />
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Средний чек</p>
                  <p className="text-lg font-semibold text-foreground">18 400 ₽</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 p-4">
                <TrendingUp className="h-5 w-5 text-[#E5D3B3]" />
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Пиковая загрузка</p>
                  <p className="text-lg font-semibold text-foreground">91%</p>
                </div>
              </div>
              <div className="rounded-2xl border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-[#E5D3B3]">Инсайт недели</p>
                <p className="mt-2 text-sm leading-6 text-foreground">
                  Больше всего дохода приносят короткие weekend-заезды в «Люкс» и «Комфорт Family».
                </p>
              </div>
            </div>
          </div>
        </article>

        <article className="glass-card p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Последние брони</p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-0.04em] text-foreground">Живая лента заявок</h2>
            </div>
            <span className="rounded-full border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#E5D3B3]">
              3 активных
            </span>
          </div>

          <div className="mt-6 space-y-3">
            {recentBookings.map((booking) => (
              <article key={booking.id} className="rounded-[1.4rem] border border-border bg-background/65 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-foreground">{booking.guest}</p>
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${statusClasses[booking.status]}`}>
                        {booking.status}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{booking.room}</p>
                    <p className="mt-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">{booking.dates}</p>
                  </div>
                  <p className="text-sm font-semibold text-foreground">{booking.amount}</p>
                </div>
              </article>
            ))}
          </div>
        </article>
      </section>
    </PageMotion>
  );
}
