import { ArrowRight, LockKeyhole, Mail, Mountain, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { motion } from "motion/react";
import { getCrmSession, saveCrmSession } from "../session";
import { crmPath } from "../paths";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const session = getCrmSession();
  const homePath = crmPath("/calendar");

  if (session) {
    return <Navigate to={homePath} replace />;
  }

  const nextPath =
    typeof (location.state as { from?: unknown } | null)?.from === "string"
      ? (location.state as { from: string }).from
      : homePath;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    saveCrmSession({
      email,
      name: "Управляющий базы",
    });
    navigate(nextPath, { replace: true });
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-4 sm:py-8 lg:py-10">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-0 h-72 w-72 -translate-x-1/2 rounded-full bg-[#E5D3B3]/18 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-72 w-72 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="absolute left-0 top-1/3 h-64 w-64 rounded-full bg-emerald-500/10 blur-3xl" />
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card relative w-full max-w-5xl overflow-hidden">
        <div className="grid lg:min-h-[680px] lg:grid-cols-[1.08fr_0.92fr]">
          <section className="order-2 crm-ambient flex flex-col justify-between border-t border-border px-5 py-6 sm:px-6 lg:order-1 lg:border-t-0 lg:border-r lg:px-8 lg:py-10">
            <div className="space-y-8">
              <span className="inline-flex rounded-full border border-[#E5D3B3]/30 bg-[#E5D3B3]/10 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.26em] text-[#E5D3B3] sm:text-xs">
                Premium Control Room
              </span>

              <div className="space-y-4">
                <h1 className="max-w-xl text-3xl font-semibold tracking-[-0.06em] text-foreground sm:text-4xl md:text-5xl">
                  Управляйте бронированиями, загрузкой и сервисом базы в одном интерфейсе.
                </h1>
                <p className="max-w-lg text-base leading-7 text-muted-foreground">
                  Новый CRM-раздел для Tourist_03 объединяет календарь размещения, управление бронями, номерным
                  фондом, услугами и клиентской базой в одном потоке работы.
                </p>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
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
                {
                  icon: ArrowRight,
                  title: "Быстрый вход",
                  text: "Старт без лишних шагов: логин и сразу переход к управлению.",
                },
              ].map((item) => (
                <article key={item.title} className="rounded-3xl border border-border bg-card/55 p-4 backdrop-blur-lg">
                  <item.icon className="h-5 w-5 text-[#E5D3B3]" />
                  <h2 className="mt-5 text-sm font-semibold text-foreground">{item.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground sm:line-clamp-none">{item.text}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="order-1 flex items-center px-4 py-5 sm:px-6 sm:py-7 lg:order-2 lg:px-8">
            <div className="mx-auto w-full max-w-md">
              <div className="glass-card rounded-[2rem] p-5 sm:p-8">
                <div className="space-y-2 text-center">
                  <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#E5D3B3]">Tourist_03 CRM</p>
                  <h2 className="text-2xl font-semibold tracking-[-0.05em] text-foreground sm:text-3xl">Вход в систему</h2>
                  <p className="text-sm leading-6 text-muted-foreground">Войдите под своей учётной записью, чтобы открыть рабочее пространство CRM.</p>
                </div>

                <form onSubmit={handleSubmit} className="mt-8 space-y-4">
                  <label className="block space-y-2">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Email</span>
                    <div className="relative">
                      <Mail className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="email"
                        className="soft-input pl-12"
                        placeholder="email@company.ru"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
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
                        required
                      />
                    </div>
                  </label>

                  <button type="submit" className="brand-button w-full gap-2">
                    Войти в CRM
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
