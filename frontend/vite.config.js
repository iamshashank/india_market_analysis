import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build into ../static/spa so Flask can serve the bundle in production.
// In dev, `npm run dev` runs Vite on :5173 and proxies /api to Flask on :8000.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "../backend/static/spa",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
      "/static": "http://localhost:8000",
    },
  },
});
