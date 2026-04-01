import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router";
import { ThemeProvider } from "next-themes";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import "./crm.css";
import { router } from "./crm/router";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider attribute="class" defaultTheme="dark" disableTransitionOnChange>
      <RouterProvider router={router} />
    </ThemeProvider>
  </React.StrictMode>,
);
