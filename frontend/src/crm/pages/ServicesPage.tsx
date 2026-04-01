import { Car, Coffee, Plus, Shield, Wifi } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { serviceCards } from "../mock-data";

const toneMap = {
  amber: {
    icon: Coffee,
    wrap: "bg-amber-500/10",
    iconColor: "text-amber-300",
  },
  sky: {
    icon: Car,
    wrap: "bg-sky-500/10",
    iconColor: "text-sky-300",
  },
  green: {
    icon: Shield,
    wrap: "bg-emerald-500/10",
    iconColor: "text-emerald-300",
  },
  violet: {
    icon: Wifi,
    wrap: "bg-violet-500/10",
    iconColor: "text-violet-300",
  },
} as const;

export default function ServicesPage() {
  const hasServices = serviceCards.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Услуги"
        title="Дополнительные услуги"
        description="Каталог платных и бесплатных сервисов, которые можно продавать вместе с размещением."
        actions={
          <button type="button" className="brand-button w-full gap-2 sm:w-auto">
            <Plus className="h-4 w-4" />
            Добавить услугу
          </button>
        }
      />

      {hasServices ? (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {serviceCards.map((service) => {
            const tone = toneMap[service.tone];
            const Icon = tone.icon;

            return (
              <article key={service.id} className="glass-card group p-5 transition hover:-translate-y-0.5">
                <div className="flex items-start justify-between">
                  <div className={`rounded-2xl border border-border p-3 ${tone.wrap}`}>
                    <Icon className={`h-5 w-5 ${tone.iconColor}`} />
                  </div>
                  <span
                    className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                      service.active
                        ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                        : "border-rose-500/20 bg-rose-500/10 text-rose-300"
                    }`}
                  >
                    {service.active ? "Активно" : "Пауза"}
                  </span>
                </div>

                <div className="mt-8 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{service.category}</p>
                  <h2 className="text-xl font-semibold tracking-[-0.04em] text-foreground transition group-hover:text-[#E5D3B3]">
                    {service.name}
                  </h2>
                  <p className="text-sm text-muted-foreground">{service.price}</p>
                </div>

                <div className="mt-8 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <button type="button" className="soft-button w-full px-4 py-2.5 sm:w-auto">
                    Изменить
                  </button>
                  <button type="button" className="w-full rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 sm:w-auto">
                    Удалить
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <section className="glass-card p-6">
          <EmptyState
            icon={Coffee}
            title="Дополнительные услуги не добавлены"
            description="Создайте реальные сервисы базы, чтобы менеджеры могли продавать их вместе с проживанием и видеть актуальные цены."
          />
        </section>
      )}
    </PageMotion>
  );
}
