import { BellRing, KeyRound, Loader2, LogOut, Menu, ShieldCheck, UserCircle2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router";
import {
  completeCrmProfilePinReset,
  fetchCrmEventCenterSummary,
  fetchCrmProfileSwitcher,
  fetchCrmSession,
  issueSelfTelegramLink,
  logoutCrmSession,
  requestCrmProfilePinReset,
  requestCrmProfilePinSetup,
  switchCrmProfile,
  type CrmProfileSwitchProfile,
  type CrmProfileSwitcherResponse,
  type CrmSession,
} from "../session";
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

type ProfileSwitchMode = "list" | "pin" | "setup" | "pending_setup" | "pending_reset" | "reset_ready" | "success";

function sanitizePin(value: string) {
  return value.replace(/\D/g, "").slice(0, 4);
}

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [session, setSession] = useState<CrmSession | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [eventNewCount, setEventNewCount] = useState(0);
  const [isRouteTransitioning, setIsRouteTransitioning] = useState(false);
  const [profileSwitcherOpen, setProfileSwitcherOpen] = useState(false);
  const [profileSwitcher, setProfileSwitcher] = useState<CrmProfileSwitcherResponse | null>(null);
  const [profileSwitcherLoading, setProfileSwitcherLoading] = useState(false);
  const [profileSwitcherError, setProfileSwitcherError] = useState("");
  const [profileMode, setProfileMode] = useState<ProfileSwitchMode>("list");
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [profileMessage, setProfileMessage] = useState("");
  const [pinValue, setPinValue] = useState("");
  const [pinConfirmValue, setPinConfirmValue] = useState("");
  const [profileActionPending, setProfileActionPending] = useState(false);
  const pendingSetupPinRef = useRef("");
  const [onboardingOpen, setOnboardingOpen] = useState(false);
  const [onboardingLink, setOnboardingLink] = useState<{ code: string; bot_username: string } | null>(null);
  const [onboardingLoading, setOnboardingLoading] = useState(false);
  const [onboardingError, setOnboardingError] = useState("");
  const calendarPath = crmPath("/calendar");
  const activeNavItem = navItems.find((item) => location.pathname === crmPath(item.path));

  useDocumentTitle(activeNavItem ? `${activeNavItem.label} — Туристика CRM` : "Туристика CRM");

  useEffect(() => {
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
    if (!session || session.hasTelegramLink) {
      return;
    }
    const dismissed = sessionStorage.getItem("tg_onboarding_dismissed");
    if (dismissed) {
      return;
    }
    setOnboardingOpen(true);
    setOnboardingLoading(true);
    setOnboardingError("");
    issueSelfTelegramLink()
      .then((data) => {
        setOnboardingLink({ code: data.code, bot_username: data.bot_username });
      })
      .catch((err: unknown) => {
        setOnboardingError(err instanceof Error ? err.message : "Не удалось получить ссылку");
      })
      .finally(() => {
        setOnboardingLoading(false);
      });
  }, [session]);

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
      sessionStorage.removeItem("tg_onboarding_dismissed");
      setSession(null);
      navigate(loginPath, { replace: true });
    }
  };

  const selectedProfile = selectedProfileId
    ? profileSwitcher?.profiles.find((profile) => profile.id === selectedProfileId) || null
    : null;

  const resetProfileForm = () => {
    setProfileMode("list");
    setSelectedProfileId(null);
    setProfileMessage("");
    setProfileSwitcherError("");
    setPinValue("");
    setPinConfirmValue("");
    setProfileActionPending(false);
    pendingSetupPinRef.current = "";
  };

  const loadProfileSwitcher = async (signal?: AbortSignal) => {
    setProfileSwitcherLoading(true);
    setProfileSwitcherError("");
    try {
      const payload = await fetchCrmProfileSwitcher(signal);
      setProfileSwitcher(payload);
      return payload;
    } catch (error: unknown) {
      if (!signal?.aborted) {
        setProfileSwitcherError(error instanceof Error ? error.message : "Не удалось загрузить карточки сотрудников");
      }
      return null;
    } finally {
      if (!signal?.aborted) {
        setProfileSwitcherLoading(false);
      }
    }
  };

  const openProfileSwitcher = () => {
    resetProfileForm();
    setProfileSwitcherOpen(true);
    void loadProfileSwitcher();
  };

  const closeProfileSwitcher = () => {
    setProfileSwitcherOpen(false);
    resetProfileForm();
  };

  // Polling пока открыт онбординг — как только TG привязан, предлагаем PIN
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!onboardingOpen || !session) return;
    let active = true;
    const poll = async () => {
      try {
        const next = await fetchCrmSession();
        if (!active) return;
        if (next?.hasTelegramLink) {
          setSession(next);
          sessionStorage.setItem("tg_onboarding_dismissed", "1");
          setOnboardingOpen(false);
          resetProfileForm();
          setProfileSwitcherOpen(true);
          void loadProfileSwitcher();
        }
      } catch { /* ignore */ }
    };
    const id = window.setInterval(poll, 3000);
    return () => { active = false; window.clearInterval(id); };
  }, [onboardingOpen, session]);

  const handleSelectProfile = (profile: CrmProfileSwitchProfile) => {
    setSelectedProfileId(profile.id);
    setPinValue("");
    setPinConfirmValue("");
    setProfileMessage("");
    setProfileSwitcherError("");
    if (profile.is_current && profile.has_pin) {
      setProfileMessage("Вы уже работаете под этой карточкой сотрудника.");
      setProfileMode("list");
      return;
    }
    if (!profile.has_pin) {
      if (!profile.has_telegram_link) {
        setProfileSwitcherError("Сначала привяжите Telegram к этой карточке сотрудника в настройках CRM.");
        setProfileMode("list");
        return;
      }
      setProfileMode("setup");
      return;
    }
    if (profile.pin_reset_ready) {
      setProfileMode("reset_ready");
      return;
    }
    setProfileMode("pin");
  };

  const handleProfilePinSubmit = async () => {
    if (!selectedProfile) {
      return;
    }
    const pin = sanitizePin(pinValue);
    const pinConfirm = sanitizePin(pinConfirmValue);
    if (pin.length !== 4) {
      setProfileSwitcherError("Введите PIN-код из 4 цифр.");
      return;
    }
    if ((profileMode === "setup" || profileMode === "reset_ready") && pin !== pinConfirm) {
      setProfileSwitcherError("PIN-коды не совпадают.");
      return;
    }

    setProfileActionPending(true);
    setProfileSwitcherError("");
    try {
      if (profileMode === "pin") {
        const nextSession = await switchCrmProfile(selectedProfile.id, pin);
        setSession(nextSession);
        closeProfileSwitcher();
        return;
      }
      if (profileMode === "setup") {
        pendingSetupPinRef.current = pin;
        await requestCrmProfilePinSetup(selectedProfile.id, pin);
        setProfileMessage("Подтвердите создание PIN-кода в Telegram. После подтверждения CRM переключит карточку автоматически.");
        setProfileMode("pending_setup");
        return;
      }
      if (profileMode === "reset_ready") {
        const nextSession = await completeCrmProfilePinReset(selectedProfile.id, pin);
        setSession(nextSession);
        setProfileMessage(`PIN-код создан. Добро пожаловать, ${nextSession.name}.`);
        setProfileMode("success");
      }
    } catch (error: unknown) {
      pendingSetupPinRef.current = "";
      setProfileSwitcherError(error instanceof Error ? error.message : "Не удалось выполнить действие");
    } finally {
      setProfileActionPending(false);
    }
  };

  const handleForgotProfilePin = async () => {
    if (!selectedProfile) {
      return;
    }
    setProfileActionPending(true);
    setProfileSwitcherError("");
    try {
      await requestCrmProfilePinReset(selectedProfile.id);
      setProfileMessage("В Telegram отправлено подтверждение сброса PIN-кода.");
      setProfileMode("pending_reset");
    } catch (error: unknown) {
      setProfileSwitcherError(error instanceof Error ? error.message : "Не удалось отправить запрос на сброс PIN");
    } finally {
      setProfileActionPending(false);
    }
  };

  useEffect(() => {
    if (!profileSwitcherOpen || !selectedProfileId || !["pending_setup", "pending_reset"].includes(profileMode)) {
      return;
    }

    let active = true;
    const poll = async () => {
      try {
        const payload = await fetchCrmProfileSwitcher();
        if (!active) {
          return;
        }
        setProfileSwitcher(payload);
        const profile = payload.profiles.find((item) => item.id === selectedProfileId);
        if (!profile) {
          setProfileSwitcherError("Карточка сотрудника больше недоступна.");
          setProfileMode("list");
          return;
        }
        if (profileMode === "pending_setup") {
          if (profile.has_pin && pendingSetupPinRef.current) {
            const nextSession = await switchCrmProfile(profile.id, pendingSetupPinRef.current);
            if (!active) {
              return;
            }
            pendingSetupPinRef.current = "";
            setSession(nextSession);
            setProfileMessage(`PIN-код создан. Добро пожаловать, ${nextSession.name}.`);
            setProfileMode("success");
          } else if (!profile.pin_pending_action && !profile.has_pin) {
            pendingSetupPinRef.current = "";
            setProfileSwitcherError("Создание PIN-кода отклонено или срок подтверждения истёк.");
            setProfileMode("setup");
          }
          return;
        }
        if (profileMode === "pending_reset") {
          if (profile.pin_reset_ready) {
            setProfileMessage("Сброс подтверждён. Создайте новый PIN-код.");
            setProfileMode("reset_ready");
          } else if (!profile.pin_pending_action) {
            setProfileSwitcherError("Сброс PIN-кода отклонён или срок подтверждения истёк.");
            setProfileMode("pin");
          }
        }
      } catch (error: unknown) {
        if (active) {
          setProfileSwitcherError(error instanceof Error ? error.message : "Не удалось проверить подтверждение Telegram");
        }
      }
    };

    void poll();
    const intervalId = window.setInterval(poll, 2000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [profileMode, profileSwitcherOpen, selectedProfileId]);

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
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#2F80ED]">Туристика CRM</p>
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
                ? "border-[#2F80ED]/30 bg-[#2F80ED]/10 text-foreground shadow-sm"
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
      <button
        type="button"
        onClick={openProfileSwitcher}
        className="w-full rounded-[1.65rem] border border-border bg-background/72 px-4 py-3 text-left shadow-sm transition hover:border-[#2F80ED]/40 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F80ED]/60"
      >
        <div className="flex items-center gap-3">
          <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[#2F80ED]/25 bg-[#2F80ED]/10 text-[#2F80ED]">
            <UserCircle2 className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="line-clamp-2 text-sm font-semibold leading-5 text-foreground" title={session.name}>
              {session.name.split(" ").slice(0, 2).join(" ")}
            </p>
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">Сменить профиль</p>
          </div>
        </div>
      </button>

      <button
        type="button"
        disabled={isLoggingOut}
        onClick={handleLogout}
        className="flex w-full items-center justify-center gap-2 rounded-[1.65rem] border border-border bg-background/72 px-4 py-3 text-sm font-semibold text-foreground transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F80ED]/60"
      >
        <LogOut className="h-4 w-4" />
        {isLoggingOut ? "Выходим..." : "Выйти"}
      </button>
    </div>
  );

  const pinTitle =
    profileMode === "setup"
      ? "Создайте PIN-код"
      : profileMode === "reset_ready"
        ? "Задайте новый PIN-код"
        : "Введите PIN-код";
  const pinDescription =
    profileMode === "setup"
      ? "PIN активируется только после подтверждения сотрудником в Telegram."
      : profileMode === "reset_ready"
        ? "Сброс уже подтверждён в Telegram, дополнительное подтверждение не требуется."
        : "Для переключения профиля нужен личный PIN сотрудника.";
  const submitLabel =
    profileMode === "setup"
      ? "Отправить в Telegram"
      : profileMode === "reset_ready"
        ? "Создать PIN"
        : "Войти";
  const profileSwitcherModal = profileSwitcherOpen ? (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/62 px-4 py-6 backdrop-blur-md">
      <div className="glass-card flex max-h-[min(760px,calc(100dvh-2rem))] w-full max-w-5xl flex-col overflow-hidden rounded-[2rem] border border-border bg-card/95 shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#2F80ED]">Профили CRM</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.05em] text-foreground">Быстрое переключение сотрудника</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Действия в CRM будут логироваться от имени активной карточки сотрудника.
            </p>
          </div>
          <button
            type="button"
            onClick={closeProfileSwitcher}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-border bg-background/70 text-muted-foreground transition hover:bg-accent hover:text-foreground"
            aria-label="Закрыть переключение профиля"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 gap-0 overflow-hidden lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.85fr)]">
          <div className="min-h-0 overflow-y-auto border-b border-border p-5 lg:border-b-0 lg:border-r">
            {profileSwitcherLoading && !profileSwitcher ? (
              <div className="flex min-h-60 items-center justify-center rounded-3xl border border-border bg-background/45">
                <Loader2 className="h-6 w-6 animate-spin text-[#2F80ED]" />
              </div>
            ) : null}
            {profileSwitcher?.profiles.length ? (
              <div className="space-y-3">
                {profileSwitcher.profiles.map((profile) => (
                  <button
                    type="button"
                    key={profile.id}
                    onClick={() => handleSelectProfile(profile)}
                    className={[
                      "w-full rounded-3xl border px-4 py-4 text-left transition",
                      selectedProfileId === profile.id
                        ? "border-[#2F80ED]/55 bg-[#2F80ED]/12"
                        : "border-border bg-background/55 hover:border-[#2F80ED]/35 hover:bg-accent",
                    ].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words text-lg font-semibold leading-6 text-foreground">{profile.display_name}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">{profile.role_label}</p>
                        {profile.camp_names.length ? (
                          <p className="mt-2 truncate text-sm text-muted-foreground">{profile.camp_names.join(", ")}</p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        {profile.is_current ? (
                          <span className="rounded-full border border-emerald-400/35 bg-emerald-400/10 px-3 py-1 text-xs font-semibold text-emerald-200">
                            Активен
                          </span>
                        ) : null}
                        {!profile.has_pin ? (
                          <span className="rounded-full border border-amber-400/35 bg-amber-400/10 px-3 py-1 text-xs font-semibold text-amber-100">
                            PIN не создан
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            ) : !profileSwitcherLoading ? (
              <div className="rounded-3xl border border-border bg-background/45 p-6 text-sm text-muted-foreground">
                Нет доступных карточек сотрудников.
              </div>
            ) : null}
          </div>

          <div className="min-h-0 overflow-y-auto p-5">
            {profileSwitcherError ? (
              <div className="mb-4 rounded-3xl border border-rose-400/35 bg-rose-500/12 px-4 py-3 text-sm text-rose-100">
                {profileSwitcherError}
              </div>
            ) : null}
            {profileMessage ? (
              <div className="mb-4 rounded-3xl border border-[#2F80ED]/35 bg-[#2F80ED]/10 px-4 py-3 text-sm leading-6 text-[#FFFFFF]">
                {profileMessage}
              </div>
            ) : null}

            {profileMode === "success" ? (
              <div className="rounded-[1.75rem] border border-border bg-background/55 p-5">
                <ShieldCheck className="h-9 w-9 text-emerald-300" />
                <h3 className="mt-4 text-xl font-semibold text-foreground">Профиль активирован</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{profileMessage}</p>
                <button type="button" onClick={closeProfileSwitcher} className="brand-button mt-6 w-full justify-center">
                  ОК
                </button>
              </div>
            ) : selectedProfile && ["pin", "setup", "reset_ready"].includes(profileMode) ? (
              <form
                className="rounded-[1.75rem] border border-border bg-background/55 p-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  void handleProfilePinSubmit();
                }}
              >
                <KeyRound className="h-8 w-8 text-[#2F80ED]" />
                <h3 className="mt-4 text-xl font-semibold text-foreground">{pinTitle}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{pinDescription}</p>
                <div className="mt-5 space-y-4">
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">PIN-код</span>
                    <input
                      value={pinValue}
                      onChange={(event) => setPinValue(sanitizePin(event.target.value))}
                      inputMode="numeric"
                      type="password"
                      autoComplete="one-time-code"
                      className="mt-2 w-full rounded-2xl border border-border bg-background px-4 py-3 text-lg font-semibold text-foreground outline-none transition focus:border-[#2F80ED]"
                      placeholder="0000"
                    />
                  </label>
                  {profileMode === "setup" || profileMode === "reset_ready" ? (
                    <label className="block">
                      <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Повторите PIN</span>
                      <input
                        value={pinConfirmValue}
                        onChange={(event) => setPinConfirmValue(sanitizePin(event.target.value))}
                        inputMode="numeric"
                        type="password"
                        autoComplete="one-time-code"
                        className="mt-2 w-full rounded-2xl border border-border bg-background px-4 py-3 text-lg font-semibold text-foreground outline-none transition focus:border-[#2F80ED]"
                        placeholder="0000"
                      />
                    </label>
                  ) : null}
                </div>
                <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={resetProfileForm}
                    className="flex-1 rounded-2xl border border-border px-4 py-3 text-sm font-semibold text-foreground transition hover:bg-accent"
                  >
                    Отмена
                  </button>
                  {profileMode === "pin" ? (
                    <button
                      type="button"
                      onClick={() => void handleForgotProfilePin()}
                      disabled={profileActionPending}
                      className="flex-1 rounded-2xl border border-[#2F80ED]/30 bg-[#2F80ED]/10 px-4 py-3 text-sm font-semibold text-[#FFFFFF] transition hover:bg-[#2F80ED]/15 disabled:opacity-60"
                    >
                      Забыл PIN
                    </button>
                  ) : null}
                  <button type="submit" disabled={profileActionPending} className="brand-button flex-1 justify-center disabled:opacity-60">
                    {profileActionPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    {submitLabel}
                  </button>
                </div>
              </form>
            ) : ["pending_setup", "pending_reset"].includes(profileMode) ? (
              <div className="rounded-[1.75rem] border border-border bg-background/55 p-5">
                <Loader2 className="h-8 w-8 animate-spin text-[#2F80ED]" />
                <h3 className="mt-4 text-xl font-semibold text-foreground">Ожидаем Telegram</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Нажмите кнопку подтверждения в боте. CRM проверяет статус автоматически.
                </p>
                <button
                  type="button"
                  onClick={resetProfileForm}
                  className="mt-6 w-full rounded-2xl border border-border px-4 py-3 text-sm font-semibold text-foreground transition hover:bg-accent"
                >
                  Отмена
                </button>
              </div>
            ) : (
              <div className="rounded-[1.75rem] border border-border bg-background/55 p-5">
                <UserCircle2 className="h-8 w-8 text-[#2F80ED]" />
                <h3 className="mt-4 text-xl font-semibold text-foreground">Выберите сотрудника</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Управляющий тоже переключается через свой PIN. Это защищает рабочее место, если CRM уже открыта на ПК.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <div className="flex h-screen min-h-screen flex-col overflow-hidden bg-background text-foreground">
      <header className="fixed inset-x-0 top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border bg-card/92 px-4 backdrop-blur-xl md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen((value) => !value)}
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-background/70 text-muted-foreground transition hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F80ED]/60"
            aria-label="Показать или скрыть меню"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#2F80ED]">Туристика CRM</p>
            <p className="truncate text-sm text-muted-foreground">Управление базой отдыха, бронями и гостями</p>
          </div>
        </div>

        <div className="flex min-w-0 items-center gap-3">
          <NavLink
            to={crmPath("/events")}
            className={({ isActive }) =>
              [
                "relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F80ED]/60",
                isActive
                  ? "border-[#2F80ED]/30 bg-[#2F80ED]/10 text-foreground"
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
      {profileSwitcherModal}
      {onboardingOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-md">
          <div className="glass-card flex w-full max-w-md flex-col overflow-hidden rounded-[2rem] border border-border bg-card/95 shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#2F80ED]">Привязка Telegram</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-[-0.05em] text-foreground">Подключите бота</h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  sessionStorage.setItem("tg_onboarding_dismissed", "1");
                  setOnboardingOpen(false);
                }}
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-border bg-background/70 text-muted-foreground transition hover:bg-accent hover:text-foreground"
                aria-label="Закрыть"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-6">
              <p className="text-sm leading-6 text-muted-foreground">
                Для уведомлений и подтверждения PIN-кода привяжите аккаунт к Telegram-боту.
              </p>
              {onboardingLoading ? (
                <div className="mt-6 flex items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-[#2F80ED]" />
                </div>
              ) : onboardingError ? (
                <div className="mt-4 rounded-3xl border border-rose-400/35 bg-rose-500/12 px-4 py-3 text-sm text-rose-100">
                  {onboardingError}
                </div>
              ) : onboardingLink ? (
                <div className="mt-5 flex flex-col gap-4">
                  <div className="rounded-2xl border border-[#2F80ED]/30 bg-[#2F80ED]/8 px-4 py-5 text-center">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#2F80ED]/70">Ваш код привязки</p>
                    <p className="mt-2 font-mono text-5xl font-bold tracking-[0.18em] text-foreground">{onboardingLink.code}</p>
                    <p className="mt-2 text-xs text-muted-foreground">Действителен 15 минут</p>
                  </div>
                  <ol className="space-y-1.5 text-sm leading-6 text-muted-foreground">
                    <li>1. Откройте Telegram-бот{onboardingLink.bot_username ? ` @${onboardingLink.bot_username}` : ""}</li>
                    <li>2. Напишите боту этот код: <span className="font-mono font-semibold text-foreground">{onboardingLink.code}</span></li>
                    <li>3. Бот подтвердит привязку — CRM обновится автоматически</li>
                  </ol>
                  {onboardingLink.bot_username ? (
                    <a
                      href={`https://t.me/${onboardingLink.bot_username}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="brand-button w-full justify-center"
                    >
                      Открыть бот в Telegram
                    </a>
                  ) : null}
                </div>
              ) : null}
              <button
                type="button"
                onClick={() => {
                  sessionStorage.setItem("tg_onboarding_dismissed", "1");
                  setOnboardingOpen(false);
                }}
                className="mt-4 w-full rounded-2xl border border-border px-4 py-3 text-sm font-semibold text-foreground transition hover:bg-accent"
              >
                Позже
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
