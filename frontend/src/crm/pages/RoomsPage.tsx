import { BedDouble, Check, Image as ImageIcon, Plus, Users } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";
import { roomCards } from "../mock-data";

export default function RoomsPage() {
  const hasRooms = roomCards.length > 0;

  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Номера"
        title="Номера и цены"
        description="Управление категориями размещения, базовыми тарифами и составом удобств."
        actions={
          <button type="button" className="brand-button w-full gap-2 sm:w-auto">
            <Plus className="h-4 w-4" />
            Добавить категорию
          </button>
        }
      />

      {hasRooms ? (
        <div className="grid gap-6 xl:grid-cols-2">
          {roomCards.map((room, index) => (
            <article
              key={room.id}
              className={`glass-card overflow-hidden transition hover:-translate-y-0.5 ${room.active ? "" : "opacity-75"}`}
            >
              <div className="grid md:grid-cols-[220px_1fr]">
                <div className="relative flex min-h-56 items-center justify-center border-b border-border bg-background/70 md:border-b-0 md:border-r">
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(229,211,179,0.22),transparent_38%)]" />
                  <ImageIcon className="relative h-9 w-9 text-muted-foreground" />
                  <span className="absolute left-4 top-4 rounded-full border border-border bg-card/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    {room.active ? "Активно" : "Пауза"}
                  </span>
                  <span className="absolute bottom-4 left-4 rounded-full border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#E5D3B3]">
                    {index === 0 ? "Base" : "Season"}
                  </span>
                </div>

                <div className="p-6">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h2 className="text-xl font-semibold tracking-[-0.04em] text-foreground">{room.name}</h2>
                      <p className="mt-2 text-sm text-muted-foreground">Категория с отдельной карточкой и пакетом удобств.</p>
                    </div>
                    <div className="rounded-2xl border border-border bg-background/70 px-4 py-3 text-right">
                      <div className="text-lg font-semibold text-foreground">{room.price}</div>
                      <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">от / ночь</div>
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-4 text-sm text-muted-foreground">
                    <span className="inline-flex items-center gap-2">
                      <Users className="h-4 w-4 text-[#E5D3B3]" />
                      {room.capacity}
                    </span>
                    <span className="inline-flex items-center gap-2">
                      <BedDouble className="h-4 w-4 text-[#E5D3B3]" />
                      {room.beds}
                    </span>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
                    {room.features.map((feature) => (
                      <span key={feature} className="inline-flex items-center gap-2 rounded-full border border-border bg-background/70 px-3 py-1.5 text-sm text-foreground">
                        <Check className="h-3.5 w-3.5 text-[#E5D3B3]" />
                        {feature}
                      </span>
                    ))}
                  </div>

                  <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <span className="rounded-2xl border border-border bg-background/70 px-4 py-2 text-sm text-muted-foreground">
                      Всего номеров: <strong className="font-semibold text-foreground">{room.count}</strong>
                    </span>
                    <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
                      <button type="button" className="soft-button w-full px-4 py-2.5 sm:w-auto">
                        Изменить
                      </button>
                      <button type="button" className="w-full rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-300 transition hover:bg-rose-500/18 sm:w-auto">
                        Удалить
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <section className="glass-card p-6">
          <EmptyState
            icon={ImageIcon}
            title="Номерной фонд ещё не заполнен"
            description="Добавьте реальные категории размещения, тарифы и удобства. После этого здесь появятся карточки номеров для редактирования."
          />
        </section>
      )}
    </PageMotion>
  );
}
