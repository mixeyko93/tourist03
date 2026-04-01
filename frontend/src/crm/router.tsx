import { Navigate, createBrowserRouter, type RouteObject } from "react-router";
import LegacyMapPage from "./routes/LegacyMapPage";
import AppLayout from "./components/AppLayout";
import AdminLayout from "./admin/components/AdminLayout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import CalendarPage from "./pages/CalendarPage";
import ShiftsPage from "./pages/ShiftsPage";
import EventsPage from "./pages/EventsPage";
import BookingsPage from "./pages/BookingsPage";
import RoomsPage from "./pages/RoomsPage";
import GuestsPage from "./pages/GuestsPage";
import ServicesPage from "./pages/ServicesPage";
import SettingsPage from "./pages/SettingsPage";
import AdminBasesPage from "./admin/pages/AdminBasesPage";
import AdminBaseEditPage from "./admin/pages/AdminBaseEditPage";
import AdminUsersPage from "./admin/pages/AdminUsersPage";
import AdminAccountsPage from "./admin/pages/AdminAccountsPage";
import AdminArchivePage from "./admin/pages/AdminArchivePage";
import AdminLoginPage from "./admin/pages/AdminLoginPage";
import { crmPath } from "./paths";

function RouteRedirect({ to, base = "" }: { to: string; base?: "" | "/react-map" }) {
  return <Navigate to={crmPath(to, base)} replace />;
}

function createCrmRoutes(base: "" | "/react-map"): RouteObject[] {
  return [
    {
      path: crmPath("/login", base),
      Component: LoginPage,
    },
    {
      path: crmPath("/map", base),
      Component: LegacyMapPage,
    },
    {
      path: base || "/",
      Component: AppLayout,
      children: [
        { index: true, Component: () => <RouteRedirect to="/calendar" base={base} /> },
        { path: "dashboard", Component: DashboardPage },
        { path: "calendar", Component: CalendarPage },
        { path: "shifts", Component: ShiftsPage },
        { path: "events", Component: EventsPage },
        { path: "bookings", Component: BookingsPage },
        { path: "rooms", Component: RoomsPage },
        { path: "guests", Component: GuestsPage },
        { path: "services", Component: ServicesPage },
        { path: "settings", Component: SettingsPage },
      ],
    },
  ];
}

function createAdminRoutes(base: "" | "/react-map"): RouteObject[] {
  return [
    {
      path: crmPath("/admin/login", base),
      Component: AdminLoginPage,
    },
    {
      path: crmPath("/admin", base),
      Component: AdminLayout,
      children: [
        { index: true, Component: () => <RouteRedirect to="/admin/bases" base={base} /> },
        { path: "bases", Component: AdminBasesPage },
        { path: "bases/new", Component: AdminBaseEditPage },
        { path: "bases/:id", Component: AdminBaseEditPage },
        { path: "users", Component: AdminUsersPage },
        { path: "accounts", Component: AdminAccountsPage },
        { path: "archive", Component: AdminArchivePage },
      ],
    },
  ];
}

export const router = createBrowserRouter([
  ...createCrmRoutes(""),
  ...createAdminRoutes(""),
  ...createCrmRoutes("/react-map"),
  ...createAdminRoutes("/react-map"),
]);
