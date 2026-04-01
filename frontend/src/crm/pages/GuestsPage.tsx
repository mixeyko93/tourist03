import { Filter, Mail, Phone, Search } from "lucide-react";
import { guestRows } from "../mock-data";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";

const guestStatusClasses = {
  Новый: "border-slate-500/20 bg-slate-500/10 text-slate-300",
  Постоянный: "border-sky-500/20 bg-sky-500/10 text-sky-300",
  VIP: "border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-[#E5D3B3]",
} as const;

export default function GuestsPage() {
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
          <button type="button" className="soft-button gap-2 self-start">
            <Filter className="h-4 w-4 text-[#E5D3B3]" />
            Фильтровать
          </button>
        </div>
      </section>

      <section className="glass-card overflow-hidden">
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
      </section>
    </PageMotion>
  );
}
