import { Navigate, createBrowserRouter, type RouteObject } from "react-router";
import LegacyMapPage from "./routes/LegacyMapPage";
import AppLayout from "./components/AppLayout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import CalendarPage from "./pages/CalendarPage";
import BookingsPage from "./pages/BookingsPage";
import RoomsPage from "./pages/RoomsPage";
import GuestsPage from "./pages/GuestsPage";
import ServicesPage from "./pages/ServicesPage";
import SettingsPage from "./pages/SettingsPage";
import { crmPath } from "./paths";

function DashboardRedirect({ base = "" }: { base?: "" | "/react-map" }) {
  return <Navigate to={crmPath("/dashboard", base)} replace />;
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
        { index: true, Component: () => <DashboardRedirect base={base} /> },
        { path: "dashboard", Component: DashboardPage },
        { path: "calendar", Component: CalendarPage },
        { path: "bookings", Component: BookingsPage },
        { path: "rooms", Component: RoomsPage },
        { path: "guests", Component: GuestsPage },
        { path: "services", Component: ServicesPage },
        { path: "settings", Component: SettingsPage },
      ],
    },
  ];
}

export const router = createBrowserRouter([
  ...createCrmRoutes(""),
  ...createCrmRoutes("/react-map"),
]);
