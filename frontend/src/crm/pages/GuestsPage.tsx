import { Filter, Mail, Phone, Search } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { guestRows } from "../mock-data";

const guestStatusClasses = {
  Новый: "border-slate-500/20 bg-slate-500/10 text-slate-300",
  Постоянный: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  VIP: "border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-[#E5D3B3]",
} as const;

export default function GuestsPage() {
  const hasGuests = guestRows.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Гости"
        title="База гостей"
        description="История приездов, контакты и ценность клиента для быстрого follow-up и персонального сервиса."
      />

      <section className="glass-card p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input type="search" className="soft-input pl-11" placeholder="Поиск по имени или телефону" />
          </div>
          <button type="button" className="soft-button w-full gap-2 self-start sm:w-auto">
            <Filter className="h-4 w-4 text-[#E5D3B3]" />
            Фильтровать
          </button>
        </div>
      </section>

      <section className="glass-card overflow-hidden md:hidden">
        {hasGuests ? (
          <div className="space-y-3 p-4">
            {guestRows.map((guest) => (
              <article key={guest.id} className="rounded-[1.4rem] border border-border bg-background/65 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{guest.name}</p>
                    <div className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1.5">
                        <Phone className="h-3.5 w-3.5 text-[#E5D3B3]" />
                        {guest.phone}
                      </span>
                      <span className="inline-flex items-center gap-1.5 break-all">
                        <Mail className="h-3.5 w-3.5 shrink-0 text-[#E5D3B3]" />
                        {guest.email}
                      </span>
                    </div>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${guestStatusClasses[guest.status]}`}>
                    {guest.status}
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Визиты</p>
                    <p className="mt-1 font-medium text-foreground">{guest.visits}</p>
                  </div>
                  <div className="rounded-2xl border border-border bg-card/55 px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Последний визит</p>
                    <p className="mt-1 font-medium text-foreground">{guest.lastVisit}</p>
                  </div>
                </div>
                <div className="mt-3 rounded-2xl border border-border bg-card/55 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Сумма</p>
                  <p className="mt-1 font-semibold text-foreground">{guest.totalSpent}</p>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="p-4">
            <EmptyState
              icon={Search}
              compact
              title="Гостевая база пока пуста"
              description="После первых реальных броней здесь появятся контакты гостей, история визитов и накопленная сумма оплат."
            />
          </div>
        )}
      </section>

      <section className="glass-card hidden overflow-hidden md:block">
        {hasGuests ? (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead className="bg-background/70">
                <tr className="border-b border-border">
                  {["Имя и контакты", "Визиты", "Сумма", "Последний визит", "Статус"].map((cell) => (
                    <th key={cell} className="px-6 py-4 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                      {cell}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {guestRows.map((guest) => (
                  <tr key={guest.id} className="border-b border-border/80 last:border-b-0 hover:bg-accent/40">
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-foreground">{guest.name}</div>
                        <div className="flex flex-col gap-1 text-xs text-muted-foreground md:flex-row md:gap-4">
                          <span className="inline-flex items-center gap-1.5">
                            <Phone className="h-3.5 w-3.5 text-[#E5D3B3]" />
                            {guest.phone}
                          </span>
                          <span className="inline-flex items-center gap-1.5">
                            <Mail className="h-3.5 w-3.5 text-[#E5D3B3]" />
                            {guest.email}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-foreground">{guest.visits}</td>
                    <td className="px-6 py-4 text-sm font-semibold text-foreground">{guest.totalSpent}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">{guest.lastVisit}</td>
                    <td className="px-6 py-4">
                      <span className={`rounded-full border px-3 py-1 text-xs font-medium ${guestStatusClasses[guest.status]}`}>
                        {guest.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6">
            <EmptyState
              icon={Search}
              title="Карточки гостей ещё не накоплены"
              description="CRM начнёт собирать клиентскую базу автоматически после появления первых подтверждённых броней."
            />
          </div>
        )}
      </section>
    </PageMotion>
  );
}
