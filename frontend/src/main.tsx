import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router";
import { installCsrfFetch } from "./crm/csrf";
import { router } from "./crm/router";

async function bootstrap() {
  if (!window.location.pathname.startsWith("/owner")) {
    await Promise.all([
      import("leaflet/dist/leaflet.css"),
      import("./styles.css"),
      import("./crm.css"),
    ]);
  }
  installCsrfFetch();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <RouterProvider router={router} />
    </React.StrictMode>,
  );
}

void bootstrap();
