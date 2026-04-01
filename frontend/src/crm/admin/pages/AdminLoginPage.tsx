import { ArrowRight, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { PageMotion } from "../../components/PageMotion";
import { crmPath } from "../../paths";
import { fetchSuperadminSession, loginSuperadminSession } from "../session";

type SessionState = "checking" | "ready" | "authenticated";

export default function AdminLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [sessionState, setSessionState] = useState<SessionState>("checking");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const homePath = crmPath("/admin/bases");
  const nextPath =
    typeof (location.state as { from?: unknown } | null)?.from === "string"
      ? (location.state as { from: string }).from
      : homePath;

  useEffect(() => {
    const controller = new AbortController();
    fetchSuperadminSession(controller.signal)
      .then((session) => {
        setSessionState(session.authenticated ? "authenticated" : "ready");
      })
      .catch(() => {
        setSessionState("ready");
      });
    return () => controller.abort();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const response = await loginSuperadminSession({ login, password });
      if (!response.authenticated) {
        throw new Error("Нет доступа");
      }
      navigate(nextPath, { replace: true });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Не удалось выполнить вход");
    } finally {
      setPending(false);
    }
  }

  if (sessionState === "authenticated") {
    return <Navigate to={nextPath} replace />;
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-4 sm:py-8 lg:py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-0 h-72 w-72 -translate-x-1/2 rounded-full bg-[#E5D3B3]/18 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-72 w-72 rounded-full bg-blue-500/12 blur-3xl" />
        <div className="absolute left-0 top-1/3 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
      </div>

      <PageMotion className="glass-card relative w-full max-w-6xl overflow-hidden">
        <div className="grid lg:min-h-[700px] lg:grid-cols-[1.05fr_0.95fr]">
          <section className="crm-ambient order-2 flex flex-col justify-between border-t border-border px-5 py-6 sm:px-6 lg:order-1 lg:border-r lg:border-t-0 lg:px-8 lg:py-10">
            <div className="space-y-8">
              <span className="inline-flex rounded-full border border-[#E5D3B3]/30 bg-[#E5D3B3]/10 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.26em] text-[#E5D3B3] sm:text-xs">
                Superadmin Control
              </span>

              <div className="space-y-4">
                <h1 className="max-w-xl text-3xl font-semibold tracking-[-0.06em] text-foreground sm:text-4xl md:text-5xl">
                  Централизованный доступ к базам, пользователям и учётным записям Tourist_03.
                </h1>
                <p className="max-w-lg text-base leading-7 text-muted-foreground">
                  Рабочее пространство суперадмина объединяет модерацию объектов, аудит действий пользователей,
                  управление управляющими и архивом в одном интерфейсе.
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {[
                {
                  icon: ShieldCheck,
                  title: "Контур доступа",
                  text: "Вход защищён служебными реквизитами суперадминистратора без лишних шагов.",
                },
                {
                  icon: UserRound,
                  title: "Управление людьми",
                  text: "Карточки пользователей, история действий и учётные записи управляющих в одном месте.",
                },
                {
                  icon: LockKeyhole,
                  title: "Быстрый контроль",
                  text: "После входа открывается справочник баз и дальнейшая работа без лишних переключений.",
                },
              ].map((item) => (
                <article key={item.title} className="rounded-3xl border border-border bg-card/55 p-4 backdrop-blur-lg">
                  <item.icon className="h-5 w-5 text-[#E5D3B3]" />
                  <h2 className="mt-5 text-sm font-semibold text-foreground">{item.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.text}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="order-1 flex items-center px-4 py-5 sm:px-6 sm:py-7 lg:order-2 lg:px-8">
            <div className="mx-auto w-full max-w-md">
              <div className="glass-card rounded-[2rem] p-5 sm:p-8">
                <div className="space-y-2 text-center">
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#E5D3B3]">Tourist_03 Superadmin</p>
                  <h2 className="text-2xl font-semibold tracking-[-0.05em] text-foreground sm:text-3xl">Вход в систему</h2>
                  <p className="text-sm leading-6 text-muted-foreground">
                    Авторизуйтесь по логину и паролю, чтобы открыть панель суперадмина.
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="mt-8 space-y-4">
                  <label className="block space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Логин</span>
                    <div className="relative">
                      <UserRound className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                      <input
                        id="superadmin-login"
                        type="text"
                        autoComplete="username"
                        className="soft-input pl-12"
                        placeholder="Введите логин"
                        value={login}
                        onChange={(event) => setLogin(event.target.value)}
                        required
                      />
                    </div>
                  </label>

                  <label className="block space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Пароль</span>
                    <div className="relative">
                      <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                      <input
                        id="superadmin-password"
                        type="password"
                        autoComplete="current-password"
                        className="soft-input pl-12"
                        placeholder="Введите пароль"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        required
                      />
                    </div>
                  </label>

                  {error ? (
                    <div className="rounded-2xl border border-destructive/25 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                      {error}
                    </div>
                  ) : null}

                  <button
                    id="superadmin-submit"
                    type="submit"
                    className="brand-button w-full gap-2"
                    disabled={pending || sessionState === "checking"}
                  >
                    {pending || sessionState === "checking" ? "Проверка доступа..." : "Войти в superadmin"}
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </form>
              </div>
            </div>
          </section>
        </div>
      </PageMotion>
    </div>
  );
}
