import { Bell, Building2, Link2, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { PageMotion } from "../components/PageMotion";
import { SectionHeading } from "../components/SectionHeading";

const tabs = [
  { id: "profile", name: "Профиль базы", icon: Building2 },
  { id: "users", name: "Сотрудники", icon: UserRound },
  { id: "notifications", name: "Уведомления", icon: Bell },
  { id: "security", name: "Безопасность", icon: ShieldCheck },
  { id: "integrations", name: "Интеграции", icon: Link2 },
];

export default function SettingsPage() {
  return (
    <PageMotion className="space-y-6">
      <SectionHeading
        eyebrow="Настройки"
        title="Параметры базы"
        description="Управление основной информацией, правилами проживания и системными предпочтениями."
      />

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="glass-card p-3">
          <nav className="space-y-1">
            {tabs.map((tab, index) => (
              <button
                key={tab.id}
                type="button"
                className={`flex w-full items-center gap-3 rounded-2xl border px-4 py-3 text-left text-sm font-medium transition ${
                  index === 0
                    ? "border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-foreground"
                    : "border-transparent text-muted-foreground hover:border-border hover:bg-accent hover:text-foreground"
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.name}
              </button>
            ))}
          </nav>

          <div className="my-4 border-t border-border" />

          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-2xl border border-transparent px-4 py-3 text-left text-sm font-medium text-rose-300 transition hover:border-rose-500/20 hover:bg-rose-500/10"
          >
            <LogOut className="h-4 w-4" />
            Выйти из аккаунта
          </button>
        </aside>

        <section className="glass-card p-6 md:p-8">
          <div className="grid gap-8">
            <div className="grid gap-5 md:grid-cols-2">
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Название базы отдыха</span>
                <input className="soft-input" defaultValue="Гостиный Дворъ" />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Юридическое лицо</span>
                <input className="soft-input" defaultValue="ООО Байкал Тур" />
              </label>
              <label className="space-y-2 md:col-span-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Адрес</span>
                <input className="soft-input" defaultValue="Республика Бурятия, с. Максимиха, ул. Байкальская, 15" />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Контактный телефон</span>
                <input className="soft-input" defaultValue="+7 (999) 000-00-00" />
              </label>
              <label className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Email для бронирований</span>
                <input className="soft-input" defaultValue="booking@gostiny-dvor.ru" />
              </label>
            </div>

            <div className="border-t border-border pt-8">
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">Правила проживания</h2>
              <div className="mt-5 grid gap-5 md:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Время заезда</span>
                  <select className="soft-input appearance-none">
                    <option>14:00</option>
                    <option>15:00</option>
                  </select>
                </label>
                <label className="space-y-2">
                  <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Время выезда</span>
                  <select className="soft-input appearance-none">
                    <option>12:00</option>
                    <option>11:00</option>
                  </select>
                </label>
              </div>

              <div className="mt-5 flex items-center justify-between rounded-3xl border border-border bg-background/65 px-5 py-4">
                <div>
                  <h3 className="text-sm font-medium text-foreground">Размещение с животными</h3>
                  <p className="mt-1 text-sm text-muted-foreground">Разрешить гостям приезжать с питомцами</p>
                </div>
                <div className="h-7 w-14 rounded-full bg-[#E5D3B3]/30 p-1">
                  <div className="ml-auto h-5 w-5 rounded-full bg-[#E5D3B3] shadow-lg shadow-[#E5D3B3]/20" />
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button type="button" className="brand-button">
                Сохранить изменения
              </button>
              <button type="button" className="soft-button">
                Отменить
              </button>
            </div>
          </div>
        </section>
      </div>
    </PageMotion>
  );
}
