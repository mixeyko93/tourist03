import {
  Building2,
  FileClock,
  LayoutDashboard,
  LogOut,
  Menu,
  UserRound,
  X,
} from "./initialIcons";
import {
  Component,
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ErrorInfo, ReactNode } from "react";
import { useLocation, useNavigate } from "react-router";

import {
  ApiError,
  ownerApi,
  type OwnerCamp,
  type OwnerChange,
  type OwnerDashboard,
  type OwnerProfile,
} from "./api";
import { OwnerRouteError, OwnerRouteLoading } from "./components";
import "./owner.css";

const LoginPage = lazy(() => import("./LoginPage"));
const DashboardPage = lazy(() => import("./DashboardPage"));
const ObjectsPage = lazy(() => import("./ObjectsPage"));
const HistoryPage = lazy(() => import("./HistoryPage"));
const ProfilePage = lazy(() => import("./ProfilePage"));
const CampPage = lazy(() => import("./CampPage"));
const ChangeDiffPage = lazy(() => import("./ChangeDiffPage"));
const CreateEntityPage = lazy(() => import("./CreateEntityPage"));

type View = "dashboard" | "objects" | "changes" | "profile";

class LazyRouteBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // The visible retry state is intentionally local; no sensitive payload is logged.
  }

  render() {
    if (this.state.error) {
      return <OwnerRouteError>{this.state.error.message || "Попробуйте загрузить раздел ещё раз."}</OwnerRouteError>;
    }
    return this.props.children;
  }
}

function routeFor(pathname: string) {
  const suffix = pathname.replace(/^\/owner\/?/, "");
  const segments = suffix.split("/").filter(Boolean);
  if (segments[0] === "objects" && segments[1] === "new") {
    return { view: "create" as const };
  }
  if (segments[0] === "objects" && /^\d+$/.test(segments[1] || "")) {
    return { view: "camp" as const, id: Number(segments[1]) };
  }
  if (segments[0] === "changes" && /^\d+$/.test(segments[1] || "")) {
    return { view: "diff" as const, id: Number(segments[1]) };
  }
  if (segments[0] === "objects") return { view: "objects" as const };
  if (segments[0] === "changes") return { view: "changes" as const };
  if (segments[0] === "profile") return { view: "profile" as const };
  return { view: "dashboard" as const };
}

export default function OwnerPortal() {
  const location = useLocation();
  const navigate = useNavigate();
  const route = routeFor(location.pathname);
  const [auth, setAuth] = useState<"loading" | "authenticated" | "anonymous">("loading");
  const [dashboard, setDashboard] = useState<OwnerDashboard | null>(null);
  const [history, setHistory] = useState<OwnerChange[] | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [error, setError] = useState("");
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);

  useEffect(() => {
    const previous = document.title;
    document.title = "Кабинет владельца — Туристика";
    return () => {
      document.title = previous;
    };
  }, []);

  const load = useCallback(async () => {
    try {
      const payload = await ownerApi.dashboard();
      setDashboard(payload);
      setAuth("authenticated");
      setError("");
      return payload;
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        setDashboard(null);
        setHistory(null);
        setAuth("anonymous");
        return null;
      }
      setError(reason instanceof Error ? reason.message : "Не удалось загрузить кабинет");
      setAuth((current) => current === "loading" ? "authenticated" : current);
      return null;
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (
      dashboard
      && route.view === "create"
      && dashboard.features.entity_creation === false
    ) {
      navigate("/owner/objects", { replace: true });
    }
  }, [dashboard, navigate, route.view]);

  useEffect(() => {
    setMobileNav(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileNav) return;
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : menuButton.current;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(
      sidebar.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) || [],
    );
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setMobileNav(false);
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      window.requestAnimationFrame(() => (previousFocus || menuButton.current)?.focus());
    };
  }, [mobileNav]);

  if (auth === "loading") {
    return <div className="owner-loading"><img src="/static/brand/turistika-icon.svg" width="58" height="58" alt="" /><span>Открываем кабинет…</span></div>;
  }
  if (auth === "anonymous") {
    return (
      <LazyRouteBoundary>
        <Suspense fallback={<div className="owner-loading"><span>Открываем форму входа…</span></div>}>
          <LoginPage onLogin={() => void load().then(() => navigate("/owner", { replace: true }))} />
        </Suspense>
      </LazyRouteBoundary>
    );
  }
  if (!dashboard) {
    return (
      <div className="owner-loading" role="alert">
        <span>{error || "Не удалось загрузить кабинет"}</span>
        <button className="owner-primary" onClick={() => void load()}>Повторить</button>
      </div>
    );
  }
  const currentDashboard = dashboard;

  const currentView: View = route.view === "camp"
    ? "objects"
    : route.view === "create"
      ? "objects"
    : route.view === "diff"
      ? "changes"
      : route.view;
  const nav: Array<{ key: View; label: string; icon: typeof LayoutDashboard }> = [
    { key: "dashboard", label: "Главная", icon: LayoutDashboard },
    { key: "objects", label: "Мои объекты", icon: Building2 },
    ...(currentDashboard.features.change_requests ? [{ key: "changes" as View, label: "Изменения", icon: FileClock }] : []),
    { key: "profile", label: "Профиль владельца", icon: UserRound },
  ];
  const viewPaths: Record<View, string> = {
    dashboard: "/owner",
    objects: "/owner/objects",
    changes: "/owner/changes",
    profile: "/owner/profile",
  };
  const selectCamp = (camp: OwnerCamp) => navigate(`/owner/objects/${camp.id}`, { state: { from: location.pathname } });
  const selectedCamp = route.view === "camp"
    ? currentDashboard.camps.find((camp) => camp.id === route.id)
    : null;

  function renderRoute() {
    if (route.view === "create") {
      if (currentDashboard.features.entity_creation === false) {
        return <OwnerRouteLoading label="Возвращаем к объектам размещения…" />;
      }
      return (
        <CreateEntityPage
          onBack={() => navigate("/owner/objects")}
          onCreated={(entityId) => {
            void load();
            navigate(`/owner/objects/${entityId}`, {
              replace: true,
              state: { from: "/owner/objects", created: true },
            });
          }}
        />
      );
    }
    if (route.view === "camp") {
      return (
        <CampPage
          camp={selectedCamp ?? undefined}
          campId={route.id}
          changeRequestsEnabled={currentDashboard.features.change_requests}
          onBack={() => navigate(String(location.state?.from || "/owner"))}
          onReload={() => void load()}
        />
      );
    }
    if (route.view === "diff") {
      return <ChangeDiffPage changeId={route.id} onBack={() => navigate("/owner/changes")} />;
    }
    if (route.view === "objects") {
      return (
        <ObjectsPage
          dashboard={currentDashboard}
          onCamp={selectCamp}
          onCreate={() => navigate("/owner/objects/new")}
          canCreate={currentDashboard.features.entity_creation !== false}
          onCampsLoaded={(camps, pagination) => setDashboard({ ...currentDashboard, camps, object_pagination: pagination })}
        />
      );
    }
    if (route.view === "changes") {
      return (
        <HistoryPage
          cachedChanges={history}
          onLoaded={setHistory}
          onOpen={(change) => navigate(`/owner/changes/${change.id}`)}
        />
      );
    }
    if (route.view === "profile") {
      return (
        <ProfilePage
          dashboard={currentDashboard}
          onUpdated={(owner: OwnerProfile) => setDashboard({ ...currentDashboard, owner })}
        />
      );
    }
    return (
      <DashboardPage
        data={currentDashboard}
        onCamp={selectCamp}
        onChanges={() => navigate("/owner/changes")}
        onCreate={() => navigate("/owner/objects/new")}
        canCreate={currentDashboard.features.entity_creation !== false}
      />
    );
  }

  return (
    <div className="owner-shell">
      {mobileNav ? <button className="owner-drawer-backdrop" aria-label="Закрыть меню" onClick={() => setMobileNav(false)} /> : null}
      <aside ref={sidebar} id="owner-navigation" className={`owner-sidebar ${mobileNav ? "open" : ""}`}>
        <a className="owner-logo" href="/owner"><img src="/static/brand/turistika-logo-horizontal-dark.svg" width="190" height="48" alt="Туристика" /></a>
        <p className="owner-product-label">Кабинет владельца</p>
        <nav aria-label="Разделы кабинета">{nav.map(({ key, label, icon: Icon }) => <button key={key} className={currentView === key ? "active" : ""} onClick={() => navigate(viewPaths[key])}><Icon />{label}{key === "changes" && currentDashboard.profile_statistics.pending_changes ? <span>{currentDashboard.profile_statistics.pending_changes}</span> : null}</button>)}</nav>
        <div className="owner-sidebar-profile"><div>{currentDashboard.owner.display_name.slice(0, 1).toUpperCase()}</div><span><b>{currentDashboard.owner.display_name}</b><small>{currentDashboard.owner.company || currentDashboard.owner.email}</small></span></div>
        <button className="owner-logout" onClick={async () => {
          await ownerApi.logout();
          setDashboard(null);
          setHistory(null);
          setAuth("anonymous");
          navigate("/owner", { replace: true });
        }}><LogOut /> Выйти</button>
      </aside>
      <div className="owner-main">
        <header className="owner-mobile-header">
          <img src="/static/brand/turistika-logo-horizontal.svg" width="148" height="37" alt="Туристика" />
          <button
            ref={menuButton}
            aria-label={mobileNav ? "Закрыть меню" : "Открыть меню"}
            aria-expanded={mobileNav}
            aria-controls="owner-navigation"
            onClick={() => setMobileNav(!mobileNav)}
          >
            {mobileNav ? <X /> : <Menu />}
          </button>
        </header>
        <main>
          {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
          <LazyRouteBoundary key={location.pathname}>
            <Suspense fallback={<OwnerRouteLoading />}>
              {renderRoute()}
            </Suspense>
          </LazyRouteBoundary>
        </main>
      </div>
    </div>
  );
}
