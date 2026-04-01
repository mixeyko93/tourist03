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

function RootRedirect() {
  return <Navigate to="/admincamps" replace />;
}

function LoginRedirect() {
  return <Navigate to="/admincamps/login" replace />;
}

function createCrmRoutes(base: "/admincamps" | "/react-map"): RouteObject[] {
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
      path: crmPath("/", base),
      Component: AppLayout,
      children: [
        { index: true, Component: DashboardPage },
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
  {
    path: "/",
    Component: RootRedirect,
  },
  {
    path: "/login",
    Component: LoginRedirect,
  },
  ...createCrmRoutes("/admincamps"),
  ...createCrmRoutes("/react-map"),
]);
