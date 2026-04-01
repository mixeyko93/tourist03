import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { useTheme } from "next-themes";
import { clearCrmSession, getCrmSession } from "../../session";
import { crmPath } from "../../paths";

const adminTabs = [
  { label: "Базы и номера", path: "/admin/bases" },
  { label: "Пользователи", path: "/admin/users" },
  { label: "Учётные записи", path: "/admin/accounts" },
  { label: "Архив", path: "/admin/archive" },
];

export default function AdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const session = getCrmSession();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const loginPath = crmPath("/login");

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!session) {
    return <Navigate to={loginPath} replace state={{ from: location.pathname }} />;
  }

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-card/88 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-4 px-4 py-4 md:px-6 lg:px-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-muted-foreground">Tourist_03 Superadmin</p>
              <h1 className="text-lg font-semibold tracking-[-0.04em] text-foreground">Суперадмин. Администрирование CRM</h1>
              <p className="text-sm text-muted-foreground">Централизованное управление базами отдыха, пользователями и учётными записями управляющих.</p>
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
                <p className="text-sm font-medium text-foreground">{session.name}</p>
                <p className="text-xs text-muted-foreground">{session.email}</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  clearCrmSession();
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

      <main className="crm-ambient flex-1 px-4 py-5 md:px-6 md:py-6 lg:px-8">
        <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
