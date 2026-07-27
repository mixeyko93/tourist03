import { Navigate, createBrowserRouter, type RouteObject } from "react-router";
import type { ComponentType } from "react";
import { crmPath } from "./paths";

function lazyComponent(loader: () => Promise<{ default: ComponentType }>): RouteObject["lazy"] {
  return async () => ({ Component: (await loader()).default });
}

function RouteRedirect({ to, base = "" }: { to: string; base?: "" | "/react-map" }) {
  return <Navigate to={crmPath(to, base)} replace />;
}

function createCrmRoutes(base: "" | "/react-map"): RouteObject[] {
  return [
    {
      path: crmPath("/login", base),
      lazy: lazyComponent(() => import("./pages/LoginPage")),
    },
    {
      path: crmPath("/map", base),
      lazy: lazyComponent(() => import("./routes/LegacyMapPage")),
    },
    {
      path: base || "/",
      lazy: lazyComponent(() => import("./components/AppLayout")),
      children: [
        { index: true, Component: () => <RouteRedirect to="/calendar" base={base} /> },
        { path: "dashboard", lazy: lazyComponent(() => import("./pages/DashboardPage")) },
        { path: "calendar", lazy: lazyComponent(() => import("./pages/CalendarPage")) },
        { path: "shifts", lazy: lazyComponent(() => import("./pages/ShiftsPage")) },
        { path: "events", lazy: lazyComponent(() => import("./pages/EventsPage")) },
        { path: "approvals", lazy: lazyComponent(() => import("./pages/ApprovalsPage")) },
        { path: "bookings", lazy: lazyComponent(() => import("./pages/BookingsPage")) },
        { path: "rooms", lazy: lazyComponent(() => import("./pages/RoomsPage")) },
        { path: "guests", lazy: lazyComponent(() => import("./pages/GuestsPage")) },
        { path: "services", lazy: lazyComponent(() => import("./pages/ServicesPage")) },
        { path: "settings", lazy: lazyComponent(() => import("./pages/SettingsPage")) },
      ],
    },
  ];
}

function createAdminRoutes(base: "" | "/react-map"): RouteObject[] {
  return [
    {
      path: crmPath("/admin/login", base),
      lazy: lazyComponent(() => import("./admin/pages/AdminLoginPage")),
    },
    {
      path: crmPath("/admin", base),
      lazy: lazyComponent(() => import("./admin/components/AdminLayout")),
      children: [
        { index: true, Component: () => <RouteRedirect to="/admin/bases" base={base} /> },
        { path: "bases", lazy: lazyComponent(() => import("./admin/pages/AdminBasesPage")) },
        { path: "bases/new", lazy: lazyComponent(() => import("./admin/pages/AdminBaseEditPage")) },
        { path: "bases/:id", lazy: lazyComponent(() => import("./admin/pages/AdminBaseEditPage")) },
        { path: "users", lazy: lazyComponent(() => import("./admin/pages/AdminUsersPage")) },
        { path: "accounts", lazy: lazyComponent(() => import("./admin/pages/AdminAccountsPage")) },
        { path: "moderation", lazy: lazyComponent(() => import("./admin/pages/AdminModerationPage")) },
        { path: "submissions", lazy: lazyComponent(() => import("./admin/pages/AdminSubmissionsPage")) },
        { path: "owner-changes", lazy: lazyComponent(() => import("./admin/pages/AdminOwnerChangesPage")) },
        { path: "superadmins", lazy: lazyComponent(() => import("./admin/pages/AdminSuperadminsPage")) },
        { path: "audit", lazy: lazyComponent(() => import("./admin/pages/AdminAuditPage")) },
        { path: "archive", lazy: lazyComponent(() => import("./admin/pages/AdminArchivePage")) },
      ],
    },
  ];
}

export const router = createBrowserRouter([
  { path: "/owner/*", lazy: lazyComponent(() => import("../owner/OwnerPortal")) },
  { path: "/tg-link", lazy: lazyComponent(() => import("./pages/TelegramLinkScanPage")) },
  { path: "/react-map/tg-link", lazy: lazyComponent(() => import("./pages/TelegramLinkScanPage")) },
  ...createCrmRoutes(""),
  ...createAdminRoutes(""),
  ...createCrmRoutes("/react-map"),
  ...createAdminRoutes("/react-map"),
]);
