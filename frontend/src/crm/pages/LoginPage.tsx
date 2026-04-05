import { ArrowRight, LockKeyhole, Mail, Moon, Mountain, ShieldCheck, Sun } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";
import { motion } from "motion/react";
import { useTheme } from "next-themes";
import { fetchCrmSession, loginCrmSession } from "../session";
import { crmPath } from "../paths";
import { useDocumentTitle } from "../components/useDocumentTitle";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isThemeMounted, setIsThemeMounted] = useState(false);
  const { theme, setTheme } = useTheme();
  const homePath = crmPath("/calendar");

  useDocumentTitle("Tourist03 CRM — Вход");

  const nextPath =
    typeof (location.state as { from?: unknown } | null)?.from === "string"
      ? (location.state as { from: string }).from
      : homePath;

  useEffect(() => {
    setIsThemeMounted(true);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchCrmSession(controller.signal)
      .then((session) => {
        if (session) {
          navigate(homePath, { replace: true });
        }
      })
      .catch(() => {
        // Ошибку проверки сессии здесь не показываем, чтобы не блокировать форму входа.
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsCheckingSession(false);
        }
      });

    return () => controller.abort();
  }, [homePath, navigate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setIsSubmitting(true);
      setErrorMessage("");
      await loginCrmSession({
        email,
        password,
      });
      navigate(nextPath, { replace: true });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось открыть рабочее пространство");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-4 sm:py-8 lg:py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-0 h-72 w-72 -translate-x-1/2 rounded-full bg-[#E5D3B3]/18 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-72 w-72 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="absolute left-0 top-1/3 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card relative w-full max-w-5xl overflow-hidden">
        <div className="absolute right-4 top-4 z-20 sm:right-5 sm:top-5">
          {isThemeMounted ? (
            <button
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="admin-icon-button"
              aria-label="Переключить тему"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
          ) : null}
        </div>

        <div className="grid lg:min-h-[680px] lg:grid-cols-[1.08fr_0.92fr]">
          <section className="order-2 crm-ambient flex flex-col gap-8 border-t border-border px-5 py-6 sm:px-6 sm:py-7 lg:order-1 lg:border-t-0 lg:border-r lg:px-8 lg:py-10">
            <div className="space-y-6 sm:space-y-7">
              <span className="crm-gold-badge inline-flex rounded-full border px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.26em] sm:text-xs">
                Premium Control Room
              </span>

              <div className="space-y-5">
                <h1 className="max-w-xl text-3xl font-semibold leading-[0.92] tracking-[-0.065em] text-foreground sm:text-4xl md:text-[4rem]">
                  Управляйте бронированиями, загрузкой и сервисом базы в одном интерфейсе.
                </h1>
                <p className="max-w-xl text-base leading-7 text-muted-foreground">
                  Новый CRM-раздел для Tourist_03 объединяет календарь размещения, управление бронями, номерным
                  фондом, услугами и клиентской базой в одном потоке работы.
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {[
                {
                  icon: Mountain,
                  title: "Живая загрузка",
                  text: "Сводка по базе с моментальным обзором занятости и выручки.",
                },
                {
                  icon: ShieldCheck,
                  title: "Единый контроль",
                  text: "Настройки, сотрудники и статусы оплат в одном сценарии.",
                },
              ].map((item) => (
                <article key={item.title} className="flex h-full flex-col rounded-3xl border border-border bg-card/55 p-5 backdrop-blur-lg">
                  <item.icon className="crm-gold-tone h-5 w-5" />
                  <h2 className="mt-6 text-sm font-semibold text-foreground">{item.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground sm:line-clamp-none">{item.text}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="order-1 flex items-center px-4 py-5 sm:px-6 sm:py-7 lg:order-2 lg:px-8">
            <div className="mx-auto w-full max-w-md">
              <div className="glass-card rounded-[2rem] p-5 sm:p-8">
                <div className="space-y-2 text-center">
                  <p className="crm-gold-tone text-xs font-semibold uppercase tracking-[0.28em]">Tourist_03 CRM</p>
                  <h2 className="text-2xl font-semibold tracking-[-0.05em] text-foreground sm:text-3xl">Вход в систему</h2>
                  <p className="text-sm leading-6 text-muted-foreground">Войдите под своей учётной записью, чтобы открыть рабочее пространство CRM.</p>
                </div>

                <form onSubmit={handleSubmit} className="mt-8 space-y-4">
                  {errorMessage ? (
                    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                      {errorMessage}
                    </div>
                  ) : null}

                  <label className="block space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Эл. почта</span>
                    <div className="relative">
                      <Mail className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="email"
                        className="soft-input pl-12"
                        placeholder="name@company.ru"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        disabled={isSubmitting || isCheckingSession}
                        required
                      />
                    </div>
                  </label>

                  <label className="block space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Пароль</span>
                    <div className="relative">
                      <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="password"
                        className="soft-input pl-12"
                        placeholder="Введите пароль"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        disabled={isSubmitting || isCheckingSession}
                        required
                      />
                    </div>
                  </label>

                  <button type="submit" disabled={isSubmitting || isCheckingSession} className="brand-button w-full gap-2 disabled:cursor-not-allowed disabled:opacity-60">
                    {isCheckingSession ? "Проверяем доступ..." : isSubmitting ? "Открываем CRM..." : "Войти в CRM"}
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </form>
              </div>
            </div>
          </section>
        </div>
      </motion.div>
    </div>
  );
}
