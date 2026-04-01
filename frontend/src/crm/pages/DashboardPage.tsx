import { BarChart3, BedDouble, Building2, CalendarClock, CircleDollarSign, Sparkles, TrendingUp, Users } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { campOptions, dashboardStats, recentBookings, revenueSeries } from "../mock-data";

const statusClasses: Record<(typeof recentBookings)[number]["status"], string> = {
  confirmed: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  processing: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  completed: "border-sky-500/25 bg-sky-500/10 text-sky-300",
};

export default function DashboardPage() {
  const hasCampOptions = campOptions.length > 0;
  const hasRevenue = revenueSeries.length > 0;
  const hasRecentBookings = recentBookings.length > 0;
  const maxRevenue = Math.max(1, ...revenueSeries.map((item) => item.revenue));
  const totalRevenue = revenueSeries.reduce((sum, item) => sum + item.revenue, 0);
  const averageOccupancy = revenueSeries.length
    ? Math.round(revenueSeries.reduce((sum, item) => sum + item.occupancy, 0) / revenueSeries.length)
    : 0;
  const peakOccupancy = revenueSeries.length ? Math.max(...revenueSeries.map((item) => item.occupancy)) : 0;
  const peakMonth = revenueSeries.reduce<(typeof revenueSeries)[number] | null>(
    (best, item) => (best === null || item.occupancy > best.occupancy ? item : best),
    null,
  );

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Сводка"
        title="Сводка по базе"
        description="Премиальный обзор текущей загрузки, динамики выручки и ближайших бронирований без переключения между разделами."
        actions={
          <>
            <select
              className="soft-input w-full min-w-0 pr-10 disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-52"
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
            <button
              type="button"
              className="brand-outline w-full disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              disabled={!hasRevenue}
            >
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
              <span className="font-medium text-foreground">
                {hasRevenue ? `${new Intl.NumberFormat("ru-RU").format(totalRevenue)} тыс. ₽` : "Нет данных"}
              </span>{" "}
              суммарно
            </div>
          </div>

          {hasRevenue ? (
            <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_220px]">
              <div className="-mx-1 overflow-x-auto pb-2">
                <div className="flex min-w-[560px] items-end gap-3 px-1">
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
              </div>

              <div className="space-y-3 rounded-[1.8rem] border border-border bg-background/65 p-4">
                <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 p-4">
                  <CircleDollarSign className="h-5 w-5 text-[#E5D3B3]" />
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Выручка за период</p>
                    <p className="text-lg font-semibold text-foreground">{new Intl.NumberFormat("ru-RU").format(totalRevenue)} тыс. ₽</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 p-4">
                  <TrendingUp className="h-5 w-5 text-[#E5D3B3]" />
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Средняя загрузка</p>
                    <p className="text-lg font-semibold text-foreground">{averageOccupancy}%</p>
                  </div>
                </div>
                <div className="rounded-2xl border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-[#E5D3B3]">Пик периода</p>
                  <p className="mt-2 text-sm leading-6 text-foreground">
                    {peakMonth ? `Максимальная загрузка ${peakOccupancy}% зафиксирована в ${peakMonth.month}.` : "Данные появятся после первых бронирований."}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState
                icon={BarChart3}
                title="Пока нет данных для аналитики"
                description="Подключите базу и начните принимать реальные бронирования. После этого здесь появятся графики выручки и загрузки."
              />
            </div>
          )}
        </article>

        <article className="glass-card p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Последние брони</p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-0.04em] text-foreground">Живая лента заявок</h2>
            </div>
            <span className="rounded-full border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[#E5D3B3]">
              {hasRecentBookings ? `${recentBookings.length} записей` : "Нет данных"}
            </span>
          </div>

          <div className="mt-6">
            {hasRecentBookings ? (
              <div className="space-y-3">
                {recentBookings.map((booking) => (
                  <article key={booking.id} className="rounded-[1.4rem] border border-border bg-background/65 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
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
                      <p className="text-sm font-semibold text-foreground sm:text-right">{booking.amount}</p>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={CalendarClock}
                compact
                title="Брони ещё не поступали"
                description="Когда гости начнут оформлять реальные заказы, новые заявки появятся в этой ленте без ручного обновления."
              />
            )}
          </div>
        </article>
      </section>

      {!hasCampOptions ? (
        <section className="glass-card p-6">
          <EmptyState
            icon={Building2}
            compact
            title="CRM ожидает подключение базы"
            description="Сейчас в системе нет подключённых объектов. Добавьте первую базу отдыха и наполните номерной фонд, чтобы открыть рабочие сценарии."
          />
        </section>
      ) : null}
    </PageMotion>
  );
}
