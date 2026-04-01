import { createBrowserRouter } from "react-router";
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

function detectBasename() {
  if (typeof window === "undefined") {
    return "/admincamps";
  }

  const { pathname } = window.location;
  if (pathname === "/react-map" || pathname.startsWith("/react-map/")) {
    return "/react-map";
  }
  if (pathname === "/admincamps" || pathname.startsWith("/admincamps/")) {
    return "/admincamps";
  }
  return "/admincamps";
}

export const router = createBrowserRouter(
  [
    {
      path: "/login",
      Component: LoginPage,
    },
    {
      path: "/map",
      Component: LegacyMapPage,
    },
    {
      path: "/",
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
  ],
  {
    basename: detectBasename(),
  },
);
