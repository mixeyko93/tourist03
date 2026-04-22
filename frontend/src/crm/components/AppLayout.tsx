import { BellRing, LogOut, Menu, MoonStar, SunMedium, UserCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { useTheme } from "next-themes";
import { fetchCrmEventCenterSummary, fetchCrmSession, logoutCrmSession, type CrmSession } from "../session";
import { crmPath } from "../paths";
import { PageLoadingState } from "./PageLoadingState";
import { useDocumentTitle } from "./useDocumentTitle";

const navItems = [
  { label: "Календарь", path: "/calendar" },
  { label: "Смены", path: "/shifts" },
  { label: "События", path: "/events" },
  { label: "Согласования", path: "/approvals" },
  { label: "Сводка", path: "/dashboard" },
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
  const [session, setSession] = useState<CrmSession | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [eventNewCount, setEventNewCount] = useState(0);
  const [isRouteTransitioning, setIsRouteTransitioning] = useState(false);
  const calendarPath = crmPath("/calendar");
  const activeNavItem = navItems.find((item) => location.pathname === crmPath(item.path));

  useDocumentTitle(activeNavItem ? `${activeNavItem.label} — Tourist03 CRM` : "Tourist03 CRM");

  useEffect(() => {
    setMounted(true);
    if (typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches) {
      setSidebarOpen(true);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const syncShellOffset = () => {
      const isDesktop = window.matchMedia("(min-width: 1024px)").matches;
      document.body.style.setProperty("--crm-shell-offset", isDesktop && sidebarOpen ? "224px" : "0px");
    };

    syncShellOffset();
    window.addEventListener("resize", syncShellOffset);

    return () => {
      window.removeEventListener("resize", syncShellOffset);
      document.body.style.removeProperty("--crm-shell-offset");
    };
  }, [sidebarOpen]);

  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 1023px)").matches) {
      setSidebarOpen(false);
    }
  }, [location.pathname]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    setIsRouteTransitioning(true);
    const timeoutId = window.setTimeout(() => {
      setIsRouteTransitioning(false);
    }, 700);
    return () => window.clearTimeout(timeoutId);
  }, [location.pathname, location.search]);

  useEffect(() => {
    const controller = new AbortController();
    setIsAuthLoading(true);
    setAuthError("");

    fetchCrmSession(controller.signal)
      .then((nextSession) => {
        setSession(nextSession);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setAuthError(error instanceof Error ? error.message : "Не удалось загрузить профиль CRM");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsAuthLoading(false);
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!session) {
      setEventNewCount(0);
      return;
    }

    let active = true;
    const controller = new AbortController();

    const loadSummary = async () => {
      try {
        const summary = await fetchCrmEventCenterSummary(undefined, controller.signal);
        if (active) {
          setEventNewCount(Number(summary.new_count || 0));
        }
      } catch {
        if (active) {
          setEventNewCount(0);
        }
      }
    };

    void loadSummary();

    const handleRefresh = () => {
      void loadSummary();
    };

    if (typeof window !== "undefined") {
      window.addEventListener("crm-events-changed", handleRefresh);
    }

    return () => {
      active = false;
      controller.abort();
      if (typeof window !== "undefined") {
        window.removeEventListener("crm-events-changed", handleRefresh);
      }
    };
  }, [session, location.pathname]);

  const loginPath = crmPath("/login");
  const navLinks = navItems.map((item) => ({
    ...item,
    to: crmPath(item.path),
  }));

  const handleLogout = async () => {
    try {
      setIsLoggingOut(true);
      await logoutCrmSession();
    } catch {
      // Даже при сетевой ошибке локально выходим из защищённого контура.
    } finally {
      setSession(null);
      navigate(loginPath, { replace: true });
    }
  };

  if (isAuthLoading) {
    return (
      <div className="crm-ambient flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
        <div className="glass-card w-full max-w-2xl rounded-3xl p-8">
          <PageLoadingState blocks={2} columnsClassName="md:grid-cols-2" blockHeightClassName="h-40" />
        </div>
      </div>
    );
  }

  if (authError) {
    return (
      <div className="crm-ambient flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
        <div className="glass-card w-full max-w-md rounded-3xl p-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#E5D3B3]">Tourist_03 CRM</p>
          <h1 className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-foreground">CRM временно недоступен</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{authError}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="brand-button mt-6 w-full justify-center"
          >
            Повторить попытку
          </button>
        </div>
      </div>
    );
  }

  if (!session) {
    return <Navigate to={loginPath} replace state={{ from: `${location.pathname}${location.search}` }} />;
  }

  const navContent = (
    <nav className="flex min-h-0 flex-col gap-2 overflow-y-auto pr-1 pb-52">
      {navLinks.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === calendarPath}
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

  const sidebarFooter = (
    <div className="absolute inset-x-3 bottom-4 space-y-3 border-t border-border/80 pt-4">
      <div className="rounded-[1.65rem] border border-border bg-background/72 px-4 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[#E5D3B3]/25 bg-[#E5D3B3]/10 text-[#E5D3B3]">
            <UserCircle2 className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-base font-semibold text-foreground">{session.name}</p>
          </div>
        </div>
      </div>

      <button
        type="button"
        disabled={isLoggingOut}
        onClick={handleLogout}
        className="flex w-full items-center justify-center gap-2 rounded-[1.65rem] border border-border bg-background/72 px-4 py-3 text-sm font-semibold text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E5D3B3]/60"
      >
        <LogOut className="h-4 w-4" />
        {isLoggingOut ? "Выходим..." : "Выйти"}
      </button>
    </div>
  );

  return (
    <div className="flex h-screen min-h-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="fixed inset-x-0 top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border bg-card/92 px-4 backdrop-blur-xl md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-background/70 text-muted-foreground transition hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E5D3B3]/60"
            aria-label="Показать или скрыть меню"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#E5D3B3]">Tourist_03 CRM</p>
            <p className="truncate text-sm text-muted-foreground">Панель управления базой отдыха</p>
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-3">
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

          <NavLink
            to={crmPath("/events")}
            className={({ isActive }) =>
              [
                "relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#E5D3B3]/60",
                isActive
                  ? "border-[#E5D3B3]/30 bg-[#E5D3B3]/10 text-foreground"
                  : "border-border bg-background/70 text-muted-foreground hover:bg-accent hover:text-foreground",
              ].join(" ")
            }
            aria-label="Открыть центр событий"
          >
            <BellRing className="h-5 w-5" />
            {eventNewCount > 0 ? (
              <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white">
                {eventNewCount > 99 ? "99+" : eventNewCount}
              </span>
            ) : null}
          </NavLink>

        </div>
        {isRouteTransitioning ? (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px overflow-hidden">
            <div className="crm-route-loader h-full w-48 rounded-full" />
          </div>
        ) : null}
      </header>

      <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden pt-16">
        <div className={`relative hidden shrink-0 transition-[width] duration-300 lg:block ${sidebarOpen ? "w-56" : "w-0"}`}>
          <aside
            className={`absolute inset-y-0 left-0 h-full w-56 overflow-hidden border-r border-border bg-card/80 px-3 py-4 backdrop-blur-xl transition-transform duration-300 lg:fixed lg:bottom-0 lg:left-0 lg:top-16 lg:z-10 lg:h-[calc(100dvh-4rem)] ${
              sidebarOpen ? "translate-x-0" : "-translate-x-full"
            }`}
            style={{ contain: "layout paint" }}
          >
            {navContent}
            {sidebarFooter}
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
          className={`fixed inset-y-16 left-0 z-30 h-[calc(100dvh-4rem)] w-[86vw] max-w-80 overflow-hidden border-r border-border bg-card/92 px-3 py-4 backdrop-blur-xl transition-transform duration-300 lg:hidden ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          {navContent}
          {sidebarFooter}
        </aside>

        <main className="crm-ambient relative min-w-0 flex-1 overflow-y-auto px-4 py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] md:px-6 md:py-6 lg:px-8">
          <div className="mx-auto flex min-h-full min-w-0 w-full max-w-[2400px] flex-col gap-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
