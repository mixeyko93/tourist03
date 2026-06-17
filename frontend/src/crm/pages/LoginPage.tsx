import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Moon,
  Mountain,
  RotateCcw,
  Save,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sun,
  UserRound,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router";
import { motion } from "motion/react";
import { useTheme } from "next-themes";
import { crmPath } from "../paths";
import { useDocumentTitle } from "../components/useDocumentTitle";
import { fetchCrmSession, fetchPublicUiOverride, loginCrmSession, saveCrmUiOverride } from "../session";

type LoginFeatureCard = {
  title: string;
  text: string;
};

type LoginPageConfig = {
  badgeText: string;
  heroTitle: string;
  heroText: string;
  loginEyebrow: string;
  loginTitle: string;
  loginText: string;
  submitText: string;
  shellMaxWidth: number;
  shellMinHeight: number;
  shellRadius: number;
  sectionPadding: number;
  leftColumnGap: number;
  heroFontSize: number;
  heroMaxWidth: number;
  bodyMaxWidth: number;
  featureCardPadding: number;
  featureCardRadius: number;
  loginCardWidth: number;
  loginCardPadding: number;
  loginCardRadius: number;
  loginCardGap: number;
  featureCards: LoginFeatureCard[];
};

const featureIcons = [Mountain, ShieldCheck] as const;

const loginPageDefaults: LoginPageConfig = {
  badgeText: "Туристика CRM",
  heroTitle: "CRM управляющего",
  heroText:
    "Рабочее пространство для управления базами, бронями, номерами, услугами и гостями.",
  loginEyebrow: "Рабочий доступ",
  loginTitle: "CRM управляющего",
  loginText: "Войдите, чтобы управлять базами, бронями и номерами",
  submitText: "Войти",
  shellMaxWidth: 1166,
  shellMinHeight: 504,
  shellRadius: 20,
  sectionPadding: 40,
  leftColumnGap: 40,
  heroFontSize: 28,
  heroMaxWidth: 840,
  bodyMaxWidth: 864,
  featureCardPadding: 18,
  featureCardRadius: 20,
  loginCardWidth: 450,
  loginCardPadding: 37,
  loginCardRadius: 20,
  loginCardGap: 11,
  featureCards: [
    {
      title: "Живая загрузка",
      text: "Сводка по базе с моментальным обзором занятости и выручки.",
    },
    {
      title: "Единый контроль",
      text: "Настройки, сотрудники и статусы оплат в одном сценарии.",
    },
  ],
};

function normalizeText(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback;
}

function normalizeInteger(value: unknown, fallback: number, min: number, max: number) {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function normalizeFeatureCards(value: unknown): LoginFeatureCard[] {
  const source = Array.isArray(value) ? value : [];
  return loginPageDefaults.featureCards.map((fallback, index) => {
    const raw = source[index];
    if (!raw || typeof raw !== "object") {
      return fallback;
    }
    const item = raw as Record<string, unknown>;
    return {
      title: normalizeText(item.title, fallback.title),
      text: normalizeText(item.text, fallback.text),
    };
  });
}

function buildLoginPageConfig(value: Record<string, unknown> | null | undefined): LoginPageConfig {
  const source = value || {};
  return {
    badgeText: normalizeText(source.badgeText, loginPageDefaults.badgeText),
    heroTitle: normalizeText(source.heroTitle, loginPageDefaults.heroTitle),
    heroText: normalizeText(source.heroText, loginPageDefaults.heroText),
    loginEyebrow: normalizeText(source.loginEyebrow, loginPageDefaults.loginEyebrow),
    loginTitle: normalizeText(source.loginTitle, loginPageDefaults.loginTitle),
    loginText: normalizeText(source.loginText, loginPageDefaults.loginText),
    submitText: normalizeText(source.submitText, loginPageDefaults.submitText),
    shellMaxWidth: normalizeInteger(source.shellMaxWidth, loginPageDefaults.shellMaxWidth, 720, 1800),
    shellMinHeight: normalizeInteger(source.shellMinHeight, loginPageDefaults.shellMinHeight, 420, 1200),
    shellRadius: normalizeInteger(source.shellRadius, loginPageDefaults.shellRadius, 12, 72),
    sectionPadding: normalizeInteger(source.sectionPadding, loginPageDefaults.sectionPadding, 8, 72),
    leftColumnGap: normalizeInteger(source.leftColumnGap, loginPageDefaults.leftColumnGap, 8, 72),
    heroFontSize: normalizeInteger(source.heroFontSize, loginPageDefaults.heroFontSize, 28, 140),
    heroMaxWidth: normalizeInteger(source.heroMaxWidth, loginPageDefaults.heroMaxWidth, 240, 900),
    bodyMaxWidth: normalizeInteger(source.bodyMaxWidth, loginPageDefaults.bodyMaxWidth, 220, 900),
    featureCardPadding: normalizeInteger(source.featureCardPadding, loginPageDefaults.featureCardPadding, 8, 48),
    featureCardRadius: normalizeInteger(source.featureCardRadius, loginPageDefaults.featureCardRadius, 12, 40),
    loginCardWidth: normalizeInteger(source.loginCardWidth, loginPageDefaults.loginCardWidth, 260, 560),
    loginCardPadding: normalizeInteger(source.loginCardPadding, loginPageDefaults.loginCardPadding, 12, 52),
    loginCardRadius: normalizeInteger(source.loginCardRadius, loginPageDefaults.loginCardRadius, 12, 48),
    loginCardGap: normalizeInteger(source.loginCardGap, loginPageDefaults.loginCardGap, 4, 36),
    featureCards: normalizeFeatureCards(source.featureCards),
  };
}

function serializeLoginPageConfig(config: LoginPageConfig): Record<string, unknown> {
  return {
    badgeText: config.badgeText,
    heroTitle: config.heroTitle,
    heroText: config.heroText,
    loginEyebrow: config.loginEyebrow,
    loginTitle: config.loginTitle,
    loginText: config.loginText,
    submitText: config.submitText,
    shellMaxWidth: config.shellMaxWidth,
    shellMinHeight: config.shellMinHeight,
    shellRadius: config.shellRadius,
    sectionPadding: config.sectionPadding,
    leftColumnGap: config.leftColumnGap,
    heroFontSize: config.heroFontSize,
    heroMaxWidth: config.heroMaxWidth,
    bodyMaxWidth: config.bodyMaxWidth,
    featureCardPadding: config.featureCardPadding,
    featureCardRadius: config.featureCardRadius,
    loginCardWidth: config.loginCardWidth,
    loginCardPadding: config.loginCardPadding,
    loginCardRadius: config.loginCardRadius,
    loginCardGap: config.loginCardGap,
    featureCards: config.featureCards.map((item) => ({
      title: item.title,
      text: item.text,
    })),
  };
}

function parseNumberInput(rawValue: string, fallback: number, min: number, max: number) {
  return normalizeInteger(rawValue ? Number(rawValue) : fallback, fallback, min, max);
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const isEditMode = searchParams.get("edit") === "1";
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [isThemeMounted, setIsThemeMounted] = useState(false);
  const [pageConfig, setPageConfig] = useState<LoginPageConfig>(loginPageDefaults);
  const [isLoadingOverrides, setIsLoadingOverrides] = useState(true);
  const [isSavingOverrides, setIsSavingOverrides] = useState(false);
  const [editorMessage, setEditorMessage] = useState("");
  const [editorError, setEditorError] = useState("");
  const [isEditorOpen, setIsEditorOpen] = useState(isEditMode);
  const [editorSessionLabel, setEditorSessionLabel] = useState("");
  const { theme, setTheme } = useTheme();
  const homePath = crmPath("/calendar");

  useDocumentTitle("Туристика CRM — Вход");

  const nextPath =
    typeof (location.state as { from?: unknown } | null)?.from === "string"
      ? (location.state as { from: string }).from
      : homePath;

  useEffect(() => {
    setIsThemeMounted(true);
  }, []);

  useEffect(() => {
    setIsEditorOpen(isEditMode);
  }, [isEditMode]);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoadingOverrides(true);
    fetchPublicUiOverride("crm_login_page", controller.signal)
      .then((payload) => {
        setPageConfig(buildLoginPageConfig(payload.payload));
      })
      .catch(() => {
        setPageConfig(loginPageDefaults);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingOverrides(false);
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchCrmSession(controller.signal)
      .then((session) => {
        setEditorSessionLabel(session ? "CRM" : "");
        if (session && !isEditMode) {
          navigate(homePath, { replace: true });
        }
      })
      .catch(() => {
        setEditorSessionLabel("");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsCheckingSession(false);
        }
      });

    return () => controller.abort();
  }, [homePath, isEditMode, navigate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setIsSubmitting(true);
      setErrorMessage("");
      await loginCrmSession({
        login,
        password,
      });
      sessionStorage.removeItem("tg_onboarding_dismissed");
      navigate(nextPath, { replace: true });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось открыть рабочее пространство");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSaveOverrides() {
    try {
      setIsSavingOverrides(true);
      setEditorError("");
      setEditorMessage("");
      await saveCrmUiOverride("crm_login_page", serializeLoginPageConfig(pageConfig));
      setEditorMessage("Правки страницы сохранены на сервере.");
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Не удалось сохранить правки");
    } finally {
      setIsSavingOverrides(false);
    }
  }

  function updateFeatureCard(index: number, field: keyof LoginFeatureCard, value: string) {
    setPageConfig((current) => ({
      ...current,
      featureCards: current.featureCards.map((item, itemIndex) =>
        itemIndex === index
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    }));
  }

  const editorNotice = editorSessionLabel
    ? `Правки будут сохраняться по активной сессии: ${editorSessionLabel}.`
    : "Правки отправляются сразу на сервер. Если сессия недействительна, страница покажет точную ошибку сохранения.";
  const heroMinFontSize = Math.max(22, Math.round(pageConfig.heroFontSize * 0.44));
  const heroFluidViewport = Math.max(2.2, Math.min(5.4, pageConfig.heroFontSize / 18));
  const heroLineHeight = pageConfig.heroFontSize <= 40 ? 1.02 : 0.92;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-4 sm:py-8 lg:py-10">
      {isEditMode ? (
        <>
          <button
            type="button"
            onClick={() => setIsEditorOpen((value) => !value)}
            className="fixed bottom-4 right-4 z-40 inline-flex items-center gap-2 rounded-2xl border border-border bg-card/90 px-4 py-3 text-sm font-semibold text-foreground shadow-lg backdrop-blur-xl"
          >
            <Settings2 className="h-4 w-4" />
            {isEditorOpen ? "Скрыть редактор" : "Открыть редактор"}
          </button>

          {isEditorOpen ? (
            <aside className="fixed right-4 top-4 z-40 flex max-h-[calc(100vh-6rem)] w-[min(420px,calc(100vw-2rem))] flex-col overflow-hidden rounded-[2rem] border border-border bg-card/95 shadow-2xl backdrop-blur-xl">
              <div className="border-b border-border px-4 py-4">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-[#2F80ED]" />
                  <h2 className="text-sm font-semibold text-foreground">Редактор страницы входа</h2>
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">{editorNotice}</p>
                {isLoadingOverrides ? <p className="mt-2 text-xs text-muted-foreground">Загружаем сохранённые значения...</p> : null}
                {editorMessage ? <p className="mt-2 text-xs font-medium text-emerald-400">{editorMessage}</p> : null}
                {editorError ? <p className="mt-2 text-xs font-medium text-rose-400">{editorError}</p> : null}
              </div>

              <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4">
                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Тексты</h3>
                  <label className="block space-y-2">
                    <span className="text-xs text-muted-foreground">Плашка</span>
                    <input
                      type="text"
                      className="soft-input"
                      value={pageConfig.badgeText}
                      onChange={(event) => setPageConfig((current) => ({ ...current, badgeText: event.target.value }))}
                    />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-xs text-muted-foreground">Главный заголовок</span>
                    <textarea
                      className="soft-input min-h-28 resize-y py-4"
                      value={pageConfig.heroTitle}
                      onChange={(event) => setPageConfig((current) => ({ ...current, heroTitle: event.target.value }))}
                    />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-xs text-muted-foreground">Подзаголовок слева</span>
                    <textarea
                      className="soft-input min-h-24 resize-y py-4"
                      value={pageConfig.heroText}
                      onChange={(event) => setPageConfig((current) => ({ ...current, heroText: event.target.value }))}
                    />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-xs text-muted-foreground">Подпись над формой</span>
                    <input
                      type="text"
                      className="soft-input"
                      value={pageConfig.loginEyebrow}
                      onChange={(event) => setPageConfig((current) => ({ ...current, loginEyebrow: event.target.value }))}
                    />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-xs text-muted-foreground">Заголовок формы</span>
                    <input
                      type="text"
                      className="soft-input"
                      value={pageConfig.loginTitle}
                      onChange={(event) => setPageConfig((current) => ({ ...current, loginTitle: event.target.value }))}
                    />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-xs text-muted-foreground">Текст под заголовком формы</span>
                    <textarea
                      className="soft-input min-h-24 resize-y py-4"
                      value={pageConfig.loginText}
                      onChange={(event) => setPageConfig((current) => ({ ...current, loginText: event.target.value }))}
                    />
                  </label>
                  <label className="block space-y-2">
                    <span className="text-xs text-muted-foreground">Текст кнопки входа</span>
                    <input
                      type="text"
                      className="soft-input"
                      value={pageConfig.submitText}
                      onChange={(event) => setPageConfig((current) => ({ ...current, submitText: event.target.value }))}
                    />
                  </label>
                </section>

                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Карточки преимуществ</h3>
                  {pageConfig.featureCards.map((item, index) => (
                    <div key={`${index}-${item.title}`} className="space-y-2 rounded-2xl border border-border bg-background/30 p-3">
                      <p className="text-xs font-semibold text-foreground">Карточка {index + 1}</p>
                      <input
                        type="text"
                        className="soft-input"
                        value={item.title}
                        onChange={(event) => updateFeatureCard(index, "title", event.target.value)}
                      />
                      <textarea
                        className="soft-input min-h-24 resize-y py-4"
                        value={item.text}
                        onChange={(event) => updateFeatureCard(index, "text", event.target.value)}
                      />
                    </div>
                  ))}
                </section>

                <section className="space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Геометрия и размеры</h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Ширина оболочки</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.shellMaxWidth}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            shellMaxWidth: parseNumberInput(event.target.value, current.shellMaxWidth, 720, 1800),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Высота оболочки</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.shellMinHeight}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            shellMinHeight: parseNumberInput(event.target.value, current.shellMinHeight, 420, 1200),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Скругление оболочки</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.shellRadius}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            shellRadius: parseNumberInput(event.target.value, current.shellRadius, 12, 72),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Внутренний отступ секций</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.sectionPadding}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            sectionPadding: parseNumberInput(event.target.value, current.sectionPadding, 8, 72),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Расстояние слева</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.leftColumnGap}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            leftColumnGap: parseNumberInput(event.target.value, current.leftColumnGap, 8, 72),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Размер главного заголовка</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.heroFontSize}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            heroFontSize: parseNumberInput(event.target.value, current.heroFontSize, 28, 140),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Ширина заголовка</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.heroMaxWidth}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            heroMaxWidth: parseNumberInput(event.target.value, current.heroMaxWidth, 240, 900),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Ширина текстового блока</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.bodyMaxWidth}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            bodyMaxWidth: parseNumberInput(event.target.value, current.bodyMaxWidth, 220, 900),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Отступ карточек преимуществ</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.featureCardPadding}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            featureCardPadding: parseNumberInput(event.target.value, current.featureCardPadding, 8, 48),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Скругление карточек</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.featureCardRadius}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            featureCardRadius: parseNumberInput(event.target.value, current.featureCardRadius, 12, 40),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Ширина формы входа</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.loginCardWidth}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            loginCardWidth: parseNumberInput(event.target.value, current.loginCardWidth, 260, 560),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Отступы формы</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.loginCardPadding}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            loginCardPadding: parseNumberInput(event.target.value, current.loginCardPadding, 12, 52),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Скругление формы</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.loginCardRadius}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            loginCardRadius: parseNumberInput(event.target.value, current.loginCardRadius, 12, 48),
                          }))
                        }
                      />
                    </label>
                    <label className="space-y-2">
                      <span className="text-xs text-muted-foreground">Интервалы внутри формы</span>
                      <input
                        type="number"
                        className="soft-input"
                        value={pageConfig.loginCardGap}
                        onChange={(event) =>
                          setPageConfig((current) => ({
                            ...current,
                            loginCardGap: parseNumberInput(event.target.value, current.loginCardGap, 4, 36),
                          }))
                        }
                      />
                    </label>
                  </div>
                </section>
              </div>

              <div className="flex flex-wrap gap-3 border-t border-border px-4 py-4">
                <button
                  type="button"
                  className="brand-outline flex-1 gap-2"
                  onClick={() => {
                    setPageConfig(loginPageDefaults);
                    setEditorError("");
                    setEditorMessage("Возврат к базовым значениям выполнен локально. Нажмите «Сохранить».");
                  }}
                >
                  <RotateCcw className="h-4 w-4" />
                  Сбросить
                </button>
                <button
                  type="button"
                  className="brand-button flex-1 gap-2"
                  onClick={handleSaveOverrides}
                  disabled={isSavingOverrides || isLoadingOverrides}
                >
                  <Save className="h-4 w-4" />
                  {isSavingOverrides ? "Сохраняем..." : "Сохранить"}
                </button>
              </div>
            </aside>
          ) : null}
        </>
      ) : null}

      <div className="relative w-full" style={{ maxWidth: pageConfig.shellMaxWidth }}>
        <div className="absolute right-4 top-4 z-30 sm:right-0 sm:top-0 sm:translate-x-[38%] sm:-translate-y-[38%]">
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
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card relative w-full overflow-hidden"
          style={{ borderRadius: pageConfig.shellRadius }}
        >
          <div className="grid lg:grid-cols-[1.08fr_0.92fr]" style={{ minHeight: pageConfig.shellMinHeight }}>
            <section
              className="order-2 crm-ambient flex flex-col border-t border-border lg:order-1 lg:border-r lg:border-t-0"
              style={{ padding: pageConfig.sectionPadding, gap: pageConfig.leftColumnGap }}
            >
              <div className="flex flex-col" style={{ gap: Math.max(pageConfig.leftColumnGap - 4, 18) }}>
                <span className="crm-gold-badge inline-flex self-start rounded-full border px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.26em] sm:text-xs">
                  {pageConfig.badgeText}
                </span>

                <div className="space-y-5">
                  <h1
                    className="font-semibold tracking-[-0.065em] text-foreground"
                    style={{
                      maxWidth: pageConfig.heroMaxWidth,
                      fontSize: `clamp(${heroMinFontSize}px, ${heroFluidViewport}vw, ${pageConfig.heroFontSize}px)`,
                      lineHeight: heroLineHeight,
                    }}
                  >
                    {pageConfig.heroTitle}
                  </h1>
                  <p className="text-base leading-7 text-muted-foreground" style={{ maxWidth: pageConfig.bodyMaxWidth }}>
                    {pageConfig.heroText}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {pageConfig.featureCards.map((item, index) => {
                  const Icon = featureIcons[index] ?? ShieldCheck;
                  return (
                    <article
                      key={`${item.title}-${index}`}
                      className="flex h-full flex-col border border-border bg-card/55 backdrop-blur-lg"
                      style={{ padding: pageConfig.featureCardPadding, borderRadius: pageConfig.featureCardRadius }}
                    >
                      <Icon className="crm-gold-tone h-5 w-5" />
                      <h2 className="mt-6 text-sm font-semibold text-foreground">{item.title}</h2>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.text}</p>
                    </article>
                  );
                })}
              </div>
            </section>

            <section className="order-1 flex items-center px-4 py-5 sm:px-6 sm:py-7 lg:order-2 lg:px-8">
              <div className="mx-auto w-full" style={{ maxWidth: pageConfig.loginCardWidth }}>
                <div className="glass-card flex flex-col" style={{ borderRadius: pageConfig.loginCardRadius, padding: pageConfig.loginCardPadding }}>
                  <div className="space-y-2 text-center">
                    <p className="crm-gold-tone text-xs font-semibold uppercase tracking-[0.28em]">{pageConfig.loginEyebrow}</p>
                    <h2 className="text-2xl font-semibold tracking-[-0.05em] text-foreground sm:text-3xl">{pageConfig.loginTitle}</h2>
                    {pageConfig.loginText ? <p className="text-sm leading-6 text-muted-foreground">{pageConfig.loginText}</p> : null}
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-4" style={{ marginTop: pageConfig.loginCardGap }}>
                    {errorMessage ? (
                      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                        {errorMessage}
                      </div>
                    ) : null}

                    <label className="block space-y-2">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Логин</span>
                      <div className="relative">
                        <UserRound className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                        <input
                          type="text"
                          className="soft-input pl-12"
                          placeholder="mikhail.stasenko"
                          value={login}
                          onChange={(event) => setLogin(event.target.value)}
                          disabled={isSubmitting || isCheckingSession}
                          required
                          autoCapitalize="none"
                          autoCorrect="off"
                        />
                      </div>
                    </label>

                    <label className="block space-y-2">
                      <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Пароль</span>
                      <div className="relative">
                        <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                        <input
                          type={showPassword ? "text" : "password"}
                          className="soft-input pl-12 pr-14"
                          placeholder="Введите пароль"
                          value={password}
                          onChange={(event) => setPassword(event.target.value)}
                          disabled={isSubmitting || isCheckingSession}
                          required
                        />
                        <button
                          type="button"
                          className="absolute right-3 top-1/2 inline-flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-xl text-muted-foreground transition hover:bg-white/5 hover:text-foreground"
                          onClick={() => setShowPassword((value) => !value)}
                          aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                          title={showPassword ? "Скрыть пароль" : "Показать пароль"}
                          disabled={isSubmitting || isCheckingSession}
                        >
                          {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </label>

                    <button
                      type="submit"
                      disabled={isSubmitting || isCheckingSession}
                      className="brand-button w-full gap-2 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isCheckingSession ? "Проверяем доступ..." : isSubmitting ? "Открываем CRM..." : pageConfig.submitText}
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  </form>
                </div>
              </div>
            </section>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
