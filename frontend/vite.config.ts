import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  base: "/static/react-map/",
  plugins: [react()],
  resolve: {
    alias: {
      "motion/react": fileURLToPath(new URL("./src/shims/motion-react.ts", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 4173,
  },
  preview: {
    host: "127.0.0.1",
    port: 4174,
  },
  build: {
    outDir: "../static/react-map",
    emptyOutDir: true,
  },
});
