import { Link2, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { useTheme } from "next-themes";
import { crmPath } from "../../paths";
import { fetchSuperadminSession, issueSuperadminTelegramLink, logoutSuperadminSession, type SuperadminSessionResponse } from "../session";
import { useDocumentTitle } from "../../components/useDocumentTitle";
import { AdminModal } from "./AdminModal";

const baseAdminTabs = [
  { label: "Базы и номера", path: "/admin/bases" },
  { label: "Пользователи", path: "/admin/users" },
  { label: "Учётные записи", path: "/admin/accounts" },
  { label: "Модерация", path: "/admin/moderation" },
  { label: "Архив", path: "/admin/archive" },
];

const rootOnlyTabs = [
  { label: "Суперадмины", path: "/admin/superadmins" },
  { label: "Системный журнал", path: "/admin/audit" },
];

export default function AdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [authState, setAuthState] = useState<"loading" | "authenticated" | "unauthenticated">("loading");
  const [authError, setAuthError] = useState("");
  const [session, setSession] = useState<SuperadminSessionResponse | null>(null);
  const [telegramLinkInfo, setTelegramLinkInfo] = useState<null | { code: string; command: string; deep_link: string | null }>(null);
  const [telegramError, setTelegramError] = useState("");
  const [isIssuingTelegramCode, setIsIssuingTelegramCode] = useState(false);
  const loginPath = crmPath("/admin/login");
  const isRoot = Boolean(session?.account?.is_root);
  const adminTabs = isRoot ? [...baseAdminTabs, ...rootOnlyTabs] : baseAdminTabs;
  const activeTab = adminTabs.find((item) => location.pathname === crmPath(item.path));

  useDocumentTitle(activeTab ? `${activeTab.label} — Tourist03 Superadmin` : "Tourist03 Superadmin");

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchSuperadminSession(controller.signal)
      .then((nextSession) => {
        setSession(nextSession);
        setAuthState(nextSession.authenticated ? "authenticated" : "unauthenticated");
      })
      .catch(() => {
        setAuthError("Не удалось проверить superadmin-сессию");
        setAuthState("unauthenticated");
      });
    return () => controller.abort();
  }, []);

  if (authState === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4 text-center text-sm text-muted-foreground">
        Проверяем доступ суперадмина...
      </div>
    );
  }

  if (authState !== "authenticated") {
    return <Navigate to={loginPath} replace state={{ from: location.pathname }} />;
  }

  if (!isRoot && rootOnlyTabs.some((item) => location.pathname === crmPath(item.path))) {
    return <Navigate to={crmPath("/admin/bases")} replace />;
  }

  async function handleIssueTelegramLink() {
    try {
      setIsIssuingTelegramCode(true);
      setTelegramError("");
      const response = await issueSuperadminTelegramLink();
      setTelegramLinkInfo(response);
      setSession((current) =>
        current
          ? {
              ...current,
              account: current.account
                ? {
                    ...current.account,
                    has_telegram_link: current.account.has_telegram_link || false,
                  }
                : current.account,
            }
          : current,
      );
    } catch (error: unknown) {
      setTelegramError(error instanceof Error ? error.message : "Не удалось выпустить код привязки Telegram");
    } finally {
      setIsIssuingTelegramCode(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-card/88 backdrop-blur-xl">
        <div className="mx-auto flex min-w-0 max-w-[2100px] flex-col gap-4 px-4 py-4 md:px-6 lg:px-8">
          <div className="flex min-w-0 flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0 space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-muted-foreground">Tourist_03 Superadmin</p>
              <h1 className="text-lg font-semibold tracking-[-0.04em] text-foreground">Суперадмин. Администрирование CRM</h1>
              <p className="text-sm text-muted-foreground">Централизованное управление базами отдыха, пользователями, управляющими и superadmin-учётками.</p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {mounted ? (
                <button
                  type="button"
                  onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                  className="admin-icon-button"
                  aria-label="Переключить тему"
                >
                  {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                </button>
              ) : null}
              <div className="hidden rounded-xl border border-border bg-background/70 px-3 py-2 md:block">
                <p className="text-sm font-medium text-foreground">
                  {session?.account?.display_name || session?.account?.login || "Суперадминистратор"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {authError || (session?.account?.is_root ? "Root-доступ ко всей системе" : "Доступ к панели суперадмина")}
                </p>
              </div>
              <button type="button" className="admin-button gap-2" onClick={handleIssueTelegramLink} disabled={isIssuingTelegramCode}>
                <Link2 className="h-4 w-4" />
                {session?.account?.has_telegram_link ? "Обновить привязку Telegram" : "Подключить Telegram"}
              </button>
              <button
                id="superadmin-logout-btn"
                type="button"
                onClick={async () => {
                  await logoutSuperadminSession().catch(() => null);
                  navigate(loginPath, { replace: true });
                }}
                className="admin-button"
              >
                Выйти
              </button>
            </div>
          </div>

          <nav className="-mx-1 overflow-x-auto pb-1">
            <div className="flex min-w-max items-center gap-2 px-1">
              {adminTabs.map((item) => (
                <NavLink
                  key={item.path}
                  to={crmPath(item.path)}
                  className={({ isActive }) =>
                    [
                      "inline-flex rounded-xl border px-4 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "border-blue-500 bg-blue-500 text-white shadow-sm"
                        : "border-border bg-background/65 text-muted-foreground hover:bg-accent hover:text-foreground",
                    ].join(" ")
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </nav>
        </div>
      </header>

      <main className="crm-ambient min-w-0 flex-1 px-4 py-5 md:px-6 md:py-6 lg:px-8">
        <div className="mx-auto flex min-w-0 w-full max-w-[2100px] flex-col gap-6">
          <Outlet />
        </div>
      </main>

      <AdminModal
        open={Boolean(telegramLinkInfo) || Boolean(telegramError)}
        title="Подключение Telegram"
        onClose={() => {
          setTelegramLinkInfo(null);
          setTelegramError("");
        }}
      >
        <div className="space-y-4">
          {telegramError ? <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{telegramError}</div> : null}
          {telegramLinkInfo ? (
            <>
              <div className="rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm text-muted-foreground">
                Код привязки: <span className="font-semibold text-foreground">{telegramLinkInfo.code}</span>
              </div>
              <div className="rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm text-muted-foreground">
                Команда для бота: <span className="font-semibold text-foreground">{telegramLinkInfo.command}</span>
              </div>
              {telegramLinkInfo.deep_link ? (
                <a href={telegramLinkInfo.deep_link} target="_blank" rel="noreferrer" className="admin-primary-button inline-flex w-full justify-center">
                  Открыть бот уведомлений CRM
                </a>
              ) : null}
            </>
          ) : null}
        </div>
      </AdminModal>
    </div>
  );
}
