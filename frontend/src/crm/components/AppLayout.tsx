import { Menu, MoonStar, SunMedium, UserCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { useTheme } from "next-themes";
import { clearCrmSession, getCrmSession } from "../session";
import { crmPath } from "../paths";

const navItems = [
  { label: "Сводка", path: "/dashboard" },
  { label: "Календарь", path: "/calendar" },
  { label: "Брони", path: "/bookings" },
  { label: "Номера и цены", path: "/rooms" },
  { label: "Гости", path: "/guests" },
  { label: "Услуги", path: "/services" },
  { label: "Настройки", path: "/settings" },
  { label: "Карта", path: "/map" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const session = getCrmSession();

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches) {
      setSidebarOpen(true);
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 1023px)").matches) {
      setSidebarOpen(false);
    }
  }, [location.pathname]);

  const dashboardPath = crmPath("/dashboard");
  const loginPath = crmPath("/login");
  const navLinks = navItems.map((item) => ({
    ...item,
    to: crmPath(item.path),
  }));

  if (!session) {
    return <Navigate to={loginPath} replace state={{ from: location.pathname }} />;
  }

  const navContent = (
    <nav className="flex flex-1 flex-col gap-2">
      {navLinks.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === dashboardPath}
          className={({ isActive }) =>
            [
              "rounded-2xl border px-4 py-3 text-sm font-medium transition",
              isActive
                ? "border-[#E5D3B3]/30 bg-[#E5D3B3]/10 text-foreground shadow-sm"
                : "border-transparent text-muted-foreground hover:border-border hover:bg-accent hover:text-foreground",
            ].join(" ")
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="relative z-20 flex h-16 shrink-0 items-center justify-between border-b border-border bg-card/85 px-4 backdrop-blur-xl md:px-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-background/70 text-muted-foreground transition hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E5D3B3]/60"
            aria-label="Показать или скрыть меню"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#E5D3B3]">Tourist_03 CRM</p>
            <p className="text-sm text-muted-foreground">Панель управления базой отдыха</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {mounted ? (
            <button
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-background/70 text-muted-foreground transition hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E5D3B3]/60"
              aria-label="Переключить тему"
            >
              {theme === "dark" ? <SunMedium className="h-5 w-5" /> : <MoonStar className="h-5 w-5" />}
            </button>
          ) : null}

          <div className="hidden items-center gap-3 rounded-2xl border border-border bg-background/70 px-3 py-2 sm:flex">
            <UserCircle2 className="h-5 w-5 text-[#E5D3B3]" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{session.name}</p>
              <p className="truncate text-xs text-muted-foreground">{session.email}</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => {
              clearCrmSession();
              navigate(loginPath, { replace: true });
            }}
            className="rounded-2xl border border-border bg-background/70 px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E5D3B3]/60"
          >
            Выйти
          </button>
        </div>
      </header>

      <div className="relative flex flex-1 overflow-hidden">
        <div className={`relative hidden shrink-0 transition-[width] duration-300 lg:block ${sidebarOpen ? "w-56" : "w-0"}`}>
          <aside
            className={`absolute inset-y-0 left-0 flex h-full w-56 flex-col border-r border-border bg-card/80 px-3 py-4 backdrop-blur-xl transition-transform duration-300 ${
              sidebarOpen ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            {navContent}
          </aside>
        </div>

        {sidebarOpen ? (
          <button
            type="button"
            className="fixed inset-0 top-16 z-20 bg-black/45 backdrop-blur-[2px] lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-label="Закрыть меню"
          />
        ) : null}

        <aside
          className={`fixed inset-y-16 left-0 z-30 flex h-[calc(100dvh-4rem)] w-[86vw] max-w-80 flex-col border-r border-border bg-card/92 px-3 py-4 backdrop-blur-xl transition-transform duration-300 lg:hidden ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {navContent}
        </aside>

        <main className="crm-ambient relative flex-1 overflow-y-auto px-4 py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] md:px-6 md:py-6 lg:px-8">
          <div className="mx-auto flex min-h-full w-full max-w-[1600px] flex-col gap-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
