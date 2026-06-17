import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import "./crm.css";
import { router } from "./crm/router";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
