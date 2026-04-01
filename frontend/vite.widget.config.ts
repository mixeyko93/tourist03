import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    outDir: "../static/map-popup-widget",
    emptyOutDir: true,
    lib: {
      entry: fileURLToPath(new URL("./src/widget/mapPopupWidget.tsx", import.meta.url)),
      name: "TouristMapPopupWidget",
      formats: ["iife"],
      fileName: () => "map-popup-widget.js",
      cssFileName: "map-popup-widget",
    },
  },
});
